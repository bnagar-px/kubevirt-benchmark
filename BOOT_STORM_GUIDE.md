# Boot Storm Testing Guide

## Overview

Boot storm testing measures VM startup performance when powering on multiple VMs simultaneously from a stopped state. This simulates real-world scenarios like:
- Recovery after planned maintenance
- Power restoration after outage
- Cluster restart scenarios
- Mass VM migration completion

## What is Boot Storm Testing?

A "boot storm" occurs when many VMs start simultaneously, creating high demand on:
- Storage I/O (reading boot images)
- Network resources (DHCP, DNS requests)
- Compute resources (CPU, memory allocation)
- Hypervisor scheduling

This test helps you understand:
1. How your infrastructure handles concurrent VM startups
2. Performance degradation under load
3. Bottlenecks in storage, network, or compute
4. Realistic recovery time objectives (RTO)

## How It Works

The boot storm test follows this workflow:

### Phase 1: Initial VM Creation
1. Creates all test namespaces in parallel batches
2. Creates and starts all VMs simultaneously
3. Measures time to Running state
4. Measures time to network readiness (ping)
5. Displays initial creation performance results

### Phase 2: Shutdown All VMs
1. Issues stop commands to all VMs in parallel
2. Waits for all VMIs to be deleted (VMs fully stopped)
3. Confirms all VMs are in stopped state

### Phase 3: Boot Storm (Simultaneous Startup)
1. Issues start commands to ALL VMs at once
2. Creates maximum load on infrastructure
3. Measures time to Running state for each VM
4. Measures time to network readiness for each VM
5. Displays boot storm performance results

### Phase 4: Comparison
Compare initial creation vs boot storm metrics to understand:
- Performance differences between cold start and warm start
- Impact of concurrent operations
- Storage backend behavior under load

## Usage

### Basic Boot Storm Test (Multi-Node)

```bash
cd datasource-clone

# VMs distributed across all nodes
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --boot-storm \
  --save-results
```

### Single Node Boot Storm Test

```bash
cd datasource-clone

# Auto-select a random node
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --boot-storm \
  --save-results

# Or specify a specific node
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --node-name worker-node-1 \
  --boot-storm \
  --save-results
```

### Advanced Boot Storm Test

```bash
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 100 \
  --vm-name rhel-9-vm \
  --namespace-prefix boot-storm-test \
  --namespace-batch-size 30 \
  --boot-storm \
  --concurrency 100 \
  --save-results \
  --log-file boot-storm-$(date +%Y%m%d-%H%M%S).log \
  --log-level INFO
```

### Command Options Explained

- `--boot-storm`: Enables boot storm testing (required)
- `--single-node`: Pins all VMs to a single node
- `--node-name worker-node-1`: Specifies which node to use (requires --single-node)
- `--namespace-batch-size 30`: Creates 30 namespaces in parallel (faster setup)
- `--concurrency 100`: Monitors up to 100 VMs in parallel
- `--start 1 --end 100`: Tests with 100 VMs
- `--save-results`: Saves detailed results (JSON and CSV) for dashboard generation

## Example Output

### Initial Creation Results
```
================================================================================
VM Creation Performance Test Results
================================================================================
Namespace                Running(s)      Ping(s)         Status
--------------------------------------------------------------------------------
boot-storm-test-1        8.45           11.23           Success
boot-storm-test-2        9.12           12.45           Success
boot-storm-test-3        8.89           11.98           Success
...
================================================================================
Statistics:
  Total VMs:              100
  Successful:             98
  Failed:                 2
  Avg Time to Running:    9.23s
  Avg Time to Ping:       12.45s
  Max Time to Running:    15.67s
  Max Time to Ping:       18.92s
================================================================================
```

### Boot Storm Results
```
================================================================================
BOOT STORM TEST - Shutdown and Power On All VMs
================================================================================

Phase 1: Stopping all VMs...
Stop commands issued in 2.34s

Phase 2: Waiting for all VMs to be fully stopped...
All VMs stopped in 45.67s
Successfully stopped: 98/100 VMs

Phase 3: Starting all VMs simultaneously (BOOT STORM)...
All start commands issued in 2.12s

Phase 4: Monitoring boot storm (concurrency: 100)...
Boot storm monitoring completed in 156.78s
Total boot storm duration: 204.57s

================================================================================
Boot Storm Performance Test Results
================================================================================
Namespace                Running(s)      Ping(s)         Status
--------------------------------------------------------------------------------
boot-storm-test-1        12.34          18.45           Success
boot-storm-test-2        15.67          22.89           Success
boot-storm-test-3        13.45          19.23           Success
...
================================================================================
Statistics:
  Total VMs:              98
  Successful:             96
  Failed:                 2
  Avg Time to Running:    14.56s
  Avg Time to Ping:       20.34s
  Max Time to Running:    28.91s
  Max Time to Ping:       35.67s
================================================================================
```

## Interpreting Results

### Key Metrics

1. **Time to Running**: How long until VM reaches Running state
   - Initial: ~9s average
   - Boot Storm: ~15s average
   - **Analysis**: 67% slower during boot storm (expected)

2. **Time to Ping**: How long until VM is network-reachable
   - Initial: ~12s average
   - Boot Storm: ~20s average
   - **Analysis**: 67% slower during boot storm

3. **Max Times**: Worst-case performance
   - Initial Max: ~16s to Running
   - Boot Storm Max: ~29s to Running
   - **Analysis**: Some VMs take 2x longer during boot storm

### What to Look For

#### Good Performance
- ✅ Boot storm times are 1.5-2x initial creation times
- ✅ All or most VMs start successfully
- ✅ Max times are within acceptable limits
- ✅ Consistent performance across VMs

#### Performance Issues
- ⚠️ Boot storm times are 3x+ initial creation times
- ⚠️ High failure rate during boot storm
- ⚠️ Very high max times (outliers)
- ⚠️ Wide variance in VM startup times

#### Critical Issues
- ❌ Boot storm times are 5x+ initial creation times
- ❌ Many VMs fail to start
- ❌ Timeouts during boot storm
- ❌ Storage or network errors

## Performance Tuning

### If Boot Storm Performance is Poor

1. **Storage Bottleneck**
   - Increase Portworx volume replication
   - Use faster storage tier
   - Enable storage caching
   - Distribute VMs across multiple storage pools

2. **Network Bottleneck**
   - Check DHCP server capacity
   - Verify network bandwidth
   - Check for network congestion
   - Review CNI plugin performance

3. **Compute Bottleneck**
   - Add more worker nodes
   - Increase node resources
   - Review CPU/memory overcommit ratios
   - Check for resource contention

4. **Hypervisor Bottleneck**
   - Tune KubeVirt settings
   - Adjust virt-launcher resources
   - Review QEMU/KVM settings
   - Check for I/O throttling

## Best Practices

### Test Planning

1. **Start Small**: Begin with 10-20 VMs, then scale up
2. **Baseline First**: Run without boot storm to establish baseline
3. **Multiple Runs**: Run tests multiple times for consistency
4. **Off-Peak Testing**: Run during maintenance windows
5. **Monitor Infrastructure**: Watch cluster metrics during tests

### Namespace Batch Size

- **Small clusters (< 10 nodes)**: Use batch size 10-20
- **Medium clusters (10-50 nodes)**: Use batch size 20-30
- **Large clusters (50+ nodes)**: Use batch size 30-50

### Concurrency Settings

- **Conservative**: Set concurrency = number of VMs / 2
- **Moderate**: Set concurrency = number of VMs
- **Aggressive**: Set concurrency = number of VMs * 2

## Troubleshooting

### VMs Fail to Stop
```bash
# Check VM status
kubectl get vm -n boot-storm-test-1

# Check VMI status
kubectl get vmi -n boot-storm-test-1

# Force delete if stuck
kubectl delete vmi rhel-9-vm -n boot-storm-test-1 --force --grace-period=0
```

### VMs Fail to Start During Boot Storm
```bash
# Check events
kubectl get events -n boot-storm-test-1 --sort-by='.lastTimestamp'

# Check virt-launcher pods
kubectl get pods -n boot-storm-test-1

# Check storage
kubectl get pvc -n boot-storm-test-1
```

### Timeout During Boot Storm
- Increase `--ping-timeout` (default: 600s)
- Reduce number of VMs
- Check cluster resources
- Review storage performance

## Real-World Scenarios

### Scenario 1: Node-Level Capacity Testing
**Goal**: Determine how many VMs a single node can handle during boot storm

```bash
python3 measure-vm-creation-time.py \
  --start 1 --end 50 \
  --single-node \
  --boot-storm \
  --namespace-batch-size 25 \
  --save-results
```

### Scenario 2: Planned Maintenance
**Goal**: Understand recovery time after maintenance window

```bash
python3 measure-vm-creation-time.py \
  --start 1 --end 200 \
  --boot-storm \
  --namespace-batch-size 40 \
  --save-results
```

### Scenario 3: Disaster Recovery
**Goal**: Validate RTO for DR scenarios

```bash
python3 measure-vm-creation-time.py \
  --start 1 --end 500 \
  --boot-storm \
  --concurrency 200 \
  --ping-timeout 1200 \
  --save-results
```

### Scenario 4: Storage Backend Comparison
**Goal**: Compare Portworx vs FADA performance

```bash
# Test with standard Portworx (if you have a registry-clone setup)
cd registry-clone
python3 measure-vm-creation-time.py \
  --start 1 --end 100 \
  --boot-storm \
  --save-results

# Test with FADA
cd ../datasource-clone
python3 measure-vm-creation-time.py \
  --start 1 --end 100 \
  --boot-storm \
  --save-results
```

### Scenario 5: Single Node vs Multi-Node Comparison
**Goal**: Compare boot storm performance on single node vs distributed

```bash
# Single node test
python3 measure-vm-creation-time.py \
  --start 1 --end 50 \
  --single-node \
  --boot-storm \
  --save-results \
  --log-file single-node-boot-storm.log

# Multi-node test
python3 measure-vm-creation-time.py \
  --start 1 --end 50 \
  --boot-storm \
  --save-results \
  --log-file multi-node-boot-storm.log
```

## Cleanup

The test automatically cleans up if you use `--cleanup`:

```bash
python3 measure-vm-creation-time.py \
  --start 1 --end 50 \
  --boot-storm \
  --save-results \
  --cleanup
```

Manual cleanup:
```bash
# Delete all test namespaces
for i in {1..50}; do
  kubectl delete namespace boot-storm-test-$i &
done
wait
```

## Visualizing Results

After running boot storm tests with `--save-results`, generate an interactive dashboard to visualize your results:

```bash
# Generate dashboard from all saved results
python3 dashboard/generate_dashboard.py \
  --days 30 \
  --base-dir results \
  --cluster-info dashboard/cluster_info.yaml \
  --output-html boot-storm-dashboard.html
```

The dashboard will show:
- Boot storm performance charts comparing creation vs boot storm metrics
- Detailed tables with all timing data
- Performance trends across multiple test runs
- Comparison across different VM counts and configurations

See [dashboard/README.md](dashboard/README.md) for detailed dashboard usage.

## Summary

Boot storm testing is essential for:
- ✅ Understanding real-world recovery scenarios
- ✅ Validating infrastructure capacity
- ✅ Identifying performance bottlenecks
- ✅ Planning for disaster recovery
- ✅ Capacity planning and sizing

**Recommended Workflow:**
1. Run boot storm tests with `--save-results`
2. Generate interactive dashboard to visualize results
3. Analyze performance trends and identify bottlenecks
4. Run tests regularly to ensure your infrastructure can handle concurrent VM startups!

