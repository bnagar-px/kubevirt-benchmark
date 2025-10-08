# Utilities Module

This directory contains shared utility functions used across all performance testing scripts.

## Files

### common.py

Core utilities module providing:

#### Logging
- `setup_logging()`: Configure logging with file output and console
- `Colors`: ANSI color codes for terminal output

#### Kubernetes Operations
- `run_kubectl_command()`: Execute kubectl with error handling
- `namespace_exists()`: Check if namespace exists
- `create_namespace()`: Create namespace if not exists
- `delete_namespace()`: Delete namespace with optional wait
- `get_vm_status()`: Get VM status
- `get_vmi_ip()`: Get VMI IP address
- `ping_vm()`: Test VM network connectivity

#### Output Formatting
- `print_summary_table()`: Format and print test results

#### Validation
- `validate_prerequisites()`: Check prerequisites before running tests

## Usage

Import utilities in your scripts:

```python
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.common import (
    setup_logging,
    run_kubectl_command,
    create_namespace,
    get_vm_status,
    print_summary_table
)
```

## Examples

### Setup Logging
```python
logger = setup_logging(log_file='test.log', log_level='INFO')
logger.info("Test started")
```

### Run kubectl Command
```python
returncode, stdout, stderr = run_kubectl_command(
    ['get', 'pods', '-n', 'default'],
    check=False,
    logger=logger
)
```

### Create Namespace
```python
if create_namespace('test-namespace', logger):
    logger.info("Namespace created successfully")
```

### Get VM Status
```python
status = get_vm_status('my-vm', 'my-namespace', logger)
if status == 'Running':
    logger.info("VM is running")
```

### Print Summary
```python
results = [
    ('namespace-1', 10.5, 15.2, True),
    ('namespace-2', 11.3, 16.8, True),
]
print_summary_table(results, "Test Results")
```

## Function Reference

See inline documentation in `common.py` for detailed function signatures and parameters.

