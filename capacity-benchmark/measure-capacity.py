#!/usr/bin/env python3
"""
KubeVirt VM Capacity Benchmark

This script tests the capacity of Virtual Machines and Volumes supported by the cluster
and a specific storage class. It runs a workload in a loop without deleting previously
created resources until a failure occurs.

Each loop iteration performs:
1. Create VMs with multiple data volumes
2. Resize root and data volumes
3. Restart VMs
4. Snapshot VMs
5. Migrate VMs

Usage:
    python3 measure-capacity.py --storage-class portworx-fada-sc --vms 5 --data-volume-count 3
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.common import (
    setup_logging, run_kubectl_command, create_namespace, namespace_exists,
    get_vm_status, restart_vm, resize_pvc, wait_for_pvc_resize,
    create_vm_snapshot, wait_for_snapshot_ready, delete_vm_snapshot,
    get_pvc_size, get_vm_volume_names, migrate_vm, wait_for_migration_complete,
    Colors
)

# Default configuration
DEFAULT_NAMESPACE = 'virt-capacity-benchmark'
DEFAULT_VM_YAML = '../examples/vm-templates/rhel9-vm-datasource.yaml'
DEFAULT_VM_NAME = 'capacity-vm'
DEFAULT_VMS_PER_ITERATION = 5
DEFAULT_DATA_VOLUME_COUNT = 9
DEFAULT_MIN_VOL_SIZE = '30Gi'
DEFAULT_MIN_VOL_INC_SIZE = '10Gi'
DEFAULT_POLL_INTERVAL = 5
DEFAULT_CONCURRENCY = 10


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='KubeVirt VM Capacity Benchmark',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run capacity test with default settings
  python3 measure-capacity.py --storage-class portworx-fada-sc

  # Run with custom VM count and data volumes
  python3 measure-capacity.py --storage-class portworx-fada-sc --vms 10 --data-volume-count 5

  # Run with maximum iterations limit
  python3 measure-capacity.py --storage-class portworx-fada-sc --max-iterations 10

  # Skip specific jobs
  python3 measure-capacity.py --storage-class portworx-fada-sc --skip-resize-job --skip-migration-job

  # Cleanup only mode
  python3 measure-capacity.py --cleanup-only
        """
    )

    # Required arguments
    parser.add_argument('--storage-class', type=str,
                        help='Storage class name (comma-separated for multiple)')

    # Test configuration
    parser.add_argument('--namespace', '-n', type=str, default=DEFAULT_NAMESPACE,
                        help=f'Namespace for test resources (default: {DEFAULT_NAMESPACE})')
    parser.add_argument('--max-iterations', type=int, default=0,
                        help='Maximum number of iterations (0 for infinite, default: 0)')
    parser.add_argument('--vms', type=int, default=DEFAULT_VMS_PER_ITERATION,
                        help=f'Number of VMs per iteration (default: {DEFAULT_VMS_PER_ITERATION})')
    parser.add_argument('--data-volume-count', type=int, default=DEFAULT_DATA_VOLUME_COUNT,
                        help=f'Number of data volumes per VM (default: {DEFAULT_DATA_VOLUME_COUNT})')
    parser.add_argument('--min-vol-size', type=str, default=DEFAULT_MIN_VOL_SIZE,
                        help=f'Minimum volume size (default: {DEFAULT_MIN_VOL_SIZE})')
    parser.add_argument('--min-vol-inc-size', type=str, default=DEFAULT_MIN_VOL_INC_SIZE,
                        help=f'Minimum volume size increment (default: {DEFAULT_MIN_VOL_INC_SIZE})')

    # VM template configuration
    parser.add_argument('--vm-yaml', type=str, default=DEFAULT_VM_YAML,
                        help=f'Path to VM YAML template (default: {DEFAULT_VM_YAML})')
    parser.add_argument('--vm-name', type=str, default=DEFAULT_VM_NAME,
                        help=f'Base VM name (default: {DEFAULT_VM_NAME})')
    parser.add_argument('--datasource-name', type=str, default='rhel9',
                        help='DataSource name (default: rhel9)')
    parser.add_argument('--datasource-namespace', type=str, default='openshift-virtualization-os-images',
                        help='DataSource namespace (default: openshift-virtualization-os-images)')
    parser.add_argument('--vm-memory', type=str, default='2048M',
                        help='VM memory (default: 2048M)')
    parser.add_argument('--vm-cpu-cores', type=int, default=1,
                        help='VM CPU cores (default: 1)')

    # Skip options
    parser.add_argument('--skip-resize-job', action='store_true',
                        help='Skip volume resize job')
    parser.add_argument('--skip-migration-job', action='store_true',
                        help='Skip migration job')
    parser.add_argument('--skip-snapshot-job', action='store_true',
                        help='Skip snapshot job')
    parser.add_argument('--skip-restart-job', action='store_true',
                        help='Skip restart job')

    # Execution options
    parser.add_argument('--concurrency', type=int, default=DEFAULT_CONCURRENCY,
                        help=f'Number of concurrent operations (default: {DEFAULT_CONCURRENCY})')
    parser.add_argument('--poll-interval', type=int, default=DEFAULT_POLL_INTERVAL,
                        help=f'Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL})')

    # Cleanup options
    parser.add_argument('--cleanup', action='store_true',
                        help='Cleanup resources after test completion')
    parser.add_argument('--cleanup-only', action='store_true',
                        help='Only cleanup resources from previous runs')

    # Logging
    parser.add_argument('--log-file', type=str,
                        help='Log file path (default: auto-generated)')
    parser.add_argument('--log-level', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')

    args = parser.parse_args()

    # Validate arguments
    if not args.cleanup_only and not args.storage_class:
        parser.error('--storage-class is required (unless using --cleanup-only)')

    return args


def parse_size_to_gi(size_str: str) -> int:
    """
    Parse size string to GiB integer.

    Args:
        size_str: Size string (e.g., "30Gi", "40Gi")

    Returns:
        Size in GiB
    """
    size_str = size_str.strip().upper()
    if size_str.endswith('GI'):
        return int(size_str[:-2])
    elif size_str.endswith('G'):
        return int(size_str[:-1])
    else:
        raise ValueError(f"Unsupported size format: {size_str}")


def increment_size(current_size: str, increment: str) -> str:
    """
    Increment size by specified amount.

    Args:
        current_size: Current size (e.g., "30Gi")
        increment: Increment amount (e.g., "10Gi")

    Returns:
        New size string (e.g., "40Gi")
    """
    current_gi = parse_size_to_gi(current_size)
    increment_gi = parse_size_to_gi(increment)
    new_size_gi = current_gi + increment_gi
    return f"{new_size_gi}Gi"


def get_storage_classes(storage_class_arg: str) -> List[str]:
    """
    Parse storage class argument into list.

    Args:
        storage_class_arg: Comma-separated storage class names

    Returns:
        List of storage class names
    """
    return [sc.strip() for sc in storage_class_arg.split(',')]


def create_vm_with_data_volumes(vm_name: str, namespace: str, vm_yaml: str, storage_class: str,
                                 data_volume_count: int, vol_size: str, args, logger) -> bool:
    """
    Create a VM with multiple data volumes.

    Args:
        vm_name: VM name
        namespace: Namespace
        vm_yaml: Path to VM YAML template
        storage_class: Storage class name
        data_volume_count: Number of data volumes
        vol_size: Volume size
        args: Command line arguments
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Creating VM {vm_name} with {data_volume_count} data volumes")

        # Read and customize VM template
        with open(vm_yaml, 'r') as f:
            vm_content = f.read()

        # Replace template variables
        vm_content = vm_content.replace('{{VM_NAME}}', vm_name)
        vm_content = vm_content.replace('{{STORAGE_CLASS_NAME}}', storage_class)
        vm_content = vm_content.replace('{{DATASOURCE_NAME}}', args.datasource_name)
        vm_content = vm_content.replace('{{DATASOURCE_NAMESPACE}}', args.datasource_namespace)
        vm_content = vm_content.replace('{{STORAGE_SIZE}}', vol_size)
        vm_content = vm_content.replace('{{VM_MEMORY}}', args.vm_memory)
        vm_content = vm_content.replace('{{VM_CPU_CORES}}', str(args.vm_cpu_cores))

        # TODO: Add data volumes to the template
        # For now, create VM with root volume only

        # Apply VM
        import subprocess
        process = subprocess.Popen(
            ['kubectl', 'create', '-f', '-', '-n', namespace],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=vm_content)

        if process.returncode != 0:
            logger.error(f"Failed to create VM {vm_name}: {stderr}")
            return False

        logger.info(f"VM {vm_name} created successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to create VM {vm_name}: {e}")
        return False


def wait_for_vm_running(vm_name: str, namespace: str, logger, timeout: int = 1800) -> bool:
    """
    Wait for a VM to reach Running state.

    Args:
        vm_name: VM name
        namespace: Namespace
        logger: Logger instance
        timeout: Timeout in seconds

    Returns:
        True if VM reached Running state, False otherwise
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        status = get_vm_status(vm_name, namespace, logger)

        if status == 'Running':
            elapsed = time.time() - start_time
            logger.info(f"VM {vm_name} reached Running state after {elapsed:.2f}s")
            return True

        time.sleep(5)

    logger.error(f"Timeout waiting for VM {vm_name} to reach Running state")
    return False


def wait_for_vms_running(vm_names: List[str], namespace: str, logger, timeout: int = 1800) -> Tuple[List[str], List[str]]:
    """
    Wait for multiple VMs to reach Running state.

    Args:
        vm_names: List of VM names
        namespace: Namespace
        logger: Logger instance
        timeout: Timeout in seconds

    Returns:
        Tuple of (successful_vms, failed_vms)
    """
    successful = []
    failed = []

    for vm_name in vm_names:
        try:
            if wait_for_vm_running(vm_name, namespace, logger, timeout):
                successful.append(vm_name)
            else:
                failed.append(vm_name)
        except Exception as e:
            logger.error(f"Error waiting for VM {vm_name}: {e}")
            failed.append(vm_name)

    return successful, failed


def run_iteration(iteration: int, namespace: str, storage_class: str, args, logger) -> bool:
    """
    Run a single capacity test iteration.

    Args:
        iteration: Iteration number
        namespace: Namespace
        storage_class: Storage class name
        args: Command line arguments
        logger: Logger instance

    Returns:
        True if iteration successful, False on failure
    """
    logger.info("=" * 100)
    logger.info(f"{Colors.BOLD}ITERATION {iteration}{Colors.ENDC}")
    logger.info(f"Storage Class: {storage_class}")
    logger.info(f"VMs to create: {args.vms}")
    logger.info(f"Data volumes per VM: {args.data_volume_count}")
    logger.info("=" * 100)

    # Generate VM names for this iteration
    vm_names = [f"{args.vm_name}-{iteration}-{i}" for i in range(1, args.vms + 1)]

    # Phase 1: Create VMs
    logger.info(f"\n{Colors.HEADER}Phase 1: Creating {args.vms} VMs{Colors.ENDC}")
    phase_start = time.time()

    created_vms = []
    for vm_name in vm_names:
        if create_vm_with_data_volumes(vm_name, namespace, args.vm_yaml, storage_class,
                                       args.data_volume_count, args.min_vol_size, args, logger):
            created_vms.append(vm_name)
        else:
            logger.error(f"Failed to create VM {vm_name}")
            return False

    # Wait for VMs to be running
    logger.info(f"Waiting for {len(created_vms)} VMs to reach Running state...")
    successful_vms, failed_vms = wait_for_vms_running(created_vms, namespace, logger)

    if failed_vms:
        logger.error(f"Phase 1 FAILED: {len(failed_vms)} VMs failed to start")
        return False

    phase_duration = time.time() - phase_start
    logger.info(f"{Colors.OKGREEN}Phase 1 COMPLETE: {len(successful_vms)} VMs running (took {phase_duration:.2f}s){Colors.ENDC}")

    # Phase 2: Resize Volumes
    if not args.skip_resize_job:
        logger.info(f"\n{Colors.HEADER}Phase 2: Resizing Volumes{Colors.ENDC}")
        phase_start = time.time()

        resize_failed = False
        for vm_name in successful_vms:
            # Get VM volumes
            pvc_names = get_vm_volume_names(vm_name, namespace, logger)

            for pvc_name in pvc_names:
                current_size = get_pvc_size(pvc_name, namespace, logger)
                if not current_size:
                    logger.error(f"Failed to get size for PVC {pvc_name}")
                    resize_failed = True
                    break

                new_size = increment_size(current_size, args.min_vol_inc_size)
                logger.info(f"Resizing {pvc_name}: {current_size} -> {new_size}")

                if not resize_pvc(pvc_name, namespace, new_size, logger):
                    logger.error(f"Failed to resize PVC {pvc_name}")
                    resize_failed = True
                    break

                if not wait_for_pvc_resize(pvc_name, namespace, new_size, logger=logger):
                    logger.error(f"PVC {pvc_name} resize did not complete")
                    resize_failed = True
                    break

            if resize_failed:
                break

        if resize_failed:
            logger.error("Phase 2 FAILED: Volume resize failed")
            return False

        phase_duration = time.time() - phase_start
        logger.info(f"{Colors.OKGREEN}Phase 2 COMPLETE: All volumes resized (took {phase_duration:.2f}s){Colors.ENDC}")
    else:
        logger.info(f"\n{Colors.WARNING}Phase 2: SKIPPED (--skip-resize-job){Colors.ENDC}")

    # Phase 3: Restart VMs
    if not args.skip_restart_job:
        logger.info(f"\n{Colors.HEADER}Phase 3: Restarting VMs{Colors.ENDC}")
        phase_start = time.time()

        restart_failed = False
        for vm_name in successful_vms:
            if not restart_vm(vm_name, namespace, logger):
                logger.error(f"Failed to restart VM {vm_name}")
                restart_failed = True
                break

        if restart_failed:
            logger.error("Phase 3 FAILED: VM restart failed")
            return False

        # Wait for VMs to be running again
        logger.info("Waiting for VMs to be running after restart...")
        successful_vms, failed_vms = wait_for_vms_running(successful_vms, namespace, logger)

        if failed_vms:
            logger.error(f"Phase 3 FAILED: {len(failed_vms)} VMs failed to restart")
            return False

        phase_duration = time.time() - phase_start
        logger.info(f"{Colors.OKGREEN}Phase 3 COMPLETE: All VMs restarted (took {phase_duration:.2f}s){Colors.ENDC}")
    else:
        logger.info(f"\n{Colors.WARNING}Phase 3: SKIPPED (--skip-restart-job){Colors.ENDC}")

    # Phase 4: Snapshot VMs
    if not args.skip_snapshot_job:
        logger.info(f"\n{Colors.HEADER}Phase 4: Creating VM Snapshots{Colors.ENDC}")
        phase_start = time.time()

        snapshot_failed = False
        snapshots_created = []

        for vm_name in successful_vms:
            snapshot_name = f"{vm_name}-snapshot"

            if not create_vm_snapshot(vm_name, snapshot_name, namespace, logger):
                logger.error(f"Failed to create snapshot for VM {vm_name}")
                snapshot_failed = True
                break

            snapshots_created.append(snapshot_name)

            if not wait_for_snapshot_ready(snapshot_name, namespace, logger=logger):
                logger.error(f"Snapshot {snapshot_name} did not become ready")
                snapshot_failed = True
                break

        if snapshot_failed:
            logger.error("Phase 4 FAILED: Snapshot creation failed")
            return False

        phase_duration = time.time() - phase_start
        logger.info(f"{Colors.OKGREEN}Phase 4 COMPLETE: {len(snapshots_created)} snapshots created (took {phase_duration:.2f}s){Colors.ENDC}")
    else:
        logger.info(f"\n{Colors.WARNING}Phase 4: SKIPPED (--skip-snapshot-job){Colors.ENDC}")

    # Phase 5: Migrate VMs
    if not args.skip_migration_job:
        logger.info(f"\n{Colors.HEADER}Phase 5: Migrating VMs{Colors.ENDC}")
        phase_start = time.time()

        migration_failed = False
        for vm_name in successful_vms:
            logger.info(f"Migrating VM {vm_name}...")

            if not migrate_vm(vm_name, namespace, logger):
                logger.error(f"Failed to initiate migration for VM {vm_name}")
                migration_failed = True
                break

            if not wait_for_migration_complete(vm_name, namespace, logger=logger):
                logger.error(f"Migration failed for VM {vm_name}")
                migration_failed = True
                break

        if migration_failed:
            logger.error("Phase 5 FAILED: Migration failed")
            return False

        phase_duration = time.time() - phase_start
        logger.info(f"{Colors.OKGREEN}Phase 5 COMPLETE: All VMs migrated (took {phase_duration:.2f}s){Colors.ENDC}")
    else:
        logger.info(f"\n{Colors.WARNING}Phase 5: SKIPPED (--skip-migration-job){Colors.ENDC}")

    logger.info(f"\n{Colors.OKGREEN}{Colors.BOLD}ITERATION {iteration} COMPLETE{Colors.ENDC}")
    return True



def cleanup_namespace(namespace: str, logger) -> bool:
    """
    Cleanup test namespace and all resources.

    Args:
        namespace: Namespace to cleanup
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Cleaning up namespace {namespace}...")

        if not namespace_exists(namespace, logger):
            logger.info(f"Namespace {namespace} does not exist, nothing to cleanup")
            return True

        # Delete namespace (this will delete all resources in it)
        returncode, stdout, stderr = run_kubectl_command(
            ['delete', 'namespace', namespace, '--wait=false'],
            check=False,
            logger=logger
        )

        if returncode != 0:
            logger.error(f"Failed to delete namespace {namespace}: {stderr}")
            return False

        logger.info(f"Namespace {namespace} deletion initiated")
        logger.info("Note: Namespace deletion may take several minutes to complete")
        return True

    except Exception as e:
        logger.error(f"Failed to cleanup namespace {namespace}: {e}")
        return False


def print_test_summary(iteration: int, total_vms: int, logger):
    """
    Print test summary.

    Args:
        iteration: Number of iterations completed
        total_vms: Total VMs created
        logger: Logger instance
    """
    logger.info("\n" + "=" * 100)
    logger.info(f"{Colors.BOLD}CAPACITY TEST SUMMARY{Colors.ENDC}")
    logger.info("=" * 100)
    logger.info(f"Iterations completed:  {iteration}")
    logger.info(f"Total VMs created:     {total_vms}")
    logger.info("=" * 100)


def main():
    """Main function."""
    args = parse_args()

    # Setup logging
    logger = setup_logging(args.log_file, args.log_level)

    logger.info("=" * 100)
    logger.info(f"{Colors.BOLD}KubeVirt VM Capacity Benchmark{Colors.ENDC}")
    logger.info("=" * 100)

    # Cleanup only mode
    if args.cleanup_only:
        logger.info("Running in cleanup-only mode")
        success = cleanup_namespace(args.namespace, logger)
        if success:
            logger.info(f"{Colors.OKGREEN}Cleanup completed successfully{Colors.ENDC}")
            return 0
        else:
            logger.error(f"{Colors.FAIL}Cleanup failed{Colors.ENDC}")
            return 1

    # Parse storage classes
    storage_classes = get_storage_classes(args.storage_class)
    logger.info(f"Storage classes: {', '.join(storage_classes)}")
    logger.info(f"VMs per iteration: {args.vms}")
    logger.info(f"Data volumes per VM: {args.data_volume_count}")
    logger.info(f"Max iterations: {args.max_iterations if args.max_iterations > 0 else 'Unlimited'}")
    logger.info(f"Namespace: {args.namespace}")

    # Create namespace
    logger.info(f"\nCreating namespace {args.namespace}...")
    if not create_namespace(args.namespace, logger):
        logger.error(f"Failed to create namespace {args.namespace}")
        return 1

    # Run iterations
    iteration = 1
    total_vms = 0
    test_start_time = time.time()

    try:
        while True:
            # Check if we've reached max iterations
            if args.max_iterations > 0 and iteration > args.max_iterations:
                logger.info(f"\n{Colors.OKGREEN}Reached maximum iterations ({args.max_iterations}){Colors.ENDC}")
                break

            # Select storage class (round-robin)
            storage_class = storage_classes[(iteration - 1) % len(storage_classes)]

            # Run iteration
            iteration_start = time.time()
            success = run_iteration(iteration, args.namespace, storage_class, args, logger)
            iteration_duration = time.time() - iteration_start

            if not success:
                logger.error(f"\n{Colors.FAIL}ITERATION {iteration} FAILED after {iteration_duration:.2f}s{Colors.ENDC}")
                logger.error("Capacity limit reached or error occurred")
                break

            total_vms += args.vms
            logger.info(f"Iteration {iteration} took {iteration_duration:.2f}s")
            logger.info(f"Total VMs created so far: {total_vms}")

            iteration += 1

            # Small delay between iterations
            time.sleep(5)

    except KeyboardInterrupt:
        logger.warning(f"\n{Colors.WARNING}Test interrupted by user{Colors.ENDC}")
    except Exception as e:
        logger.error(f"\n{Colors.FAIL}Unexpected error: {e}{Colors.ENDC}")
        import traceback
        logger.error(traceback.format_exc())

    # Print summary
    test_duration = time.time() - test_start_time
    logger.info(f"\nTotal test duration: {test_duration:.2f}s ({test_duration/60:.2f} minutes)")
    print_test_summary(iteration - 1, total_vms, logger)

    # Cleanup if requested
    if args.cleanup:
        logger.info(f"\n{Colors.WARNING}Cleanup requested, deleting namespace {args.namespace}...{Colors.ENDC}")
        cleanup_namespace(args.namespace, logger)
    else:
        logger.info(f"\n{Colors.WARNING}Resources left in namespace {args.namespace}{Colors.ENDC}")
        logger.info(f"To cleanup, run: kubectl delete namespace {args.namespace}")
        logger.info(f"Or run: python3 {sys.argv[0]} --cleanup-only")

    logger.info(f"\n{Colors.OKGREEN}Test completed{Colors.ENDC}")
    return 0


if __name__ == '__main__':
    sys.exit(main())


