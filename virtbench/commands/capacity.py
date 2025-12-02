#!/usr/bin/env python3
"""
Capacity benchmark command
"""
import click
import subprocess
import sys
from pathlib import Path
from rich.console import Console

from virtbench.utils.yaml_modifier import modify_storage_class
from virtbench.common import print_banner, build_python_command, generate_log_filename

console = Console()


@click.command('capacity-benchmark')
@click.option('--storage-class', required=True, help='Storage class name (REQUIRED)')
@click.option('--vms', default=5, type=int, help='Number of VMs to create per iteration')
@click.option('--max-iterations', default=10, type=int, help='Maximum number of iterations')
@click.option('--vm-template',
              default='examples/vm-templates/rhel9-vm-datasource.yaml',
              help='Path to VM template YAML')
@click.option('--namespace-prefix', default='capacity-test', help='Namespace prefix')
@click.option('--concurrency', '-c', default=10, type=int, help='Max parallel threads')
@click.option('--poll-interval', default=5, type=int, help='Seconds between status checks')
@click.option('--ping-timeout', default=300, type=int, help='Timeout for ping tests in seconds')
@click.option('--ssh-pod', default='ssh-test-pod', help='Pod name for ping tests')
@click.option('--ssh-pod-ns', default='default', help='Namespace for SSH test pod')
@click.option('--cleanup/--no-cleanup', default=False, help='Delete test resources after completion')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompts')
@click.option('--save-results', is_flag=True, help='Save detailed results to results folder')
@click.option('--results-folder', default='../results', help='Base directory to store test results')
@click.option('--px-version', help='Portworx version (auto-detect if not provided)')
@click.option('--px-namespace', default='portworx', help='Portworx namespace')
@click.pass_context
def capacity_benchmark(ctx, **kwargs):
    """
    Run capacity benchmark
    
    This workload tests cluster capacity by iteratively creating VMs until
    resource limits are reached or max iterations is hit.
    
    \b
    Examples:
      # Run capacity test with 5 VMs per iteration
      virtbench capacity-benchmark --storage-class fada-raw-sc --vms 5
      
      # Run with custom max iterations
      virtbench capacity-benchmark --storage-class fada-raw-sc --vms 5 --max-iterations 20
      
      # Run with cleanup after test
      virtbench capacity-benchmark --storage-class fada-raw-sc --vms 5 --cleanup
    """
    print_banner("Capacity Benchmark")
    
    # Get repo root from context
    repo_root = ctx.obj.repo_root
    
    # Resolve template path
    template_path = Path(kwargs['vm_template'])
    if not template_path.is_absolute():
        template_path = repo_root / template_path
    
    if not template_path.exists():
        console.print(f"[red]Error: Template file not found: {template_path}[/red]")
        sys.exit(1)
    
    # Handle storage class modification
    console.print(f"[cyan]Using storage class: {kwargs['storage_class']}[/cyan]")
    try:
        modify_storage_class(template_path, kwargs['storage_class'])
    except Exception as e:
        console.print(f"[red]Error modifying storage class: {e}[/red]")
        sys.exit(1)
    
    # Build Python script command
    script_path = repo_root / 'capacity-benchmark' / 'measure-capacity.py'
    
    if not script_path.exists():
        console.print(f"[red]Error: Script not found: {script_path}[/red]")
        sys.exit(1)
    
    # Map CLI args to Python script args
    python_args = {
        'vms': kwargs['vms'],
        'max-iterations': kwargs['max_iterations'],
        'vm-template': str(template_path),
        'namespace-prefix': kwargs['namespace_prefix'],
        'concurrency': kwargs['concurrency'],
        'poll-interval': kwargs['poll_interval'],
        'ping-timeout': kwargs['ping_timeout'],
        'ssh-pod': kwargs['ssh_pod'],
        'ssh-pod-ns': kwargs['ssh_pod_ns'],
        'results-folder': kwargs['results_folder'],
        'px-namespace': kwargs['px_namespace'],
        'log-level': ctx.obj.log_level,
    }
    
    # Add boolean flags
    if kwargs['cleanup']:
        python_args['cleanup'] = True
    if kwargs['yes']:
        python_args['yes'] = True
    if kwargs['save_results']:
        python_args['save-results'] = True
    
    # Add optional args
    if kwargs.get('px_version'):
        python_args['px-version'] = kwargs['px_version']
    
    # Add global flags from context
    if ctx.obj.log_file:
        python_args['log-file'] = ctx.obj.log_file
    else:
        python_args['log-file'] = generate_log_filename('capacity-benchmark')
    
    # Build and run command
    cmd = build_python_command(script_path, python_args)
    
    console.print(f"[dim]Running: {' '.join(cmd[:2])} ...[/dim]")
    console.print()
    
    try:
        result = subprocess.run(cmd, cwd=repo_root)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

