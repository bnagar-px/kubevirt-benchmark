# Cluster Validation Guide

This guide explains how to validate your cluster before running KubeVirt benchmarks.

## Overview

The cluster validation script (`utils/validate_cluster.py`) checks that your OpenShift cluster is properly configured and ready to run KubeVirt performance tests.

## Quick Start

### Basic Validation

```bash
cd utils
python3 validate_cluster.py --storage-class portworx-fada-sc
```

### Comprehensive Validation

```bash
python3 validate_cluster.py --all --storage-class portworx-fada-sc
```

## Validation Checks

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

## Command Line Options

```bash
python3 validate_cluster.py --help
```

### Common Options

| Option | Description | Default |
|--------|-------------|---------|
| `--storage-class NAME` | Storage class name to validate | - |
| `--datasource NAME` | DataSource name to validate | rhel9 |
| `--datasource-namespace NS` | DataSource namespace | openshift-virtualization-os-images |
| `--min-worker-nodes NUM` | Minimum worker nodes required | 1 |
| `--all` | Run all validation checks | false |
| `--log-level LEVEL` | Logging level | INFO |

## Usage Examples

### 1. Validate Storage Class

```bash
python3 validate_cluster.py --storage-class portworx-fada-sc
```

### 2. Validate with Custom DataSource

```bash
python3 validate_cluster.py \
  --storage-class portworx-fada-sc \
  --datasource fedora \
  --datasource-namespace openshift-virtualization-os-images
```

### 3. Require Minimum Worker Nodes

```bash
python3 validate_cluster.py \
  --storage-class portworx-fada-sc \
  --min-worker-nodes 5
```

### 4. Run All Checks

```bash
python3 validate_cluster.py --all \
  --storage-class portworx-fada-sc \
  --datasource rhel9
```

## Exit Codes

- `0` - All checks passed, cluster is ready
- `1` - One or more checks failed, cluster not ready

## Integration with Benchmark Scripts

### Python Integration

```python
import subprocess
import sys

def validate_cluster(storage_class):
    """Validate cluster before running benchmarks"""
    result = subprocess.run(
        ['python3', 'utils/validate_cluster.py', '--storage-class', storage_class],
        capture_output=True
    )
    if result.returncode != 0:
        print("Cluster validation failed!")
        sys.exit(1)
    print("Cluster validation passed!")

validate_cluster('portworx-fada-sc')
```

### Shell Script Integration

```bash
#!/bin/bash
set -e

python3 utils/validate_cluster.py --storage-class portworx-fada-sc

if [ $? -eq 0 ]; then
    echo "Starting benchmarks..."
    python3 measure-vm-creation-time.py --start 1 --end 10
else
    echo "Validation failed. Fix issues before running benchmarks."
    exit 1
fi
```

## Troubleshooting Validation Failures

### OpenShift Virtualization Not Found

**Error:** `No KubeVirt resource found. Is OpenShift Virtualization installed?`

**Check:**
```bash
# Check if KubeVirt resource exists
kubectl get kubevirt -A

# Expected output:
# NAMESPACE       NAME                               AGE   PHASE
# openshift-cnv   kubevirt-kubevirt-hyperconverged   58d   Deployed
```

**Fix:**
1. Install OpenShift Virtualization operator from OperatorHub
2. Create HyperConverged resource
3. Wait for deployment to complete

### Components Not Ready

**Error:** `KubeVirt components not ready: virt-api (1/2), virt-controller (0/2)`

**Check:**
```bash
# Check deployment status
kubectl get deployment -n openshift-cnv | grep -E "virt-api|virt-controller|virt-operator"

# Check pod status
kubectl get pods -n openshift-cnv | grep -E "virt-api|virt-controller|virt-operator"

# Check pod logs for errors
kubectl logs -n openshift-cnv deployment/virt-api
kubectl logs -n openshift-cnv deployment/virt-controller
```

**Fix:**
- Wait for pods to become ready
- Check for resource constraints
- Review pod events: `kubectl describe pod <pod-name> -n openshift-cnv`

### virt-handler Daemonset Issues

**Error:** `virt-handler daemonset not ready (2/3 pods ready)`

**Check:**
```bash
# Check daemonset status
kubectl get daemonset virt-handler -n openshift-cnv

# Check which nodes are missing virt-handler
kubectl get pods -n openshift-cnv -l kubevirt.io=virt-handler -o wide

# Check node labels
kubectl get nodes --show-labels | grep worker
```

**Fix:**
- Ensure all worker nodes have `kubernetes.io/os=linux` label
- Check node conditions: `kubectl describe node <node-name>`
- Review daemonset events: `kubectl describe daemonset virt-handler -n openshift-cnv`

### Storage Class Not Found

**Error:** `Storage class 'portworx-fada-sc' not found`

**Check:**
```bash
# List all storage classes
kubectl get storageclass

# Check specific storage class
kubectl get storageclass portworx-fada-sc -o yaml
```

**Fix:**
```bash
# Create storage class from examples
kubectl apply -f examples/storage-classes/portworx/portworx-fada-sc.yaml
```

## See Also

- [TEMPLATE_GUIDE.md](TEMPLATE_GUIDE.md) - VM template usage guide
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [SETUP.md](SETUP.md) - Detailed setup instructions

