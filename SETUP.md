# Setup Guide

This guide walks you through setting up the KubeVirt Performance Testing Suite in your OpenShift environment.

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] OpenShift Container Platform 4.10+ installed
- [ ] OpenShift Virtualization operator installed and configured
- [ ] Portworx Enterprise 2.x+ installed and configured
- [ ] kubectl CLI installed and configured
- [ ] Python 3.6+ installed
- [ ] Cluster admin or equivalent permissions
- [ ] Sufficient cluster resources (CPU, memory, storage)

## Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/kubevirt-benchmark-suite.git
cd kubevirt-benchmark-suite
```

## Step 2: Configure Storage Classes

### Option A: Standard Portworx Storage

1. Review the storage class configuration:
```bash
cat examples/storage-classes/portworx/portworx-raw-sc.yaml
```

2. Update parameters if needed (replication factor, I/O priority, etc.)

3. Create the storage class:
```bash
kubectl apply -f examples/storage-classes/portworx/portworx-raw-sc.yaml
```

4. Verify:
```bash
kubectl get sc portworx-raw-sc
```

### Option B: Pure FlashArray Direct Access (FADA)

1. Review the FADA storage class:
```bash
cat examples/storage-classes/portworx/portworx-fada-sc.yaml
```

2. **Important**: Update the `pure_fa_pod_name` parameter with your FlashArray pod name:
```bash
# Find your FlashArray pod name
kubectl get pods -n kube-system | grep pure

# Edit the storage class
vim examples/storage-classes/portworx/portworx-fada-sc.yaml
# Update: pure_fa_pod_name: "your-actual-flasharray-pod-name"
```

3. Create the storage class:
```bash
kubectl apply -f examples/storage-classes/portworx/portworx-fada-sc.yaml
```

4. Verify:
```bash
kubectl get sc portworx-fada-sc
```

## Step 3: Create SSH Test Pod

The SSH test pod is used for network connectivity tests (ping).

1. Review the SSH pod configuration:
```bash
cat examples/ssh-pod.yaml
```

2. Create the pod:
```bash
kubectl apply -f examples/ssh-pod.yaml
```

3. Wait for the pod to be ready:
```bash
kubectl wait --for=condition=Ready pod/ssh-test-pod -n default --timeout=300s
```

4. Verify the pod can ping:
```bash
kubectl exec -n default ssh-test-pod -- ping -c 1 8.8.8.8
```

## Step 4: Setup for DataSource Clone Tests

If you plan to use the datasource-clone method:

### 4.1: Verify DataSource

Check if the RHEL 9 DataSource exists:
```bash
kubectl get datasource -n openshift-virtualization-os-images
```

### 4.2: Update VM Template

Edit the VM template to replace placeholders:
```bash
# Option 1: Use sed to replace the storage class template variable
sed -i 's/{{STORAGE_CLASS_NAME}}/portworx-fada-sc/g' examples/vm-templates/vm-template.yaml

# Option 2: Manually edit the template
vim examples/vm-templates/vm-template.yaml
```

Update the following template variables:
- `{{STORAGE_CLASS_NAME}}`: Replace with your storage class name (e.g., `portworx-fada-sc` or `portworx-raw-sc`)
- `sourceRef.name`: Update DataSource name if different from `rhel9`
- `storage`: Adjust size as needed (default: 30Gi)

## Step 5: Setup for Failure Recovery Tests

If you plan to run FAR (Fence Agents Remediation) tests:

### 5.1: Verify FAR Operator

Check if the Fence Agents Remediation operator is installed:
```bash
kubectl get pods -n openshift-workload-availability
```

If not installed, install it from OperatorHub.

### 5.2: Configure FAR Template

Edit the FAR configuration:
```bash
vim failure-recovery/far-template.yaml
```

Update with your environment details:
- Node names
- BMC IP addresses
- BMC credentials (consider using Secrets in production)
- BMC ports

### 5.3: Test FAR Configuration (Optional)

Before running full tests, verify FAR works on a single node:
```bash
# Create a test namespace with a VM
kubectl create namespace far-test
kubectl apply -f examples/vm-templates/vm-template.yaml -n far-test

# Wait for VM to be running
kubectl get vm -n far-test -w

# Apply FAR (this will reboot the node!)
kubectl apply -f failure-recovery/far-template.yaml

# Monitor recovery
kubectl get vmi -n far-test -w

# Cleanup
kubectl delete -f failure-recovery/far-template.yaml
kubectl delete namespace far-test
```

## Step 6: Make Scripts Executable

```bash
chmod +x datasource-clone/measure-vm-creation-time.py
chmod +x migration/measure-vm-migration-time.py
chmod +x failure-recovery/measure-recovery-time.py
chmod +x failure-recovery/run-far-test.sh
chmod +x failure-recovery/patch-vms.sh
```

## Step 7: Verify Setup

Run a small-scale test to verify everything works:

### DataSource Clone Test
```bash
cd datasource-clone
python3 measure-vm-creation-time.py --start 1 --end 5 --log-level DEBUG
```

## Step 8: Cleanup Test Resources

After verification, clean up test resources:

```bash
# Delete test namespaces
for i in {1..5}; do
  kubectl delete namespace kubevirt-perf-test-$i
done
```

## Troubleshooting Setup Issues

### Issue: Storage Class Not Found

**Symptom**: PVCs remain in Pending state

**Solution**:
```bash
# Verify Portworx is running
kubectl get pods -n kube-system | grep portworx

# Check storage class
kubectl get sc

# Verify Portworx cluster status
/opt/pwx/bin/pxctl status
```

### Issue: Golden Images Not Ready

**Symptom**: DataVolumes stuck in "ImportInProgress"

**Solution**:
```bash
# Check CDI operator logs
kubectl logs -n openshift-cnv -l name=cdi-operator

# Check importer pod logs
kubectl get pods -n openshift-virtualization-os-images
kubectl logs -n openshift-virtualization-os-images <importer-pod-name>

# Verify image stream exists
kubectl get imagestream -n openshift-virtualization-os-images
```

### Issue: SSH Pod Cannot Ping

**Symptom**: Ping tests fail

**Solution**:
```bash
# Check pod status
kubectl get pod ssh-test-pod -n default

# Check pod logs
kubectl logs ssh-test-pod -n default

# Verify network connectivity
kubectl exec -n default ssh-test-pod -- ip addr
kubectl exec -n default ssh-test-pod -- ping -c 1 8.8.8.8

# Check network policies
kubectl get networkpolicies -A
```

### Issue: Permission Denied

**Symptom**: kubectl commands fail with permission errors

**Solution**:
```bash
# Verify your permissions
kubectl auth can-i create vm --all-namespaces
kubectl auth can-i create namespace

# If needed, request cluster-admin or appropriate RBAC roles
```

### Issue: Python Script Fails

**Symptom**: Import errors or syntax errors

**Solution**:
```bash
# Verify Python version
python3 --version  # Should be 3.6+

# Check if utils module is accessible
cd kubevirt-benchmark-suite
python3 -c "import sys; sys.path.insert(0, '.'); from utils.common import setup_logging"
```

## Next Steps

Once setup is complete:

1. Review the [README.md](README.md) for usage examples
2. Start with small-scale tests (10-20 VMs)
3. Gradually increase scale based on cluster capacity
4. Monitor cluster resources during tests
5. Save test results for analysis

## Production Considerations

When using in production environments:

1. **Credentials**: Use Kubernetes Secrets for sensitive data (BMC passwords, etc.)
2. **Resource Limits**: Set appropriate resource requests/limits on VMs
3. **Network Policies**: Configure network policies as needed
4. **Monitoring**: Set up monitoring for test execution
5. **Scheduling**: Use node selectors/affinity to control VM placement
6. **Backup**: Ensure test data is backed up if needed

## Support

For issues or questions:
- Check the [Troubleshooting](#troubleshooting-setup-issues) section
- Review GitHub Issues
- Consult the [CONTRIBUTING.md](CONTRIBUTING.md) guide

