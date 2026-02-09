# Capacity Benchmark Testing

Tests cluster capacity limits by running comprehensive VM operations in a loop until failure.

**Use Case**: Discover maximum VM capacity, test volume expansion limits, validate snapshot functionality, and stress-test the cluster.

## How It Works

The capacity benchmark test runs in iterations, with each iteration performing:

1. **Phase 1**: Creates VMs with multiple data volumes
2. **Phase 2**: Resizes root and data volumes (tests volume expansion)
3. **Phase 3**: Restarts VMs (tests VM lifecycle)
4. **Phase 4**: Creates VM snapshots (tests snapshot functionality)
5. Repeats until failure or max iterations reached

## Basic Capacity Test

### Using virtbench CLI

```bash
# Run capacity test with default settings (5 VMs per iteration)
virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS

# Run with custom VM count
virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS --vms 10

# Run with maximum iterations limit
virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS --max-iterations 5
```

### Using Python Script

```bash
cd capacity-benchmark

# Run capacity test with default settings (5 VMs per iteration)
python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS

# Run with custom VM count
python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS --vms 10

# Run with maximum iterations limit
python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS --max-iterations 5
```

## Skip Specific Phases

You can skip specific test phases to focus on particular aspects of capacity testing.

### Using virtbench CLI

```bash
# Test only VM creation capacity (skip resize, restart, snapshot, migration)
virtbench capacity-benchmark \
  --storage-class YOUR-STORAGE-CLASS \
  --vms 10 \
  --skip-resize-job \
  --skip-restart-job \
  --skip-snapshot-job

# Test volume expansion limits
virtbench capacity-benchmark \
  --storage-class YOUR-STORAGE-CLASS \
  --vms 5 \
  --min-vol-size 30Gi \
  --min-vol-inc-size 20Gi \
  --max-iterations 10
```

### Using Python Script

```bash
cd capacity-benchmark

# Test only VM creation capacity (skip resize, restart, snapshot)
python3 measure-capacity.py \
  --storage-class YOUR-STORAGE-CLASS \
  --vms 10 \
  --skip-resize-job \
  --skip-restart-job \
  --skip-snapshot-job

# Test volume expansion limits
python3 measure-capacity.py \
  --storage-class YOUR-STORAGE-CLASS \
  --vms 5 \
  --min-vol-size 30Gi \
  --min-vol-inc-size 20Gi \
  --max-iterations 10
```

## Save Results to Files

### Using virtbench CLI

```bash
# Run capacity test and save results
virtbench capacity-benchmark \
  --storage-class YOUR-STORAGE-CLASS \
  --vms 5 \
  --save-results

# Save results with storage version for dashboard organization
virtbench capacity-benchmark \
  --storage-class YOUR-STORAGE-CLASS \
  --vms 5 \
  --save-results \
  --storage-version 3.2.0
```

Results will be saved to:
```
results/{storage-version}/{num-disks}-disk/{timestamp}_capacity_benchmark_{total_vms}vms/
```

Example:
```
results/3.2.0/10-disk/20251207-083451_capacity_benchmark_22vms/
```

Files created:
- `capacity_benchmark_results.json` (detailed results)
- `summary_capacity_benchmark.json` (summary for dashboard)
- `capacity_benchmark_results.csv` (key metrics)

### Using Python Script

```bash
cd capacity-benchmark
python3 measure-capacity.py \
  --storage-class YOUR-STORAGE-CLASS \
  --vms 5 \
  --save-results \
  --storage-version 3.2.0
```

## Advanced Configuration

### Custom VM Template

```bash
# Use custom VM template
virtbench capacity-benchmark \
  --storage-class YOUR-STORAGE-CLASS \
  --vm-yaml /path/to/custom-vm-template.yaml \
  --vms 5
```

### Custom DataSource

```bash
# Use different DataSource
virtbench capacity-benchmark \
  --storage-class YOUR-STORAGE-CLASS \
  --datasource-name fedora \
  --datasource-namespace openshift-virtualization-os-images \
  --vms 5
```

### Custom VM Resources

```bash
# Configure VM memory and CPU
virtbench capacity-benchmark \
  --storage-class YOUR-STORAGE-CLASS \
  --vm-memory 4Gi \
  --vm-cpu-cores 2 \
  --vms 5
```

### Custom Data Volume Configuration

```bash
# Configure number of data volumes and sizes
virtbench capacity-benchmark \
  --storage-class YOUR-STORAGE-CLASS \
  --data-volume-count 5 \
  --min-vol-size 50Gi \
  --min-vol-inc-size 25Gi \
  --vms 3
```

### Concurrency and Timeouts

```bash
# Configure parallel operations and timeouts
virtbench capacity-benchmark \
  --storage-class YOUR-STORAGE-CLASS \
  --concurrency 20 \
  --poll-interval 10 \
  --scheduling-timeout 180 \
  --vms 5
```

## Cleanup

### Using virtbench CLI

```bash
# Cleanup resources after test
virtbench capacity-benchmark --cleanup-only
```

### Using Python Script

```bash
cd capacity-benchmark
python3 measure-capacity.py --cleanup-only
```

## Understanding Results

The capacity benchmark provides detailed metrics for each iteration:

- **VMs Created**: Number of VMs successfully created
- **Volumes Resized**: Number of volumes successfully expanded
- **VMs Restarted**: Number of VMs successfully restarted
- **Snapshots Created**: Number of snapshots successfully created
- **Time per Phase**: Duration of each phase
- **Failure Point**: Which phase failed and why (if applicable)

### Interpreting Capacity Limits

The test stops when:

1. **Scheduling Timeout**: VMs stuck in "Scheduling" state (resource exhaustion)
2. **Volume Resize Failure**: Storage backend cannot expand volumes
3. **Snapshot Failure**: Snapshot creation fails
4. **Max Iterations Reached**: Configured limit reached

## Best Practices

1. **Start Small**: Begin with 5 VMs per iteration to understand baseline
2. **Monitor Resources**: Watch cluster resource utilization during tests
3. **Storage Limits**: Be aware of storage quota and IOPS limits
4. **Cleanup**: Always cleanup after tests to free resources
5. **Save Results**: Use `--save-results` to track capacity over time

## Troubleshooting

### VMs Stuck in Scheduling

**Cause**: Insufficient cluster resources (CPU, memory, or storage)

**Solution**:
- Check node resource availability
- Reduce VM count per iteration
- Add more worker nodes

### Volume Resize Failures

**Cause**: Storage class doesn't support volume expansion

**Solution**:
- Verify `AllowVolumeExpansion: true` in StorageClass
- Use `--skip-resize-job` to skip this phase
- Check storage backend limits

### Snapshot Failures

**Cause**: Storage provisioner doesn't support CSI snapshots

**Solution**:
- Verify VolumeSnapshotClass exists
- Use `--skip-snapshot-job` to skip this phase
- Check storage backend snapshot support

## See Also

- [Configuration Options](../configuration.md) - Detailed configuration reference
- [Output and Results](../output-and-results.md) - Understanding test output
- [Results Dashboard](../results-dashboard.md) - Visualize capacity results

