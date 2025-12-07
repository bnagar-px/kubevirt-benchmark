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

Usage:
    python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS --vms 5 --data-volume-count 3
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
    get_pvc_size, get_vm_volume_names, Colors, save_capacity_results
)

# Default configuration
DEFAULT_NAMESPACE = 'virt-capacity-benchmark'
DEFAULT_VM_YAML = '../examples/vm-templates/vm-template.yaml'
DEFAULT_VM_NAME = 'rhel-9-vm'
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
  python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS

  # Run with custom VM count and data volumes
  python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS --vms 10 --data-volume-count 5

  # Run with maximum iterations limit
  python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS --max-iterations 10

  # Skip specific jobs
  python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS --skip-resize-job --skip-snapshot-job

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
    parser.add_argument('--skip-snapshot-job', action='store_true',
                        help='Skip snapshot job')
    parser.add_argument('--skip-restart-job', action='store_true',
                        help='Skip restart job')

    # Execution options
    parser.add_argument('--concurrency', type=int, default=DEFAULT_CONCURRENCY,
                        help=f'Number of concurrent operations (default: {DEFAULT_CONCURRENCY})')
    parser.add_argument('--poll-interval', type=int, default=DEFAULT_POLL_INTERVAL,
                        help=f'Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL})')
    parser.add_argument('--scheduling-timeout', type=int, default=120,
                        help='Seconds to wait in Scheduling state before declaring capacity reached (default: 120)')
    parser.add_argument('--max-create-retries', type=int, default=5,
                        help='Maximum retries for VM creation on transient errors (default: 5)')

    # Cleanup options
    parser.add_argument('--cleanup', action='store_true',
                        help='Cleanup resources after test completion')
    parser.add_argument('--cleanup-only', action='store_true',
                        help='Only cleanup resources from previous runs')

    # Results options
    parser.add_argument('--save-results', action='store_true',
                        help='Save results to JSON/CSV files in results directory')
    parser.add_argument('--results-dir', type=str, default='results',
                        help='Directory to save results (default: results)')
    parser.add_argument('--storage-version', type=str, default=None,
                        help='Storage version for results folder hierarchy (e.g., 3.2.0)')

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
                                 data_volume_count: int, vol_size: str, args, logger,
                                 max_retries: int = 5, initial_delay: float = 2.0) -> bool:
    """
    Create a VM with multiple data volumes, with retry logic for transient errors.

    Args:
        vm_name: VM name
        namespace: Namespace
        vm_yaml: Path to VM YAML template
        storage_class: Storage class name
        data_volume_count: Number of data volumes
        vol_size: Volume size
        args: Command line arguments
        logger: Logger instance
        max_retries: Maximum number of retry attempts (default: 5)
        initial_delay: Initial delay between retries in seconds (default: 2.0)
                      Uses exponential backoff: delay * 2^attempt

    Returns:
        True if successful, False otherwise
    """
    # Retryable errors - transient webhook/API server issues
    retryable_errors = [
        'context deadline exceeded',
        'connection refused',
        'connection reset',
        'timeout',
        'Internal error occurred',
        'webhook',
        'etcdserver: request timed out',
        'the object has been modified',
        'Operation cannot be fulfilled',
        'TLS handshake timeout',
        'i/o timeout',
    ]

    logger.info(f"Creating VM {vm_name} with {data_volume_count} data volumes")

    # Read and customize VM template (do this once, outside retry loop)
    try:
        with open(vm_yaml, 'r') as f:
            vm_content = f.read()

        # Check if template uses placeholders or hardcoded names
        has_placeholders = '{{VM_NAME}}' in vm_content

        if has_placeholders:
            # Replace template variables (for templates with placeholders like vm-template.yaml)
            vm_content = vm_content.replace('{{VM_NAME}}', vm_name)
            vm_content = vm_content.replace('{{STORAGE_CLASS_NAME}}', storage_class)
            vm_content = vm_content.replace('{{DATASOURCE_NAME}}', args.datasource_name)
            vm_content = vm_content.replace('{{DATASOURCE_NAMESPACE}}', args.datasource_namespace)
            vm_content = vm_content.replace('{{STORAGE_SIZE}}', vol_size)
            vm_content = vm_content.replace('{{VM_MEMORY}}', args.vm_memory)
            vm_content = vm_content.replace('{{VM_CPU_CORES}}', str(args.vm_cpu_cores))
        else:
            # Handle templates with hardcoded names (like rhel9-vm-datasource.yaml)
            # Replace the base VM name from args with the unique vm_name
            base_vm_name = args.vm_name  # e.g., 'rhel-9-vm'
            if base_vm_name and base_vm_name != vm_name:
                # Replace hardcoded VM name references with the unique name
                # Order matters: replace longer patterns first to avoid partial matches
                # This handles: name: rhel-9-vm-volume -> name: rhel-9-vm-1-1-volume
                # And: name: rhel-9-vm -> name: rhel-9-vm-1-1
                vm_content = vm_content.replace(f'{base_vm_name}-volume', f'{vm_name}-volume')
                # Use regex to replace exact VM name (with word boundary via newline/space)
                import re
                # Replace "name: rhel-9-vm" but not "name: rhel-9-vm-volume" (already handled above)
                vm_content = re.sub(
                    rf'(name:\s*){re.escape(base_vm_name)}(\s*$|\s*\n)',
                    rf'\g<1>{vm_name}\2',
                    vm_content,
                    flags=re.MULTILINE
                )
            # Also replace storage class placeholder if present
            vm_content = vm_content.replace('{{STORAGE_CLASS_NAME}}', storage_class)
    except Exception as e:
        logger.error(f"Failed to prepare VM template for {vm_name}: {e}")
        return False

    # TODO: Add data volumes to the template
    # For now, create VM with root volume only

    # Retry loop for VM creation
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            import subprocess
            process = subprocess.Popen(
                ['kubectl', 'create', '-f', '-', '-n', namespace],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=vm_content)

            if process.returncode == 0:
                logger.info(f"VM {vm_name} created successfully")
                return True

            # Check if error is retryable
            error_msg = stderr.strip()
            last_error = error_msg
            is_retryable = any(err.lower() in error_msg.lower() for err in retryable_errors)

            if is_retryable and attempt < max_retries:
                delay = initial_delay * (2 ** (attempt - 1))  # Exponential backoff
                logger.warning(f"Retryable error creating VM {vm_name} (attempt {attempt}/{max_retries}): {error_msg}")
                logger.info(f"Retrying in {delay:.1f}s...")
                time.sleep(delay)
            elif is_retryable:
                logger.error(f"Failed to create VM {vm_name} after {max_retries} attempts: {error_msg}")
                return False
            else:
                # Non-retryable error, fail immediately
                logger.error(f"Failed to create VM {vm_name}: {error_msg}")
                return False

        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                delay = initial_delay * (2 ** (attempt - 1))
                logger.warning(f"Exception creating VM {vm_name} (attempt {attempt}/{max_retries}): {e}")
                logger.info(f"Retrying in {delay:.1f}s...")
                time.sleep(delay)
            else:
                logger.error(f"Failed to create VM {vm_name} after {max_retries} attempts: {e}")
                return False

    logger.error(f"Failed to create VM {vm_name}: {last_error}")
    return False


def wait_for_vm_running(vm_name: str, namespace: str, logger, timeout: int = 1800,
                        scheduling_timeout: int = 120) -> Tuple[bool, str]:
    """
    Wait for a VM to reach Running state.

    Args:
        vm_name: VM name
        namespace: Namespace
        logger: Logger instance
        timeout: Total timeout in seconds
        scheduling_timeout: Max time to wait in Scheduling state before failing (capacity reached)

    Returns:
        Tuple of (success, failure_reason)
        - (True, '') if VM reached Running state
        - (False, 'scheduling') if VM stuck in Scheduling (capacity reached)
        - (False, 'timeout') if general timeout
        - (False, 'error') if VM in error state
    """
    start_time = time.time()
    scheduling_start = None

    while time.time() - start_time < timeout:
        status = get_vm_status(vm_name, namespace, logger)

        if status == 'Running':
            elapsed = time.time() - start_time
            logger.info(f"VM {vm_name} reached Running state after {elapsed:.2f}s")
            return True, ''

        # Track time spent in Scheduling state
        if status == 'Scheduling':
            if scheduling_start is None:
                scheduling_start = time.time()
            elif time.time() - scheduling_start > scheduling_timeout:
                logger.warning(f"VM {vm_name} stuck in Scheduling state for {scheduling_timeout}s - cluster capacity likely reached")
                return False, 'scheduling'
        else:
            # Reset scheduling timer if status changes
            scheduling_start = None

        # Check for error states
        if status == 'ErrorUnschedulable':
            # ErrorUnschedulable means cluster capacity reached - this is expected in capacity testing
            logger.warning(f"VM {vm_name} in ErrorUnschedulable state - cluster capacity reached")
            return False, 'capacity'
        elif status in ('CrashLoopBackOff', 'ErrImagePull', 'Error'):
            logger.error(f"VM {vm_name} in error state: {status}")
            return False, 'error'

        time.sleep(5)

    logger.error(f"Timeout waiting for VM {vm_name} to reach Running state (last status: {status})")
    return False, 'timeout'


def wait_for_vms_running(vm_names: List[str], namespace: str, logger, timeout: int = 1800,
                         scheduling_timeout: int = 120) -> Tuple[List[str], List[str], str]:
    """
    Wait for multiple VMs to reach Running state.

    Args:
        vm_names: List of VM names
        namespace: Namespace
        logger: Logger instance
        timeout: Total timeout in seconds
        scheduling_timeout: Max time to wait in Scheduling state

    Returns:
        Tuple of (successful_vms, failed_vms, failure_reason)
        failure_reason is 'scheduling' if capacity reached, 'timeout' or 'error' otherwise
    """
    successful = []
    failed = []
    failure_reason = ''

    for vm_name in vm_names:
        try:
            success, reason = wait_for_vm_running(vm_name, namespace, logger, timeout, scheduling_timeout)
            if success:
                successful.append(vm_name)
            else:
                failed.append(vm_name)
                failure_reason = reason
                # If capacity reached (scheduling or ErrorUnschedulable), don't wait for remaining VMs
                if reason in ('scheduling', 'capacity'):
                    remaining_count = len(vm_names) - len(successful) - len(failed)
                    if remaining_count > 0:
                        logger.warning(f"Capacity reached - skipping wait for remaining {remaining_count} VMs")
                        # Add remaining VMs to failed list
                        remaining_idx = vm_names.index(vm_name) + 1
                        failed.extend(vm_names[remaining_idx:])
                    break
        except Exception as e:
            logger.error(f"Error waiting for VM {vm_name}: {e}")
            failed.append(vm_name)
            failure_reason = 'error'

    return successful, failed, failure_reason


def run_iteration(iteration: int, namespace: str, storage_class: str, args, logger) -> Tuple[bool, bool, int]:
    """
    Run a single capacity test iteration.

    Args:
        iteration: Iteration number
        namespace: Namespace
        storage_class: Storage class name
        args: Command line arguments
        logger: Logger instance

    Returns:
        Tuple of (success, capacity_reached, vms_created)
        - success: True if iteration completed successfully
        - capacity_reached: True if cluster capacity was reached (VMs stuck in Scheduling)
        - vms_created: Number of VMs that reached Running state
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
    max_create_retries = getattr(args, 'max_create_retries', 5)
    for vm_name in vm_names:
        if create_vm_with_data_volumes(vm_name, namespace, args.vm_yaml, storage_class,
                                       args.data_volume_count, args.min_vol_size, args, logger,
                                       max_retries=max_create_retries):
            created_vms.append(vm_name)
        else:
            logger.error(f"Failed to create VM {vm_name}")
            return False, False, 0

    # Wait for VMs to be running
    scheduling_timeout = getattr(args, 'scheduling_timeout', 120)
    logger.info(f"Waiting for {len(created_vms)} VMs to reach Running state (scheduling timeout: {scheduling_timeout}s)...")
    successful_vms, failed_vms, failure_reason = wait_for_vms_running(
        created_vms, namespace, logger, scheduling_timeout=scheduling_timeout
    )

    if failed_vms:
        if failure_reason in ('scheduling', 'capacity'):
            logger.warning(f"{Colors.WARNING}CAPACITY REACHED: {len(failed_vms)} VMs could not be scheduled{Colors.ENDC}")
            logger.info(f"Successfully started {len(successful_vms)} VMs before capacity was reached")
            return False, True, len(successful_vms)
        else:
            logger.error(f"Phase 1 FAILED: {len(failed_vms)} VMs failed to start (reason: {failure_reason})")
            return False, False, len(successful_vms)

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
            return False, False, len(successful_vms)

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
            return False, False, len(successful_vms)

        # Wait for VMs to be running again
        logger.info("Waiting for VMs to be running after restart...")
        successful_vms, failed_vms, failure_reason = wait_for_vms_running(successful_vms, namespace, logger)

        if failed_vms:
            logger.error(f"Phase 3 FAILED: {len(failed_vms)} VMs failed to restart")
            return False, False, len(successful_vms)

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
            return False, False, len(successful_vms)

        phase_duration = time.time() - phase_start
        logger.info(f"{Colors.OKGREEN}Phase 4 COMPLETE: {len(snapshots_created)} snapshots created (took {phase_duration:.2f}s){Colors.ENDC}")
    else:
        logger.info(f"\n{Colors.WARNING}Phase 4: SKIPPED (--skip-snapshot-job){Colors.ENDC}")

    logger.info(f"\n{Colors.OKGREEN}{Colors.BOLD}ITERATION {iteration} COMPLETE{Colors.ENDC}")
    return True, False, len(successful_vms)



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


def print_test_summary(results: dict, logger):
    """
    Print comprehensive test summary report.

    Args:
        results: Dictionary containing test results
        logger: Logger instance
    """
    logger.info("\n" + "=" * 100)
    logger.info(f"{Colors.BOLD}CAPACITY BENCHMARK REPORT{Colors.ENDC}")
    logger.info("=" * 100)

    # Test Configuration
    logger.info(f"\n{Colors.HEADER}Test Configuration:{Colors.ENDC}")
    logger.info(f"  Storage Class(es):     {results.get('storage_classes', 'N/A')}")
    logger.info(f"  VMs per iteration:     {results.get('vms_per_iteration', 'N/A')}")
    logger.info(f"  Data volumes per VM:   {results.get('data_volumes_per_vm', 'N/A')}")
    logger.info(f"  Volume size:           {results.get('volume_size', 'N/A')}")
    logger.info(f"  VM Memory:             {results.get('vm_memory', 'N/A')}")
    logger.info(f"  VM CPU Cores:          {results.get('vm_cpu_cores', 'N/A')}")

    # Test Results
    logger.info(f"\n{Colors.HEADER}Test Results:{Colors.ENDC}")
    logger.info(f"  Iterations completed:  {results.get('iterations_completed', 0)}")
    logger.info(f"  Total VMs created:     {results.get('total_vms', 0)}")
    logger.info(f"  Total PVCs created:    {results.get('total_pvcs', 0)}")
    logger.info(f"  Test duration:         {results.get('duration_str', 'N/A')}")

    # Capacity Status
    capacity_reached = results.get('capacity_reached', False)
    if capacity_reached:
        logger.info(f"\n{Colors.OKGREEN}✓ CAPACITY LIMIT REACHED{Colors.ENDC}")
        logger.info(f"  The cluster reached its capacity limit.")
        logger.info(f"  Maximum VMs that could be scheduled: {results.get('total_vms', 0)}")
    else:
        end_reason = results.get('end_reason', 'unknown')
        if end_reason == 'max_iterations':
            logger.info(f"\n{Colors.WARNING}⚠ MAX ITERATIONS REACHED{Colors.ENDC}")
            logger.info(f"  Test stopped after reaching max iterations limit.")
            logger.info(f"  Cluster may have more capacity available.")
        elif end_reason == 'interrupted':
            logger.info(f"\n{Colors.WARNING}⚠ TEST INTERRUPTED{Colors.ENDC}")
            logger.info(f"  Test was interrupted by user.")
        elif end_reason == 'error':
            logger.info(f"\n{Colors.FAIL}✗ TEST FAILED{Colors.ENDC}")
            logger.info(f"  Test encountered an error.")
        else:
            logger.info(f"\n{Colors.WARNING}⚠ TEST ENDED{Colors.ENDC}")

    # Phases executed
    phases_skipped = results.get('phases_skipped', [])
    phases_run = ['Create VMs']
    if 'resize' not in phases_skipped:
        phases_run.append('Resize Volumes')
    if 'restart' not in phases_skipped:
        phases_run.append('Restart VMs')
    if 'snapshot' not in phases_skipped:
        phases_run.append('Create Snapshots')

    logger.info(f"\n{Colors.HEADER}Phases Executed:{Colors.ENDC}")
    for phase in phases_run:
        logger.info(f"  ✓ {phase}")
    for phase in phases_skipped:
        logger.info(f"  - {phase.capitalize()} (skipped)")

    logger.info("\n" + "=" * 100)


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
    capacity_reached = False
    end_reason = 'unknown'

    try:
        while True:
            # Check if we've reached max iterations
            if args.max_iterations > 0 and iteration > args.max_iterations:
                logger.info(f"\n{Colors.OKGREEN}Reached maximum iterations ({args.max_iterations}){Colors.ENDC}")
                end_reason = 'max_iterations'
                break

            # Select storage class (round-robin)
            storage_class = storage_classes[(iteration - 1) % len(storage_classes)]

            # Run iteration
            iteration_start = time.time()
            success, iter_capacity_reached, vms_created = run_iteration(iteration, args.namespace, storage_class, args, logger)
            iteration_duration = time.time() - iteration_start

            # Always count VMs that were successfully created
            total_vms += vms_created

            if not success:
                if iter_capacity_reached:
                    capacity_reached = True
                    end_reason = 'capacity'
                    logger.warning(f"\n{Colors.WARNING}ITERATION {iteration} - CAPACITY REACHED after {iteration_duration:.2f}s{Colors.ENDC}")
                    logger.info(f"{Colors.OKGREEN}Cluster capacity limit reached!{Colors.ENDC}")
                    logger.info(f"Successfully created {vms_created} VMs in this iteration before capacity was reached")
                else:
                    end_reason = 'error'
                    logger.error(f"\n{Colors.FAIL}ITERATION {iteration} FAILED after {iteration_duration:.2f}s{Colors.ENDC}")
                    logger.error("Error occurred during iteration")
                break

            logger.info(f"Iteration {iteration} took {iteration_duration:.2f}s")
            logger.info(f"Total VMs created so far: {total_vms}")

            iteration += 1

            # Small delay between iterations
            time.sleep(5)

    except KeyboardInterrupt:
        logger.warning(f"\n{Colors.WARNING}Test interrupted by user{Colors.ENDC}")
        end_reason = 'interrupted'
    except Exception as e:
        logger.error(f"\n{Colors.FAIL}Unexpected error: {e}{Colors.ENDC}")
        import traceback
        logger.error(traceback.format_exc())
        end_reason = 'error'

    # Build results dictionary
    test_duration = time.time() - test_start_time
    duration_minutes = test_duration / 60
    duration_str = f"{test_duration:.2f}s ({duration_minutes:.2f} minutes)"

    # Determine which phases were skipped
    phases_skipped = []
    if args.skip_resize_job:
        phases_skipped.append('resize')
    if args.skip_restart_job:
        phases_skipped.append('restart')
    if args.skip_snapshot_job:
        phases_skipped.append('snapshot')

    results = {
        'storage_classes': ', '.join(storage_classes),
        'vms_per_iteration': args.vms,
        'data_volumes_per_vm': args.data_volume_count,
        'volume_size': args.min_vol_size,
        'vm_memory': args.vm_memory,
        'vm_cpu_cores': args.vm_cpu_cores,
        'iterations_completed': iteration - 1 if end_reason != 'capacity' else iteration,
        'total_vms': total_vms,
        'total_pvcs': total_vms * args.data_volume_count,
        'duration_str': duration_str,
        'capacity_reached': capacity_reached,
        'end_reason': end_reason,
        'phases_skipped': phases_skipped,
    }

    # Print summary report
    print_test_summary(results, logger)

    # Save results if requested
    if args.save_results:
        try:
            output_dir = save_capacity_results(
                results,
                base_dir=args.results_dir,
                storage_version=args.storage_version,
                logger=logger
            )
            logger.info(f"{Colors.OKGREEN}Results saved to: {output_dir}{Colors.ENDC}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
    else:
        logger.info("Results not saved (use --save-results to enable)")

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


