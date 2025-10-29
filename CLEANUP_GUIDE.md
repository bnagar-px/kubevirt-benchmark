# Cleanup Guide

This guide provides comprehensive information about cleaning up resources created during KubeVirt performance testing.

## Table of Contents

- [Overview](#overview)
- [Automatic Cleanup](#automatic-cleanup)
- [Manual Cleanup](#manual-cleanup)
- [Cleanup Options Reference](#cleanup-options-reference)
- [Safety Features](#safety-features)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

The KubeVirt Performance Testing Suite creates various Kubernetes resources during testing:

- **Namespaces**: Test namespaces (e.g., `kubevirt-perf-test-1` to `kubevirt-perf-test-N`)
- **VMs**: VirtualMachine resources
- **VMIs**: VirtualMachineInstance resources (created automatically by VMs)
- **DataVolumes**: For VM disk provisioning
- **PVCs**: PersistentVolumeClaims for storage
- **VMIMs**: VirtualMachineInstanceMigration objects (for migration tests)
- **FAR Resources**: FenceAgentsRemediation custom resources (for failure recovery tests)

All test scripts now support comprehensive cleanup functionality to remove these resources after testing.

## Automatic Cleanup

### VM Creation Tests

#### Basic Cleanup
```bash
cd datasource-clone

# Clean up after successful test
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --cleanup
```

#### Cleanup on Failure
```bash
# Clean up even if some VMs fail to start
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --cleanup-on-failure
```

#### Dry Run (Preview)
```bash
# See what would be deleted without actually deleting
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --dry-run-cleanup
```

#### Skip Confirmation
```bash
# Skip confirmation prompt (use with caution!)
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 100 \
  --vm-name rhel-9-vm \
  --cleanup \
  --yes
```

#### Boot Storm Cleanup
```bash
# Cleanup works the same for boot storm tests
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 50 \
  --vm-name rhel-9-vm \
  --boot-storm \
  --cleanup
```

**Resources Cleaned:**
- ✅ All VMs in test namespaces
- ✅ All DataVolumes
- ✅ All PVCs
- ✅ All test namespaces

### Migration Tests

#### Cleanup VMIMs Only
```bash
cd migration

# Clean up migration objects (VMs remain)
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 50 \
  --source-node worker-1 \
  --target-node worker-2 \
  --cleanup
```

#### Cleanup Everything
```bash
# Clean up VMs and namespaces (only if created by test)
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 50 \
  --create-vms \
  --source-node worker-1 \
  --cleanup
```

#### Evacuation Cleanup
```bash
# Clean up after node evacuation
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 100 \
  --evacuate \
  --source-node worker-3 \
  --cleanup
```

**Resources Cleaned:**
- ✅ All VirtualMachineInstanceMigration objects
- ✅ VMs and namespaces (only if `--create-vms` was used)
- ✅ Node selector modifications (automatic)

### Failure Recovery Tests

#### Basic FAR Cleanup
```bash
cd failure-recovery

# Clean up FAR resources and annotations
python3 measure-recovery-time.py \
  --start 1 \
  --end 60 \
  --vm-name rhel-9-vm \
  --ssh-pod ssh-test-pod \
  --ssh-pod-ns default \
  --cleanup \
  --far-name my-far-resource \
  --failed-node worker-1
```

#### Complete Cleanup (Including VMs)
```bash
# Clean up FAR resources AND delete VMs/namespaces
python3 measure-recovery-time.py \
  --start 1 \
  --end 60 \
  --vm-name rhel-9-vm \
  --ssh-pod ssh-test-pod \
  --ssh-pod-ns default \
  --cleanup \
  --cleanup-vms \
  --far-name my-far-resource \
  --far-namespace default \
  --failed-node worker-1
```

**Resources Cleaned:**
- ✅ FenceAgentsRemediation custom resources
- ✅ FAR annotations from VMs (`vm.kubevirt.io/fenced`)
- ✅ Uncordon failed nodes
- ✅ VMs, DataVolumes, PVCs, namespaces (with `--cleanup-vms`)

## Manual Cleanup

If automatic cleanup fails or you need to clean up manually:

### Delete Namespaces

```bash
# Delete specific range
for i in {1..50}; do
  kubectl delete namespace kubevirt-perf-test-$i &
done
wait

# Delete all test namespaces
kubectl get namespaces | grep kubevirt-perf-test | awk '{print $1}' | xargs kubectl delete namespace

# Force delete stuck namespace
kubectl delete namespace kubevirt-perf-test-1 --force --grace-period=0
```

### Delete VMs

```bash
# Delete VM in specific namespace
kubectl delete vm rhel-9-vm -n kubevirt-perf-test-1

# Delete all VMs in namespace
kubectl delete vm --all -n kubevirt-perf-test-1
```

### Delete DataVolumes

```bash
# Delete specific DataVolume
kubectl delete dv rhel-9-vm-dv -n kubevirt-perf-test-1

# Delete all DataVolumes in namespace
kubectl delete dv --all -n kubevirt-perf-test-1
```

### Delete PVCs

```bash
# Delete specific PVC
kubectl delete pvc rhel-9-vm-pvc -n kubevirt-perf-test-1

# Delete all PVCs in namespace
kubectl delete pvc --all -n kubevirt-perf-test-1
```

### Delete VMIMs

```bash
# Delete specific VMIM
kubectl delete virtualmachineinstancemigration migration-rhel-9-vm -n kubevirt-perf-test-1

# Delete all VMIMs in namespace
kubectl delete virtualmachineinstancemigration --all -n kubevirt-perf-test-1

# Delete VMIMs across all test namespaces
for i in {1..50}; do
  kubectl delete virtualmachineinstancemigration --all -n kubevirt-perf-test-$i
done
```

### Clean FAR Resources

```bash
# Delete FAR resource
kubectl delete fenceagentsremediation my-far-resource -n default

# Remove FAR annotation from VM
kubectl annotate vm rhel-9-vm vm.kubevirt.io/fenced- -n kubevirt-perf-test-1

# Uncordon node
kubectl uncordon worker-1
```

### Emergency Cleanup Script

```bash
#!/bin/bash
# emergency-cleanup.sh - Clean up all test resources

NAMESPACE_PREFIX="kubevirt-perf-test"
START=1
END=100

echo "Cleaning up test resources..."

# Delete all VMIMs
for i in $(seq $START $END); do
  kubectl delete virtualmachineinstancemigration --all -n ${NAMESPACE_PREFIX}-$i 2>/dev/null &
done
wait

# Delete all namespaces
for i in $(seq $START $END); do
  kubectl delete namespace ${NAMESPACE_PREFIX}-$i 2>/dev/null &
done
wait

echo "Cleanup complete!"
```

## Cleanup Options Reference

### Common Options (All Scripts)

| Option | Description | Default |
|--------|-------------|---------|
| `--cleanup` | Delete test resources after completion | false |
| `--cleanup-on-failure` | Clean up even if tests fail | false |
| `--dry-run-cleanup` | Show what would be deleted without deleting | false |
| `--yes` | Skip confirmation prompt | false |

### VM Creation Test Options

All common options plus:
- Cleans up: VMs, DataVolumes, PVCs, namespaces
- Works with: `--boot-storm`, `--single-node` modes

### Migration Test Options

All common options plus:
- Cleans up: VMIMs always, VMs/namespaces only if `--create-vms` was used
- Works with: `--parallel`, `--evacuate`, `--round-robin` modes

### Failure Recovery Test Options

| Option | Description | Default |
|--------|-------------|---------|
| `--cleanup` | Clean up FAR resources and annotations | false |
| `--cleanup-vms` | Also delete VMs and namespaces | false |
| `--far-name` | Name of FAR resource to delete | required |
| `--far-namespace` | Namespace of FAR resource | default |
| `--failed-node` | Node to uncordon | required |

## Safety Features

### 1. Confirmation Prompt

When cleaning up more than 10 namespaces, you'll be prompted:

```
WARNING: You are about to clean up 50 namespaces.
This will delete all VMs, DataVolumes, PVCs, and other resources.

Are you sure you want to continue? (yes/no):
```

Skip with `--yes` flag (use with caution).

### 2. Dry Run Mode

Preview what would be deleted:

```bash
python3 measure-vm-creation-time.py --start 1 --end 50 --dry-run-cleanup
```

Output:
```
[DRY RUN] Would delete VM: rhel-9-vm in kubevirt-perf-test-1
[DRY RUN] Would delete DataVolume: rhel-9-vm-dv in kubevirt-perf-test-1
[DRY RUN] Would delete namespace: kubevirt-perf-test-1
...
```

### 3. Namespace Prefix Verification

Cleanup only affects namespaces matching the test prefix (default: `kubevirt-perf-test`).

### 4. Detailed Logging

All cleanup operations are logged:

```
[INFO] 2024-01-15 10:30:00 - Deleting 50 namespaces in batches of 20...
[INFO] 2024-01-15 10:30:01 - Deleted VM rhel-9-vm in namespace kubevirt-perf-test-1
[INFO] 2024-01-15 10:30:02 - Deleted DataVolume rhel-9-vm-dv in namespace kubevirt-perf-test-1
```

### 5. Error Handling

Cleanup errors don't mask test results. Errors are logged but don't cause test failure.

### 6. Interrupt Handling (Ctrl+C)

If you press Ctrl+C during a test with `--cleanup` or `--cleanup-on-failure`:

```
Interrupt received (Ctrl+C)
Cleaning up resources before exit...
```

Resources are cleaned up before the script exits.

## Troubleshooting

### Namespace Stuck in Terminating

```bash
# Check what's blocking deletion
kubectl get namespace kubevirt-perf-test-1 -o yaml

# Force delete
kubectl delete namespace kubevirt-perf-test-1 --force --grace-period=0

# If still stuck, remove finalizers
kubectl patch namespace kubevirt-perf-test-1 -p '{"metadata":{"finalizers":[]}}' --type=merge
```

### PVC Not Deleting

```bash
# Check if PVC is in use
kubectl describe pvc rhel-9-vm-pvc -n kubevirt-perf-test-1

# Delete VM first, then PVC
kubectl delete vm rhel-9-vm -n kubevirt-perf-test-1
kubectl delete pvc rhel-9-vm-pvc -n kubevirt-perf-test-1
```

### VMIM Stuck

```bash
# Check VMIM status
kubectl get virtualmachineinstancemigration -n kubevirt-perf-test-1

# Force delete
kubectl delete virtualmachineinstancemigration migration-rhel-9-vm -n kubevirt-perf-test-1 --force --grace-period=0
```

### Node Won't Uncordon

```bash
# Check node status
kubectl get node worker-1 -o yaml

# Force uncordon
kubectl uncordon worker-1

# If still cordoned, check for taints
kubectl describe node worker-1 | grep Taints

# Remove taints if needed
kubectl taint nodes worker-1 key=value:NoSchedule-
```

## Best Practices

1. **Always Use Dry Run First**: In production, always run `--dry-run-cleanup` first
2. **Save Logs**: Use `--log-file` to preserve cleanup logs
3. **Cleanup After Tests**: Use `--cleanup` to avoid resource accumulation
4. **Monitor Cleanup**: Watch for errors in cleanup logs
5. **Verify Deletion**: After cleanup, verify resources are gone:
   ```bash
   kubectl get namespaces | grep kubevirt-perf-test
   ```
6. **Batch Cleanup**: For large numbers of namespaces, cleanup happens in parallel batches
7. **Production Safety**: Never use `--yes` in production without dry run first
8. **FAR Cleanup**: Always clean up FAR resources to avoid node scheduling issues
9. **Interrupt Safety**: If you need to stop a test, Ctrl+C will trigger cleanup if enabled
10. **Resource Limits**: Be aware of cluster resource limits when running large-scale tests

## Cleanup Summary Example

After cleanup completes, you'll see:

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

For FAR tests:

```
================================================================================
FAR CLEANUP SUMMARY
================================================================================
  FAR Resources Deleted:       1
  Annotations Removed:         60
  Nodes Uncordoned:            1
  Namespaces Deleted:          60
  VMs Deleted:                 60
  DataVolumes Deleted:         60
  PVCs Deleted:                60
  Errors:                      0
================================================================================
```

## Support

If you encounter cleanup issues:

1. Check the logs for error messages
2. Try manual cleanup commands
3. Use `--dry-run-cleanup` to diagnose issues
4. Check Kubernetes events: `kubectl get events -n kubevirt-perf-test-1`
5. Verify cluster permissions: `kubectl auth can-i delete namespace`

For persistent issues, open a GitHub issue with:
- Cleanup command used
- Error messages from logs
- Output of `kubectl get all -n kubevirt-perf-test-1`

