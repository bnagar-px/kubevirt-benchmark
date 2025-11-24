#!/usr/bin/env python3
"""
Common utilities for KubeVirt performance testing.

This module provides shared functionality including logging setup,
kubectl command execution, and common helper functions.
"""

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
import os
from typing import Optional, Tuple, List
import csv

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def setup_logging(log_file: Optional[str] = None, log_level: str = 'INFO') -> logging.Logger:
    """
    Configure logging for the test suite.
    
    Args:
        log_file: Optional file path to write logs to
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger('kubevirt-perf')
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if not log_file:
        log_file = f"kubevirt-perf-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    
    # File handler if specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)  # Always log everything to file
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.info(f"Logging to file: {log_file}")
        except Exception as e:
            logger.error(f"Failed to create log file {log_file}: {e}")
    
    return logger


def run_kubectl_command(
    args: List[str],
    check: bool = True,
    capture_output: bool = True,
    timeout: Optional[int] = None,
    logger: Optional[logging.Logger] = None
) -> Tuple[int, str, str]:
    """
    Execute a kubectl command with error handling.
    
    Args:
        args: List of command arguments (e.g., ['get', 'pods'])
        check: Raise exception on non-zero exit code
        capture_output: Capture stdout and stderr
        timeout: Command timeout in seconds
        logger: Logger instance for debug output
    
    Returns:
        Tuple of (return_code, stdout, stderr)
    
    Raises:
        subprocess.CalledProcessError: If check=True and command fails
        subprocess.TimeoutExpired: If command exceeds timeout
    """
    cmd = ['kubectl'] + args
    
    if logger:
        logger.debug(f"Executing: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            check=check
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        if logger:
            logger.error(f"Command failed: {' '.join(cmd)}")
            logger.error(f"Exit code: {e.returncode}")
            logger.error(f"Stderr: {e.stderr}")
        if check:
            raise
        return e.returncode, e.stdout, e.stderr
    except subprocess.TimeoutExpired as e:
        if logger:
            logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        raise


def namespace_exists(namespace: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Check if a namespace exists.
    
    Args:
        namespace: Namespace name
        logger: Logger instance
    
    Returns:
        True if namespace exists, False otherwise
    """
    try:
        returncode, _, _ = run_kubectl_command(
            ['get', 'namespace', namespace],
            check=False,
            logger=logger
        )
        return returncode == 0
    except Exception as e:
        if logger:
            logger.error(f"Error checking namespace {namespace}: {e}")
        return False


def create_namespace(namespace: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Create a namespace if it doesn't exist.

    Args:
        namespace: Namespace name
        logger: Logger instance

    Returns:
        True if created or already exists, False on error
    """
    if namespace_exists(namespace, logger):
        if logger:
            logger.debug(f"Namespace {namespace} already exists")
        return True

    try:
        run_kubectl_command(['create', 'namespace', namespace], logger=logger)
        if logger:
            logger.info(f"Created namespace: {namespace}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to create namespace {namespace}: {e}")
        return False


def create_namespaces_parallel(namespaces: List[str], batch_size: int = 20,
                               logger: Optional[logging.Logger] = None) -> List[str]:
    """
    Create multiple namespaces in parallel batches.

    Args:
        namespaces: List of namespace names to create
        batch_size: Number of namespaces to create in parallel
        logger: Logger instance

    Returns:
        List of successfully created namespace names
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if logger:
        logger.info(f"Creating {len(namespaces)} namespaces in batches of {batch_size}...")

    successful = []
    failed = []

    with ThreadPoolExecutor(max_workers=batch_size) as executor:
        futures = {executor.submit(create_namespace, ns, logger): ns for ns in namespaces}

        for future in as_completed(futures):
            ns = futures[future]
            try:
                if future.result():
                    successful.append(ns)
                else:
                    failed.append(ns)
            except Exception as e:
                if logger:
                    logger.error(f"Exception creating namespace {ns}: {e}")
                failed.append(ns)

    if logger:
        logger.info(f"Namespace creation complete: {len(successful)} successful, {len(failed)} failed")

    return successful


def delete_namespace(namespace: str, wait: bool = False, logger: Optional[logging.Logger] = None) -> bool:
    """
    Delete a namespace.

    Args:
        namespace: Namespace name
        wait: Wait for namespace to be fully deleted
        logger: Logger instance

    Returns:
        True if deleted successfully, False on error
    """
    try:
        run_kubectl_command(['delete', 'namespace', namespace], logger=logger)
        if logger:
            logger.info(f"Deleted namespace: {namespace}")

        if wait:
            # Wait for namespace to be fully deleted
            max_wait = 300  # 5 minutes
            start_time = time.time()
            while namespace_exists(namespace, logger):
                if time.time() - start_time > max_wait:
                    if logger:
                        logger.warning(f"Timeout waiting for namespace {namespace} deletion")
                    return False
                time.sleep(2)

        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to delete namespace {namespace}: {e}")
        return False


def delete_namespaces_parallel(namespaces: List[str], batch_size: int = 20,
                               logger: Optional[logging.Logger] = None) -> Tuple[List[str], List[str]]:
    """
    Delete multiple namespaces in parallel batches.

    Args:
        namespaces: List of namespace names to delete
        batch_size: Number of namespaces to delete in parallel
        logger: Logger instance

    Returns:
        Tuple of (successful_deletions, failed_deletions)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if logger:
        logger.info(f"Deleting {len(namespaces)} namespaces in batches of {batch_size}...")

    successful = []
    failed = []

    with ThreadPoolExecutor(max_workers=batch_size) as executor:
        futures = {executor.submit(delete_namespace, ns, False, logger): ns for ns in namespaces}

        for future in as_completed(futures):
            ns = futures[future]
            try:
                if future.result():
                    successful.append(ns)
                else:
                    failed.append(ns)
            except Exception as e:
                if logger:
                    logger.error(f"Exception deleting namespace {ns}: {e}")
                failed.append(ns)

    if logger:
        logger.info(f"Namespace deletion complete: {len(successful)} successful, {len(failed)} failed")

    return successful, failed


def delete_vm(vm_name: str, namespace: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Delete a VM resource.

    Args:
        vm_name: VM name
        namespace: Namespace
        logger: Logger instance

    Returns:
        True if deleted successfully, False on error
    """
    try:
        run_kubectl_command(['delete', 'vm', vm_name, '-n', namespace], check=False, logger=logger)
        if logger:
            logger.debug(f"Deleted VM {vm_name} in namespace {namespace}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to delete VM {vm_name} in {namespace}: {e}")
        return False


def delete_datavolume(dv_name: str, namespace: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Delete a DataVolume resource.

    Args:
        dv_name: DataVolume name
        namespace: Namespace
        logger: Logger instance

    Returns:
        True if deleted successfully, False on error
    """
    try:
        run_kubectl_command(['delete', 'dv', dv_name, '-n', namespace], check=False, logger=logger)
        if logger:
            logger.debug(f"Deleted DataVolume {dv_name} in namespace {namespace}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to delete DataVolume {dv_name} in {namespace}: {e}")
        return False


def delete_pvc(pvc_name: str, namespace: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Delete a PersistentVolumeClaim resource.

    Args:
        pvc_name: PVC name
        namespace: Namespace
        logger: Logger instance

    Returns:
        True if deleted successfully, False on error
    """
    try:
        run_kubectl_command(['delete', 'pvc', pvc_name, '-n', namespace], check=False, logger=logger)
        if logger:
            logger.debug(f"Deleted PVC {pvc_name} in namespace {namespace}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to delete PVC {pvc_name} in {namespace}: {e}")
        return False


def delete_vmim(vmim_name: str, namespace: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Delete a VirtualMachineInstanceMigration resource.

    Args:
        vmim_name: VMIM name
        namespace: Namespace
        logger: Logger instance

    Returns:
        True if deleted successfully, False on error
    """
    try:
        run_kubectl_command(['delete', 'virtualmachineinstancemigration', vmim_name, '-n', namespace],
                          check=False, logger=logger)
        if logger:
            logger.debug(f"Deleted VMIM {vmim_name} in namespace {namespace}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to delete VMIM {vmim_name} in {namespace}: {e}")
        return False


def list_resources_in_namespace(namespace: str, resource_type: str,
                                logger: Optional[logging.Logger] = None) -> List[str]:
    """
    List all resources of a specific type in a namespace.

    Args:
        namespace: Namespace name
        resource_type: Resource type (e.g., 'vm', 'dv', 'pvc', 'vmim')
        logger: Logger instance

    Returns:
        List of resource names
    """
    try:
        returncode, stdout, _ = run_kubectl_command(
            ['get', resource_type, '-n', namespace, '-o', 'jsonpath={.items[*].metadata.name}'],
            check=False,
            logger=logger
        )
        if returncode == 0 and stdout:
            return stdout.strip().split()
        return []
    except Exception as e:
        if logger:
            logger.debug(f"Error listing {resource_type} in {namespace}: {e}")
        return []


def cleanup_namespace_resources(namespace: str, vm_name: Optional[str] = None,
                                dry_run: bool = False, logger: Optional[logging.Logger] = None) -> dict:
    """
    Clean up all test resources in a namespace.

    Args:
        namespace: Namespace name
        vm_name: Optional VM name to delete (if None, deletes all VMs)
        dry_run: If True, only show what would be deleted
        logger: Logger instance

    Returns:
        Dictionary with cleanup statistics
    """
    stats = {
        'vms_deleted': 0,
        'dvs_deleted': 0,
        'pvcs_deleted': 0,
        'vmims_deleted': 0,
        'errors': 0
    }

    if not namespace_exists(namespace, logger):
        if logger:
            logger.debug(f"Namespace {namespace} does not exist, skipping cleanup")
        return stats

    # Delete VirtualMachineInstanceMigrations
    vmims = list_resources_in_namespace(namespace, 'virtualmachineinstancemigration', logger)
    for vmim in vmims:
        if dry_run:
            if logger:
                logger.info(f"[DRY RUN] Would delete VMIM: {vmim} in {namespace}")
        else:
            if delete_vmim(vmim, namespace, logger):
                stats['vmims_deleted'] += 1
            else:
                stats['errors'] += 1

    # Delete VMs
    if vm_name:
        vms = [vm_name]
    else:
        vms = list_resources_in_namespace(namespace, 'vm', logger)

    for vm in vms:
        if dry_run:
            if logger:
                logger.info(f"[DRY RUN] Would delete VM: {vm} in {namespace}")
        else:
            if delete_vm(vm, namespace, logger):
                stats['vms_deleted'] += 1
            else:
                stats['errors'] += 1

    # Delete DataVolumes
    dvs = list_resources_in_namespace(namespace, 'dv', logger)
    for dv in dvs:
        if dry_run:
            if logger:
                logger.info(f"[DRY RUN] Would delete DataVolume: {dv} in {namespace}")
        else:
            if delete_datavolume(dv, namespace, logger):
                stats['dvs_deleted'] += 1
            else:
                stats['errors'] += 1

    # Delete PVCs (if any remain after DV deletion)
    pvcs = list_resources_in_namespace(namespace, 'pvc', logger)
    for pvc in pvcs:
        if dry_run:
            if logger:
                logger.info(f"[DRY RUN] Would delete PVC: {pvc} in {namespace}")
        else:
            if delete_pvc(pvc, namespace, logger):
                stats['pvcs_deleted'] += 1
            else:
                stats['errors'] += 1

    return stats


def cleanup_test_namespaces(namespace_prefix: str, start: int, end: int,
                           vm_name: Optional[str] = None, delete_namespaces: bool = True,
                           dry_run: bool = False, batch_size: int = 20,
                           logger: Optional[logging.Logger] = None) -> dict:
    """
    Clean up all test resources across multiple namespaces.

    Args:
        namespace_prefix: Namespace prefix (e.g., 'kubevirt-perf-test')
        start: Starting namespace index
        end: Ending namespace index
        vm_name: Optional VM name to delete
        delete_namespaces: If True, delete namespaces after cleaning resources
        dry_run: If True, only show what would be deleted
        batch_size: Number of namespaces to process in parallel
        logger: Logger instance

    Returns:
        Dictionary with overall cleanup statistics
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    namespaces = [f"{namespace_prefix}-{i}" for i in range(start, end + 1)]

    if logger:
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Cleaning up {len(namespaces)} namespaces...")

    overall_stats = {
        'namespaces_processed': 0,
        'namespaces_deleted': 0,
        'total_vms_deleted': 0,
        'total_dvs_deleted': 0,
        'total_pvcs_deleted': 0,
        'total_vmims_deleted': 0,
        'total_errors': 0
    }

    # Clean up resources in each namespace
    with ThreadPoolExecutor(max_workers=batch_size) as executor:
        futures = {
            executor.submit(cleanup_namespace_resources, ns, vm_name, dry_run, logger): ns
            for ns in namespaces
        }

        for future in as_completed(futures):
            ns = futures[future]
            try:
                stats = future.result()
                overall_stats['namespaces_processed'] += 1
                overall_stats['total_vms_deleted'] += stats['vms_deleted']
                overall_stats['total_dvs_deleted'] += stats['dvs_deleted']
                overall_stats['total_pvcs_deleted'] += stats['pvcs_deleted']
                overall_stats['total_vmims_deleted'] += stats['vmims_deleted']
                overall_stats['total_errors'] += stats['errors']
            except Exception as e:
                if logger:
                    logger.error(f"Exception cleaning namespace {ns}: {e}")
                overall_stats['total_errors'] += 1

    # Delete namespaces if requested
    if delete_namespaces and not dry_run:
        if logger:
            logger.info(f"Deleting {len(namespaces)} namespaces...")
        successful, failed = delete_namespaces_parallel(namespaces, batch_size, logger)
        overall_stats['namespaces_deleted'] = len(successful)
        overall_stats['total_errors'] += len(failed)
    elif delete_namespaces and dry_run:
        if logger:
            for ns in namespaces:
                logger.info(f"[DRY RUN] Would delete namespace: {ns}")

    return overall_stats


def remove_far_annotation(vm_name: str, namespace: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Remove FAR (Fence Agents Remediation) annotation from a VM.

    Args:
        vm_name: VM name
        namespace: Namespace
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    try:
        import json
        patch = {
            "metadata": {
                "annotations": {
                    "vm.kubevirt.io/fenced": None
                }
            }
        }
        patch_json = json.dumps(patch)

        run_kubectl_command(
            ['patch', 'vm', vm_name, '-n', namespace, '--type', 'merge', '-p', patch_json],
            check=False,
            logger=logger
        )
        if logger:
            logger.debug(f"Removed FAR annotation from VM {vm_name} in {namespace}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to remove FAR annotation from VM {vm_name} in {namespace}: {e}")
        return False


def delete_far_resource(far_name: str, namespace: str = 'default',
                       logger: Optional[logging.Logger] = None) -> bool:
    """
    Delete a FenceAgentsRemediation custom resource.

    Args:
        far_name: FAR resource name
        namespace: Namespace (default: 'default')
        logger: Logger instance

    Returns:
        True if deleted successfully, False on error
    """
    try:
        run_kubectl_command(
            ['delete', 'fenceagentsremediation', far_name, '-n', namespace],
            check=False,
            logger=logger
        )
        if logger:
            logger.info(f"Deleted FAR resource: {far_name} in namespace {namespace}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to delete FAR resource {far_name}: {e}")
        return False


def uncordon_node(node_name: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Uncordon a node to make it schedulable again.

    Args:
        node_name: Node name
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    try:
        run_kubectl_command(['uncordon', node_name], logger=logger)
        if logger:
            logger.info(f"Uncordoned node: {node_name}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to uncordon node {node_name}: {e}")
        return False


def confirm_cleanup(num_namespaces: int, auto_yes: bool = False) -> bool:
    """
    Prompt user to confirm cleanup operation.

    Args:
        num_namespaces: Number of namespaces to be cleaned up
        auto_yes: If True, skip confirmation prompt

    Returns:
        True if user confirms, False otherwise
    """
    if auto_yes:
        return True

    if num_namespaces > 10:
        print(f"\n{Colors.WARNING}WARNING: You are about to clean up {num_namespaces} namespaces.{Colors.ENDC}")
        print(f"{Colors.WARNING}This will delete all VMs, DataVolumes, PVCs, and other resources.{Colors.ENDC}")
        response = input(f"\nAre you sure you want to continue? (yes/no): ").strip().lower()
        return response in ['yes', 'y']

    return True


def print_cleanup_summary(stats: dict, logger: Optional[logging.Logger] = None):
    """
    Print a summary of cleanup operations.

    Args:
        stats: Dictionary with cleanup statistics
        logger: Logger instance
    """
    message = f"""
{'=' * 80}
CLEANUP SUMMARY
{'=' * 80}
  Namespaces Processed:        {stats.get('namespaces_processed', 0)}
  Namespaces Deleted:          {stats.get('namespaces_deleted', 0)}
  VMs Deleted:                 {stats.get('total_vms_deleted', 0)}
  DataVolumes Deleted:         {stats.get('total_dvs_deleted', 0)}
  PVCs Deleted:                {stats.get('total_pvcs_deleted', 0)}
  VMIMs Deleted:               {stats.get('total_vmims_deleted', 0)}
  Errors:                      {stats.get('total_errors', 0)}
{'=' * 80}
"""

    if logger:
        logger.info(message)
    else:
        print(message)


def get_vm_status(vm_name: str, namespace: str, logger: Optional[logging.Logger] = None) -> Optional[str]:
    """
    Get the status of a VM.
    
    Args:
        vm_name: VM name
        namespace: Namespace
        logger: Logger instance
    
    Returns:
        VM status string or None if not found
    """
    try:
        returncode, stdout, _ = run_kubectl_command(
            ['get', 'vm', vm_name, '-n', namespace, '-o', 'jsonpath={.status.printableStatus}'],
            check=False,
            logger=logger
        )
        if returncode == 0 and stdout:
            return stdout.strip()
        return None
    except Exception as e:
        if logger:
            logger.debug(f"Error getting VM status for {vm_name} in {namespace}: {e}")
        return None


def get_vmi_ip(vmi_name: str, namespace: str, logger: Optional[logging.Logger] = None) -> Optional[str]:
    """
    Get the IP address of a VMI.
    
    Args:
        vmi_name: VMI name
        namespace: Namespace
        logger: Logger instance
    
    Returns:
        IP address or None if not available
    """
    try:
        returncode, stdout, _ = run_kubectl_command(
            ['get', 'vmi', vmi_name, '-n', namespace, '-o', 'jsonpath={.status.interfaces[0].ipAddress}'],
            check=False,
            logger=logger
        )
        if returncode == 0 and stdout and stdout != '<none>':
            return stdout.strip()
        return None
    except Exception as e:
        if logger:
            logger.debug(f"Error getting VMI IP for {vmi_name} in {namespace}: {e}")
        return None


def ping_vm(ip: str, ssh_pod: str, ssh_pod_ns: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Ping a VM from an SSH pod.

    Args:
        ip: VM IP address
        ssh_pod: SSH pod name
        ssh_pod_ns: SSH pod namespace
        logger: Logger instance

    Returns:
        True if ping successful, False otherwise
    """
    try:
        returncode, _, _ = run_kubectl_command(
            ['exec', '-n', ssh_pod_ns, ssh_pod, '--', 'ping', '-c', '1', '-W', '2', ip],
            check=False,
            capture_output=True,
            timeout=5,
            logger=logger
        )
        return returncode == 0
    except Exception as e:
        if logger:
            logger.debug(f"Ping failed for {ip}: {e}")
        return False


def stop_vm(vm_name: str, namespace: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Stop a VM by setting runStrategy to Halted.

    Args:
        vm_name: VM name
        namespace: Namespace
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    try:
        run_kubectl_command(
            ['patch', 'vm', vm_name, '-n', namespace, '--type', 'merge',
             '-p', '{"spec":{"runStrategy":"Halted"}}'],
            logger=logger
        )
        if logger:
            logger.info(f"Stopped VM {vm_name} in namespace {namespace}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to stop VM {vm_name} in {namespace}: {e}")
        return False


def start_vm(vm_name: str, namespace: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Start a VM by setting runStrategy to Always.

    Args:
        vm_name: VM name
        namespace: Namespace
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    try:
        run_kubectl_command(
            ['patch', 'vm', vm_name, '-n', namespace, '--type', 'merge',
             '-p', '{"spec":{"runStrategy":"Always"}}'],
            logger=logger
        )
        if logger:
            logger.info(f"Started VM {vm_name} in namespace {namespace}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to start VM {vm_name} in {namespace}: {e}")
        return False


def wait_for_vm_stopped(vm_name: str, namespace: str, timeout: int = 300,
                        logger: Optional[logging.Logger] = None) -> bool:
    """
    Wait for a VM to be fully stopped (VMI deleted).

    Args:
        vm_name: VM name
        namespace: Namespace
        timeout: Timeout in seconds
        logger: Logger instance

    Returns:
        True if VM stopped, False on timeout
    """
    import time
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            returncode, _, _ = run_kubectl_command(
                ['get', 'vmi', vm_name, '-n', namespace],
                check=False,
                logger=logger
            )
            if returncode != 0:  # VMI not found = VM is stopped
                if logger:
                    logger.debug(f"VM {vm_name} in {namespace} is stopped")
                return True
        except Exception:
            pass
        time.sleep(2)

    if logger:
        logger.warning(f"Timeout waiting for VM {vm_name} in {namespace} to stop")
    return False


def get_worker_nodes(logger: Optional[logging.Logger] = None) -> List[str]:
    """
    Get list of worker nodes in the cluster.

    Args:
        logger: Logger instance

    Returns:
        List of worker node names
    """
    try:
        returncode, stdout, stderr = run_kubectl_command(
            ['get', 'nodes', '-l', 'node-role.kubernetes.io/worker=',
             '-o', 'jsonpath={.items[*].metadata.name}'],
            logger=logger
        )

        if returncode == 0 and stdout:
            nodes = stdout.strip().split()
            if logger:
                logger.info(f"Found {len(nodes)} worker nodes: {', '.join(nodes)}")
            return nodes
        else:
            if logger:
                logger.warning("No worker nodes found, trying all nodes...")
            # Fallback: get all nodes
            returncode, stdout, stderr = run_kubectl_command(
                ['get', 'nodes', '-o', 'jsonpath={.items[*].metadata.name}'],
                logger=logger
            )
            if returncode == 0 and stdout:
                nodes = stdout.strip().split()
                if logger:
                    logger.info(f"Found {len(nodes)} nodes: {', '.join(nodes)}")
                return nodes

        return []
    except Exception as e:
        if logger:
            logger.error(f"Failed to get worker nodes: {e}")
        return []


def select_random_node(logger: Optional[logging.Logger] = None) -> Optional[str]:
    """
    Select a random worker node from the cluster.

    Args:
        logger: Logger instance

    Returns:
        Node name or None if no nodes found
    """
    import random

    nodes = get_worker_nodes(logger)
    if not nodes:
        if logger:
            logger.error("No worker nodes available")
        return None

    selected_node = random.choice(nodes)
    if logger:
        logger.info(f"Randomly selected node: {selected_node}")

    return selected_node


def get_vm_node(vm_name: str, namespace: str,
                logger: Optional[logging.Logger] = None) -> Optional[str]:
    """
    Get the node where a VM is currently running.

    Args:
        vm_name: Name of the VM
        namespace: Namespace of the VM
        logger: Logger instance

    Returns:
        Node name where VM is running, or None if not found
    """
    try:
        args = ['get', 'vmi', vm_name, '-n', namespace, '-o', "jsonpath='{.status.nodeName}'"]
        returncode, stdout, stderr = run_kubectl_command(args, check=False, logger=logger)

        if returncode == 0 and stdout and stdout.strip():
            node_name = stdout.strip().strip("'\"")
            if logger:
                logger.debug(f"VM {vm_name} is running on node: {node_name}")
            return node_name
        else:
            if logger:
                logger.debug(f"Could not determine node for VM {vm_name} in namespace {namespace}")
            return None

    except Exception as e:
        if logger:
            logger.error(f"Failed to get node for VM {vm_name}: {e}")
        return None


def remove_node_selector_from_vm(vm_name: str, namespace: str,
                                 logger: Optional[logging.Logger] = None) -> bool:
    """
    Remove nodeSelector from a VM to allow live migration.

    Args:
        vm_name: Name of the VM
        namespace: Namespace of the VM
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    try:
        if logger:
            logger.debug(f"[{namespace}] Removing nodeSelector from VM {vm_name}")

        # Remove nodeSelector from VM spec using kubectl patch
        patch = {
            "spec": {
                "template": {
                    "spec": {
                        "nodeSelector": None
                    }
                }
            }
        }

        patch_json = json.dumps(patch)

        args = ['patch', 'vm', vm_name, '-n', namespace,
                '--type', 'merge', '-p', patch_json]
        returncode, stdout, stderr = run_kubectl_command(args, check=False, logger=logger)

        if returncode != 0:
            if logger:
                logger.warning(f"[{namespace}] Failed to remove nodeSelector from VM: {stderr}")
            return False

        if logger:
            logger.debug(f"[{namespace}] Successfully removed nodeSelector from VM")

        return True

    except Exception as e:
        if logger:
            logger.error(f"[{namespace}] Exception removing nodeSelector from VM: {e}")
        return False


def remove_node_selector_from_vmi(vm_name: str, namespace: str,
                                   logger: Optional[logging.Logger] = None) -> bool:
    """
    Remove nodeSelector from a VMI to allow live migration.

    Args:
        vm_name: Name of the VMI
        namespace: Namespace of the VMI
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    try:
        if logger:
            logger.debug(f"[{namespace}] Removing nodeSelector from VMI {vm_name}")

        # Remove nodeSelector from VMI spec using kubectl patch
        patch = {
            "spec": {
                "nodeSelector": None
            }
        }

        patch_json = json.dumps(patch)

        args = ['patch', 'vmi', vm_name, '-n', namespace,
                '--type', 'merge', '-p', patch_json]
        returncode, stdout, stderr = run_kubectl_command(args, check=False, logger=logger)

        if returncode != 0:
            if logger:
                logger.warning(f"[{namespace}] Failed to remove nodeSelector from VMI: {stderr}")
            return False

        if logger:
            logger.debug(f"[{namespace}] Successfully removed nodeSelector from VMI")

        return True

    except Exception as e:
        if logger:
            logger.error(f"[{namespace}] Exception removing nodeSelector from VMI: {e}")
        return False


def remove_node_selectors(vm_name: str, namespace: str,
                          logger: Optional[logging.Logger] = None) -> bool:
    """
    Remove nodeSelector from both VM and VMI to allow live migration.

    Args:
        vm_name: Name of the VM/VMI
        namespace: Namespace
        logger: Logger instance

    Returns:
        True if both successful, False otherwise
    """
    vm_success = remove_node_selector_from_vm(vm_name, namespace, logger)
    vmi_success = remove_node_selector_from_vmi(vm_name, namespace, logger)

    return vm_success and vmi_success


def migrate_vm(vm_name: str, namespace: str, target_node: Optional[str] = None,
               logger: Optional[logging.Logger] = None) -> bool:
    """
    Trigger live migration of a VM.

    Args:
        vm_name: Name of the VM to migrate
        namespace: Namespace of the VM
        target_node: Target node name (optional, let Kubernetes choose if None)
        logger: Logger instance

    Returns:
        True if migration was triggered successfully, False otherwise
    """
    try:
        if target_node:
            # Create VirtualMachineInstanceMigration with target node
            migration_yaml = f"""
apiVersion: kubevirt.io/v1
kind: VirtualMachineInstanceMigration
metadata:
  name: {vm_name}-migration
  namespace: {namespace}
spec:
  vmiName: {vm_name}
"""
            # Note: KubeVirt doesn't support direct target node selection in migration
            # The scheduler will choose the target node based on available resources
            # We'll use nodeSelector on the VM spec if target node is needed
            if logger:
                logger.warning(f"Target node specified ({target_node}), but KubeVirt migration uses scheduler")

        # Trigger migration using virtctl or kubectl
        cmd = f"kubectl create -f - <<EOF\napiVersion: kubevirt.io/v1\nkind: VirtualMachineInstanceMigration\nmetadata:\n  name: migration-{vm_name}-$(date +%s)\n  namespace: {namespace}\nspec:\n  vmiName: {vm_name}\nEOF"

        # Simpler approach: use kubectl patch to trigger migration
        cmd = f"kubectl patch vmi {vm_name} -n {namespace} --type merge -p '{{\"spec\":{{\"evictionStrategy\":\"LiveMigrate\"}}}}'"

        # Actually, the best way is to create a VirtualMachineInstanceMigration object
        import subprocess
        migration_name = f"migration-{vm_name}"
        migration_yaml = f"""apiVersion: kubevirt.io/v1
kind: VirtualMachineInstanceMigration
metadata:
  name: {migration_name}
  namespace: {namespace}
spec:
  vmiName: {vm_name}
"""

        # Delete any existing migration object first
        subprocess.run(
            f"kubectl delete virtualmachineinstancemigration {migration_name} -n {namespace} 2>/dev/null || true",
            shell=True, capture_output=True
        )

        # Create migration object
        result = subprocess.run(
            f"kubectl create -f -",
            shell=True, input=migration_yaml.encode(), capture_output=True, text=False
        )

        if result.returncode == 0:
            if logger:
                logger.info(f"[{namespace}] Migration triggered for VM {vm_name}")
            return True
        else:
            if logger:
                logger.error(f"[{namespace}] Failed to trigger migration for VM {vm_name}: {result.stderr.decode()}")
            return False

    except Exception as e:
        if logger:
            logger.error(f"Failed to trigger migration for VM {vm_name}: {e}")
        return False


def get_migration_status(vm_name: str, namespace: str,
                        logger: Optional[logging.Logger] = None) -> Optional[str]:
    """
    Get the current migration status of a VM.

    Args:
        vm_name: Name of the VM
        namespace: Namespace of the VM
        logger: Logger instance

    Returns:
        Migration status string, or None if no migration in progress
    """
    try:
        # Check VMI migration state
        cmd = f"kubectl get vmi {vm_name} -n {namespace} -o jsonpath='{{.status.migrationState.status}}'"
        result = run_kubectl_command(cmd, logger)

        if result and result.strip():
            status = result.strip().strip("'\"")
            return status

        return None

    except Exception as e:
        if logger:
            logger.debug(f"No migration status for VM {vm_name}: {e}")
        return None


def get_vmim_timestamps(vm_name: str, namespace: str,
                       logger: Optional[logging.Logger] = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Get migration timestamps from VirtualMachineInstanceMigration object.

    Args:
        vm_name: Name of the VM
        namespace: Namespace
        logger: Logger instance

    Returns:
        Tuple of (startTimestamp, endTimestamp, phase)
    """
    try:
        migration_name = f"migration-{vm_name}"

        # Get VMIM object
        args = ['get', 'virtualmachineinstancemigration', migration_name, '-n', namespace,
                '-o', 'json']
        returncode, stdout, stderr = run_kubectl_command(args, check=False, logger=logger)

        if returncode != 0:
            return None, None, None

        import json
        vmim = json.loads(stdout)

        # Extract timestamps from status.migrationState
        migration_state = vmim.get('status', {}).get('migrationState', {})
        start_ts = migration_state.get('startTimestamp')
        end_ts = migration_state.get('endTimestamp')
        phase = vmim.get('status', {}).get('phase')

        return start_ts, end_ts, phase

    except Exception as e:
        if logger:
            logger.debug(f"Failed to get VMIM timestamps for {vm_name}: {e}")
        return None, None, None


def calculate_vmim_duration(start_timestamp: str, end_timestamp: str) -> Optional[float]:
    """
    Calculate duration from VMIM timestamps.

    Args:
        start_timestamp: ISO 8601 timestamp string
        end_timestamp: ISO 8601 timestamp string

    Returns:
        Duration in seconds, or None if calculation fails
    """
    try:
        from datetime import datetime

        # Parse ISO 8601 timestamps
        start = datetime.fromisoformat(start_timestamp.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_timestamp.replace('Z', '+00:00'))

        duration = (end - start).total_seconds()
        return duration

    except Exception:
        return None


def wait_for_migration_complete(vm_name: str, namespace: str, timeout: int = 600,
                                logger: Optional[logging.Logger] = None) -> Tuple[bool, float, Optional[str], Optional[float]]:
    """
    Wait for VM migration to complete.

    Args:
        vm_name: Name of the VM
        namespace: Namespace of the VM
        timeout: Maximum time to wait in seconds
        logger: Logger instance

    Returns:
        Tuple of (success, observed_duration, target_node, vmim_duration)
        - observed_duration: Time measured by polling node changes
        - vmim_duration: Time from VMIM timestamps (more accurate)
    """
    start_time = time.time()
    original_node = get_vm_node(vm_name, namespace, logger)

    if logger:
        logger.info(f"[{namespace}] Waiting for migration of {vm_name} from node {original_node}")

    while time.time() - start_time < timeout:
        # Check if VM has moved to a different node
        current_node = get_vm_node(vm_name, namespace, logger)

        if current_node and current_node != original_node:
            # VM has migrated to a new node
            observed_duration = time.time() - start_time

            # Get VMIM timestamps for accurate measurement
            start_ts, end_ts, phase = get_vmim_timestamps(vm_name, namespace, logger)
            vmim_duration = None

            if start_ts and end_ts:
                vmim_duration = calculate_vmim_duration(start_ts, end_ts)
                if logger and vmim_duration:
                    logger.info(f"[{namespace}] Migration complete: {vm_name} moved from {original_node} to {current_node}")
                    logger.info(f"[{namespace}]   Observed time: {observed_duration:.2f}s | VMIM time: {vmim_duration:.2f}s")
            else:
                if logger:
                    logger.info(f"[{namespace}] Migration complete: {vm_name} moved from {original_node} to {current_node} in {observed_duration:.2f}s")

            return True, observed_duration, current_node, vmim_duration

        # Check migration status
        status = get_migration_status(vm_name, namespace, logger)
        if status == "Failed":
            if logger:
                logger.error(f"[{namespace}] Migration failed for VM {vm_name}")
            return False, time.time() - start_time, None, None

        time.sleep(2)

    # Timeout
    if logger:
        logger.error(f"[{namespace}] Migration timeout for VM {vm_name} after {timeout}s")
    return False, timeout, None, None


def get_available_nodes(exclude_nodes: List[str] = None,
                       logger: Optional[logging.Logger] = None) -> List[str]:
    """
    Get list of available worker nodes, optionally excluding specific nodes.

    Args:
        exclude_nodes: List of node names to exclude
        logger: Logger instance

    Returns:
        List of available node names
    """
    if exclude_nodes is None:
        exclude_nodes = []

    all_nodes = get_worker_nodes(logger)
    available_nodes = [node for node in all_nodes if node not in exclude_nodes]

    if logger:
        logger.debug(f"Available nodes (excluding {exclude_nodes}): {available_nodes}")

    return available_nodes


def find_busiest_node(namespaces: List[str], vm_name: str,
                     logger: Optional[logging.Logger] = None) -> Optional[str]:
    """
    Find the node with the most VMs from the given namespaces.

    Args:
        namespaces: List of namespace names to check
        vm_name: VM name to look for
        logger: Logger instance

    Returns:
        Node name with the most VMs, or None if no VMs found
    """
    node_counts = {}

    if logger:
        logger.info(f"Scanning {len(namespaces)} namespaces to find busiest node...")

    for ns in namespaces:
        node = get_vm_node(vm_name, ns, logger)
        if node:
            node_counts[node] = node_counts.get(node, 0) + 1

    if not node_counts:
        if logger:
            logger.warning("No VMs found on any node")
        return None

    busiest_node = max(node_counts, key=node_counts.get)

    if logger:
        logger.info(f"\nVM distribution across nodes:")
        for node, count in sorted(node_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {node}: {count} VMs")
        logger.info(f"\nBusiest node: {busiest_node} with {node_counts[busiest_node]} VMs")

    return busiest_node


def get_vms_on_node(namespaces: List[str], vm_name: str, target_node: str,
                   logger: Optional[logging.Logger] = None) -> List[str]:
    """
    Get list of namespaces where VMs are running on a specific node.

    Args:
        namespaces: List of namespace names to check
        vm_name: VM name to look for
        target_node: Node name to filter by
        logger: Logger instance

    Returns:
        List of namespace names where VMs are on the target node
    """
    vms_on_node = []

    if logger:
        logger.info(f"Scanning {len(namespaces)} namespaces for VMs on {target_node}...")

    for ns in namespaces:
        current_node = get_vm_node(vm_name, ns, logger)
        if current_node == target_node:
            vms_on_node.append(ns)
            if logger:
                logger.debug(f"[{ns}] VM is on {target_node}")

    if logger:
        logger.info(f"Found {len(vms_on_node)} VMs on {target_node}")

    return vms_on_node


def add_node_selector_to_vm_yaml(yaml_file: str, node_name: str,
                                  logger: Optional[logging.Logger] = None) -> str:
    """
    Add nodeSelector to a VM YAML file and return modified content.

    Args:
        yaml_file: Path to VM YAML file
        node_name: Node name to select
        logger: Logger instance

    Returns:
        Modified YAML content as string
    """
    try:
        with open(yaml_file, 'r') as f:
            content = f.read()

        # Check if nodeSelector already exists
        if 'nodeSelector:' in content:
            if logger:
                logger.debug(f"nodeSelector already exists in {yaml_file}, will be replaced")
            # Remove existing nodeSelector section
            import re
            content = re.sub(r'\s+nodeSelector:.*?(?=\n\s{0,6}\w|\Z)', '', content, flags=re.DOTALL)

        # Parse YAML to find the right location
        # We need to add nodeSelector under spec.template.spec
        # It should be at the same level as domain, networks, volumes, tolerations

        lines = content.split('\n')
        modified_lines = []
        added = False
        in_template = False
        in_template_spec = False
        template_spec_indent = 0

        for i, line in enumerate(lines):
            # Track if we're in the template section
            if line.strip().startswith('template:'):
                in_template = True
                modified_lines.append(line)
                continue

            # Track if we're in template.spec
            if in_template and line.strip().startswith('spec:') and not in_template_spec:
                in_template_spec = True
                template_spec_indent = len(line) - len(line.lstrip())
                modified_lines.append(line)

                # Add nodeSelector right after spec: line
                node_selector_lines = [
                    ' ' * (template_spec_indent + 2) + 'nodeSelector:',
                    ' ' * (template_spec_indent + 4) + f'kubernetes.io/hostname: {node_name}'
                ]
                modified_lines.extend(node_selector_lines)
                added = True
                continue

            # Check if we've left the template.spec section
            if in_template_spec and line.strip() and not line.startswith(' ' * (template_spec_indent + 1)):
                in_template_spec = False
                in_template = False

            modified_lines.append(line)

        if not added:
            if logger:
                logger.error(f"Could not find template.spec in {yaml_file}, nodeSelector not added")
            return content

        result = '\n'.join(modified_lines)

        if logger:
            logger.debug(f"Successfully added nodeSelector for node {node_name}")

        return result

    except Exception as e:
        if logger:
            logger.error(f"Failed to add nodeSelector to {yaml_file}: {e}")
        return None


def print_summary_table(
    results: List[Tuple],
    title: str = "Performance Test Summary",
    skip_clone: bool = False,
    logger=None
):
    """
    Print or log a formatted summary table of test results.

    Args:
        results: List of tuples containing test results
        title: Table title
        skip_clone: If True, omit clone duration column and statistics
        logger: Optional logger instance. If provided, logs instead of printing.
    """
    def output(msg=""):
        if logger:
            logger.info(msg)
        else:
            print(msg)

    output(f"\n{Colors.BOLD}{title}{Colors.ENDC}")
    output("=" * 95)

    if skip_clone:
        header = f"{'Namespace':<30}{'Running(s)':<20}{'Ping(s)':<20}{'Status':<20}"
    else:
        header = f"{'Namespace':<30}{'Running(s)':<15}{'Ping(s)':<15}{'Clone(s)':<15}{'Status':<20}"

    output(header)
    output("-" * 95)

    successful = 0
    failed = 0
    running_times = []
    ping_times = []
    clone_times = []

    for result in sorted(results, key=lambda x: x[0]):
        ns, run_t, ping_t, clone_t, ok = result[:5]

        run_str = f"{run_t:.2f}" if run_t is not None else '-'
        ping_str = f"{ping_t:.2f}" if ping_t is not None and ok else 'Timeout'
        clone_str = f"{clone_t:.2f}" if clone_t is not None else '-'
        status = f"{Colors.OKGREEN}Success{Colors.ENDC}" if ok else f"{Colors.FAIL}Failed{Colors.ENDC}"

        if skip_clone:
            line = f"{ns:<30}{run_str:<20}{ping_str:<20}{status:<20}"
        else:
            line = f"{ns:<30}{run_str:<15}{ping_str:<15}{clone_str:<15}{status:<20}"

        output(line)

        if ok:
            successful += 1
            if run_t is not None:
                running_times.append(run_t)
            if ping_t is not None:
                ping_times.append(ping_t)
            if not skip_clone and clone_t is not None:
                clone_times.append(clone_t)
        else:
            failed += 1

    output("=" * 95)
    output(f"\n{Colors.BOLD}Statistics:{Colors.ENDC}")
    output(f"  Total VMs:              {successful + failed}")
    output(f"  Successful:             {Colors.OKGREEN}{successful}{Colors.ENDC}")
    output(f"  Failed:                 {Colors.FAIL}{failed}{Colors.ENDC}")

    if running_times:
        output(f"  Avg Time to Running:    {sum(running_times) / len(running_times):.2f}s")
        output(f"  Max Time to Running:    {max(running_times):.2f}s")
        output(f"  Min Time to Running:    {min(running_times):.2f}s")

    if ping_times:
        output(f"  Avg Time to Ping:       {sum(ping_times) / len(ping_times):.2f}s")
        output(f"  Max Time to Ping:       {max(ping_times):.2f}s")
        output(f"  Min Time to Ping:       {min(ping_times):.2f}s")

    if not skip_clone and clone_times:
        output(f"  Avg Clone Duration:     {sum(clone_times) / len(clone_times):.2f}s")
        output(f"  Max Clone Duration:     {max(clone_times):.2f}s")
        output(f"  Min Clone Duration:     {min(clone_times):.2f}s")

    output("=" * 95)


def save_results(args, results, base_dir="results", prefix="vm_creation_results",
                 logger=None, skip_clone=False, total_time=None):
    """
    Save test results into the specified results folder (or create a new one), including summary statistics.

    Args:
        args: Parsed CLI arguments (used for naming output folders)
        results: List of tuples (namespace, running_time, ping_time, clone_duration, success)
        base_dir: Base directory to store results. If None, a new timestamped one is created.
        prefix: File prefix for generated files
        logger: Logger instance (optional)
        skip_clone: If True, omit clone duration metrics from saved results and summaries
        total_time: Total time taken for the test (VM creation or boot storm)

    Returns:
        Tuple of (json_path, csv_path, summary_json_path, summary_csv_path, output_dir)
    """
    # --- Prepare base output directory ---
    if base_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = f"{args.namespace_prefix}_{args.start}-{args.end}"
        output_dir = os.path.join("results", f"{timestamp}_{suffix}")
        os.makedirs(output_dir, exist_ok=True)
        if logger:
            logger.info(f"Created new results directory: {output_dir}")
    else:
        output_dir = base_dir
        os.makedirs(output_dir, exist_ok=True)

    # File paths
    json_path = os.path.join(output_dir, f"{prefix}.json")
    csv_path = os.path.join(output_dir, f"{prefix}.csv")
    summary_json_path = os.path.join(output_dir, f"summary_{prefix}.json")
    summary_csv_path = os.path.join(output_dir, f"summary_{prefix}.csv")

    # Convert tuples to dicts
    data = []
    for ns, run_t, ping_t, clone_t, success in results:
        entry = {
            "namespace": ns,
            "running_time_sec": round(run_t, 2) if run_t is not None else None,
            "ping_time_sec": round(ping_t, 2) if ping_t is not None else None,
            "success": bool(success),
        }
        if not skip_clone:
            entry["clone_duration_sec"] = round(clone_t, 2) if clone_t is not None else None
        data.append(entry)

    # Save detailed JSON
    with open(json_path, "w") as jf:
        json.dump(data, jf, indent=4)
    if logger:
        logger.info(f"Saved detailed JSON results to {json_path}")

    # Save detailed CSV
    with open(csv_path, "w", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    if logger:
        logger.info(f"Saved detailed CSV results to {csv_path}")

    # --- Compute summary statistics ---
    total = len(results)
    successful = sum(1 for r in results if r[4])
    failed = total - successful

    running_times = [r[1] for r in results if r[1] is not None]
    ping_times = [r[2] for r in results if r[2] is not None]
    clone_times = [r[3] for r in results if r[3] is not None] if not skip_clone else []

    def calc_stats(name, values):
        return {
            "metric": name,
            "avg": round(sum(values) / len(values), 2) if values else None,
            "max": round(max(values), 2) if values else None,
            "min": round(min(values), 2) if values else None,
            "count": len(values),
        }

    metrics = [
        calc_stats("running_time_sec", running_times),
        calc_stats("ping_time_sec", ping_times),
    ]
    if not skip_clone:
        metrics.append(calc_stats("clone_duration_sec", clone_times))

    # --- Add total test duration ---
    summary = {
        "total_vms": total,
        "successful": successful,
        "failed": failed,
        "total_test_duration_sec": round(total_time, 2) if total_time else None,
        "metrics": metrics,
    }

    # --- Save summary JSON ---
    with open(summary_json_path, "w") as sf:
        json.dump(summary, sf, indent=4)
    if logger:
        logger.info(f"Saved summary JSON to {summary_json_path}")

    # --- Save summary CSV ---
    with open(summary_csv_path, "w", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=["metric", "avg", "max", "min", "count"])
        writer.writeheader()
        for m in summary["metrics"]:
            writer.writerow(m)
    if logger:
        logger.info(f"Saved summary CSV to {summary_csv_path}")

    return json_path, csv_path, summary_json_path, summary_csv_path, output_dir


def save_migration_results(args, results, base_dir="results", logger=None, total_time=None):
    """
    Save VM migration results (per-VM data and summary) into JSON and CSV files.

    Args:
        args: Parsed CLI args (used for folder naming)
        results: List of tuples (namespace, success, observed_duration, source, target, vmim_duration)
        base_dir: Parent folder
        logger: Logger instance
        total_time: Total wall-clock migration duration (sec)
    """



    # --- Prepare base output directory ---
    if base_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = f"{args.namespace_prefix}_{args.start}-{args.end}"
        output_dir = os.path.join(base_dir, f"{timestamp}_live_migration_{suffix}")
        os.makedirs(output_dir, exist_ok=True)
        if logger:
            logger.info(f"Created new results directory: {output_dir}")
    else:
        output_dir = base_dir
        os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "migration_results.json")
    csv_path = os.path.join(output_dir, "migration_results.csv")
    summary_json_path = os.path.join(output_dir, "summary_migration_results.json")
    summary_csv_path = os.path.join(output_dir, "summary_migration_results.csv")

    # --- Detailed per-VM results ---
    data = []
    for ns, success, observed, source, target, vmim in results:
        entry = {
            "namespace": ns,
            "source_node": source or "Unknown",
            "target_node": target or "Unknown",
            "observed_time_sec": round(observed, 2) if observed else None,
            "vmim_time_sec": round(vmim, 2) if vmim else None,
            "status": "Success" if success else "Failed",
        }
        data.append(entry)

    with open(json_path, "w") as jf:
        json.dump(data, jf, indent=4)
    with open(csv_path, "w", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    if logger:
        logger.info(f"Saved detailed migration results to {json_path}")

    # --- Summary statistics ---
    total = len(results)
    successful = sum(1 for r in results if r[1])
    failed = total - successful

    observed_times = [r[2] for r in results if r[1] and r[2]]
    vmim_times = [r[5] for r in results if r[1] and r[5]]

    summary = {
        "total_vms": total,
        "successful": successful,
        "failed": failed,
        "total_migration_duration_sec": round(total_time, 2) if total_time else None,
        "metrics": [
            {
                "metric": "observed_time_sec",
                "avg": round(sum(observed_times) / len(observed_times), 2) if observed_times else None,
                "min": round(min(observed_times), 2) if observed_times else None,
                "max": round(max(observed_times), 2) if observed_times else None,
                "count": len(observed_times),
            },
            {
                "metric": "vmim_time_sec",
                "avg": round(sum(vmim_times) / len(vmim_times), 2) if vmim_times else None,
                "min": round(min(vmim_times), 2) if vmim_times else None,
                "max": round(max(vmim_times), 2) if vmim_times else None,
                "count": len(vmim_times),
            },
            {
                "metric": "difference_observed_vmim_sec",
                "avg": round((sum(observed_times) / len(observed_times)) - (sum(vmim_times) / len(vmim_times)), 2)
                if observed_times and vmim_times else None,
                "note": "Difference includes polling overhead (~2s) and status update delays",
            },
        ],
    }

    with open(summary_json_path, "w") as sf:
        json.dump(summary, sf, indent=4)
    with open(summary_csv_path, "w", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=["metric", "avg", "min", "max", "count"])
        writer.writeheader()
        for m in summary["metrics"]:
            if "avg" in m:
                writer.writerow({
                    "metric": m["metric"],
                    "avg": m.get("avg"),
                    "min": m.get("min"),
                    "max": m.get("max"),
                    "count": m.get("count"),
                })

    if logger:
        logger.info(f"Saved summary migration results to {summary_json_path}")

    return json_path, csv_path, summary_json_path, summary_csv_path, output_dir

def validate_prerequisites(ssh_pod: str, ssh_pod_ns: str, logger: logging.Logger) -> bool:
    """
    Validate that prerequisites are met before running tests.

    Args:
        ssh_pod: SSH pod name
        ssh_pod_ns: SSH pod namespace
        logger: Logger instance

    Returns:
        True if all prerequisites are met, False otherwise
    """
    logger.info("Validating prerequisites...")

    # Check kubectl connectivity
    try:
        run_kubectl_command(['cluster-info'], logger=logger)
        logger.info("[OK] kubectl connectivity verified")
    except Exception as e:
        logger.error(f"[FAIL] kubectl connectivity failed: {e}")
        return False

    # Check SSH pod exists
    try:
        returncode, _, _ = run_kubectl_command(
            ['get', 'pod', ssh_pod, '-n', ssh_pod_ns],
            check=False,
            logger=logger
        )
        if returncode == 0:
            logger.info(f"[OK] SSH pod {ssh_pod} found in namespace {ssh_pod_ns}")
        else:
            logger.warning(f"[WARN] SSH pod {ssh_pod} not found in namespace {ssh_pod_ns}")
            logger.warning("  Ping tests will fail. Create an SSH pod or skip ping tests.")
    except Exception as e:
        logger.warning(f"[WARN] Error checking SSH pod: {e}")

    return True

def get_px_version_from_cluster(logger=None, namespace="portworx") -> str:
    """
    Detect Portworx version from the running StorageCluster (stc) in namespace 'portworx'.
    Returns the version string or 'unknown' if not found.
    """
    try:
        cmd = [
            "kubectl", "get", "stc", "-n", f"{namespace}",
            "-o", "jsonpath={.items[0].status.version}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        version = result.stdout.strip()
        if not version:
            # Try alternate spec path if status not found
            cmd_alt = [
                "kubectl", "get", "stc", "-n", f"{namespace}",
                "-o", "jsonpath={.items[0].spec.version}"
            ]
            result = subprocess.run(cmd_alt, capture_output=True, text=True, timeout=10)
            version = result.stdout.strip()

        if version:
            if logger:
                logger.info(f"Detected Portworx version from cluster: {version}")
            return version
        else:
            if logger:
                logger.warning("Unable to detect Portworx version — defaulting to 'unknown'")
            return "unknown"

    except Exception as e:
        if logger:
            logger.warning(f"Error detecting Portworx version: {e}")
        return "unknown"

def restart_vm(vm_name: str, namespace: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Restart a VM by stopping and starting it.

    Args:
        vm_name: VM name
        namespace: Namespace name
        logger: Logger instance

    Returns:
        True if restart successful, False otherwise
    """
    try:
        if logger:
            logger.info(f"[{namespace}] Restarting VM {vm_name}")

        # Stop the VM
        if not stop_vm(vm_name, namespace, logger):
            return False

        # Wait for VM to stop
        if not wait_for_vm_stopped(vm_name, namespace, timeout=300, logger=logger):
            if logger:
                logger.error(f"[{namespace}] VM {vm_name} did not stop in time")
            return False

        # Start the VM
        if not start_vm(vm_name, namespace, logger):
            return False

        if logger:
            logger.info(f"[{namespace}] VM {vm_name} restarted successfully")
        return True

    except Exception as e:
        if logger:
            logger.error(f"[{namespace}] Failed to restart VM {vm_name}: {e}")
        return False


def resize_pvc(pvc_name: str, namespace: str, new_size: str,
               logger: Optional[logging.Logger] = None) -> bool:
    """
    Resize a PersistentVolumeClaim.

    Args:
        pvc_name: PVC name
        namespace: Namespace name
        new_size: New size (e.g., "40Gi")
        logger: Logger instance

    Returns:
        True if resize successful, False otherwise
    """
    try:
        if logger:
            logger.info(f"[{namespace}] Resizing PVC {pvc_name} to {new_size}")

        # Patch the PVC with new size
        patch = json.dumps({
            "spec": {
                "resources": {
                    "requests": {
                        "storage": new_size
                    }
                }
            }
        })

        returncode, stdout, stderr = run_kubectl_command(
            ['patch', 'pvc', pvc_name, '-n', namespace, '--type=merge', '-p', patch],
            check=False,
            logger=logger
        )

        if returncode != 0:
            if logger:
                logger.error(f"[{namespace}] Failed to resize PVC {pvc_name}: {stderr}")
            return False

        if logger:
            logger.info(f"[{namespace}] PVC {pvc_name} resize initiated to {new_size}")
        return True

    except Exception as e:
        if logger:
            logger.error(f"[{namespace}] Failed to resize PVC {pvc_name}: {e}")
        return False


def wait_for_pvc_resize(pvc_name: str, namespace: str, expected_size: str,
                        timeout: int = 600, poll_interval: int = 5,
                        logger: Optional[logging.Logger] = None) -> bool:
    """
    Wait for PVC resize to complete.

    Args:
        pvc_name: PVC name
        namespace: Namespace name
        expected_size: Expected size after resize (e.g., "40Gi")
        timeout: Timeout in seconds
        poll_interval: Polling interval in seconds
        logger: Logger instance

    Returns:
        True if resize completed, False on timeout
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            returncode, stdout, stderr = run_kubectl_command(
                ['get', 'pvc', pvc_name, '-n', namespace, '-o', 'json'],
                check=False,
                logger=logger
            )

            if returncode == 0:
                pvc_data = json.loads(stdout)
                status = pvc_data.get('status', {})
                capacity = status.get('capacity', {}).get('storage', '')

                # Check if resize is complete
                if capacity == expected_size:
                    if logger:
                        logger.info(f"[{namespace}] PVC {pvc_name} resized to {capacity}")
                    return True

                # Check for resize conditions
                conditions = status.get('conditions', [])
                for condition in conditions:
                    if condition.get('type') == 'Resizing' and condition.get('status') == 'True':
                        if logger:
                            logger.debug(f"[{namespace}] PVC {pvc_name} is resizing...")
                    elif condition.get('type') == 'FileSystemResizePending':
                        if logger:
                            logger.debug(f"[{namespace}] PVC {pvc_name} filesystem resize pending...")

            time.sleep(poll_interval)

        except Exception as e:
            if logger:
                logger.error(f"[{namespace}] Error checking PVC resize status: {e}")
            time.sleep(poll_interval)

    if logger:
        logger.error(f"[{namespace}] Timeout waiting for PVC {pvc_name} resize")
    return False


def create_vm_snapshot(vm_name: str, snapshot_name: str, namespace: str,
                       logger: Optional[logging.Logger] = None) -> bool:
    """
    Create a VirtualMachineSnapshot.

    Args:
        vm_name: VM name to snapshot
        snapshot_name: Snapshot name
        namespace: Namespace name
        logger: Logger instance

    Returns:
        True if snapshot created successfully, False otherwise
    """
    try:
        if logger:
            logger.info(f"[{namespace}] Creating snapshot {snapshot_name} for VM {vm_name}")

        # Create snapshot YAML
        snapshot_yaml = f"""apiVersion: snapshot.kubevirt.io/v1alpha1
kind: VirtualMachineSnapshot
metadata:
  name: {snapshot_name}
  namespace: {namespace}
spec:
  source:
    apiGroup: kubevirt.io
    kind: VirtualMachine
    name: {vm_name}
"""

        # Apply snapshot
        process = subprocess.Popen(
            ['kubectl', 'apply', '-f', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=snapshot_yaml)

        if process.returncode != 0:
            if logger:
                logger.error(f"[{namespace}] Failed to create snapshot: {stderr}")
            return False

        if logger:
            logger.info(f"[{namespace}] Snapshot {snapshot_name} created")
        return True

    except Exception as e:
        if logger:
            logger.error(f"[{namespace}] Failed to create snapshot {snapshot_name}: {e}")
        return False


def wait_for_snapshot_ready(snapshot_name: str, namespace: str, timeout: int = 600,
                            poll_interval: int = 5, logger: Optional[logging.Logger] = None) -> bool:
    """
    Wait for VirtualMachineSnapshot to be ready.

    Args:
        snapshot_name: Snapshot name
        namespace: Namespace name
        timeout: Timeout in seconds
        poll_interval: Polling interval in seconds
        logger: Logger instance

    Returns:
        True if snapshot is ready, False on timeout
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            returncode, stdout, stderr = run_kubectl_command(
                ['get', 'vmsnapshot', snapshot_name, '-n', namespace, '-o', 'json'],
                check=False,
                logger=logger
            )

            if returncode == 0:
                snapshot_data = json.loads(stdout)
                status = snapshot_data.get('status', {})
                ready_to_use = status.get('readyToUse', False)

                if ready_to_use:
                    if logger:
                        logger.info(f"[{namespace}] Snapshot {snapshot_name} is ready")
                    return True

                # Check for errors
                conditions = status.get('conditions', [])
                for condition in conditions:
                    if condition.get('type') == 'Ready' and condition.get('status') == 'False':
                        reason = condition.get('reason', 'Unknown')
                        message = condition.get('message', '')
                        if logger:
                            logger.warning(f"[{namespace}] Snapshot not ready: {reason} - {message}")

            time.sleep(poll_interval)

        except Exception as e:
            if logger:
                logger.error(f"[{namespace}] Error checking snapshot status: {e}")
            time.sleep(poll_interval)

    if logger:
        logger.error(f"[{namespace}] Timeout waiting for snapshot {snapshot_name}")
    return False


def delete_vm_snapshot(snapshot_name: str, namespace: str,
                       logger: Optional[logging.Logger] = None) -> bool:
    """
    Delete a VirtualMachineSnapshot.

    Args:
        snapshot_name: Snapshot name
        namespace: Namespace name
        logger: Logger instance

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        returncode, stdout, stderr = run_kubectl_command(
            ['delete', 'vmsnapshot', snapshot_name, '-n', namespace],
            check=False,
            logger=logger
        )

        if returncode == 0:
            if logger:
                logger.info(f"[{namespace}] Deleted snapshot {snapshot_name}")
            return True
        else:
            if logger:
                logger.error(f"[{namespace}] Failed to delete snapshot: {stderr}")
            return False

    except Exception as e:
        if logger:
            logger.error(f"[{namespace}] Failed to delete snapshot {snapshot_name}: {e}")
        return False


def get_pvc_size(pvc_name: str, namespace: str, logger: Optional[logging.Logger] = None) -> Optional[str]:
    """
    Get current size of a PVC.

    Args:
        pvc_name: PVC name
        namespace: Namespace name
        logger: Logger instance

    Returns:
        PVC size as string (e.g., "30Gi") or None on error
    """
    try:
        returncode, stdout, stderr = run_kubectl_command(
            ['get', 'pvc', pvc_name, '-n', namespace, '-o', 'json'],
            check=False,
            logger=logger
        )

        if returncode == 0:
            pvc_data = json.loads(stdout)
            size = pvc_data.get('status', {}).get('capacity', {}).get('storage', '')
            return size if size else None

        return None

    except Exception as e:
        if logger:
            logger.error(f"[{namespace}] Failed to get PVC size: {e}")
        return None


def get_vm_volume_names(vm_name: str, namespace: str,
                        logger: Optional[logging.Logger] = None) -> List[str]:
    """
    Get list of PVC names used by a VM.

    Args:
        vm_name: VM name
        namespace: Namespace name
        logger: Logger instance

    Returns:
        List of PVC names
    """
    try:
        returncode, stdout, stderr = run_kubectl_command(
            ['get', 'vm', vm_name, '-n', namespace, '-o', 'json'],
            check=False,
            logger=logger
        )

        if returncode != 0:
            return []

        vm_data = json.loads(stdout)
        volumes = vm_data.get('spec', {}).get('template', {}).get('spec', {}).get('volumes', [])

        pvc_names = []
        for volume in volumes:
            # Check for dataVolume
            if 'dataVolume' in volume:
                pvc_names.append(volume['dataVolume']['name'])
            # Check for persistentVolumeClaim
            elif 'persistentVolumeClaim' in volume:
                pvc_names.append(volume['persistentVolumeClaim']['claimName'])

        return pvc_names

    except Exception as e:
        if logger:
            logger.error(f"[{namespace}] Failed to get VM volumes: {e}")
        return []

