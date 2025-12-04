# KubeVirt Performance Testing Suite

A comprehensive, vendor-neutral performance testing toolkit for KubeVirt virtual machines running on OpenShift Container Platform (OCP) or any Kubernetes distribution with KubeVirt.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Complete Setup Guide](#complete-setup-guide)
  - [Option A: Using virtbench CLI (Recommended)](#option-a-using-virtbench-cli-recommended)
  - [Option B: Using Python Scripts Directly](#option-b-using-python-scripts-directly)
- [Testing Scenarios](#testing-scenarios)
  - [Scenario 1: DataSource-Based VM Provisioning](#scenario-1-datasource-based-vm-provisioning)
  - [Scenario 2: Single Node Boot Storm Testing](#scenario-2-single-node-boot-storm-testing)
  - [Scenario 3: Multi-Node Boot Storm Testing](#scenario-3-multi-node-boot-storm-testing)
  - [Scenario 4: Live Migration Testing](#scenario-4-live-migration-testing)
  - [Scenario 5: Capacity Benchmark Testing](#scenario-5-capacity-benchmark-testing)
  - [Scenario 6: Failure and Recovery Testing](#scenario-6-failure-and-recovery-testing)
- [Boot Storm Testing Guide](#boot-storm-testing-guide)
- [VM Template Guide](#vm-template-guide)
- [Cluster Validation Guide](#cluster-validation-guide)
- [Configuration Options](#configuration-options)
- [Output and Results](#output-and-results)
- [Results Dashboard](#results-dashboard)
- [Cleanup Guide](#cleanup-guide)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)
- [Repository Structure](#repository-structure)
- [License](#license)

---

## Overview

This suite provides automated performance testing tools to measure and validate KubeVirt VM provisioning, boot times, network readiness, and failure recovery scenarios. It's designed for production environments running OpenShift Virtualization or KubeVirt with any CSI-compatible storage backend.

## Features

- **Unified CLI Interface**: Professional kubectl-like CLI (`virtbench`) with shell completion
- **VM Creation Performance Testing**: Measure VM provisioning and boot times at scale
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
- **Multiple Storage Backends**: Works with any CSI-compatible storage class (Portworx, Ceph, vSphere, AWS EBS, etc.)
- **Comprehensive Logging**: Detailed logs with timestamps and error tracking
- **Flexible Configuration**: Command-line arguments for easy customization
- **Interactive Results Dashboard**: Auto-generate rich HTML dashboards for all test results

## Prerequisites

### Software Requirements
- OpenShift Container Platform 4.x with OpenShift Virtualization (or Kubernetes with KubeVirt)
- Any CSI-compatible storage provider with a configured StorageClass
- **Python 3.8 or higher** (required - scripts will exit if version is below 3.8)
- kubectl CLI configured with cluster access
- Bash shell (for helper scripts)

> **⚠️ Important:** Python 3.8+ is a hard requirement. The scripts will check for this and exit with an error if Python version is below 3.8.

### Cluster Requirements
- Sufficient cluster resources to run test VMs
- At least one StorageClass configured (any CSI-compatible storage)
- OpenShift Virtualization operator installed (or KubeVirt on vanilla Kubernetes)
- Network connectivity between test pods and VMs

### Permissions
The user running these tests needs:
- Ability to create/delete namespaces
- Ability to create/delete VMs, VMIs, and PVCs
- Ability to exec into pods (for ping tests)
- Ability to patch VM resources (for FAR tests)

---

## Complete Setup Guide

This section provides exhaustive step-by-step instructions to get you up and running. Follow these steps exactly and you'll be ready to run benchmarks.

### Option A: Using virtbench CLI (Recommended)

The `virtbench` CLI provides a unified, kubectl-like interface for all benchmarks. This is the recommended approach.

#### Step 1: Verify Prerequisites

```bash
# 1.1 Check Python version (must be 3.8 or higher)
python3 --version
# Expected: Python 3.8.x or higher

# 1.2 Check kubectl is configured and can access your cluster
kubectl cluster-info
# Expected: Kubernetes control plane is running at https://...

# 1.3 Check OpenShift Virtualization is installed
kubectl get kubevirt -A
# Expected: NAMESPACE       NAME                               AGE   PHASE
#           openshift-cnv   kubevirt-kubevirt-hyperconverged   ...   Deployed

# 1.4 Check storage classes are available
kubectl get storageclass
# Expected: At least one storage class available
```

#### Step 2: Clone and Install

```bash
# 2.1 Clone the repository
git clone https://github.com/your-org/kubevirt-benchmark-suite.git
cd kubevirt-benchmark-suite

# 2.2 Run the installation script
./install.sh
# This will:
# - Check Python version (exits if < 3.8)
# - Install Python dependencies
# - Install virtbench CLI (Python-based)

# 2.3 Verify virtbench is installed
virtbench version
# Expected: virtbench version X.Y.Z

# 2.4 (Optional) Enable shell completion
# For bash:
eval "$(_VIRTBENCH_COMPLETE=bash_source virtbench)"
# For zsh:
eval "$(_VIRTBENCH_COMPLETE=zsh_source virtbench)"
# To make it permanent, add the above line to your ~/.bashrc or ~/.zshrc
```

#### Step 3: Configure Environment Variable

When using `virtbench` from any directory, it needs to locate the repository:

```bash
# 3.1 Set the environment variable (add to ~/.bashrc or ~/.zshrc for persistence)
export VIRTBENCH_REPO=/path/to/kubevirt-benchmark-suite

# 3.2 Verify it's set
echo $VIRTBENCH_REPO
# Expected: /path/to/kubevirt-benchmark-suite

# 3.3 Add to shell profile for persistence
echo 'export VIRTBENCH_REPO=/path/to/kubevirt-benchmark-suite' >> ~/.bashrc
source ~/.bashrc
```

#### Step 4: Identify Your Storage Class

```bash
# 4.1 List available storage classes
kubectl get storageclass

# 4.2 Note the name of your storage class
# Examples: standard, gp2, ceph-rbd, vsphere-csi, ocs-storagecluster-ceph-rbd

# 4.3 Verify the storage class is working
kubectl get pvc -A | head -5
```

#### Step 5: Create SSH Pod for Network Tests

The SSH pod is required for ping tests that validate VM network connectivity:

```bash
# 5.1 Create the SSH test pod
kubectl apply -f examples/ssh-pod.yaml

# 5.2 Wait for the pod to be ready
kubectl wait --for=condition=Ready pod/ssh-test-pod -n default --timeout=300s

# 5.3 Verify the pod is running
kubectl get pod ssh-test-pod -n default
# Expected: NAME           READY   STATUS    RESTARTS   AGE
#           ssh-test-pod   1/1     Running   0          ...
```

#### Step 6: Verify DataSource Availability

```bash
# 6.1 Check available DataSources
kubectl get datasource -n openshift-virtualization-os-images

# 6.2 Verify the rhel9 DataSource exists (default for tests)
kubectl get datasource rhel9 -n openshift-virtualization-os-images
# Expected: NAME    AGE
#           rhel9   ...
```

#### Step 7: Validate Your Cluster

```bash
# 7.1 Run cluster validation (replace YOUR-STORAGE-CLASS)
virtbench validate-cluster --storage-class YOUR-STORAGE-CLASS

# 7.2 For comprehensive validation
virtbench validate-cluster --storage-class YOUR-STORAGE-CLASS --all

# Expected output:
# ✓ kubectl access and cluster connectivity
# ✓ OpenShift Virtualization installed and healthy
# ✓ Storage class available
# ✓ Worker nodes ready
# ✓ DataSource available
# ✓ User permissions verified
```

#### Step 8: Run Your First Test

```bash
# 8.1 Run a small test to verify everything works
virtbench datasource-clone \
  --start 1 \
  --end 3 \
  --storage-class YOUR-STORAGE-CLASS \
  --cleanup

# Expected: Creates 3 VMs, measures performance, then cleans up

# 8.2 View the results
# Results are displayed in the console with timing metrics
```

#### Step 9: You're Ready!

You can now run any benchmark. Here are some examples:

```bash
# DataSource clone test (VM creation)
virtbench datasource-clone --start 1 --end 10 --storage-class YOUR-STORAGE-CLASS --save-results

# Migration test
virtbench migration --start 1 --end 5 --source-node WORKER-NODE-NAME --save-results

# Capacity benchmark
virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS --vms 5 --max-iterations 3

# Failure recovery test
virtbench failure-recovery --start 1 --end 10 --node-name WORKER-NODE-NAME
```

---

### Option B: Using Python Scripts Directly

If you prefer not to use the virtbench CLI, you can run the Python scripts directly.

#### Step 1: Verify Prerequisites

```bash
# 1.1 Check Python version (must be 3.8 or higher)
python3 --version
# Expected: Python 3.8.x or higher

# 1.2 Check kubectl is configured
kubectl cluster-info

# 1.3 Check OpenShift Virtualization is installed
kubectl get kubevirt -A

# 1.4 Check storage classes are available
kubectl get storageclass
```

#### Step 2: Clone and Install Dependencies

```bash
# 2.1 Clone the repository
git clone https://github.com/your-org/kubevirt-benchmark-suite.git
cd kubevirt-benchmark-suite

# 2.2 Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# 2.3 Install Python dependencies
pip3 install -r requirements.txt

# 2.4 Verify installation
python3 -c "import kubernetes; print('kubernetes module OK')"
python3 -c "import yaml; print('yaml module OK')"
```

#### Step 3: Identify Your Storage Class

```bash
# 3.1 List available storage classes
kubectl get storageclass

# 3.2 Note the name of your storage class (e.g., standard, gp2, ceph-rbd)
```

#### Step 4: Configure VM Templates (Optional)

```bash
# 4.1 Option A: Use the template helper script
./utils/apply_template.sh \
  --output /tmp/my-vm.yaml \
  --vm-name my-test-vm \
  --storage-class YOUR-STORAGE-CLASS \
  --memory 4Gi \
  --cpu-cores 2

# 4.2 Option B: Replace storage class in all templates at once
./utils/replace-storage-class.sh YOUR-STORAGE-CLASS

# 4.3 Verify the replacement
grep "storageClassName:" examples/vm-templates/*.yaml
```

#### Step 5: Create SSH Pod for Network Tests

```bash
# 5.1 Create the SSH test pod
kubectl apply -f examples/ssh-pod.yaml

# 5.2 Wait for the pod to be ready
kubectl wait --for=condition=Ready pod/ssh-test-pod -n default --timeout=300s

# 5.3 Verify the pod is running
kubectl get pod ssh-test-pod -n default
```

#### Step 6: Verify DataSource Availability

```bash
# 6.1 Check available DataSources
kubectl get datasource -n openshift-virtualization-os-images

# 6.2 Verify the rhel9 DataSource exists
kubectl get datasource rhel9 -n openshift-virtualization-os-images
```

#### Step 7: Validate Your Cluster

```bash
# 7.1 Run cluster validation
python3 utils/validate_cluster.py --storage-class YOUR-STORAGE-CLASS

# 7.2 For comprehensive validation
python3 utils/validate_cluster.py --storage-class YOUR-STORAGE-CLASS --all
```

#### Step 8: Run Your First Test

```bash
# 8.1 Navigate to the test directory
cd datasource-clone

# 8.2 Run a small test
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 3 \
  --vm-name rhel-9-vm \
  --cleanup

# 8.3 View the results in the console
```

#### Step 9: You're Ready!

You can now run any benchmark script directly:

```bash
# DataSource clone test (VM creation)
cd datasource-clone
python3 measure-vm-creation-time.py --start 1 --end 10 --vm-name rhel-9-vm --save-results

# Migration test
cd migration
python3 measure-vm-migration-time.py --start 1 --end 5 --source-node WORKER-NODE-NAME --save-results

# Capacity benchmark
cd capacity-benchmark
python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS --vms 5 --max-iterations 3

# Failure recovery test
cd failure-recovery
python3 measure-recovery-time.py --start 1 --end 10 --vm-name rhel-9-vm
```

---

## Important: Configure Your Storage Class

**Before running any tests, you MUST configure the storage class for your environment.**

### Quick Setup (Choose One):

**Option 1: Use CLI flag (Recommended)**
```bash
# Replace YOUR-STORAGE-CLASS with your actual storage class name
virtbench datasource-clone --start 1 --end 10 --storage-class YOUR-STORAGE-CLASS
```

**Option 2: Configure all YAML templates at once**
```bash
# Find your storage class
kubectl get storageclass

# Replace {{STORAGE_CLASS_NAME}} in all templates
./utils/replace-storage-class.sh YOUR-STORAGE-CLASS

# Verify
grep "storageClassName:" examples/vm-templates/*.yaml
```

## Testing Scenarios

### Scenario 1: DataSource-Based VM Provisioning

Tests VM creation using KubeVirt DataSource cloning for efficient VM provisioning.

**Use Case**: Measure VM provisioning performance with your storage backend.

**Example (CLI)**:
```bash
# Run performance test with your storage class
virtbench datasource-clone \
  --start 1 \
  --end 100 \
  --storage-class YOUR-STORAGE-CLASS \
  --log-file results-$(date +%Y%m%d-%H%M%S).log
```

**Example (Python script)**:
```bash
cd datasource-clone

# Run performance test (requires pre-configured template)
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 100 \
  --vm-name rhel-9-vm \
  --vm-template ../examples/vm-templates/rhel9-vm-datasource.yaml \
  --save-results \
  --log-file results-$(date +%Y%m%d-%H%M%S).log
```

### Scenario 2: Single Node Boot Storm Testing

Tests VM startup performance on a single node when powering on multiple VMs simultaneously.

**Use Case**: Validates node-level capacity and boot storm performance (e.g., how many VMs can a single node handle during boot storm).

**Example (virtbench CLI - Recommended)**:
```bash
# Run test on a single node (auto-selected) with your storage class
virtbench datasource-clone \
  --start 1 \
  --end 50 \
  --storage-class YOUR-STORAGE-CLASS \
  --single-node \
  --boot-storm \
  --log-file single-node-boot-storm-$(date +%Y%m%d-%H%M%S).log

# Or specify a specific node
virtbench datasource-clone \
  --start 1 \
  --end 50 \
  --storage-class YOUR-STORAGE-CLASS \
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

**Example (virtbench CLI - Recommended)**:
```bash
# Run test with boot storm (VMs distributed across all nodes)
virtbench datasource-clone \
  --start 1 \
  --end 100 \
  --storage-class YOUR-STORAGE-CLASS \
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

#### Sequential Migration

**virtbench CLI:**
```bash
# Migrate 10 VMs one by one from worker-1 to worker-2
virtbench migration \
  --start 1 \
  --end 10 \
  --source-node worker-1 \
  --target-node worker-2 \
  --save-results
```

**Python script:**
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

#### Parallel Migration

**virtbench CLI:**
```bash
# Migrate 50 VMs in parallel with 10 concurrent migrations
virtbench migration \
  --start 1 \
  --end 50 \
  --source-node worker-1 \
  --target-node worker-2 \
  --parallel \
  --concurrency 10 \
  --save-results
```

**Python script:**
```bash
cd migration

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

#### Parallel Migration with Advanced Options

**virtbench CLI:**
```bash
# High-scale parallel migration with interleaved scheduling and custom timeout
virtbench migration \
  --start 1 \
  --end 200 \
  --parallel \
  --concurrency 50 \
  --skip-ping \
  --save-results \
  --migration-timeout 1000 \
  --interleaved-scheduling
```

**Python script:**
```bash
cd migration

# High-scale parallel migration with interleaved scheduling and custom timeout
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 200 \
  --parallel \
  --concurrency 50 \
  --skip-ping \
  --save-results \
  --migration-timeout 1000 \
  --interleaved-scheduling
```

#### Node Evacuation (Specific Node)

**virtbench CLI:**
```bash
# Evacuate all VMs from worker-3 before maintenance
virtbench migration \
  --start 1 \
  --end 100 \
  --source-node worker-3 \
  --evacuate \
  --concurrency 20 \
  --save-results
```

**Python script:**
```bash
cd migration

# Evacuate all VMs from worker-3 before maintenance
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 100 \
  --source-node worker-3 \
  --evacuate \
  --concurrency 20 \
  --save-results
```

#### Node Evacuation (Auto-Select Busiest)

**virtbench CLI:**
```bash
# Automatically find and evacuate the busiest node
virtbench migration \
  --start 1 \
  --end 100 \
  --evacuate \
  --auto-select-busiest \
  --concurrency 20 \
  --save-results
```

**Python script:**
```bash
cd migration

# Automatically find and evacuate the busiest node
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 100 \
  --evacuate \
  --auto-select-busiest \
  --concurrency 20 \
  --save-results
```

#### Round-Robin Migration

**virtbench CLI:**
```bash
# Distribute VMs across all nodes for load balancing
virtbench migration \
  --start 1 \
  --end 100 \
  --round-robin \
  --concurrency 20 \
  --save-results
```

**Python script:**
```bash
cd migration

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

**Cleanup after migration tests:**

**virtbench CLI:**
```bash
# Clean up VMIMs only (VMs remain)
virtbench migration --start 1 --end 100 --cleanup

# Clean up everything if VMs were created by the test
virtbench migration --start 1 --end 100 --create-vms --cleanup
```

**Python script:**
```bash
cd migration

# Clean up VMIMs only (VMs remain)
python3 measure-vm-migration-time.py --start 1 --end 100 --cleanup

# Clean up everything if VMs were created by the test
python3 measure-vm-migration-time.py --start 1 --end 100 --create-vms --cleanup
```

---

### Scenario 5: Capacity Benchmark Testing

Tests cluster capacity limits by running comprehensive VM operations in a loop until failure.

**Use Case**: Discover maximum VM capacity, test volume expansion limits, validate snapshot functionality, and stress-test the cluster.

#### Basic Capacity Test

**virtbench CLI:**
```bash
# Run capacity test with default settings (5 VMs per iteration)
virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS

# Run with custom VM count
virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS --vms 10

# Run with maximum iterations limit
virtbench capacity-benchmark --storage-class YOUR-STORAGE-CLASS --max-iterations 5
```

**Python script:**
```bash
cd capacity-benchmark

# Run capacity test with default settings (5 VMs per iteration)
python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS

# Run with custom VM count
python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS --vms 10

# Run with maximum iterations limit
python3 measure-capacity.py --storage-class YOUR-STORAGE-CLASS --max-iterations 5
```

#### Skip Specific Phases

**virtbench CLI:**
```bash
# Test only VM creation capacity (skip resize, restart, snapshot, migration)
virtbench capacity-benchmark \
  --storage-class YOUR-STORAGE-CLASS \
  --vms 10 \
  --skip-resize-job \
  --skip-restart-job \
  --skip-snapshot-job \
  --skip-migration-job

# Test volume expansion limits
virtbench capacity-benchmark \
  --storage-class YOUR-STORAGE-CLASS \
  --vms 5 \
  --min-vol-size 30Gi \
  --min-vol-inc-size 20Gi \
  --max-iterations 10
```

**Python script:**
```bash
cd capacity-benchmark

# Test only VM creation capacity (skip resize, restart, snapshot, migration)
python3 measure-capacity.py \
  --storage-class YOUR-STORAGE-CLASS \
  --vms 10 \
  --skip-resize-job \
  --skip-restart-job \
  --skip-snapshot-job \
  --skip-migration-job

# Test volume expansion limits
python3 measure-capacity.py \
  --storage-class YOUR-STORAGE-CLASS \
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

**Cleanup:**

**virtbench CLI:**
```bash
# Cleanup resources after test
virtbench capacity-benchmark --cleanup-only
```

**Python script:**
```bash
cd capacity-benchmark
python3 measure-capacity.py --cleanup-only
```

---

### Scenario 6: Failure and Recovery Testing

Tests VM recovery time after simulated node failures using Fence Agents Remediation (FAR).

**Use Case**: Validates high availability and disaster recovery capabilities.

**virtbench CLI:**
```bash
# Run failure recovery test
virtbench failure-recovery \
  --start 1 \
  --end 60 \
  --node-name worker-node-1 \
  --vm-name rhel-9-vm \
  --save-results

# With custom FAR configuration
virtbench failure-recovery \
  --start 1 \
  --end 60 \
  --node-name worker-node-1 \
  --vm-name rhel-9-vm \
  --far-name my-far-resource \
  --save-results
```

**Python script:**
```bash
cd failure-recovery

# Edit far-template.yaml with your node details
vim far-template.yaml

# Run the complete FAR test using the shell script
./run-far-test.sh \
  --start 1 \
  --end 60 \
  --node-name worker-node-1 \
  --vm-name rhel-9-vm

# Or run the Python script directly
python3 measure-recovery-time.py \
  --start 1 \
  --end 60 \
  --vm-name rhel-9-vm \
  --save-results
```

**Cleanup:**

**virtbench CLI:**
```bash
# Clean up FAR resources
virtbench failure-recovery \
  --start 1 \
  --end 60 \
  --vm-name rhel-9-vm \
  --cleanup \
  --far-name my-far-resource \
  --failed-node worker-node-1
```

**Python script:**
```bash
cd failure-recovery
python3 measure-recovery-time.py \
  --start 1 \
  --end 60 \
  --vm-name rhel-9-vm \
  --cleanup \
  --far-name my-far-resource \
  --failed-node worker-node-1
```

---

## Boot Storm Testing Guide

### What is Boot Storm Testing?

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

### How It Works

The boot storm test follows this workflow:

**Phase 1: Initial VM Creation**
1. Creates all test namespaces in parallel batches
2. Creates and starts all VMs simultaneously
3. Measures time to Running state
4. Measures time to network readiness (ping)
5. Displays initial creation performance results

**Phase 2: Shutdown All VMs**
1. Issues stop commands to all VMs in parallel
2. Waits for all VMIs to be deleted (VMs fully stopped)
3. Confirms all VMs are in stopped state

**Phase 3: Boot Storm (Simultaneous Startup)**
1. Issues start commands to ALL VMs at once
2. Creates maximum load on infrastructure
3. Measures time to Running state for each VM
4. Measures time to network readiness for each VM
5. Displays boot storm performance results

**Phase 4: Comparison**
Compare initial creation vs boot storm metrics to understand:
- Performance differences between cold start and warm start
- Impact of concurrent operations
- Storage backend behavior under load

### Boot Storm Examples

**virtbench CLI:**
```bash
# Basic boot storm test (multi-node)
virtbench datasource-clone \
  --start 1 \
  --end 50 \
  --storage-class YOUR-STORAGE-CLASS \
  --boot-storm \
  --save-results

# Single node boot storm test
virtbench datasource-clone \
  --start 1 \
  --end 50 \
  --storage-class YOUR-STORAGE-CLASS \
  --single-node \
  --boot-storm \
  --save-results

# Advanced boot storm test
virtbench datasource-clone \
  --start 1 \
  --end 100 \
  --storage-class YOUR-STORAGE-CLASS \
  --namespace-prefix boot-storm-test \
  --namespace-batch-size 30 \
  --boot-storm \
  --concurrency 100 \
  --save-results \
  --log-file boot-storm-$(date +%Y%m%d-%H%M%S).log
```

**Python script:**
```bash
cd datasource-clone

# Basic boot storm test (multi-node)
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --boot-storm \
  --save-results

# Single node boot storm test
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --single-node \
  --boot-storm \
  --save-results

# Advanced boot storm test
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 100 \
  --vm-name rhel-9-vm \
  --namespace-prefix boot-storm-test \
  --namespace-batch-size 30 \
  --boot-storm \
  --concurrency 100 \
  --save-results \
  --log-file boot-storm-$(date +%Y%m%d-%H%M%S).log
```

### Interpreting Boot Storm Results

**Key Metrics:**
- **Time to Running**: How long until VM reaches Running state
- **Time to Ping**: How long until VM is network-reachable
- **Max Times**: Worst-case performance

**What to Look For:**

| Performance Level | Boot Storm vs Initial | Recommendation |
|-------------------|----------------------|----------------|
| Good | 1.5-2x slower | Infrastructure handles load well |
| Concerning | 3x slower | Investigate bottlenecks |
| Critical | 5x+ slower | Major infrastructure issues |

### Performance Tuning

If boot storm performance is poor:

1. **Storage Bottleneck**: Increase storage IOPS, use faster storage tier, enable caching
2. **Network Bottleneck**: Check DHCP server capacity, verify network bandwidth
3. **Compute Bottleneck**: Add more worker nodes, increase node resources
4. **Hypervisor Bottleneck**: Tune KubeVirt settings, adjust virt-launcher resources

---

## VM Template Guide

### Overview

The VM templates use placeholder variables (e.g., `{{VM_NAME}}`, `{{STORAGE_CLASS_NAME}}`) that can be replaced with actual values before deployment.

### Template Variables

| Variable | Description | Example Values |
|----------|-------------|----------------|
| `{{VM_NAME}}` | VM name | `rhel-9-vm`, `my-test-vm` |
| `{{STORAGE_CLASS_NAME}}` | Storage class name | `standard`, `gp2`, `ceph-rbd` |
| `{{DATASOURCE_NAME}}` | DataSource name | `rhel9`, `fedora`, `centos` |
| `{{DATASOURCE_NAMESPACE}}` | DataSource namespace | `openshift-virtualization-os-images` |
| `{{STORAGE_SIZE}}` | Root disk storage size | `30Gi`, `50Gi`, `100Gi` |
| `{{VM_MEMORY}}` | VM memory allocation | `2048M`, `4Gi`, `8Gi` |
| `{{VM_CPU_CORES}}` | Number of CPU cores | `1`, `2`, `4`, `8` |

### Using the Helper Script (Recommended)

```bash
cd utils

# Basic usage
./apply_template.sh \
  --output /tmp/my-vm.yaml \
  --vm-name my-test-vm \
  --storage-class YOUR-STORAGE-CLASS

# Fully customized VM
./apply_template.sh \
  --output /tmp/custom-vm.yaml \
  --vm-name high-performance-vm \
  --storage-class YOUR-STORAGE-CLASS \
  --datasource fedora \
  --storage-size 100Gi \
  --memory 8Gi \
  --cpu-cores 4

# Generate and apply in one command
./apply_template.sh \
  --output /tmp/vm.yaml \
  --vm-name test-vm \
  --storage-class YOUR-STORAGE-CLASS && \
kubectl apply -f /tmp/vm.yaml -n test-namespace
```

### Helper Script Options

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --template FILE` | Template file path | ../examples/vm-templates/vm-template.yaml |
| `-o, --output FILE` | Output file path | (required) |
| `-n, --vm-name NAME` | VM name | rhel-9-vm |
| `-s, --storage-class NAME` | Storage class name | (required) |
| `-d, --datasource NAME` | DataSource name | rhel9 |
| `--datasource-namespace NS` | DataSource namespace | openshift-virtualization-os-images |
| `--storage-size SIZE` | Storage size | 30Gi |
| `--memory SIZE` | VM memory | 2048M |
| `--cpu-cores NUM` | Number of CPU cores | 1 |

### Common Use Cases

```bash
# Testing different storage classes
./apply_template.sh -o /tmp/vm-sc1.yaml -n test-vm -s storage-class-1
./apply_template.sh -o /tmp/vm-sc2.yaml -n test-vm -s storage-class-2

# Creating VMs with different sizes
./apply_template.sh -o /tmp/vm-small.yaml -n small-vm -s YOUR-STORAGE-CLASS --storage-size 20Gi --memory 1Gi --cpu-cores 1
./apply_template.sh -o /tmp/vm-large.yaml -n large-vm -s YOUR-STORAGE-CLASS --storage-size 100Gi --memory 8Gi --cpu-cores 4

# Testing different OS images
./apply_template.sh -o /tmp/vm-rhel9.yaml -n rhel9-vm -s YOUR-STORAGE-CLASS -d rhel9
./apply_template.sh -o /tmp/vm-fedora.yaml -n fedora-vm -s YOUR-STORAGE-CLASS -d fedora
```

---

## Cluster Validation Guide

### Overview

The cluster validation script checks that your OpenShift cluster is properly configured and ready to run KubeVirt performance tests.

### Validation Checks

The script validates:
- ✓ kubectl access and cluster connectivity
- ✓ OpenShift Virtualization installation and health
  - KubeVirt resource status (Deployed phase)
  - Critical deployments: virt-api, virt-controller, virt-operator
  - virt-handler daemonset on all nodes
- ✓ Storage class availability
- ✓ Worker node readiness
- ✓ DataSource availability
- ✓ User permissions
- ✓ Node resource utilization

### Running Validation

**virtbench CLI:**
```bash
# Basic validation
virtbench validate-cluster --storage-class YOUR-STORAGE-CLASS

# Comprehensive validation
virtbench validate-cluster --storage-class YOUR-STORAGE-CLASS --all

# With custom DataSource
virtbench validate-cluster \
  --storage-class YOUR-STORAGE-CLASS \
  --datasource fedora \
  --datasource-namespace openshift-virtualization-os-images

# Require minimum worker nodes
virtbench validate-cluster \
  --storage-class YOUR-STORAGE-CLASS \
  --min-worker-nodes 5
```

**Python script:**
```bash
cd utils

# Basic validation
python3 validate_cluster.py --storage-class YOUR-STORAGE-CLASS

# Comprehensive validation
python3 validate_cluster.py --all --storage-class YOUR-STORAGE-CLASS

# With custom DataSource
python3 validate_cluster.py \
  --storage-class YOUR-STORAGE-CLASS \
  --datasource fedora \
  --datasource-namespace openshift-virtualization-os-images
```

### Validation Options

| Option | Description | Default |
|--------|-------------|---------|
| `--storage-class NAME` | Storage class name to validate | (required) |
| `--datasource NAME` | DataSource name to validate | rhel9 |
| `--datasource-namespace NS` | DataSource namespace | openshift-virtualization-os-images |
| `--min-worker-nodes NUM` | Minimum worker nodes required | 1 |
| `--all` | Run all validation checks | false |
| `--log-level LEVEL` | Logging level | INFO |

### Exit Codes

- `0` - All checks passed, cluster is ready
- `1` - One or more checks failed, cluster not ready

### Troubleshooting Validation Failures

**OpenShift Virtualization Not Found:**
```bash
# Check if KubeVirt resource exists
kubectl get kubevirt -A
# Expected: NAMESPACE openshift-cnv, PHASE Deployed
```

**Components Not Ready:**
```bash
# Check deployment status
kubectl get deployment -n openshift-cnv | grep -E "virt-api|virt-controller|virt-operator"

# Check pod logs for errors
kubectl logs -n openshift-cnv deployment/virt-api
```

**Storage Class Not Found:**
```bash
# List all storage classes
kubectl get storageclass

# Create a storage class appropriate for your storage backend
# Refer to your storage provider's documentation
```

---

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
| `--storage-version`      | Storage version to include in results path (optional)                                  | -                  |

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
| `--storage-version` | Storage version to include in results path (optional) | - |
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
- Check storage class is available: `kubectl get sc`
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

> **For detailed dashboard documentation, see [dashboard/README.md](dashboard/README.md)**

---

## Cleanup Guide

All test scripts support comprehensive cleanup with multiple options for different scenarios.

### Cleanup Options

| Option | Description |
|--------|-------------|
| `--cleanup` | Delete resources and namespaces after test completes |
| `--cleanup-on-failure` | Clean up resources even if tests fail |
| `--dry-run-cleanup` | Show what would be deleted without actually deleting |
| `--yes` | Skip confirmation prompt for cleanup |

### What Gets Cleaned Up

**VM Creation Tests:**
- All VMs created during the test
- All DataVolumes (DVs) associated with the VMs
- All PersistentVolumeClaims (PVCs)
- All test namespaces (kubevirt-perf-test-1 through kubevirt-perf-test-N)

**Migration Tests:**
- VirtualMachineInstanceMigration (VMIM) resources
- Optionally: VMs, DataVolumes, PVCs, and namespaces (if `--create-vms` was used)

**Failure Recovery Tests:**
- FenceAgentsRemediation (FAR) custom resources
- FAR annotations from VMs
- Uncordon nodes that were marked as failed
- Optionally: VMs, DataVolumes, PVCs, and namespaces (with `--cleanup-vms`)

### Cleanup Examples

#### VM Creation Tests

**virtbench CLI:**
```bash
# Clean up after test
virtbench datasource-clone --start 1 --end 50 --storage-class YOUR-STORAGE-CLASS --cleanup

# Dry run to see what would be deleted
virtbench datasource-clone --start 1 --end 50 --storage-class YOUR-STORAGE-CLASS --dry-run-cleanup

# Clean up even if tests fail
virtbench datasource-clone --start 1 --end 50 --storage-class YOUR-STORAGE-CLASS --cleanup-on-failure

# Skip confirmation prompt
virtbench datasource-clone --start 1 --end 50 --storage-class YOUR-STORAGE-CLASS --cleanup --yes
```

**Python script:**
```bash
cd datasource-clone

# Clean up after test
python3 measure-vm-creation-time.py --start 1 --end 50 --vm-name rhel-9-vm --cleanup

# Dry run to see what would be deleted
python3 measure-vm-creation-time.py --start 1 --end 50 --vm-name rhel-9-vm --dry-run-cleanup
```

#### Migration Tests

**virtbench CLI:**
```bash
# Clean up VMIMs only (VMs remain)
virtbench migration --start 1 --end 50 --cleanup

# Clean up everything if VMs were created by the test
virtbench migration --start 1 --end 50 --create-vms --cleanup

# Dry run to see what would be deleted
virtbench migration --start 1 --end 50 --dry-run-cleanup
```

**Python script:**
```bash
cd migration

# Clean up VMIMs only (VMs remain)
python3 measure-vm-migration-time.py --start 1 --end 50 --cleanup

# Clean up everything if VMs were created by the test
python3 measure-vm-migration-time.py --start 1 --end 50 --create-vms --cleanup

# Dry run to see what would be deleted
python3 measure-vm-migration-time.py --start 1 --end 50 --dry-run-cleanup
```

#### Failure Recovery Tests

**virtbench CLI:**
```bash
# Clean up FAR resources and annotations
virtbench failure-recovery \
  --start 1 --end 60 \
  --vm-name rhel-9-vm \
  --cleanup \
  --far-name my-far-resource \
  --failed-node worker-1

# Also delete VMs and namespaces
virtbench failure-recovery \
  --start 1 --end 60 \
  --vm-name rhel-9-vm \
  --cleanup \
  --cleanup-vms \
  --far-name my-far-resource \
  --failed-node worker-1
```

**Python script:**
```bash
cd failure-recovery

# Clean up FAR resources and annotations
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

#### Capacity Benchmark Tests

**virtbench CLI:**
```bash
# Cleanup resources after test
virtbench capacity-benchmark --cleanup-only
```

**Python script:**
```bash
cd capacity-benchmark
python3 measure-capacity.py --cleanup-only
```

### Manual Cleanup

If automatic cleanup fails or you need to clean up manually:

```bash
# Delete all test namespaces matching the prefix
for ns in $(kubectl get ns -o name | grep kubevirt-perf-test); do
  kubectl delete $ns &
done
wait

# Delete specific namespace range
for i in {1..50}; do
  kubectl delete namespace kubevirt-perf-test-$i --ignore-not-found &
done
wait

# Delete VMIMs in all namespaces
kubectl delete vmim --all -A

# Delete stuck VMs
kubectl get vm -A -o name | xargs -I {} kubectl delete {} --force --grace-period=0
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


---

## Repository Structure

```
kubevirt-benchmark-suite/
├── README.md                          # This comprehensive documentation
├── LICENSE                            # Apache 2.0 License
├── requirements.txt                   # Python dependencies
├── setup.py                           # Python package setup
├── install.sh                         # Installation script
│
├── virtbench/                         # virtbench CLI (Python-based)
│   ├── __init__.py                   # Package initialization
│   ├── cli.py                        # Click-based CLI entry point
│   ├── common.py                     # Common utilities
│   ├── commands/                     # Subcommand implementations
│   │   ├── datasource_clone.py       # DataSource clone subcommand
│   │   ├── migration.py              # Migration subcommand
│   │   ├── capacity.py               # Capacity benchmark subcommand
│   │   ├── failure_recovery.py       # Failure recovery subcommand
│   │   ├── validate.py               # Cluster validation subcommand
│   │   └── version.py                # Version subcommand
│   └── utils/                        # CLI utilities
│       └── yaml_modifier.py          # YAML modification helpers
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
│   └── replace-storage-class.sh      # Storage class replacement script
│
└── examples/                          # Example configurations
    ├── storage-classes/              # Sample StorageClass definitions (vendor-specific)
    ├── vm-templates/                 # VM template files
    │   └── vm-template.yaml          # Templated VM configuration
    ├── ssh-pod.yaml                  # SSH test pod for network tests
    ├── sequential-migration.sh       # Sequential migration example
    ├── parallel-migration.sh         # Parallel migration example
    ├── evacuation-scenario.sh        # Node evacuation example
    └── round-robin-migration.sh      # Round-robin migration example
```

---

## Best Practices

1. **Validate First**: Always run cluster validation before benchmarks
   ```bash
   virtbench validate-cluster --storage-class YOUR-STORAGE-CLASS --all
   ```

2. **Use Templates**: Use the template helper script for consistent VM configurations
   ```bash
   ./utils/apply_template.sh -o /tmp/vm.yaml -n my-vm -s YOUR-STORAGE-CLASS
   ```

3. **Start Small**: Begin with 5-10 VMs to validate your setup before scaling
   ```bash
   virtbench datasource-clone --start 1 --end 5 --storage-class YOUR-STORAGE-CLASS
   ```

4. **Monitor Resources**: Watch cluster resource utilization during tests
   ```bash
   kubectl top nodes
   kubectl top pods -A
   ```

5. **Use Dedicated Namespaces**: Tests create namespaces with predictable names for easy cleanup

6. **Save Results**: Use `--save-results` to preserve test results data for dashboard generation
   ```bash
   virtbench datasource-clone --start 1 --end 100 --storage-class YOUR-STORAGE-CLASS --save-results
   ```

7. **Cleanup**: Remove test resources after completion to free cluster resources
   ```bash
   virtbench datasource-clone --start 1 --end 100 --storage-class YOUR-STORAGE-CLASS --cleanup
   ```

8. **Network Testing**: Deploy an SSH pod in advance for ping tests
   ```bash
   kubectl apply -f examples/ssh-pod.yaml
   kubectl wait --for=condition=Ready pod/ssh-test-pod -n default --timeout=300s
   ```

9. **Use Log Files**: Save logs for debugging and analysis
   ```bash
   virtbench datasource-clone --start 1 --end 100 --storage-class YOUR-STORAGE-CLASS \
     --log-file test-$(date +%Y%m%d-%H%M%S).log
   ```

10. **Run Multiple Iterations**: For reliable benchmarks, run tests multiple times and compare results

---

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub

## Acknowledgments

- OpenShift Virtualization Team
- KubeVirt Community
- All contributors and users

