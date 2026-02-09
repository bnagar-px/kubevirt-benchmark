# Boot Storm Testing Guide

A "boot storm" occurs when many VMs start simultaneously, creating high demand on storage I/O, network resources, compute resources, and hypervisor scheduling. This guide explains how to test and understand boot storm performance.

## What is Boot Storm Testing?

Boot storm testing helps you understand:

1. **Concurrent Startup Performance**: How your infrastructure handles simultaneous VM startups
2. **Performance Degradation**: Impact of load on individual VM boot times
3. **Bottleneck Identification**: Discover limits in storage, network, or compute
4. **Recovery Time Objectives (RTO)**: Realistic expectations for disaster recovery scenarios

## Boot Storm Test Workflow

The boot storm test follows a four-phase workflow:

### Phase 1: Initial VM Creation

1. Creates all test namespaces in parallel batches
2. Creates and starts all VMs simultaneously
3. Measures time to Running state for each VM
4. Measures time to network readiness (ping) for each VM
5. Displays initial creation performance results

This phase establishes a baseline for comparison.

### Phase 2: Shutdown All VMs

1. Issues stop commands to all VMs in parallel
2. Waits for all VMIs to be deleted (VMs fully stopped)
3. Confirms all VMs are in stopped state

This ensures a clean starting point for the boot storm test.

### Phase 3: Boot Storm (Simultaneous Startup)

1. Issues start commands to ALL VMs at once
2. Creates maximum load on infrastructure
3. Measures time to Running state for each VM
4. Measures time to network readiness for each VM
5. Displays boot storm performance results

This is the actual boot storm test.

### Phase 4: Comparison

Compare initial creation vs boot storm metrics to understand:
- Performance differences between cold start and warm start
- Impact of concurrent operations
- Storage backend behavior under load
- Infrastructure capacity limits

## Testing Scenarios

### Single Node Boot Storm

Tests VM startup performance on a single node when powering on multiple VMs simultaneously.

**Use Case**: Validates node-level capacity and boot storm performance (e.g., how many VMs can a single node handle during boot storm).

**Command:**
```bash
virtbench datasource-clone \
  --start 1 \
  --end 50 \
  --storage-class YOUR-STORAGE-CLASS \
  --single-node \
  --boot-storm \
  --save-results
```

**What it does**:
1. Selects a single node (random or specified with `--node-name`)
2. Creates and starts all VMs on that node (initial test)
3. Stops all VMs and waits for complete shutdown
4. Starts all VMs simultaneously on the same node (boot storm)
5. Measures time to Running state and time to ping for each VM
6. Provides separate statistics for initial creation and boot storm

### Multi-Node Boot Storm

Tests VM startup performance across all nodes when powering on multiple VMs simultaneously.

**Use Case**: Validates cluster-wide performance under boot storm conditions (e.g., after maintenance, power outage recovery).

**Command:**
```bash
virtbench datasource-clone \
  --start 1 \
  --end 100 \
  --storage-class YOUR-STORAGE-CLASS \
  --boot-storm \
  --save-results
```

**What it does**:
1. Creates and starts all VMs (distributed across nodes)
2. Stops all VMs and waits for complete shutdown
3. Starts all VMs simultaneously (boot storm)
4. Measures time to Running state and time to ping for each VM
5. Provides separate statistics for initial creation and boot storm

## Interpreting Boot Storm Results

### Key Metrics

- **Time to Running**: How long until VM reaches Running state
- **Time to Ping**: How long until VM is network-reachable
- **Average Times**: Mean performance across all VMs
- **Max Times**: Worst-case performance (important for SLA planning)
- **Success Rate**: Percentage of VMs that successfully started

### What to Look For

**Good Performance Indicators:**
- Boot storm times similar to initial creation times
- Consistent performance across all VMs
- High success rate (100%)
- Predictable max times

**Performance Issues:**
- Boot storm times significantly higher than initial creation
- Wide variance in boot times
- VMs failing to start
- Increasing times as more VMs start

### Common Bottlenecks

1. **Storage I/O**: High disk read/write contention
2. **Network**: Bandwidth saturation during image pulls
3. **Compute**: CPU/memory exhaustion on nodes
4. **Hypervisor**: KubeVirt scheduling delays

## Best Practices

1. **Start Small**: Begin with 10-20 VMs to establish baseline
2. **Incremental Testing**: Gradually increase VM count to find limits
3. **Monitor Resources**: Watch node CPU, memory, and storage I/O during tests
4. **Multiple Runs**: Run tests multiple times for consistent results
5. **Save Results**: Always use `--save-results` to track performance over time
6. **Clean Environment**: Ensure cluster is not under load before testing

## Advanced Options

### Namespace Batch Size

Control how many namespaces are created in parallel:

```bash
virtbench datasource-clone \
  --start 1 \
  --end 100 \
  --storage-class YOUR-STORAGE-CLASS \
  --boot-storm \
  --namespace-batch-size 50
```

### Concurrency Control

Adjust monitoring concurrency for large-scale tests:

```bash
virtbench datasource-clone \
  --start 1 \
  --end 200 \
  --storage-class YOUR-STORAGE-CLASS \
  --boot-storm \
  --concurrency 200
```

## See Also

- [DataSource Clone Testing](test-scenarios/datasource-clone.md) - Full VM creation guide
- [Configuration Options](configuration.md) - All available options
- [Output and Results](output-and-results.md) - Understanding test output

