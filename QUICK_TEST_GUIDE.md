# Quick Test Guide - How to Run VM Creation Tests

## Prerequisites

### 1. Deploy SSH Test Pod (One-time setup)
```bash
kubectl apply -f examples/ssh-pod.yaml
kubectl wait --for=condition=Ready pod/ssh-test-pod -n default --timeout=300s
```

### 2. Verify Prerequisites
```bash
# Check kubectl access
kubectl cluster-info
kubectl get nodes

# Verify SSH pod is running
kubectl get pod ssh-test-pod -n default
```

## Test Scenarios

### Scenario 1: Quick Test (10 VMs)

**Purpose**: Verify everything works

```bash
cd registry-clone

python3 measure-vm-creation-time.py \
  --start 1 \
  --end 10 \
  --vm-name rhel-9-vm
```

**Expected Duration**: 2-3 minutes

---

### Scenario 2: Standard Test (50 VMs)

**Purpose**: Typical performance test

```bash
cd registry-clone

python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --namespace-batch-size 25 \
  --log-file results-$(date +%Y%m%d-%H%M%S).log
```

**Expected Duration**: 5-10 minutes

---

### Scenario 3: Large Scale Test (100 VMs)

**Purpose**: Stress test infrastructure

```bash
cd registry-clone

python3 measure-vm-creation-time.py \
  --start 1 \
  --end 100 \
  --vm-name rhel-9-vm \
  --namespace-batch-size 30 \
  --concurrency 100 \
  --log-file results-$(date +%Y%m%d-%H%M%S).log
```

**Expected Duration**: 10-20 minutes

---

### Scenario 4: Boot Storm Test (50 VMs, Multi-Node)

**Purpose**: Test concurrent VM startup across all nodes

```bash
cd registry-clone

python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --boot-storm \
  --namespace-batch-size 25 \
  --log-file boot-storm-$(date +%Y%m%d-%H%M%S).log
```

**Expected Duration**: 10-15 minutes (includes shutdown and restart)

**What it does**:
1. Creates and starts 50 VMs (distributed across nodes)
2. Measures initial creation performance
3. Stops all VMs
4. Starts all VMs simultaneously (boot storm)
5. Measures boot storm performance
6. Compares results

---

### Scenario 4b: Single Node Boot Storm Test (50 VMs)

**Purpose**: Test concurrent VM startup on a single node

```bash
cd registry-clone

# Auto-select a random node
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --boot-storm \
  --namespace-batch-size 25 \
  --log-file single-node-boot-storm-$(date +%Y%m%d-%H%M%S).log

# Or specify a specific node
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --node-name worker-node-1 \
  --boot-storm \
  --namespace-batch-size 25 \
  --log-file single-node-boot-storm-$(date +%Y%m%d-%H%M%S).log
```

**Expected Duration**: 10-15 minutes (includes shutdown and restart)

**What it does**:
1. Selects a single node (random or specified)
2. Creates and starts 50 VMs on that node
3. Measures initial creation performance
4. Stops all VMs
5. Starts all VMs simultaneously on the same node (boot storm)
6. Measures boot storm performance
7. Compares results

**Use Case**: Node-level capacity testing and boot storm performance

---

### Scenario 5: DataSource Test (FADA)

**Purpose**: Test with Pure FlashArray Direct Access

```bash
cd datasource-clone

# First, update vm-template.yaml with your DataSource name
# Edit: sourceRef.name: your-datasource-name

python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --namespace-batch-size 25 \
  --log-file fada-results-$(date +%Y%m%d-%H%M%S).log
```

**Expected Duration**: 5-10 minutes

---

### Scenario 6: Complete Test with Cleanup

**Purpose**: Full test that cleans up after itself

```bash
cd registry-clone

python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --boot-storm \
  --cleanup \
  --log-file complete-test-$(date +%Y%m%d-%H%M%S).log
```

**Expected Duration**: 10-15 minutes

**Note**: Automatically deletes all test namespaces after completion

---

## Understanding the Output

### Phase 1: Namespace Creation
```
[INFO] Creating namespaces kubevirt-perf-test-1 to kubevirt-perf-test-50 in batches of 25...
[INFO] Namespace creation complete: 50 successful, 0 failed
```
✅ **Fast**: With parallel creation, 50 namespaces in ~2-3 seconds

### Phase 2: VM Creation
```
[INFO] Phase 1: Creating all VMs in parallel...
[INFO] Created 50 VMs in 3.45s
```
✅ **Parallel**: All VMs created simultaneously

### Phase 3: Monitoring
```
[INFO] Phase 2: Monitoring VMs (concurrency: 50)...
[INFO] [kubevirt-perf-test-1] VM Running at 8.45s
[INFO] [kubevirt-perf-test-1] VMI IP: 10.244.1.23
[INFO] [kubevirt-perf-test-1] Ping successful after 11.23s
```
✅ **Real-time**: See each VM's progress

### Phase 4: Summary
```
================================================================================
VM Creation Performance Test Results
================================================================================
Namespace                Running(s)      Ping(s)         Status
--------------------------------------------------------------------------------
kubevirt-perf-test-1     8.45           11.23           Success
kubevirt-perf-test-2     9.12           12.45           Success
...
================================================================================
Statistics:
  Total VMs:              50
  Successful:             48
  Failed:                 2
  Avg Time to Running:    9.23s
  Avg Time to Ping:       12.45s
  Max Time to Running:    15.67s
  Max Time to Ping:       18.92s
================================================================================
```
✅ **Detailed**: Complete statistics and per-VM results

### Boot Storm Output (if enabled)
```
================================================================================
BOOT STORM TEST - Shutdown and Power On All VMs
================================================================================

Phase 1: Stopping all VMs...
Stop commands issued in 2.34s

Phase 2: Waiting for all VMs to be fully stopped...
All VMs stopped in 45.67s

Phase 3: Starting all VMs simultaneously (BOOT STORM)...
All start commands issued in 2.12s

Phase 4: Monitoring boot storm...
Boot storm monitoring completed in 156.78s

================================================================================
Boot Storm Performance Test Results
================================================================================
[Similar table with boot storm metrics]
```

## Command-Line Options Reference

### Essential Options
| Option | Description | Example |
|--------|-------------|---------|
| `--start` | Starting namespace index | `--start 1` |
| `--end` | Ending namespace index | `--end 50` |
| `--vm-name` | VM resource name | `--vm-name rhel-9-vm` |

### Performance Options
| Option | Description | Default | Recommendation |
|--------|-------------|---------|----------------|
| `--namespace-batch-size` | Parallel namespace creation | 20 | 25-30 for large tests |
| `--concurrency` | Parallel monitoring threads | 50 | Match number of VMs |
| `--poll-interval` | Status check interval (seconds) | 1 | Keep at 1 |
| `--ping-timeout` | Ping timeout (seconds) | 600 | Increase for slow networks |

### Testing Options
| Option | Description | Default |
|--------|-------------|---------|
| `--boot-storm` | Enable boot storm testing | false |
| `--single-node` | Run all VMs on a single node | false |
| `--node-name` | Specific node to use (requires --single-node) | auto-select |
| `--cleanup` | Auto-delete after test | false |
| `--skip-namespace-creation` | Use existing namespaces | false |

### Logging Options
| Option | Description | Default |
|--------|-------------|---------|
| `--log-file` | Save logs to file | stdout |
| `--log-level` | DEBUG/INFO/WARNING/ERROR | INFO |

## Troubleshooting

### Issue: SSH pod not found
```bash
# Deploy SSH pod
kubectl apply -f examples/ssh-pod.yaml

# Wait for it to be ready
kubectl wait --for=condition=Ready pod/ssh-test-pod -n default --timeout=300s
```

### Issue: VMs not starting
```bash
# Check events in a namespace
kubectl get events -n kubevirt-perf-test-1 --sort-by='.lastTimestamp'

# Check VM status
kubectl get vm -n kubevirt-perf-test-1

# Check VMI status
kubectl get vmi -n kubevirt-perf-test-1

# Check PVC status
kubectl get pvc -n kubevirt-perf-test-1
```

### Issue: Ping timeouts
```bash
# Increase timeout
python3 measure-vm-creation-time.py \
  --start 1 --end 10 \
  --ping-timeout 1200

# Check VM IP
kubectl get vmi rhel-9-vm -n kubevirt-perf-test-1 -o jsonpath='{.status.interfaces[0].ipAddress}'

# Manual ping test
kubectl exec -n default ssh-test-pod -- ping -c 3 <VM-IP>
```

### Issue: Namespace creation fails
```bash
# Check RBAC permissions
kubectl auth can-i create namespace

# Check for existing namespaces
kubectl get ns | grep kubevirt-perf-test

# Delete stuck namespaces
kubectl delete ns kubevirt-perf-test-1 --force --grace-period=0
```

## Cleanup

### Automatic Cleanup
Use `--cleanup` flag:
```bash
python3 measure-vm-creation-time.py --start 1 --end 50 --cleanup
```

### Manual Cleanup
```bash
# Delete specific range
for i in {1..50}; do
  kubectl delete namespace kubevirt-perf-test-$i &
done
wait

# Delete all test namespaces
kubectl get ns | grep kubevirt-perf-test | awk '{print $1}' | xargs kubectl delete ns
```

## Tips for Best Results

### 1. Start Small
- Begin with 10 VMs to verify setup
- Gradually increase to 50, 100, etc.

### 2. Use Appropriate Batch Sizes
- Small clusters: `--namespace-batch-size 10`
- Medium clusters: `--namespace-batch-size 20-30`
- Large clusters: `--namespace-batch-size 40-50`

### 3. Monitor Cluster Resources
```bash
# Watch node resources
kubectl top nodes

# Watch pod resources
kubectl top pods -A

# Watch storage
kubectl get pvc -A | grep kubevirt-perf-test
```

### 4. Save Logs
Always use `--log-file` for detailed analysis:
```bash
--log-file results-$(date +%Y%m%d-%H%M%S).log
```

### 5. Run Multiple Times
Run tests 3-5 times and average results for consistency.

## Next Steps

1. ✅ Run quick test (10 VMs) to verify setup
2. ✅ Run standard test (50 VMs) for baseline
3. ✅ Run boot storm test to understand concurrent startup
4. ✅ Compare results across different storage backends
5. ✅ Document your findings

## Need Help?

- Check [README.md](README.md) for detailed documentation
- See [BOOT_STORM_GUIDE.md](BOOT_STORM_GUIDE.md) for boot storm details
- Review [SETUP.md](SETUP.md) for setup instructions
- Check logs with `--log-level DEBUG` for troubleshooting

Happy testing! 🚀

