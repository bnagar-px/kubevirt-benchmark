#!/usr/bin/env python3
"""
Capacity benchmark command
"""
import click
import subprocess
import sys
from pathlib import Path
from rich.console import Console

from virtbench.common import print_banner, build_python_command, generate_log_filename

console = Console()


@click.command('capacity-benchmark')
@click.option('--storage-class', required=False, help='Storage class name (required unless --cleanup-only)')
@click.option('--namespace', '-n', default='virt-capacity-benchmark', help='Namespace for test resources')
@click.option('--vms', default=5, type=int, help='Number of VMs to create per iteration')
@click.option('--max-iterations', default=0, type=int, help='Maximum number of iterations (0 for unlimited)')
@click.option('--data-volume-count', default=9, type=int, help='Number of data volumes per VM')
@click.option('--min-vol-size', default='30Gi', help='Minimum volume size')
@click.option('--min-vol-inc-size', default='10Gi', help='Minimum volume size increment')
@click.option('--vm-yaml', default='examples/vm-templates/vm-template.yaml',
              help='Path to VM YAML template')
@click.option('--vm-name', default='rhel-9-vm', help='Base VM name')
@click.option('--datasource-name', default='rhel9', help='DataSource name')
@click.option('--datasource-namespace', default='openshift-virtualization-os-images',
              help='DataSource namespace')
@click.option('--vm-memory', default='2048M', help='VM memory')
@click.option('--vm-cpu-cores', default=1, type=int, help='VM CPU cores')
@click.option('--skip-resize-job', is_flag=True, help='Skip volume resize job')
@click.option('--skip-snapshot-job', is_flag=True, help='Skip snapshot job')
@click.option('--skip-restart-job', is_flag=True, help='Skip restart job')
@click.option('--concurrency', '-c', default=10, type=int, help='Max parallel threads')
@click.option('--poll-interval', default=5, type=int, help='Seconds between status checks')
@click.option('--scheduling-timeout', default=120, type=int,
              help='Seconds to wait in Scheduling state before declaring capacity reached (default: 120)')
@click.option('--max-create-retries', default=5, type=int,
              help='Maximum retries for VM creation on transient errors (default: 5)')
@click.option('--cleanup/--no-cleanup', default=False, help='Delete test resources after completion')
@click.option('--cleanup-only', is_flag=True, help='Only cleanup resources from previous runs')
@click.option('--save-results', is_flag=True, help='Save results to JSON/CSV files in results directory')
@click.option('--results-dir', default='results', help='Directory to save results (default: results)')
@click.option('--storage-version', default=None, help='Storage version for results folder hierarchy (e.g., 3.2.0)')
@click.option('--log-file', type=click.Path(), help='Log file path (auto-generated if not specified)')
@click.option('--log-level', default='INFO', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              help='Logging level')
@click.pass_context
def capacity_benchmark(ctx, **kwargs):
    """
    Run capacity benchmark

    This workload tests cluster capacity by iteratively creating VMs until
    resource limits are reached or max iterations is hit.

    \b
    Examples:
      # Run capacity test with 5 VMs per iteration
      virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS --vms 5

      # Run with custom max iterations
      virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS --vms 5 --max-iterations 20

      # Skip specific jobs
      virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS --skip-resize-job --skip-snapshot-job

      # Save results to files
      virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS --vms 5 --save-results

      # Save results with storage version for folder hierarchy
      virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS --vms 5 --save-results --storage-version 3.2.0

      # Cleanup only mode
      virtbench capacity-benchmark --cleanup-only
    """
    print_banner("Capacity Benchmark")

    # Get repo root from context
    repo_root = ctx.obj.repo_root

    # Validate: storage-class is required unless cleanup-only
    if not kwargs['cleanup_only'] and not kwargs.get('storage_class'):
        console.print("[red]Error: --storage-class is required unless using --cleanup-only[/red]")
        sys.exit(1)

    # Build Python script command
    script_path = repo_root / 'capacity-benchmark' / 'measure-capacity.py'

    if not script_path.exists():
        console.print(f"[red]Error: Script not found: {script_path}[/red]")
        sys.exit(1)

    # Handle cleanup-only mode
    if kwargs['cleanup_only']:
        python_args = {
            'namespace': kwargs['namespace'],
            'log-level': kwargs['log_level'],
        }
        python_args['cleanup-only'] = True

        # Add log-file
        if kwargs.get('log_file'):
            python_args['log-file'] = kwargs['log_file']
        elif ctx.obj.log_file:
            python_args['log-file'] = ctx.obj.log_file
        else:
            python_args['log-file'] = generate_log_filename('capacity-benchmark')

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

    # Resolve template path
    template_path = Path(kwargs['vm_yaml'])
    if not template_path.is_absolute():
        template_path = repo_root / template_path

    if not template_path.exists():
        console.print(f"[red]Error: Template file not found: {template_path}[/red]")
        sys.exit(1)

    console.print(f"[cyan]Using storage class: {kwargs['storage_class']}[/cyan]")

    # Map CLI args to Python script args
    python_args = {
        'storage-class': kwargs['storage_class'],
        'namespace': kwargs['namespace'],
        'vms': kwargs['vms'],
        'max-iterations': kwargs['max_iterations'],
        'data-volume-count': kwargs['data_volume_count'],
        'min-vol-size': kwargs['min_vol_size'],
        'min-vol-inc-size': kwargs['min_vol_inc_size'],
        'vm-yaml': str(template_path),
        'vm-name': kwargs['vm_name'],
        'datasource-name': kwargs['datasource_name'],
        'datasource-namespace': kwargs['datasource_namespace'],
        'vm-memory': kwargs['vm_memory'],
        'vm-cpu-cores': kwargs['vm_cpu_cores'],
        'concurrency': kwargs['concurrency'],
        'poll-interval': kwargs['poll_interval'],
        'scheduling-timeout': kwargs['scheduling_timeout'],
        'max-create-retries': kwargs['max_create_retries'],
        'log-level': kwargs['log_level'],
    }

    # Add skip flags
    if kwargs['skip_resize_job']:
        python_args['skip-resize-job'] = True
    if kwargs['skip_snapshot_job']:
        python_args['skip-snapshot-job'] = True
    if kwargs['skip_restart_job']:
        python_args['skip-restart-job'] = True

    # Add cleanup flag
    if kwargs['cleanup']:
        python_args['cleanup'] = True

    # Add save-results flags
    if kwargs['save_results']:
        python_args['save-results'] = True
        python_args['results-dir'] = kwargs['results_dir']
        if kwargs.get('storage_version'):
            python_args['storage-version'] = kwargs['storage_version']

    # Add log-file (prefer subcommand option, then global context, then auto-generate)
    if kwargs.get('log_file'):
        python_args['log-file'] = kwargs['log_file']
    elif ctx.obj.log_file:
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

