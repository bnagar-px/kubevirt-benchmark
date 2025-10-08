# KubeVirt Performance Testing Suite

A comprehensive performance testing toolkit for KubeVirt virtual machines running on OpenShift Container Platform (OCP) with Portworx storage.

## Overview

This suite provides automated performance testing tools to measure and validate KubeVirt VM provisioning, boot times, network readiness, and failure recovery scenarios. It's designed for production environments running OpenShift Virtualization with Portworx as the storage backend.

## Features

- **VM Creation Performance Testing**: Measure VM provisioning and boot times at scale
- **Boot Storm Testing**: Test VM startup performance when powering on multiple VMs simultaneously
- **Live Migration Testing**: Measure VM live migration performance across different scenarios
- **Single Node Testing**: Pin all VMs to a single node for node-level capacity testing
- **Network Readiness Validation**: Test VM network connectivity and measure time-to-ready
- **Failure and Recovery Testing**: Validate VM recovery times after node failures
- **Parallel Execution**: Support for testing hundreds of VMs concurrently
- **Parallel Namespace Creation**: Create namespaces in batches for faster test setup
- **Multiple Storage Backends**: Support for both standard Portworx and Pure FlashArray Direct Access (FADA)
- **Comprehensive Logging**: Detailed logs with timestamps and error tracking
- **Flexible Configuration**: Command-line arguments for easy customization

## Prerequisites

### Software Requirements
- OpenShift Container Platform 4.x with OpenShift Virtualization
- Portworx Enterprise 2.x or later
- Python 3.6 or later
- kubectl CLI configured with cluster access
- Bash shell (for helper scripts)

### Cluster Requirements
- Sufficient cluster resources to run test VMs
- Portworx storage classes configured
- OpenShift Virtualization operator installed
- Network connectivity between test pods and VMs

### Permissions
The user running these tests needs:
- Ability to create/delete namespaces
- Ability to create/delete VMs, VMIs, and PVCs
- Ability to exec into pods (for ping tests)
- Ability to patch VM resources (for FAR tests)

## Repository Structure

```
kubevirt-performance-testing/
├── README.md                          # This file
├── QUICKSTART.md                      # 5-minute quick start guide
├── SETUP.md                           # Detailed setup instructions
├── CONTRIBUTING.md                    # Contribution guidelines
├── LICENSE                            # Apache 2.0 License
├── requirements.txt                   # Python dependencies
│
├── datasource-clone/                  # DataSource-based VM provisioning tests
│   ├── measure-vm-creation-time.py   # Main test script
│   └── vm-template.yaml              # VM YAML template
│
├── migration/                         # Live migration performance tests
│   └── measure-vm-migration-time.py  # Main migration test script
│
├── failure-recovery/                  # Failure and recovery tests
│   ├── measure-recovery-time.py      # Recovery measurement script
│   ├── run-far-test.sh               # FAR test orchestration
│   ├── patch-vms.sh                  # VM patching helper
│   └── far-template.yaml             # FAR configuration template
│
├── utils/                             # Shared utilities
│   ├── common.py                     # Common functions and logging
│   └── README.md                     # Utils documentation
│
└── examples/                          # Example configurations
    ├── storage-classes/              # Sample StorageClass definitions
    ├── vm-templates/                 # Sample VM templates
    ├── ssh-pod.yaml                  # SSH test pod for network tests
    ├── sequential-migration.sh       # Sequential migration example
    ├── parallel-migration.sh         # Parallel migration example
    ├── evacuation-scenario.sh        # Node evacuation example
    └── round-robin-migration.sh      # Round-robin migration example
```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/kubevirt-perf-testing.git
cd kubevirt-perf-testing
```

### 2. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 3. Configure Your Environment

Ensure kubectl is configured to access your OpenShift cluster:

```bash
kubectl cluster-info
kubectl get nodes
```

### 4. Run a Basic Test

Test VM creation with 10 VMs:

```bash
cd datasource-clone
python3 measure-vm-creation-time.py --start 1 --end 10 --vm-name rhel-9-vm
```

## Testing Scenarios

### Scenario 1: DataSource-Based VM Provisioning

Tests VM creation using KubeVirt DataSource with Pure FlashArray Direct Access (FADA).

**Use Case**: Optimal for Pure Storage FlashArray backends with direct volume access.

**Example**:
```bash
cd datasource-clone

# Run performance test
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 100 \
  --vm-name rhel-9-vm \
  --log-file results-$(date +%Y%m%d-%H%M%S).log
```

### Scenario 2: Single Node Boot Storm Testing

Tests VM startup performance on a single node when powering on multiple VMs simultaneously.

**Use Case**: Validates node-level capacity and boot storm performance (e.g., how many VMs can a single node handle during boot storm).

**Example**:
```bash
cd datasource-clone

# Run test on a single node (auto-selected)
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --boot-storm \
  --log-file single-node-boot-storm-$(date +%Y%m%d-%H%M%S).log

# Or specify a specific node
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --node-name worker-node-1 \
  --boot-storm \
  --log-file single-node-boot-storm-$(date +%Y%m%d-%H%M%S).log
```

**What it does**:
1. Selects a single node (random or specified)
2. Creates and starts all VMs on that node (initial test)
3. Stops all VMs and waits for complete shutdown
4. Starts all VMs simultaneously on the same node (boot storm)
5. Measures time to Running state and time to ping for each VM
6. Provides separate statistics for initial creation and boot storm

### Scenario 3: Multi-Node Boot Storm Testing

Tests VM startup performance across all nodes when powering on multiple VMs simultaneously.

**Use Case**: Validates cluster-wide performance under boot storm conditions (e.g., after maintenance, power outage recovery).

**Example**:
```bash
cd datasource-clone

# Run test with boot storm (VMs distributed across all nodes)
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 100 \
  --vm-name rhel-9-vm \
  --boot-storm \
  --log-file boot-storm-$(date +%Y%m%d-%H%M%S).log
```

**What it does**:
1. Creates and starts all VMs (distributed across nodes)
2. Stops all VMs and waits for complete shutdown
3. Starts all VMs simultaneously (boot storm)
4. Measures time to Running state and time to ping for each VM
5. Provides separate statistics for initial creation and boot storm

### Scenario 4: Live Migration Testing

Tests VM live migration performance across different scenarios.

**Use Case**: Validates migration performance for node maintenance, load balancing, and disaster recovery scenarios.

**Example - Sequential Migration**:
```bash
cd migration

# Migrate 10 VMs one by one from worker-1 to worker-2
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 10 \
  --source-node worker-1 \
  --target-node worker-2
```

**Example - Parallel Migration**:
```bash
# Migrate 50 VMs in parallel with 10 concurrent migrations
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 50 \
  --source-node worker-1 \
  --target-node worker-2 \
  --parallel \
  --concurrency 10
```

**Example - Node Evacuation (Specific Node)**:
```bash
# Evacuate all VMs from worker-3 before maintenance
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 100 \
  --source-node worker-3 \
  --evacuate \
  --concurrency 20
```

**Example - Node Evacuation (Auto-Select Busiest)**:
```bash
# Automatically find and evacuate the busiest node
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 100 \
  --evacuate \
  --auto-select-busiest \
  --concurrency 20
```

**Example - Round-Robin Migration**:
```bash
# Distribute VMs across all nodes for load balancing
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 100 \
  --round-robin \
  --concurrency 20
```

**What it does**:
1. Validates VMs are running
2. Triggers live migration (sequential, parallel, evacuation, or round-robin)
3. Monitors migration progress
4. Measures migration duration (both observed and VMIM timestamps)
5. Validates network connectivity after migration
6. Provides detailed statistics with dual timing measurements

**See example scripts**: `examples/sequential-migration.sh`, `examples/parallel-migration.sh`, `examples/evacuation-scenario.sh`, `examples/round-robin-migration.sh`

---

### Scenario 5: Failure and Recovery Testing

Tests VM recovery time after simulated node failures using Fence Agents Remediation (FAR).

**Use Case**: Validates high availability and disaster recovery capabilities.

**Example**:
```bash
cd failure-recovery

# Edit far-template.yaml with your node details
vim far-template.yaml

# Run the complete FAR test
./run-far-test.sh \
  --start 1 \
  --end 60 \
  --node-name worker-node-1 \
  --vm-name rhel-9-vm
```

## Configuration Options

### VM Creation Tests

| Option | Description | Default |
|--------|-------------|---------|
| `--start` | Starting namespace index | 1 |
| `--end` | Ending namespace index | 100 |
| `--vm-name` | VM resource name | rhel-9-vm |
| `--concurrency` | Max parallel monitoring threads | 50 |
| `--ssh-pod` | Pod name for ping tests | ssh-test-pod |
| `--ssh-pod-ns` | Namespace of SSH pod | default |
| `--poll-interval` | Seconds between status checks | 1 |
| `--ping-timeout` | Ping timeout in seconds | 600 |
| `--log-file` | Output log file path | stdout |
| `--log-level` | Logging level (DEBUG/INFO/WARNING/ERROR) | INFO |
| `--namespace-prefix` | Prefix for test namespaces | kubevirt-perf-test |
| `--namespace-batch-size` | Namespaces to create in parallel | 20 |
| `--boot-storm` | Enable boot storm testing | false |
| `--single-node` | Run all VMs on a single node | false |
| `--node-name` | Specific node to use (requires --single-node) | auto-select |
| `--cleanup` | Delete resources after test | false |

### Recovery Tests

| Option | Description | Default |
|--------|-------------|---------|
| `--start` | Starting namespace index | 1 |
| `--end` | Ending namespace index | 5 |
| `--vm-name` | VMI resource name | rhel-9-vm |
| `--concurrency` | Max parallel threads | 10 |
| `--ssh-pod` | Pod name for ping tests | ssh-test-pod |
| `--ssh-pod-ns` | Namespace of SSH pod | default |
| `--poll-interval` | Seconds between polls | 1 |
| `--log-file` | Output log file path | stdout |
| `--log-level` | Logging level | INFO |

## Output and Results

### Console Output

Tests provide real-time progress updates:
```
[INFO] 2024-01-15 10:30:00 - Starting VM creation test
[INFO] 2024-01-15 10:30:00 - Creating namespaces kubevirt-perf-test-1 to kubevirt-perf-test-100
[INFO] 2024-01-15 10:30:05 - Dispatching VM creation in parallel
[INFO] 2024-01-15 10:30:15 - [kubevirt-perf-test-1] VM Running at 8.45s
[INFO] 2024-01-15 10:30:18 - [kubevirt-perf-test-1] Ping success at 11.23s
...
```

### Summary Report

At completion, a summary table is displayed:

```
Performance Test Summary
================================================================================
Namespace                Running(s)      Ping(s)         Status
--------------------------------------------------------------------------------
kubevirt-perf-test-1     8.45           11.23           Success
kubevirt-perf-test-2     9.12           12.45           Success
kubevirt-perf-test-3     8.89           11.98           Success
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
  Total Test Duration:    125.34s
================================================================================
```

### Log Files

Detailed logs are saved to the specified log file with:
- Timestamps for all operations
- Error messages and stack traces
- Resource creation/deletion events
- Performance metrics

## Troubleshooting

### Common Issues

**Issue**: VMs fail to reach Running state
- Check Portworx storage class is available: `kubectl get sc`
- Verify sufficient cluster resources: `kubectl top nodes`
- Check VM events: `kubectl describe vm <vm-name> -n <namespace>`

**Issue**: Ping tests timeout
- Verify SSH pod exists and is running: `kubectl get pod <ssh-pod> -n <namespace>`
- Check network policies allow pod-to-pod communication
- Verify VM has cloud-init configured correctly

**Issue**: Permission denied errors
- Ensure your user has cluster-admin or equivalent permissions
- Check RBAC policies: `kubectl auth can-i create vm --all-namespaces`

**Issue**: Golden image PVCs not ready
- Check DataVolume status: `kubectl get dv -n openshift-virtualization-os-images`
- Verify registry image stream exists: `kubectl get imagestream -n openshift-virtualization-os-images`
- Check CDI operator logs: `kubectl logs -n openshift-cnv -l name=cdi-operator`

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
python3 measure-vm-creation-time.py --log-level DEBUG --start 1 --end 5
```

## Best Practices

1. **Start Small**: Begin with 5-10 VMs to validate your setup before scaling
2. **Monitor Resources**: Watch cluster resource utilization during tests
3. **Use Dedicated Namespaces**: Tests create namespaces with predictable names for easy cleanup
4. **Save Results**: Always use `--log-file` to preserve test results
5. **Cleanup**: Remove test resources after completion to free cluster resources
6. **Network Testing**: Deploy an SSH pod in advance for ping tests

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Contact: [your-support-email]
- Documentation: [your-docs-url]

## Acknowledgments

- OpenShift Virtualization Team
- Portworx Engineering
- KubeVirt Community

