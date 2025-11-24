# KubeVirt Performance Testing Suite

A comprehensive performance testing toolkit for KubeVirt virtual machines running on OpenShift Container Platform (OCP) with Portworx storage.

## Overview

This suite provides automated performance testing tools to measure and validate KubeVirt VM provisioning, boot times, network readiness, and failure recovery scenarios. It's designed for production environments running OpenShift Virtualization with Portworx as the storage backend.

## New: virtbench CLI

The suite now includes **virtbench**, a unified command-line interface that provides a professional, kubectl-like experience for all benchmarks.

```bash
# Install the CLI
./install.sh

# Run benchmarks with a single command
virtbench capacity-benchmark --storage-class fada-raw-sc --vms 5
virtbench datasource-clone --storage-class fada-raw-sc --vms 50
virtbench migration --storage-class fada-raw-sc --namespaces 10
```

See [CLI_README.md](CLI_README.md) for complete CLI documentation.

## Features

- **Unified CLI Interface**: Professional kubectl-like CLI with shell completion
- **VM Creation Performance Testing**: Measure VM provisioning and boot times at scale
- **Capacity Benchmark Testing**: Test cluster limits with 5-phase testing (create, resize, restart, snapshot, migrate)
- **Boot Storm Testing**: Test VM startup performance when powering on multiple VMs simultaneously
- **Live Migration Testing**: Measure VM live migration performance across different scenarios
- **Capacity Benchmark Testing**: Test cluster capacity limits with comprehensive VM operations (create, resize, restart, snapshot, migrate)
- **Single Node Testing**: Pin all VMs to a single node for node-level capacity testing
- **Network Readiness Validation**: Test VM network connectivity and measure time-to-ready
- **Failure and Recovery Testing**: Validate VM recovery times after node failures
- **VM Snapshot Testing**: Test VM snapshot creation and readiness
- **Volume Resize Testing**: Test PVC expansion capabilities
- **Parallel Execution**: Support for testing hundreds of VMs concurrently
- **Parallel Namespace Creation**: Create namespaces in batches for faster test setup
- **Multiple Storage Backends**: Support for both standard Portworx and Pure FlashArray Direct Access (FADA)
- **Comprehensive Logging**: Detailed logs with timestamps and error tracking
- **Flexible Configuration**: Command-line arguments for easy customization
- **Interactive Results Dashboard**: Auto-generate rich HTML dashboards for all test results

## Prerequisites

### Software Requirements
- OpenShift Container Platform 4.x with OpenShift Virtualization
- Portworx Enterprise 2.x or later
- Python 3.6 or later
- Go 1.21 or later (for building virtbench CLI)
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
kubevirt-benchmark-suite/
├── README.md                          # This file
├── CLI_README.md                      # virtbench CLI documentation
├── QUICKSTART.md                      # 5-minute quick start guide
├── SETUP.md                           # Detailed setup instructions
├── CLEANUP_GUIDE.md                   # Comprehensive cleanup guide
├── CONTRIBUTING.md                    # Contribution guidelines
├── LICENSE                            # Apache 2.0 License
├── requirements.txt                   # Python dependencies
├── go.mod                             # Go module file
├── go.sum                             # Go dependencies
├── Makefile                           # Build automation
├── install.sh                         # Installation script
│
├── cmd/virtbench/                     # virtbench CLI source code
│   ├── main.go                       # CLI entry point
│   ├── root.go                       # Root command
│   ├── common.go                     # Common utilities
│   ├── datasource_clone.go           # DataSource clone subcommand
│   ├── migration.go                  # Migration subcommand
│   ├── capacity_benchmark.go         # Capacity benchmark subcommand
│   ├── failure_recovery.go           # Failure recovery subcommand
│   ├── validate_cluster.go           # Cluster validation subcommand
│   ├── version.go                    # Version subcommand
│   └── completion.go                 # Shell completion subcommand
│
├── bin/                               # Built binaries (generated)
│   └── virtbench                     # virtbench CLI binary
│
├── dashboard/                        # Interactive dashboard for test results
│   └── generate_dashboard.py         # Dashboard generation script
│   
├── datasource-clone/                 # DataSource-based VM provisioning tests
│   └── measure-vm-creation-time.py   # Main test script
│
├── migration/                         # Live migration performance tests
│   └── measure-vm-migration-time.py  # Main migration test script
│
├── capacity-benchmark/                # Capacity benchmark tests
│   ├── measure-capacity.py           # Main capacity test script
│   └── README.md                     # Capacity benchmark documentation
│
├── failure-recovery/                  # Failure and recovery tests
│   ├── measure-recovery-time.py      # Recovery measurement script
│   ├── run-far-test.sh               # FAR test orchestration
│   ├── patch-vms.sh                  # VM patching helper
│   └── far-template.yaml             # FAR configuration template
│
├── utils/                             # Shared utilities
│   ├── common.py                     # Common functions and logging
│   ├── validate_cluster.py           # Cluster validation script
│   ├── apply_template.sh             # Template helper script
│   └── README.md                     # Utils documentation
│
└── examples/                          # Example configurations
    ├── storage-classes/              # Sample StorageClass definitions
    │   └── portworx/                 # Portworx storage classes
    │       ├── portworx-fada-sc.yaml # Pure FlashArray Direct Access SC
    │       └── portworx-raw-sc.yaml  # Standard Portworx SC
    ├── vm-templates/                 # VM template files
    │   └── vm-template.yaml          # Templated VM configuration
    ├── ssh-pod.yaml                  # SSH test pod for network tests
    ├── sequential-migration.sh       # Sequential migration example
    ├── parallel-migration.sh         # Parallel migration example
    ├── evacuation-scenario.sh        # Node evacuation example
    └── round-robin-migration.sh      # Round-robin migration example
```

## Quick Start

### Option 1: Using virtbench CLI (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/kubevirt-benchmark-suite.git
cd kubevirt-benchmark-suite

# 2. Install virtbench CLI
./install.sh

# 3. Create SSH pod for ping tests (required for network validation)
kubectl apply -f examples/ssh-pod.yaml
kubectl wait --for=condition=Ready pod/ssh-test-pod -n default --timeout=300s

# 4. Validate your cluster
virtbench validate-cluster --storage-class fada-raw-sc

# 5. Run a benchmark
virtbench capacity-benchmark --storage-class fada-raw-sc --vms 5 --max-iterations 3
```

See [CLI_README.md](CLI_README.md) for complete CLI documentation.

### Option 2: Using Python Scripts Directly

```bash
# 1. Clone the repository
git clone https://github.com/your-org/kubevirt-benchmark-suite.git
cd kubevirt-benchmark-suite

# 2. Install Python dependencies
pip3 install -r requirements.txt

# 3. Create SSH pod for ping tests (required for network validation)
kubectl apply -f examples/ssh-pod.yaml
kubectl wait --for=condition=Ready pod/ssh-test-pod -n default --timeout=300s

# 3. Validate your cluster
python3 utils/validate_cluster.py --storage-class portworx-fada-sc

# 4. Configure VM templates
./utils/apply_template.sh \
  --output /tmp/my-vm.yaml \
  --vm-name my-test-vm \
  --storage-class portworx-fada-sc \
  --memory 4Gi \
  --cpu-cores 2

# 5. Run a basic test
cd datasource-clone
python3 measure-vm-creation-time.py --start 1 --end 10 --vm-name rhel-9-vm
```

See [TEMPLATE_GUIDE.md](TEMPLATE_GUIDE.md) for detailed template usage.

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
  --save-results \
  --log-file results-$(date +%Y%m%d-%H%M%S).log
```

### Scenario 2: Single Node Boot Storm Testing

Tests VM startup performance on a single node when powering on multiple VMs simultaneously.

**Use Case**: Validates node-level capacity and boot storm performance (e.g., how many VMs can a single node handle during boot storm).

**Example (virtbench CLI)**:
```bash
# Run test on a single node (auto-selected)
virtbench datasource-clone \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --boot-storm \
  --log-file single-node-boot-storm-$(date +%Y%m%d-%H%M%S).log

# Or specify a specific node
virtbench datasource-clone \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --node-name worker-node-1 \
  --boot-storm \
  --log-file single-node-boot-storm-$(date +%Y%m%d-%H%M%S).log
```

**Example (Python script)**:
```bash
cd datasource-clone

# Run test on a single node (auto-selected)
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --boot-storm \
  --save-results \
  --log-file single-node-boot-storm-$(date +%Y%m%d-%H%M%S).log

# Or specify a specific node
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --node-name worker-node-1 \
  --boot-storm \
  --save-results \
  --log-file single-node-boot-storm-$(date +%Y%m%d-%H%M%S).log

# Save results in JSON and CSV format to a directory
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --node-name worker-node-1 \
  --boot-storm \
  --save-results
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

**Example (virtbench CLI)**:
```bash
# Run test with boot storm (VMs distributed across all nodes)
virtbench datasource-clone \
  --start 1 \
  --end 100 \
  --vm-name rhel-9-vm \
  --boot-storm \
  --log-file boot-storm-$(date +%Y%m%d-%H%M%S).log
```

**Example (Python script)**:
```bash
cd datasource-clone

# Run test with boot storm (VMs distributed across all nodes)
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 100 \
  --vm-name rhel-9-vm \
  --boot-storm \
  --save-results \
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
  --target-node worker-2 \
  --save-results
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
  --concurrency 10 \
  --save-results
```

**Example - Parallel Migration with Advanced Options**:
```bash
# High-scale parallel migration with interleaved scheduling and custom timeout
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 200 \
  --parallel \
  --concurrency 50 \
  --skip-ping \
  --save-results \
  --migration-timeout 1000 \
  --px-version 3.5.0-run2-optimized \
  --interleaved-scheduling
```

**Example - Node Evacuation (Specific Node)**:
```bash
# Evacuate all VMs from worker-3 before maintenance
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 100 \
  --source-node worker-3 \
  --evacuate \
  --concurrency 20 \
  --save-results
```

**Example - Node Evacuation (Auto-Select Busiest)**:
```bash
# Automatically find and evacuate the busiest node
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 100 \
  --evacuate \
  --auto-select-busiest \
  --concurrency 20 \
  --save-results
```

**Example - Round-Robin Migration**:
```bash
# Distribute VMs across all nodes for load balancing
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 100 \
  --round-robin \
  --concurrency 20 \
  --save-results
```

**What it does**:
1. Validates VMs are running
2. Triggers live migration (sequential, parallel, evacuation, or round-robin)
3. Monitors migration progress
4. Measures migration duration (both observed and VMIM timestamps)
5. Validates network connectivity after migration
6. Provides detailed statistics with dual timing measurements

**See example scripts**: `examples/sequential-migration.sh`, `examples/parallel-migration.sh`, `examples/evacuation-scenario.sh`, `examples/round-robin-migration.sh`

**Cleanup after migration tests**:
```bash
# Clean up VMIMs only (VMs remain)
python3 measure-vm-migration-time.py --start 1 --end 100 --cleanup

# Clean up everything if VMs were created by the test
python3 measure-vm-migration-time.py --start 1 --end 100 --create-vms --cleanup
```

---

### Scenario 5: Capacity Benchmark Testing

Tests cluster capacity limits by running comprehensive VM operations in a loop until failure.

**Use Case**: Discover maximum VM capacity, test volume expansion limits, validate snapshot functionality, and stress-test the cluster.

**Example - Basic Capacity Test**:
```bash
cd capacity-benchmark

# Run capacity test with default settings (5 VMs per iteration)
python3 measure-capacity.py --storage-class portworx-fada-sc

# Run with custom VM count
python3 measure-capacity.py --storage-class portworx-fada-sc --vms 10

# Run with maximum iterations limit
python3 measure-capacity.py --storage-class portworx-fada-sc --max-iterations 5
```

**Example - Skip Specific Phases**:
```bash
# Test only VM creation capacity (skip resize, restart, snapshot, migration)
python3 measure-capacity.py \
  --storage-class portworx-fada-sc \
  --vms 10 \
  --skip-resize-job \
  --skip-restart-job \
  --skip-snapshot-job \
  --skip-migration-job

# Test volume expansion limits
python3 measure-capacity.py \
  --storage-class portworx-fada-sc \
  --vms 5 \
  --min-vol-size 30Gi \
  --min-vol-inc-size 20Gi \
  --max-iterations 10
```

**What it does**:
1. **Phase 1**: Creates VMs with multiple data volumes
2. **Phase 2**: Resizes root and data volumes (tests volume expansion)
3. **Phase 3**: Restarts VMs (tests VM lifecycle)
4. **Phase 4**: Creates VM snapshots (tests snapshot functionality)
5. **Phase 5**: Migrates VMs (tests live migration)
6. Repeats until failure or max iterations reached

**Cleanup**:
```bash
# Cleanup resources after test
python3 measure-capacity.py --cleanup-only
```

**See detailed documentation**: `capacity-benchmark/README.md`

---

### Scenario 6: Failure and Recovery Testing

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

| Option                   | Description                                                                            | Default            |
|--------------------------|----------------------------------------------------------------------------------------|--------------------|
| `--start`                | Starting namespace index                                                               | 1                  |
| `--end`                  | Ending namespace index                                                                 | 100                |
| `--vm-name`              | VM resource name                                                                       | rhel-9-vm          |
| `--concurrency`          | Max parallel monitoring threads                                                        | 50                 |
| `--ssh-pod`              | Pod name for ping tests                                                                | ssh-test-pod       |
| `--ssh-pod-ns`           | Namespace of SSH pod                                                                   | default            |
| `--poll-interval`        | Seconds between status checks                                                          | 1                  |
| `--ping-timeout`         | Ping timeout in seconds                                                                | 600                |
| `--log-file`             | Output log file path                                                                   | stdout             |
| `--log-level`            | Logging level (DEBUG/INFO/WARNING/ERROR)                                               | INFO               |
| `--namespace-prefix`     | Prefix for test namespaces                                                             | kubevirt-perf-test |
| `--namespace-batch-size` | Namespaces to create in parallel                                                       | 20                 |
| `--boot-storm`           | Enable boot storm testing                                                              | false              |
| `--single-node`          | Run all VMs on a single node                                                           | false              |
| `--node-name`            | Specific node to use (requires --single-node)                                          | auto-select        |
| `--cleanup`              | Delete resources and namespaces after test                                             | false              |
| `--cleanup-on-failure`   | Clean up even if tests fail                                                            | false              |
| `--dry-run-cleanup`      | Show what would be deleted without deleting                                            | false              |
| `--yes`                  | Skip confirmation prompt for cleanup                                                   | false              |
| `--save_results`         | Save detailed results (JSON and CSV) inside a timestamped folder under results/ folder | false              |
| `--results_folder`       | Base directory to store test results                                                   | ../results         |
| `--px_version`           | Portworx version to include in results path (auto-detect if not provided)              | auto-detect        |
| `--px_namespace`         | Default namespace where Portworx is installed                                          | Portworx           |

### Live Migration Tests

| Option | Description | Default |
|--------|-------------|---------|
| `--start` | Starting namespace index | 1 |
| `--end` | Ending namespace index | 10 |
| `--vm-name` | VM resource name | rhel-9-vm |
| `--namespace-prefix` | Prefix for test namespaces | kubevirt-perf-test |
| `--create-vms` | Create VMs before migration | false |
| `--vm-template` | VM template YAML file | ../examples/vm-templates/vm-template.yaml |
| `--single-node` | Create all VMs on a single node (requires --create-vms) | false |
| `--node-name` | Specific node to create VMs on (requires --single-node) | auto-select |
| `--source-node` | Source node name for migration | None |
| `--target-node` | Target node name for migration | auto-select |
| `--parallel` | Migrate VMs in parallel | false |
| `--evacuate` | Evacuate all VMs from source node | false |
| `--auto-select-busiest` | Auto-select the node with most VMs (requires --evacuate) | false |
| `--round-robin` | Migrate VMs in round-robin fashion across all nodes | false |
| `--concurrency` | Number of concurrent migrations | 10 |
| `--migration-timeout` | Timeout for each migration in seconds | 600 |
| `--ssh-pod` | SSH test pod name for ping tests | ssh-pod-name |
| `--ssh-pod-ns` | SSH test pod namespace | default |
| `--ping-timeout` | Timeout for ping test in seconds | 600 |
| `--skip-ping` | Skip ping validation after migration | false |
| `--interleaved-scheduling` | Distribute parallel migration threads in interleaved pattern across nodes | false |
| `--log-file` | Output log file path | stdout |
| `--log-level` | Logging level (DEBUG/INFO/WARNING/ERROR) | INFO |
| `--cleanup` | Delete VMs, VMIMs, and namespaces after test | false |
| `--cleanup-on-failure` | Clean up resources even if tests fail | false |
| `--dry-run-cleanup` | Show what would be deleted without deleting | false |
| `--yes` | Skip confirmation prompt for cleanup | false |
| `--skip-checks` | Skip VM verifications before migration | false |
| `--save-results` | Save detailed migration results (JSON and CSV) under results/ | false |
| `--px-version` | Portworx version to include in results path (auto-detect if not provided) | auto-detect |
| `--px-namespace` | Namespace where Portworx is installed | portworx |
| `--results-folder` | Base directory to store test results | ../results |

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


## Results Dashboard

### Generate Interactive Dashboard

After running tests with `--save-results`, generate an interactive HTML dashboard to visualize all your performance test results:

```bash
# Basic usage (last 15 days)
python3 dashboard/generate_dashboard.py

# Custom time range and configuration
python3 dashboard/generate_dashboard.py \
  --days 50 \
  --base-dir results \
  --cluster-info dashboard/cluster_info.yaml \
  --manual-results dashboard/manual_results.yaml \
  --output-html results_dashboard.html
```

**Dashboard Features:**
- **Multi-level Organization**: Results organized by PX Version → Disk Count → VM Size
- **Interactive Charts**: Plotly-based bar charts showing duration metrics
- **Detailed Tables**: Sortable and searchable DataTables for all test results
- **Cluster Information**: Display cluster metadata and configuration
- **Manual Results**: Include manually collected test results

**What you get:**
- VM Creation performance charts and tables
- Boot Storm performance metrics
- Live Migration duration analysis
- Summary statistics across all test runs
- Time-series visualization of performance trends

> **📖 For detailed dashboard documentation, see [dashboard/README.md](dashboard/README.md)**

## Utility Tools

### Cluster Validation

Validate your cluster before running benchmarks:

```bash
# Basic validation
python3 utils/validate_cluster.py --storage-class portworx-fada-sc

# Comprehensive validation
python3 utils/validate_cluster.py --all --storage-class portworx-fada-sc
```

See [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md) for details.

### Template Management

Apply template variables to VM configurations:

```bash
# Basic usage
./utils/apply_template.sh -o /tmp/vm.yaml -n my-vm -s portworx-fada-sc

# Full customization
./utils/apply_template.sh \
  -o /tmp/custom-vm.yaml \
  -n high-perf-vm \
  -s portworx-raw-sc \
  --storage-size 100Gi \
  --memory 8Gi \
  --cpu-cores 4
```

See [TEMPLATE_GUIDE.md](TEMPLATE_GUIDE.md) for details.


## Cleanup

### Automatic Cleanup

All test scripts support comprehensive cleanup with the following options:

#### VM Creation Tests
```bash
# Clean up after successful test
python3 measure-vm-creation-time.py --start 1 --end 50 --cleanup

# Clean up even if test fails
python3 measure-vm-creation-time.py --start 1 --end 50 --cleanup-on-failure

# Preview what would be deleted (dry run)
python3 measure-vm-creation-time.py --start 1 --end 50 --dry-run-cleanup

# Skip confirmation prompt (use with caution)
python3 measure-vm-creation-time.py --start 1 --end 50 --cleanup --yes
```

**What gets cleaned up:**
- All VMs created during the test
- All DataVolumes (DVs) associated with the VMs
- All PersistentVolumeClaims (PVCs)
- All test namespaces (kubevirt-perf-test-1 through kubevirt-perf-test-N)

#### Migration Tests
```bash
# Clean up VMIMs and optionally VMs/namespaces
cd migration
python3 measure-vm-migration-time.py --start 1 --end 50 --create-vms --cleanup

# Dry run to see what would be deleted
python3 measure-vm-migration-time.py --start 1 --end 50 --dry-run-cleanup
```

**What gets cleaned up:**
- All VirtualMachineInstanceMigration (VMIM) objects
- VMs and namespaces (only if created with `--create-vms`)
- Node selector modifications are automatically cleaned

#### Failure Recovery Tests
```bash
# Clean up FAR resources and annotations
cd failure-recovery
python3 measure-recovery-time.py \
  --start 1 --end 60 \
  --vm-name rhel-9-vm \
  --cleanup \
  --far-name my-far-resource \
  --failed-node worker-1

# Also delete VMs and namespaces
python3 measure-recovery-time.py \
  --start 1 --end 60 \
  --vm-name rhel-9-vm \
  --cleanup \
  --cleanup-vms \
  --far-name my-far-resource \
  --failed-node worker-1
```

**What gets cleaned up:**
- FenceAgentsRemediation (FAR) custom resources
- FAR annotations from VMs
- Uncordon nodes that were marked as failed
- Optionally: VMs, DataVolumes, PVCs, and namespaces (with `--cleanup-vms`)

### Manual Cleanup

If automatic cleanup fails or you need to clean up manually:

```bash
# Delete specific namespace range
for i in {1..50}; do
  kubectl delete namespace kubevirt-perf-test-$i &
done
wait

# Force delete stuck namespaces
kubectl delete namespace kubevirt-perf-test-1 --force --grace-period=0

# Clean up VMIMs
kubectl delete virtualmachineinstancemigration --all -n kubevirt-perf-test-1

# Remove FAR resources
kubectl delete fenceagentsremediation my-far-resource

# Uncordon nodes
kubectl uncordon worker-1
```

### Safety Features

1. **Confirmation Prompt**: When cleaning up more than 10 namespaces, you'll be prompted to confirm (unless `--yes` is used)
2. **Dry Run Mode**: Use `--dry-run-cleanup` to preview what would be deleted
3. **Namespace Prefix Verification**: Only deletes resources matching the test namespace prefix
4. **Detailed Logging**: All cleanup operations are logged with timestamps
5. **Error Handling**: Cleanup failures don't mask test results
6. **Interrupt Handling**: Ctrl+C during tests triggers cleanup if `--cleanup` or `--cleanup-on-failure` is set

### Cleanup Summary

After cleanup completes, you'll see a summary like:

```
================================================================================
CLEANUP SUMMARY
================================================================================
  Namespaces Processed:        50
  Namespaces Deleted:          50
  VMs Deleted:                 50
  DataVolumes Deleted:         50
  PVCs Deleted:                50
  VMIMs Deleted:               25
  Errors:                      0
================================================================================
```
> **📖 For comprehensive cleanup documentation, see [CLEANUP_GUIDE.md](CLEANUP_GUIDE.md)**


## Best Practices

1. **Validate First**: Always run cluster validation before benchmarks
2. **Use Templates**: Use the template helper script for consistent VM configurations
3. **Start Small**: Begin with 5-10 VMs to validate your setup before scaling
4. **Monitor Resources**: Watch cluster resource utilization during tests
5. **Use Dedicated Namespaces**: Tests create namespaces with predictable names for easy cleanup
6. **Save Results**: Use `--save-results` to preserve test results data for dashboard generation
7. **Cleanup**: Remove test resources after completion to free cluster resources
8. **Network Testing**: Deploy an SSH pod in advance for ping tests


## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub

## Acknowledgments

- OpenShift Virtualization Team
- Portworx Engineering
- KubeVirt Community

