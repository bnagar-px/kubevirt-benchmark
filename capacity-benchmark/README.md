# KubeVirt VM Capacity Benchmark

## Overview

The **Capacity Benchmark** tests the maximum capacity of Virtual Machines and Volumes supported by your cluster and storage class. It runs a comprehensive workload in a loop, creating resources continuously until a failure occurs, helping you discover the limits of your infrastructure.

## What It Tests

Each iteration performs **5 phases** of operations:

1. **Create VMs** - Creates VMs with multiple data volumes
2. **Resize Volumes** - Expands root and data volumes (tests volume expansion)
3. **Restart VMs** - Stops and starts VMs (tests VM lifecycle)
4. **Snapshot VMs** - Creates VM snapshots (tests snapshot functionality)
5. **Migrate VMs** - Live migrates VMs (tests live migration)

The test runs in a loop without deleting resources until:
- A failure occurs (capacity limit reached)
- Maximum iterations reached (if specified)
- User interrupts the test (Ctrl+C)

## Prerequisites

- OpenShift cluster with OpenShift Virtualization installed
- Storage class that supports:
  - Volume expansion (`allowVolumeExpansion: true`)
  - Volume snapshots (VolumeSnapshotClass configured)
  - ReadWriteMany (RWX) access mode for migration
- DataSource available (e.g., `rhel9` in `openshift-virtualization-os-images`)
- `kubectl` or `oc` CLI configured

## Usage

### Basic Usage

```bash
# Run capacity test with default settings
python3 measure-capacity.py --storage-class portworx-fada-sc

# Run with custom VM count per iteration
python3 measure-capacity.py --storage-class portworx-fada-sc --vms 10

# Run with maximum iterations limit
python3 measure-capacity.py --storage-class portworx-fada-sc --max-iterations 5
```

### Advanced Usage

```bash
# Run with multiple storage classes (round-robin)
python3 measure-capacity.py --storage-class portworx-fada-sc,portworx-raw-sc --vms 5

# Run with custom data volume count
python3 measure-capacity.py --storage-class portworx-fada-sc --vms 5 --data-volume-count 3

# Skip specific phases
python3 measure-capacity.py --storage-class portworx-fada-sc --skip-resize-job --skip-migration-job

# Run with cleanup after completion
python3 measure-capacity.py --storage-class portworx-fada-sc --max-iterations 3 --cleanup
```

### Cleanup

```bash
# Cleanup resources from previous run
python3 measure-capacity.py --cleanup-only

# Or manually delete the namespace
kubectl delete namespace virt-capacity-benchmark
```

## Command-Line Options

### Required Options

| Option | Description |
|--------|-------------|
| `--storage-class` | Storage class name (comma-separated for multiple) |

### Test Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--namespace` | `virt-capacity-benchmark` | Namespace for test resources |
| `--max-iterations` | `0` (unlimited) | Maximum number of iterations |
| `--vms` | `5` | Number of VMs per iteration |
| `--data-volume-count` | `9` | Number of data volumes per VM |
| `--min-vol-size` | `30Gi` | Initial volume size |
| `--min-vol-inc-size` | `10Gi` | Volume size increment for resize |

### VM Template Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--vm-yaml` | `../examples/vm-templates/vm-template.yaml` | Path to VM YAML template |
| `--vm-name` | `capacity-vm` | Base VM name |
| `--datasource-name` | `rhel9` | DataSource name |
| `--datasource-namespace` | `openshift-virtualization-os-images` | DataSource namespace |
| `--vm-memory` | `2048M` | VM memory |
| `--vm-cpu-cores` | `1` | VM CPU cores |

### Skip Options

| Option | Description |
|--------|-------------|
| `--skip-resize-job` | Skip volume resize phase |
| `--skip-migration-job` | Skip migration phase |
| `--skip-snapshot-job` | Skip snapshot phase |
| `--skip-restart-job` | Skip restart phase |

### Execution Options

| Option | Default | Description |
|--------|---------|-------------|
| `--concurrency` | `10` | Number of concurrent operations |
| `--poll-interval` | `5` | Polling interval in seconds |

### Cleanup Options

| Option | Description |
|--------|-------------|
| `--cleanup` | Cleanup resources after test completion |
| `--cleanup-only` | Only cleanup resources from previous runs |

### Logging Options

| Option | Default | Description |
|--------|---------|-------------|
| `--log-file` | Auto-generated | Log file path |
| `--log-level` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Example Scenarios

### Scenario 1: Find Maximum VM Capacity

Test how many VMs your cluster can support:

```bash
python3 measure-capacity.py \
  --storage-class portworx-fada-sc \
  --vms 10 \
  --skip-resize-job \
  --skip-snapshot-job \
  --skip-migration-job
```

This creates 10 VMs per iteration and only tests VM creation capacity.

### Scenario 2: Test Volume Expansion Limits

Test volume expansion capabilities:

```bash
python3 measure-capacity.py \
  --storage-class portworx-fada-sc \
  --vms 5 \
  --min-vol-size 30Gi \
  --min-vol-inc-size 20Gi \
  --max-iterations 10
```

This creates 5 VMs and expands volumes by 20Gi each iteration (30Gi → 50Gi → 70Gi → ...).

### Scenario 3: Comprehensive Capacity Test

Test all features until failure:

```bash
python3 measure-capacity.py \
  --storage-class portworx-fada-sc \
  --vms 5 \
  --data-volume-count 3 \
  --log-level DEBUG
```

This runs all 5 phases (create, resize, restart, snapshot, migrate) until failure.

### Scenario 4: Multi-Storage Class Test

Test with multiple storage classes in round-robin:

```bash
python3 measure-capacity.py \
  --storage-class portworx-fada-sc,portworx-raw-sc \
  --vms 5 \
  --max-iterations 10
```

This alternates between storage classes for each iteration.

## Output

The test provides detailed output for each phase:

```
====================================================================================================
ITERATION 1
Storage Class: portworx-fada-sc
VMs to create: 5
Data volumes per VM: 9
====================================================================================================

Phase 1: Creating 5 VMs
Creating VM capacity-vm-1-1 with 9 data volumes
VM capacity-vm-1-1 created successfully
...
Phase 1 COMPLETE: 5 VMs running (took 245.32s)

Phase 2: Resizing Volumes
Resizing capacity-vm-1-1-volume: 30Gi -> 40Gi
...
Phase 2 COMPLETE: All volumes resized (took 120.45s)

Phase 3: Restarting VMs
...
Phase 3 COMPLETE: All VMs restarted (took 180.22s)

Phase 4: Creating VM Snapshots
...
Phase 4 COMPLETE: 5 snapshots created (took 95.67s)

Phase 5: Migrating VMs
...
Phase 5 COMPLETE: All VMs migrated (took 210.88s)

ITERATION 1 COMPLETE
```

## Troubleshooting

### Volume Resize Fails

**Error**: `Phase 2 FAILED: Volume resize failed`

**Solution**: Check if your storage class supports volume expansion:

```bash
kubectl get storageclass portworx-fada-sc -o jsonpath='{.allowVolumeExpansion}'
```

If `false`, use `--skip-resize-job` to skip this phase.

### Snapshot Creation Fails

**Error**: `Phase 4 FAILED: Snapshot creation failed`

**Solution**: Check if VolumeSnapshotClass is configured:

```bash
kubectl get volumesnapshotclass
```

If not available, use `--skip-snapshot-job` to skip this phase.

### Migration Fails

**Error**: `Phase 5 FAILED: Migration failed`

**Solution**: Check if your storage class supports ReadWriteMany (RWX):

```bash
kubectl get storageclass portworx-fada-sc -o yaml | grep -A5 parameters
```

If RWX is not supported, use `--skip-migration-job` to skip this phase.

### Out of Resources

**Error**: `Failed to create VM` or `PVC pending`

**Solution**: This indicates you've reached capacity limits. Check:

```bash
# Check node resources
kubectl top nodes

# Check PVC status
kubectl get pvc -n virt-capacity-benchmark

# Check storage pool capacity
kubectl get storagecluster -A
```

## Best Practices

1. **Start Small**: Begin with `--vms 5` and `--max-iterations 3` to validate the test works
2. **Monitor Resources**: Watch cluster resources during the test (CPU, memory, storage)
3. **Use Skip Options**: Skip phases not supported by your storage class
4. **Set Max Iterations**: Use `--max-iterations` to prevent infinite loops during testing
5. **Enable Cleanup**: Use `--cleanup` to automatically cleanup after test completion
6. **Debug Mode**: Use `--log-level DEBUG` for detailed troubleshooting

## Performance Considerations

- **VM Creation**: Depends on DataSource clone speed and storage performance
- **Volume Resize**: Depends on storage class and volume size
- **VM Restart**: Typically 30-60 seconds per VM
- **Snapshot Creation**: Depends on VM disk size and storage class
- **Migration**: Depends on VM memory size and network bandwidth

## See Also

- [Main README](../README.md) - Repository overview
- [VM Templates](../examples/vm-templates/) - VM template examples
- [Validation Guide](../VALIDATION_GUIDE.md) - Cluster validation
- [Setup Guide](../SETUP.md) - Initial setup instructions

