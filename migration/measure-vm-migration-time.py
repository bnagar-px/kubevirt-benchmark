#!/usr/bin/env python3
"""
KubeVirt VM Live Migration Performance Test

This script measures VM live migration performance across different scenarios:
- Sequential migration (one by one)
- Parallel migration (multiple VMs simultaneously)
- Evacuation scenario (all VMs from one node)
- Round-robin migration (distribute across multiple nodes)

Usage:
    # Sequential migration
    python3 measure-vm-migration-time.py --start 1 --end 10 --source-node worker-1 --target-node worker-2
    
    # Parallel migration
    python3 measure-vm-migration-time.py --start 1 --end 50 --source-node worker-1 --target-node worker-2 --parallel --concurrency 10
    
    # Evacuation scenario
    python3 measure-vm-migration-time.py --start 1 --end 100 --source-node worker-1 --evacuate
    
    # Round-robin migration
    python3 measure-vm-migration-time.py --start 1 --end 100 --round-robin

Author: Portworx
License: Apache 2.0
"""

import argparse
import os
import subprocess
import sys
import time
import random
import yaml
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.common import (
    setup_logging, run_kubectl_command, create_namespace, create_namespaces_parallel,
    delete_namespace, get_vm_status, get_vmi_ip, ping_vm, print_summary_table,
    validate_prerequisites, get_worker_nodes, select_random_node,
    add_node_selector_to_vm_yaml, get_vm_node, migrate_vm, get_migration_status,
    wait_for_migration_complete, get_available_nodes, create_namespace,
    find_busiest_node, get_vms_on_node, remove_node_selectors,
    cleanup_test_namespaces, confirm_cleanup, print_cleanup_summary,
    list_resources_in_namespace, delete_vmim, save_migration_results, get_px_version_from_cluster
)

# Default configuration
DEFAULT_VM_NAME = 'rhel-9-vm'
DEFAULT_NAMESPACE_PREFIX = 'kubevirt-perf-test'
DEFAULT_VM_YAML = '../examples/vm-templates/rhel9-vm-datasource.yaml'


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Measure KubeVirt VM live migration performance.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sequential migration from node-1 to node-2
  python3 measure-vm-migration-time.py --start 1 --end 10 --source-node worker-1 --target-node worker-2
  
  # Parallel migration with 10 concurrent migrations
  python3 measure-vm-migration-time.py --start 1 --end 50 --source-node worker-1 --target-node worker-2 --parallel --concurrency 10
  
  # Evacuate all VMs from node-1
  python3 measure-vm-migration-time.py --start 1 --end 100 --source-node worker-1 --evacuate
  
  # Round-robin migration across all nodes
  python3 measure-vm-migration-time.py --start 1 --end 100 --round-robin
  
  # Create VMs first, then migrate
  python3 measure-vm-migration-time.py --start 1 --end 10 --create-vms --source-node worker-1 --target-node worker-2
        """
    )
    
    # VM range
    parser.add_argument('-s', '--start', type=int, default=1,
                       help='Start index for test namespaces (default: 1)')
    parser.add_argument('-e', '--end', type=int, default=10,
                       help='End index for test namespaces (default: 10)')
    parser.add_argument('-n', '--vm-name', type=str, default=DEFAULT_VM_NAME,
                       help=f'VM name (default: {DEFAULT_VM_NAME})')
    
    # Namespace configuration
    parser.add_argument('--namespace-prefix', type=str, default=DEFAULT_NAMESPACE_PREFIX,
                       help=f'Prefix for test namespaces (default: {DEFAULT_NAMESPACE_PREFIX})')
    
    # VM creation
    parser.add_argument('--create-vms', action='store_true',
                       help='Create VMs before migration (default: use existing VMs)')
    parser.add_argument('--vm-template', type=str, default=DEFAULT_VM_YAML,
                       help=f'VM template YAML file (default: {DEFAULT_VM_YAML})')
    parser.add_argument('--single-node', action='store_true',
                       help='Create all VMs on a single node (requires --create-vms)')
    parser.add_argument('--node-name', type=str, default=None,
                       help='Specific node to create VMs on (requires --single-node and --create-vms)')
    
    # Migration scenarios
    parser.add_argument('--source-node', type=str, default=None,
                       help='Source node name (required for sequential/parallel/evacuate)')
    parser.add_argument('--target-node', type=str, default=None,
                       help='Target node name (optional, auto-select if not specified)')
    parser.add_argument('--parallel', action='store_true',
                       help='Migrate VMs in parallel (default: sequential)')
    parser.add_argument('--evacuate', action='store_true',
                       help='Evacuate all VMs from source node to any available nodes')
    parser.add_argument('--auto-select-busiest', action='store_true',
                       help='Auto-select the node with most VMs for evacuation (requires --evacuate)')
    parser.add_argument('--round-robin', action='store_true',
                       help='Migrate VMs in round-robin fashion across all nodes')
    
    # Performance options
    parser.add_argument('-c', '--concurrency', type=int, default=10,
                       help='Number of concurrent migrations (default: 10)')
    parser.add_argument('--migration-timeout', type=int, default=600,
                       help='Timeout for each migration in seconds (default: 600)')
    
    # Validation options
    parser.add_argument('--ssh-pod', type=str, default='ssh-pod-name',
                       help='SSH test pod name for ping tests (default: ssh-pod-name)')
    parser.add_argument('--ssh-pod-ns', type=str, default='default',
                       help='SSH test pod namespace (default: default)')
    parser.add_argument('--ping-timeout', type=int, default=600,
                       help='Timeout for ping test in seconds (default: 600)')
    parser.add_argument('--skip-ping', action='store_true',
                       help='Skip ping validation after migration')
    
    # Logging options
    parser.add_argument('--log-file', type=str, default=None,
                       help='Log file path (default: console only)')
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    
    # Cleanup options
    parser.add_argument('--cleanup', action='store_true',
                       help='Delete VMs, VMIMs, and namespaces after test')
    parser.add_argument('--cleanup-on-failure', action='store_true',
                       help='Clean up resources even if tests fail')
    parser.add_argument('--dry-run-cleanup', action='store_true',
                       help='Show what would be deleted without actually deleting')
    parser.add_argument('--yes', action='store_true',
                       help='Skip confirmation prompt for cleanup (use with caution)')
    parser.add_argument('--skip-checks', action='store_true',
                       help='Skip VM verifications before migration')
    parser.add_argument(
        '--save-results',
        action='store_true',
        help='Save detailed migration results (JSON and CSV) under results/.'
    )

    parser.add_argument(
        '--px-version',
        type=str,
        default=None,
        help='Portworx version to include in results path (auto-detect if not provided)'
    )

    parser.add_argument(
        '--px-namespace',
        type=str,
        default="portworx",
        help='Namespace where Portworx is installed (default: portworx)'
    )

    parser.add_argument(
        '--results-folder',
        type=str,
        default=os.path.join(os.path.dirname(os.getcwd()), 'results'),
        help='Base directory to store test results (default: ../results)'
    )

    parser.add_argument(
        '--interleaved-scheduling',
        action='store_true',
        help='Distribute parallel migration threads in interleaved pattern across nodes. '
             'Instead of sequential (1,2,3,...), distributes VMs evenly across nodes first. '
             'Example: With 400 VMs and 5 nodes, processes VMs in order: 1,81,161,241,321,2,82,162,... '
             'This ensures even load distribution across all nodes from the start, preventing '
             'hotspots and improving overall migration performance.'
    )

    return parser.parse_args()


def validate_migration_args(args, logger):
    """Validate migration-specific arguments."""
    # Validate --single-node usage
    if args.single_node and not args.create_vms:
        logger.error("--single-node requires --create-vms")
        return False

    if args.node_name and not args.single_node:
        logger.error("--node-name requires --single-node")
        return False

    if args.round_robin:
        # Round-robin doesn't need source/target nodes
        logger.info("Round-robin mode: will distribute VMs across all available nodes")
        return True

    if args.evacuate:
        # Evacuation can use either --source-node or --auto-select-busiest
        if args.auto_select_busiest:
            logger.info("Evacuation mode: will auto-select busiest node")
            if args.source_node:
                logger.warning("Both --source-node and --auto-select-busiest specified, will use --source-node")
            return True
        elif args.source_node:
            logger.info(f"Evacuation mode: will migrate all VMs from {args.source_node}")
            return True
        else:
            logger.error("--evacuate requires either --source-node or --auto-select-busiest")
            return False

    # Check if --auto-select-busiest is used without --evacuate
    if args.auto_select_busiest and not args.evacuate:
        logger.error("--auto-select-busiest can only be used with --evacuate")
        return False


    return True


def create_vms_on_node(namespaces: List[str], vm_yaml: str, node_name: str,
                       vm_name: str, logger) -> Dict[str, bool]:
    """
    Create VMs on a specific node.
    
    Returns:
        Dictionary mapping namespace to success status
    """
    logger.info(f"\nCreating {len(namespaces)} VMs on node {node_name}...")
    
    # Import create_vm function from datasource-clone script
    # For now, we'll use a simplified version
    from utils.common import add_node_selector_to_vm_yaml
    import subprocess
    
    results = {}
    
    for ns in namespaces:
        try:
            # Modify VM YAML to add nodeSelector
            modified_yaml = add_node_selector_to_vm_yaml(vm_yaml, node_name, logger)
            
            if not modified_yaml:
                logger.error(f"[{ns}] Failed to modify VM YAML")
                results[ns] = False
                continue
            
            # Create VM
            result = subprocess.run(
                f"kubectl create -f - -n {ns}",
                shell=True, input=modified_yaml.encode(), capture_output=True
            )
            
            if result.returncode == 0:
                logger.info(f"[{ns}] VM created successfully")
                results[ns] = True
            else:
                logger.error(f"[{ns}] Failed to create VM: {result.stderr.decode()}")
                results[ns] = False
        
        except Exception as e:
            logger.error(f"[{ns}] Exception creating VM: {e}")
            results[ns] = False
    
    return results


def wait_for_vms_running(namespaces: List[str], vm_name: str, timeout: int, logger) -> Dict[str, bool]:
    """Wait for all VMs to reach Running state."""
    logger.info(f"\nWaiting for {len(namespaces)} VMs to reach Running state...")

    results = {}
    start_time = time.time()

    for ns in namespaces:
        elapsed = time.time() - start_time
        remaining = max(0, timeout - elapsed)

        if remaining <= 0:
            logger.warning(f"[{ns}] Timeout waiting for VMs to reach Running state")
            results[ns] = False
            continue

        status = get_vm_status(vm_name, ns, logger)
        results[ns] = (status == "Running")

        if not results[ns]:
            logger.warning(f"[{ns}] VM did not reach Running state (status: {status})")

    return results


def migrate_vm_sequential(
    ns: str,
    vm_name: str,
    target_node: Optional[str],
    migration_timeout: int,
    logger,
    max_retries: int = 10,
    retry_delay: int = 2
) -> Tuple[str, bool, float, Optional[str], Optional[str], Optional[float]]:
    """
    Migrate a single VM and measure time.

    Retries VMIM creation up to `max_retries` times if webhook/internal errors occur.
    """

    try:
        # Get source node
        source_node = get_vm_node(vm_name, ns, logger)
        if not source_node:
            logger.error(f"[{ns}] Could not determine source node for VM {vm_name}")
            return ns, False, 0.0, None, None, None

        logger.info(f"[{ns}] Starting migration from {source_node}")

        # --- Retry VMIM creation only ---
        for attempt in range(1, max_retries + 1):
            try:
                if migrate_vm(vm_name, ns, target_node, logger):
                    break
                else:
                    logger.warning(f"[{ns}] Failed to trigger migration (attempt {attempt}/{max_retries})")
            except Exception as e:
                err_str = str(e)
                logger.warning(f"[{ns}] Exception creating VMIM (attempt {attempt}/{max_retries}): {err_str}")

            # backoff before next retry
            if attempt < max_retries:
                logger.info(f"[{ns}] Retrying VMIM creation in {retry_delay}s...")
                time.sleep(retry_delay)
        else:
            # ran out of retries
            logger.error(f"[{ns}] Failed to create VMIM after {max_retries} attempts")
            return ns, False, 0.0, source_node, None, None

        # Wait for migration to complete
        success, observed_duration, actual_target, vmim_duration = wait_for_migration_complete(
            vm_name, ns, migration_timeout, logger
        )

        return ns, success, observed_duration, source_node, actual_target, vmim_duration

    except Exception as e:
        logger.error(f"[{ns}] Exception during migration: {e}")
        return ns, False, 0.0, None, None, None


def main():
    """Main function."""
    args = parse_arguments()
    
    # Setup logging
    logger = setup_logging(args.log_file, args.log_level)
    
    # Print configuration
    logger.info("=" * 80)
    logger.info("KubeVirt VM Live Migration Performance Test")
    logger.info("=" * 80)
    logger.info(f"VM range: {args.start} to {args.end}")
    logger.info(f"VM name: {args.vm_name}")
    logger.info(f"Namespace prefix: {args.namespace_prefix}")
    logger.info(f"Create VMs: {args.create_vms}")

    if not args.px_version:
        args.px_version = get_px_version_from_cluster(logger, namespace=args.px_namespace)
    else:
        logger.info(f"Using provided PX version: {args.px_version}")

    if args.round_robin:
        logger.info("Migration mode: Round-robin")
    elif args.evacuate:
        if args.auto_select_busiest:
            logger.info("Migration mode: Evacuation (auto-select busiest node)")
        else:
            logger.info(f"Migration mode: Evacuation from {args.source_node}")
    elif args.parallel:
        logger.info(f"Migration mode: Parallel (concurrency: {args.concurrency})")
    else:
        logger.info("Migration mode: Sequential")

    if args.source_node and not args.evacuate:
        logger.info(f"Source node: {args.source_node}")
    if args.target_node:
        logger.info(f"Target node: {args.target_node}")
    
    logger.info("=" * 80)
    
    # Validate arguments
    if not validate_migration_args(args, logger):
        sys.exit(1)

    # Validate prerequisites (SSH pod for ping tests)
    if not args.skip_ping:
        if not validate_prerequisites(args.ssh_pod, args.ssh_pod_ns, logger):
            logger.warning("SSH pod not available, will skip ping tests")
            args.skip_ping = True

    # Prepare namespaces
    namespaces = [f"{args.namespace_prefix}-{i}" for i in range(args.start, args.end + 1)]
    logger.info(f"\nTarget namespaces: {namespaces[0]} to {namespaces[-1]} ({len(namespaces)} total)")

    # Phase 1: Create VMs if requested
    if args.create_vms:
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 1: Creating VMs")
        logger.info("=" * 80)

        # Determine node for VM creation
        creation_node = None

        if args.single_node:
            # Single-node mode: create all VMs on one node
            if args.node_name:
                creation_node = args.node_name
                logger.info(f"Single-node mode: Creating all VMs on {creation_node}")
            else:
                # Auto-select a node
                creation_node = select_random_node(logger)
                if not creation_node:
                    logger.error("Failed to select a node for single-node mode")
                    sys.exit(1)
                logger.info(f"Single-node mode: Auto-selected node {creation_node}")
        elif args.source_node:
            creation_node = args.source_node
            logger.info(f"Creating VMs on source node: {creation_node}")
        elif args.round_robin:
            # For round-robin, create VMs distributed across nodes
            creation_node = None
            logger.info("Round-robin mode: VMs will be created across all nodes")
        else:
            # Auto-select a source node
            creation_node = select_random_node(logger)
            if not creation_node:
                logger.error("Failed to select a source node")
                sys.exit(1)
            logger.info(f"Auto-selected source node: {creation_node}")

        # Create namespaces
        logger.info(f"\nCreating {len(namespaces)} namespaces...")
        successful_ns = create_namespaces_parallel(namespaces, 20, logger)

        if len(successful_ns) < len(namespaces):
            logger.error(f"Failed to create all namespaces. Created: {len(successful_ns)}/{len(namespaces)}")
            sys.exit(1)

        # Create VMs
        if creation_node:
            create_results = create_vms_on_node(namespaces, args.vm_template, creation_node, args.vm_name, logger)
        else:
            # For round-robin, create VMs without node selector
            logger.info("Creating VMs without node selector (will be distributed)")
            create_results = create_vms_on_node(namespaces, args.vm_template, None, args.vm_name, logger)

        # Wait for VMs to be running
        logger.info("\nWaiting for VMs to reach Running state...")
        running_results = wait_for_vms_running(namespaces, args.vm_name, 600, logger)

        successful_vms = sum(1 for success in running_results.values() if success)
        logger.info(f"\nVMs running: {successful_vms}/{len(namespaces)}")

        if successful_vms == 0:
            logger.error("No VMs are running. Cannot proceed with migration.")
            sys.exit(1)

        # Remove nodeSelectors to allow migration
        if creation_node:
            logger.info("\n" + "=" * 80)
            logger.info("REMOVING NODE SELECTORS FOR MIGRATION")
            logger.info("=" * 80)
            logger.info(f"\nVMs were created with nodeSelector on {creation_node}")
            logger.info("Removing nodeSelector from VM and VMI objects to allow live migration...")

            removal_success = 0
            removal_failed = 0

            for ns in namespaces:
                if remove_node_selectors(args.vm_name, ns, logger):
                    removal_success += 1
                    logger.info(f"[{ns}] Removed nodeSelector")
                else:
                    removal_failed += 1
                    logger.warning(f"[{ns}] Failed to remove nodeSelector")

            logger.info(f"\nNodeSelector removal: {removal_success} successful, {removal_failed} failed")

            if removal_success == 0:
                logger.error("Failed to remove nodeSelectors. VMs cannot be migrated.")
                sys.exit(1)

            logger.info("VMs are now ready for live migration!")
            logger.info("=" * 80)

    # Phase 2: Verify VMs exist and are running
    else:
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 1: Verifying Existing VMs")
        logger.info("=" * 80)
        if not args.skip_checks:
            logger.info(f"\nChecking {len(namespaces)} VMs...")
            running_count = 0

            for ns in namespaces:
                status = get_vm_status(args.vm_name, ns, logger)
                if status == "Running":
                    running_count += 1
                else:
                    logger.warning(f"[{ns}] VM not running (status: {status})")

            logger.info(f"\nFound {running_count}/{len(namespaces)} running VMs")

            if running_count == 0:
                logger.error("No running VMs found. Use --create-vms to create VMs first.")
                sys.exit(1)

            # Check if VMs have nodeSelectors and remove them
            logger.info("\n" + "=" * 80)
            logger.info("CHECKING FOR NODE SELECTORS")
            logger.info("=" * 80)
            logger.info("Checking if VMs have nodeSelector that would prevent migration...")

            # Remove nodeSelectors from all VMs to ensure they can be migrated
            removal_success = 0
            removal_failed = 0

            for ns in namespaces:
                if remove_node_selectors(args.vm_name, ns, logger):
                    removal_success += 1
                else:
                    removal_failed += 1

            if removal_success > 0:
                logger.info(f"\nRemoved nodeSelector from {removal_success} VMs")
            if removal_failed > 0:
                logger.warning(f"Failed to remove nodeSelector from {removal_failed} VMs")
        else:
            logger.info("Skipping VM Verifications...")
        logger.info("VMs are ready for live migration!")
        logger.info("=" * 80)

    logger.info("Detecting disk count from existing VM spec...")
    try:
        sample_ns = f"{args.namespace_prefix}-{args.start}"
        vm_yaml_cmd = [
            "kubectl", "get", "vm", args.vm_name, "-n", sample_ns, "-o", "yaml"
        ]
        result = subprocess.run(vm_yaml_cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout:
            vm_spec = yaml.safe_load(result.stdout)
            volumes = (
                vm_spec.get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("volumes", [])
            )
            non_cloudinit = [
                v for v in volumes
                if not any(k in v for k in ["cloudInitNoCloud", "cloudInitConfigDrive"])
            ]
            num_disks = len(non_cloudinit)
            logger.info(f"Detected {num_disks} disks (excluding cloud-init volumes)")
        else:
            logger.warning("Could not retrieve VM spec; defaulting to 1 disk")
            num_disks = 1
    except Exception as e:
        logger.error(f"Error detecting disks: {e}")
        num_disks = 1

    # Phase 2: Perform Migration
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 2: Live Migration")
    logger.info("=" * 80)

    migration_results = []
    migration_phase_start = datetime.now()

    # Scenario 1: Sequential Migration
    if not args.parallel and not args.evacuate and not args.round_robin:
        logger.info(f"\nSequential migration from {args.source_node or 'auto-selected node'} to {args.target_node or 'auto-selected node'}")

        for ns in namespaces:
            result = migrate_vm_sequential(ns, args.vm_name, args.target_node, args.migration_timeout, logger)
            migration_results.append(result)

            # Small delay between migrations
            time.sleep(1)

    # Scenario 2: Parallel Migration
    elif args.parallel and not args.evacuate and not args.round_robin:
        logger.info(f"\nParallel migration from {args.source_node or 'auto-selected node'} "
                    f"to {args.target_node or 'auto-selected node'}")
        logger.info(f"Concurrency: {args.concurrency}")

        # Detect available nodes
        available_nodes = get_worker_nodes(logger)
        num_nodes = len(available_nodes) if available_nodes else 1
        logger.info(f"Found {num_nodes} worker nodes: {', '.join(available_nodes) if available_nodes else 'N/A'}")

        # Default: sequential namespace order
        reordered_namespaces = namespaces

        # --- Interleaved scheduling ---
        if args.interleaved_scheduling:
            total_namespaces = len(namespaces)
            group_size = total_namespaces // num_nodes or 1

            reordered_namespaces = []
            for offset in range(group_size):
                for i in range(offset, total_namespaces, group_size):
                    reordered_namespaces.append(namespaces[i])

            logger.info(f"Detected {num_nodes} available nodes for interleaved scheduling")
            logger.info(f"Reordered namespaces for interleaved scheduling (stride={group_size}). "
                        f"First 10: {reordered_namespaces[:10]}")
        else:
            logger.info("Using default sequential namespace order for parallel scheduling")

        # --- Parallel migration execution ---
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = {
                executor.submit(
                    migrate_vm_sequential,
                    ns,
                    args.vm_name,
                    args.target_node,
                    args.migration_timeout,
                    logger
                ): ns for ns in reordered_namespaces
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    migration_results.append(result)
                except Exception as e:
                    ns = futures[future]
                    logger.error(f"[{ns}] Exception during migration: {e}")
                    migration_results.append((ns, False, 0.0, None, None, None))

    # Scenario 3: Evacuation
    elif args.evacuate:
        # Determine source node
        if args.auto_select_busiest and not args.source_node:
            logger.info("\n" + "=" * 80)
            logger.info("AUTO-SELECTING BUSIEST NODE")
            logger.info("=" * 80)

            source_node = find_busiest_node(namespaces, args.vm_name, logger)

            if not source_node:
                logger.error("Could not find any VMs to determine busiest node")
                sys.exit(1)

            logger.info(f"\nSelected source node for evacuation: {source_node}")
            logger.info("=" * 80)
        else:
            source_node = args.source_node

        logger.info(f"\nEvacuation: migrating all VMs from {source_node}")
        logger.info(f"Concurrency: {args.concurrency}")

        # Find VMs actually running on the source node
        logger.info("\n" + "=" * 80)
        logger.info("IDENTIFYING VMs ON SOURCE NODE")
        logger.info("=" * 80)

        vms_to_evacuate = get_vms_on_node(namespaces, args.vm_name, source_node, logger)

        if not vms_to_evacuate:
            logger.error(f"No VMs found on {source_node} within the specified namespace range")
            logger.info(f"Checked namespaces: {namespaces[0]} to {namespaces[-1]}")
            sys.exit(1)

        logger.info(f"\nVMs to evacuate from {source_node}:")
        for ns in vms_to_evacuate:
            logger.info(f"  - {ns}")

        # Get available target nodes (excluding source)
        available_nodes = get_available_nodes([source_node], logger)

        if not available_nodes:
            logger.error(f"No available nodes to evacuate to (excluding {source_node})")
            sys.exit(1)

        logger.info(f"\nAvailable target nodes: {available_nodes}")
        logger.info("=" * 80)

        # Migrate only the VMs that are on the source node
        logger.info(f"\nStarting evacuation of {len(vms_to_evacuate)} VMs...")

        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = {
                executor.submit(migrate_vm_sequential, ns, args.vm_name, None,
                              args.migration_timeout, logger): ns
                for ns in vms_to_evacuate  # Only migrate VMs on source node
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    migration_results.append(result)
                except Exception as e:
                    ns = futures[future]
                    logger.error(f"[{ns}] Exception during migration: {e}")
                    migration_results.append((ns, False, 0.0, None, None, None))

    # Scenario 4: Round-Robin
    elif args.round_robin:
        logger.info("\nRound-robin migration across all nodes")
        logger.info(f"Concurrency: {args.concurrency}")

        # Get all worker nodes
        all_nodes = get_worker_nodes(logger)

        if len(all_nodes) < 2:
            logger.error("Need at least 2 nodes for round-robin migration")
            sys.exit(1)

        logger.info(f"Available nodes: {all_nodes}")

        # For each VM, select a target node different from current node
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = {}

            for ns in namespaces:
                # Get current node
                current_node = get_vm_node(args.vm_name, ns, logger)

                if current_node:
                    # Select a different node
                    available = [n for n in all_nodes if n != current_node]
                    target = random.choice(available) if available else None
                else:
                    target = None

                future = executor.submit(migrate_vm_sequential, ns, args.vm_name, target,
                                       args.migration_timeout, logger)
                futures[future] = ns

            for future in as_completed(futures):
                try:
                    result = future.result()
                    migration_results.append(result)
                except Exception as e:
                    ns = futures[future]
                    logger.error(f"[{ns}] Exception during migration: {e}")
                    migration_results.append((ns, False, 0.0, None, None, None))

    total_migration_time = (datetime.now() - migration_phase_start).total_seconds()
    # Phase 4: Validation (Ping Test)
    if not args.skip_ping:
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 3: Network Validation")
        logger.info("=" * 80)

        logger.info(f"\nTesting network connectivity for {len(namespaces)} VMs...")

        ping_results = {}
        for ns in namespaces:
            vm_ip = get_vmi_ip(args.vm_name, ns, logger)
            if vm_ip:
                ping_success = ping_vm(vm_ip, args.ssh_pod, args.ssh_pod_ns, logger)
                ping_results[ns] = ping_success
                if ping_success:
                    logger.info(f"[{ns}] Ping successful to {vm_ip}")
                else:
                    logger.warning(f"[{ns}] Ping failed to {vm_ip}")
            else:
                logger.warning(f"[{ns}] Could not get VM IP")
                ping_results[ns] = False

        successful_pings = sum(1 for success in ping_results.values() if success)
        logger.info(f"\nPing successful: {successful_pings}/{len(namespaces)}")

    # Phase 5: Display Results
    logger.info("\n" + "=" * 80)
    logger.info("MIGRATION RESULTS")
    logger.info("=" * 80)

    # Prepare results table
    table_data = []
    for ns, success, observed_duration, source, target, vmim_duration in migration_results:
        status = "Success" if success else "Failed"
        table_data.append({
            'namespace': ns,
            'source_node': source or 'Unknown',
            'target_node': target or 'Unknown',
            'observed_duration': f"{observed_duration:.2f}s" if success else "N/A",
            'vmim_duration': f"{vmim_duration:.2f}s" if (success and vmim_duration) else "N/A",
            'status': status
        })

    # Print table
    if table_data:
        logger.info(f"Total migration time for {len(migration_results)} VMs: {total_migration_time:.2f}s")
        logger.info("\n" + "=" * 150)
        logger.info(f"{'Namespace':<25} {'Source Node':<30} {'Target Node':<30} {'Observed Time':<15} {'VMIM Time':<15} {'Status':<10}")
        logger.info("=" * 150)

        for row in table_data:
            logger.info(f"{row['namespace']:<25} {row['source_node']:<30} {row['target_node']:<30} "
                  f"{row['observed_duration']:<15} {row['vmim_duration']:<15} {row['status']:<10}")

        logger.info("=" * 150)

    # Statistics
    successful_migrations = sum(1 for _, success, _, _, _, _ in migration_results if success)
    failed_migrations = len(migration_results) - successful_migrations

    if successful_migrations > 0:
        # Observed durations (node change detection)
        observed_durations = [observed_duration for _, success, observed_duration, _, _, _ in migration_results if success]
        avg_observed = sum(observed_durations) / len(observed_durations)
        min_observed = min(observed_durations)
        max_observed = max(observed_durations)

        # VMIM durations (official KubeVirt timestamps)
        vmim_durations = [vmim_duration for _, success, _, _, _, vmim_duration in migration_results
                         if success and vmim_duration is not None]

        logger.info("\n" + "=" * 80)
        logger.info("MIGRATION STATISTICS")
        logger.info("=" * 80)
        logger.info(f"\n  Total VMs:              {len(migration_results)}")
        logger.info(f"  Successful Migrations:  {successful_migrations}")
        logger.info(f"  Failed Migrations:      {failed_migrations}")

        logger.info(f"\n  Observed Time (Node Change Detection):")
        logger.info(f"    Average:              {avg_observed:.2f}s")
        logger.info(f"    Minimum:              {min_observed:.2f}s")
        logger.info(f"    Maximum:              {max_observed:.2f}s")

        if vmim_durations:
            avg_vmim = sum(vmim_durations) / len(vmim_durations)
            min_vmim = min(vmim_durations)
            max_vmim = max(vmim_durations)

            logger.info(f"\n  VMIM Time (Official KubeVirt Timestamps):")
            logger.info(f"    Average:              {avg_vmim:.2f}s")
            logger.info(f"    Minimum:              {min_vmim:.2f}s")
            logger.info(f"    Maximum:              {max_vmim:.2f}s")

            # Calculate difference
            avg_diff = avg_observed - avg_vmim
            logger.info(f"\n  Difference (Observed - VMIM):")
            logger.info(f"    Average:              {avg_diff:.2f}s")
            logger.info(f"    Note: Difference includes polling overhead (~2s) and status update delays")
        else:
            logger.info(f"\n  VMIM Time: Not available (timestamps not found)")

        logger.info("=" * 80)

    # --- Save structured migration results if requested ---
    if args.save_results:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = f"{args.namespace_prefix}_{args.start}-{args.end}"

        out_dir = os.path.join(
            args.results_folder,
            args.px_version,
            f"{num_disks}-disk",
            f"{timestamp}_live_migration_{suffix}"
        )
        os.makedirs(out_dir, exist_ok=True)

        logger.info(f"Created results directory: {out_dir}")

        # Save detailed and summary results in the correct folder
        save_migration_results(
            args,
            migration_results,
            base_dir=out_dir,
            logger=logger,
            total_time=total_migration_time
        )

        logger.info(f"Migration results saved under: {out_dir}")
    else:
        logger.info("Migration results not saved (use --save-results to enable).")


    # Determine if cleanup should run
    should_cleanup = args.cleanup or (args.cleanup_on_failure and failed_migrations > 0)

    # Cleanup
    if should_cleanup or args.dry_run_cleanup:
        logger.info("\n" + "=" * 80)
        logger.info("CLEANUP")
        logger.info("=" * 80)

        # Confirm cleanup if needed
        if not args.dry_run_cleanup and not confirm_cleanup(len(namespaces), args.yes):
            logger.info("Cleanup cancelled by user")
        else:
            logger.info(f"\n{'[DRY RUN] ' if args.dry_run_cleanup else ''}Cleaning up test resources...")

            try:
                # Clean up VMIMs first
                logger.info("Cleaning up VirtualMachineInstanceMigration objects...")
                vmim_count = 0
                for ns in namespaces:
                    vmims = list_resources_in_namespace(ns, 'virtualmachineinstancemigration', logger)
                    for vmim in vmims:
                        if args.dry_run_cleanup:
                            logger.info(f"[DRY RUN] Would delete VMIM: {vmim} in {ns}")
                        else:
                            if delete_vmim(vmim, ns, logger):
                                vmim_count += 1

                logger.info(f"{'[DRY RUN] Would delete' if args.dry_run_cleanup else 'Deleted'} {vmim_count} VMIM objects")

                # Clean up VMs and namespaces if they were created by this test
                if args.create_vms:
                    stats = cleanup_test_namespaces(
                        namespace_prefix=args.namespace_prefix,
                        start=args.start,
                        end=args.end,
                        vm_name=args.vm_name,
                        delete_namespaces=True,
                        dry_run=args.dry_run_cleanup,
                        batch_size=args.concurrency,
                        logger=logger
                    )
                    print_cleanup_summary(stats, logger)
                else:
                    logger.info("VMs were not created by this test, skipping VM/namespace deletion")
                    logger.info("Only VMIM objects were cleaned up")

                if not args.dry_run_cleanup:
                    logger.info("Cleanup completed successfully!")

            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                logger.warning("Some resources may not have been cleaned up")

    logger.info("\nMigration test complete!")


if __name__ == '__main__':
    main()

