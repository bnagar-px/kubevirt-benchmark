#!/usr/bin/env python3
"""
VM Migration benchmark command
"""
import click
import subprocess
import sys
from pathlib import Path
from rich.console import Console

from virtbench.utils.yaml_modifier import modify_storage_class
from virtbench.common import print_banner, build_python_command, generate_log_filename

console = Console()


@click.command('migration')
@click.option('--start', '-s', default=1, type=int, help='Start index for test namespaces')
@click.option('--end', '-e', default=10, type=int, help='End index for test namespaces')
@click.option('--vm-name', '-n', default='rhel-9-vm', help='VM resource name')
@click.option('--vm-template',
              default='examples/vm-templates/rhel9-vm-datasource.yaml',
              help='Path to VM template YAML')
@click.option('--storage-class', help='Storage class name (overrides template value)')
@click.option('--namespace-prefix', default='migration', help='Namespace prefix')
@click.option('--source-node', help='Source node name to migrate VMs from')
@click.option('--target-node', help='Target node name to migrate VMs to')
@click.option('--create-vms', is_flag=True, help='Create VMs before migration')
@click.option('--parallel', is_flag=True, help='Migrate all VMs in parallel')
@click.option('--evacuate', is_flag=True, help='Evacuate all VMs from source node')
@click.option('--concurrency', '-c', default=10, type=int, help='Max parallel threads')
@click.option('--poll-interval', default=5, type=int, help='Seconds between status checks')
@click.option('--migration-timeout', default=600, type=int, help='Timeout for migration in seconds')
@click.option('--cleanup/--no-cleanup', default=False, help='Delete test resources after completion')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompts')
@click.option('--save-results', is_flag=True, help='Save detailed results to results folder')
@click.option('--results-folder', default='../results', help='Base directory to store test results')
@click.option('--storage-version', help='Storage version to include in results path (optional)')
@click.option('--log-file', type=click.Path(), help='Log file path (auto-generated if not specified)')
@click.pass_context
def migration(ctx, **kwargs):
    """
    Run VM migration benchmark

    This workload tests the performance of live migrating VMs between nodes.

    \b
    Examples:
      # Migrate VMs from worker-1
      virtbench migration --start 1 --end 10 --source-node worker-1

      # Create VMs first, then migrate
      virtbench migration --start 1 --end 5 --create-vms --storage-class YOUR-STORAGE-CLASS

      # Parallel migration
      virtbench migration --start 1 --end 10 --source-node worker-1 --parallel

      # Evacuate all VMs from a node
      virtbench migration --start 1 --end 10 --source-node worker-1 --evacuate
    """
    print_banner("VM Migration Benchmark")
    
    # Get repo root from context
    repo_root = ctx.obj.repo_root
    
    # Resolve template path
    template_path = Path(kwargs['vm_template'])
    if not template_path.is_absolute():
        template_path = repo_root / template_path
    
    if kwargs['create_vms'] and not template_path.exists():
        console.print(f"[red]Error: Template file not found: {template_path}[/red]")
        sys.exit(1)
    
    # Handle storage class modification
    if kwargs['storage_class'] and kwargs['create_vms']:
        console.print(f"[cyan]Using storage class: {kwargs['storage_class']}[/cyan]")
        try:
            modify_storage_class(template_path, kwargs['storage_class'])
        except Exception as e:
            console.print(f"[red]Error modifying storage class: {e}[/red]")
            sys.exit(1)
    
    # Build Python script command
    script_path = repo_root / 'migration' / 'measure-vm-migration-time.py'
    
    if not script_path.exists():
        console.print(f"[red]Error: Script not found: {script_path}[/red]")
        sys.exit(1)
    
    # Map CLI args to Python script args
    python_args = {
        'start': kwargs['start'],
        'end': kwargs['end'],
        'vm-name': kwargs['vm_name'],
        'vm-template': str(template_path),
        'namespace-prefix': kwargs['namespace_prefix'],
        'concurrency': kwargs['concurrency'],
        'poll-interval': kwargs['poll_interval'],
        'migration-timeout': kwargs['migration_timeout'],
        'results-folder': kwargs['results_folder'],
        'log-level': ctx.obj.log_level.upper(),
    }

    # Add boolean flags
    if kwargs['create_vms']:
        python_args['create-vms'] = True
    if kwargs['parallel']:
        python_args['parallel'] = True
    if kwargs['evacuate']:
        python_args['evacuate'] = True
    if kwargs['cleanup']:
        python_args['cleanup'] = True
    if kwargs['yes']:
        python_args['yes'] = True
    if kwargs['save_results']:
        python_args['save-results'] = True

    # Add optional args
    if kwargs.get('source_node'):
        python_args['source-node'] = kwargs['source_node']
    if kwargs.get('target_node'):
        python_args['target-node'] = kwargs['target_node']
    if kwargs.get('storage_version'):
        python_args['storage-version'] = kwargs['storage_version']
    
    # Add log-file (prefer subcommand option, then global context, then auto-generate)
    if kwargs.get('log_file'):
        python_args['log-file'] = kwargs['log_file']
    elif ctx.obj.log_file:
        python_args['log-file'] = ctx.obj.log_file
    else:
        python_args['log-file'] = generate_log_filename('migration')
    
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

