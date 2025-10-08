#!/usr/bin/env python3
"""
KubeVirt VM Recovery Performance Test

This script measures VM recovery time after node failure events triggered by
Fence Agents Remediation (FAR). It monitors VMI state transitions and network
connectivity restoration.

Usage:
    python3 measure-recovery-time.py --start 1 --end 60 --vm-name rhel-9-vm

Author: Portworx
License: Apache 2.0
"""

import argparse
import os
import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.common import (
    setup_logging, run_kubectl_command, print_summary_table
)

# Default configuration
DEFAULT_VM_NAME = 'rhel-9-vm'
DEFAULT_SSH_POD = 'ssh-test-pod'
DEFAULT_SSH_POD_NS = 'default'
DEFAULT_POLL_INTERVAL = 1
DEFAULT_CONCURRENCY = 10
DEFAULT_NAMESPACE_PREFIX = 'kubevirt-perf-test'


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Measure KubeVirt VM recovery time after node failure.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor recovery for VMs in namespaces 1-60
  %(prog)s --start 1 --end 60 --vm-name rhel-9-vm

  # Monitor with custom SSH pod
  %(prog)s --start 1 --end 100 --ssh-pod my-ssh-pod --ssh-pod-ns test

  # Monitor with detailed logging
  %(prog)s --start 1 --end 50 --log-level DEBUG --log-file recovery.log
        """
    )
    
    # Test range
    parser.add_argument(
        '-s', '--start',
        type=int,
        default=1,
        help='Start namespace index (default: 1)'
    )
    parser.add_argument(
        '-e', '--end',
        type=int,
        default=5,
        help='End namespace index, inclusive (default: 5)'
    )
    
    # VM configuration
    parser.add_argument(
        '-n', '--vm-name',
        type=str,
        required=True,
        help='VMI resource name to monitor'
    )
    parser.add_argument(
        '--namespace-prefix',
        type=str,
        default=DEFAULT_NAMESPACE_PREFIX,
        help=f'Prefix for test namespaces (default: {DEFAULT_NAMESPACE_PREFIX})'
    )
    
    # Performance tuning
    parser.add_argument(
        '-c', '--concurrency',
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f'Max parallel monitoring threads (default: {DEFAULT_CONCURRENCY})'
    )
    parser.add_argument(
        '--poll-interval',
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f'Seconds between status checks (default: {DEFAULT_POLL_INTERVAL})'
    )
    
    # SSH pod for ping tests
    parser.add_argument(
        '--ssh-pod',
        type=str,
        required=True,
        help='Pod name for ping tests'
    )
    parser.add_argument(
        '--ssh-pod-ns',
        type=str,
        required=True,
        help='Namespace of SSH pod'
    )
    
    # Logging
    parser.add_argument(
        '--log-file',
        type=str,
        help='Path to log file (default: stdout only)'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    args = parser.parse_args()
    
    # Validation
    if args.start < 1:
        parser.error("--start must be >= 1")
    if args.end < args.start:
        parser.error("--end must be >= --start")
    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")
    
    return args


def get_vmi_status_and_ip(vmi_name: str, namespace: str, logger) -> Tuple[str, str, str]:
    """
    Get VMI phase, ready status, and IP address.
    
    Args:
        vmi_name: VMI name
        namespace: Namespace
        logger: Logger instance
    
    Returns:
        Tuple of (phase, ready_status, ip_address)
    """
    try:
        # Get phase
        returncode, phase, _ = run_kubectl_command(
            ['get', 'vmi', vmi_name, '-n', namespace, '-o', 'jsonpath={.status.phase}'],
            check=False,
            logger=logger
        )
        phase = phase.strip() if returncode == 0 else ''
        
        # Get ready condition
        returncode, ready, _ = run_kubectl_command(
            ['get', 'vmi', vmi_name, '-n', namespace, '-o', 
             'jsonpath={.status.conditions[?(@.type=="Ready")].status}'],
            check=False,
            logger=logger
        )
        ready = ready.strip() if returncode == 0 else ''
        
        # Get IP
        returncode, ip, _ = run_kubectl_command(
            ['get', 'vmi', vmi_name, '-n', namespace, '-o', 
             'jsonpath={.status.interfaces[0].ipAddress}'],
            check=False,
            logger=logger
        )
        ip = ip.strip() if returncode == 0 and ip and ip != '<none>' else ''
        
        return phase, ready, ip
    
    except Exception as e:
        logger.debug(f"Error getting VMI status for {vmi_name} in {namespace}: {e}")
        return '', '', ''


def wait_for_vmi_running(ns: str, vmi_name: str, start_ts: datetime, poll_interval: int, logger) -> Tuple[str, float]:
    """
    Wait for VMI to reach Running state with Ready=True and valid IP.
    
    Args:
        ns: Namespace
        vmi_name: VMI name
        start_ts: Start timestamp
        poll_interval: Polling interval in seconds
        logger: Logger instance
    
    Returns:
        Tuple of (ip_address, elapsed_seconds)
    """
    logger.info(f"[{ns}] Waiting for VMI {vmi_name} to be Running and Ready...")
    
    while True:
        phase, ready, ip = get_vmi_status_and_ip(vmi_name, ns, logger)
        
        if phase == 'Running' and ready == 'True' and ip:
            elapsed = (datetime.now() - start_ts).total_seconds()
            logger.info(f"[{ns}] VMI Running and Ready after {elapsed:.2f}s (IP: {ip})")
            return ip, elapsed
        
        time.sleep(poll_interval)


def wait_for_ping_recovery(ns: str, vmi_name: str, ssh_pod: str, ssh_pod_ns: str,
                           start_ts: datetime, poll_interval: int, logger) -> Tuple[str, float]:
    """
    Wait for VMI to respond to ping, continuously checking for IP changes.
    
    Args:
        ns: Namespace
        vmi_name: VMI name
        ssh_pod: SSH pod name
        ssh_pod_ns: SSH pod namespace
        start_ts: Start timestamp
        poll_interval: Polling interval in seconds
        logger: Logger instance
    
    Returns:
        Tuple of (ip_address, elapsed_seconds)
    """
    logger.info(f"[{ns}] Waiting for VMI to respond to ping...")
    
    while True:
        # Get current IP (may change during recovery)
        _, _, ip = get_vmi_status_and_ip(vmi_name, ns, logger)
        
        if not ip:
            time.sleep(poll_interval)
            continue
        
        # Try to ping
        try:
            returncode, _, _ = run_kubectl_command(
                ['exec', '-n', ssh_pod_ns, ssh_pod, '--', 'ping', '-c', '1', '-W', '2', ip],
                check=False,
                capture_output=True,
                timeout=5,
                logger=logger
            )
            
            if returncode == 0:
                elapsed = (datetime.now() - start_ts).total_seconds()
                logger.info(f"[{ns}] Ping successful after {elapsed:.2f}s (IP: {ip})")
                return ip, elapsed
        
        except Exception as e:
            logger.debug(f"[{ns}] Ping attempt failed: {e}")
        
        time.sleep(poll_interval)


def monitor_recovery(ns: str, vmi_name: str, start_ts: datetime, ssh_pod: str, ssh_pod_ns: str,
                     poll_interval: int, logger) -> Tuple[str, str, float, str, float]:
    """
    Monitor a single VMI recovery.
    
    Args:
        ns: Namespace
        vmi_name: VMI name
        start_ts: Start timestamp
        ssh_pod: SSH pod name
        ssh_pod_ns: SSH pod namespace
        poll_interval: Polling interval
        logger: Logger instance
    
    Returns:
        Tuple of (namespace, ip_at_running, time_to_running, ip_at_ping, time_to_ping)
    """
    try:
        # Wait for Running state
        ip_running, time_running = wait_for_vmi_running(ns, vmi_name, start_ts, poll_interval, logger)
        
        # Wait for ping
        ip_ping, time_ping = wait_for_ping_recovery(
            ns, vmi_name, ssh_pod, ssh_pod_ns, start_ts, poll_interval, logger
        )
        
        return ns, ip_running, time_running, ip_ping, time_ping
    
    except Exception as e:
        logger.error(f"[{ns}] Error monitoring recovery: {e}")
        return ns, '', None, '', None


def main():
    """Main execution function."""
    args = parse_args()
    
    # Setup logging
    logger = setup_logging(args.log_file, args.log_level)
    
    logger.info("=" * 80)
    logger.info("KubeVirt VM Recovery Performance Test")
    logger.info("=" * 80)
    logger.info(f"Monitoring namespaces: {args.namespace_prefix}-{args.start} to {args.namespace_prefix}-{args.end}")
    logger.info(f"VMI name: {args.vm_name}")
    logger.info(f"SSH pod: {args.ssh_pod} (namespace: {args.ssh_pod_ns})")
    logger.info(f"Concurrency: {args.concurrency}")
    logger.info(f"Poll interval: {args.poll_interval}s")
    logger.info("=" * 80)
    logger.info("\nStarting recovery monitoring...")
    logger.info("Trigger the node failure event (FAR) now if not already done.")
    logger.info("=" * 80)
    
    # Start global timer
    start_ts = datetime.now()
    
    # Build namespace list
    namespaces = [f"{args.namespace_prefix}-{i}" for i in range(args.start, args.end + 1)]
    logger.info(f"\nMonitoring {len(namespaces)} VMIs...")
    
    # Monitor all VMIs in parallel
    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {
            executor.submit(
                monitor_recovery, ns, args.vm_name, start_ts,
                args.ssh_pod, args.ssh_pod_ns, args.poll_interval, logger
            ): ns
            for ns in namespaces
        }
        
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                ns = futures[future]
                logger.error(f"[{ns}] Recovery monitoring failed: {e}")
                results.append((ns, '', None, '', None))
    
    total_elapsed = (datetime.now() - start_ts).total_seconds()
    logger.info(f"\nAll VMIs monitored. Total elapsed time: {total_elapsed:.2f}s")
    
    # Print detailed summary
    print("\n" + "=" * 100)
    print(f"{'Namespace':<30}{'Time to Run(s)':<15}{'Time to Ping(s)':<15}{'IP at Run':<20}{'IP at Ping':<20}")
    print("-" * 100)
    
    running_times = []
    ping_times = []
    
    for ns, ip_run, t_run, ip_ping, t_ping in sorted(results, key=lambda x: x[0]):
        run_str = f"{t_run:.2f}" if t_run is not None else 'Failed'
        ping_str = f"{t_ping:.2f}" if t_ping is not None else 'Failed'
        
        print(f"{ns:<30}{run_str:<15}{ping_str:<15}{ip_run:<20}{ip_ping:<20}")
        
        if t_run is not None:
            running_times.append(t_run)
        if t_ping is not None:
            ping_times.append(t_ping)
    
    print("=" * 100)
    
    # Print statistics
    print(f"\n{'Recovery Statistics:'}")
    print(f"  Total VMIs:                {len(results)}")
    print(f"  Successfully recovered:    {len(ping_times)}")
    print(f"  Failed to recover:         {len(results) - len(ping_times)}")
    
    if running_times:
        print(f"\n  Time to Running:")
        print(f"    Average:                 {sum(running_times)/len(running_times):.2f}s")
        print(f"    Maximum:                 {max(running_times):.2f}s")
        print(f"    Minimum:                 {min(running_times):.2f}s")
    
    if ping_times:
        print(f"\n  Time to Ping:")
        print(f"    Average:                 {sum(ping_times)/len(ping_times):.2f}s")
        print(f"    Maximum:                 {max(ping_times):.2f}s")
        print(f"    Minimum:                 {min(ping_times):.2f}s")
    
    print("\n" + "=" * 100)
    
    logger.info("\nRecovery test completed successfully!")
    
    # Exit with error code if any VMs failed
    failed_count = len(results) - len(ping_times)
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == '__main__':
    main()

