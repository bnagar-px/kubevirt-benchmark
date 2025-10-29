# Quick Start Guide

Get started with KubeVirt performance testing in 5 minutes!

## Prerequisites

- OpenShift cluster with KubeVirt and Portworx
- kubectl configured
- Python 3.6+

## 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/kubevirt-benchmark-suite.git
cd kubevirt-benchmark-suite

# Make scripts executable
chmod +x datasource-clone/*.py migration/*.py failure-recovery/*.py failure-recovery/*.sh
```

## 2. Create SSH Test Pod

```bash
# Deploy SSH pod for network tests
kubectl apply -f examples/ssh-pod.yaml

# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/ssh-test-pod -n default --timeout=300s
```

## 3. Run Your First Test

### DataSource-Based VM Provisioning

```bash
cd datasource-clone

# Update VM template with your storage class
# Replace {{STORAGE_CLASS_NAME}} with your actual storage class
# Options: portworx-fada-sc, portworx-raw-sc, or your custom storage class
sed -i 's/{{STORAGE_CLASS_NAME}}/portworx-fada-sc/g' ../examples/vm-templates/vm-template.yaml

# Run a small test (5 VMs)
python3 measure-vm-creation-time.py --start 1 --end 5
```

## 4. View Results

The test will output:
- Real-time progress for each VM
- Time to Running state
- Time to network ready (ping)
- Summary statistics

Example output:
```
Performance Test Summary
================================================================================
Namespace                Running(s)      Ping(s)         Status
--------------------------------------------------------------------------------
kubevirt-perf-test-1     8.45           11.23           Success
kubevirt-perf-test-2     9.12           12.45           Success
...
================================================================================
Statistics:
  Total VMs:              5
  Successful:             5
  Failed:                 0
  Avg Time to Running:    9.23s
  Avg Time to Ping:       12.45s
================================================================================
```

## 5. Cleanup

```bash
# Delete test namespaces
for i in {1..5}; do
  kubectl delete namespace kubevirt-perf-test-$i
done
```

## Common Commands

### Run with custom settings
```bash
# Test 50 VMs with higher concurrency
python3 measure-vm-creation-time.py --start 1 --end 50 --concurrency 100

# Save results to file
python3 measure-vm-creation-time.py --start 1 --end 20 --log-file results.log

# Use custom namespace prefix
python3 measure-vm-creation-time.py --start 1 --end 10 --namespace-prefix my-test

# Enable debug logging
python3 measure-vm-creation-time.py --start 1 --end 5 --log-level DEBUG
```

### Cleanup with script
```bash
# Cleanup and delete namespaces automatically
python3 measure-vm-creation-time.py --start 1 --end 10 --cleanup
```

## Troubleshooting

### VMs not starting?
```bash
# Check storage class
kubectl get sc

# Check Portworx status
kubectl get pods -n kube-system | grep portworx

# Check VM events
kubectl describe vm rhel-9-vm -n kubevirt-perf-test-1
```

### Ping tests failing?
```bash
# Verify SSH pod is running
kubectl get pod ssh-test-pod -n default

# Test SSH pod connectivity
kubectl exec -n default ssh-test-pod -- ping -c 1 8.8.8.8
```

### Permission errors?
```bash
# Check your permissions
kubectl auth can-i create vm --all-namespaces
kubectl auth can-i create namespace
```

## Next Steps

1. **Scale Up**: Try testing with 50-100 VMs
2. **Customize**: Modify VM templates for your needs
3. **Monitor**: Watch cluster resources during tests
4. **Analyze**: Compare results across different configurations
5. **FAR Testing**: Try failure recovery tests (see [SETUP.md](SETUP.md))

## Getting Help

- Full documentation: [README.md](README.md)
- Setup guide: [SETUP.md](SETUP.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Issues: GitHub Issues

## Tips for Best Results

1. **Start Small**: Begin with 5-10 VMs to validate setup
2. **Monitor Resources**: Watch CPU, memory, and storage during tests
3. **Use Logs**: Always save logs with `--log-file` for analysis
4. **Test Incrementally**: Gradually increase VM count
5. **Clean Up**: Remove test resources to free cluster capacity

Happy testing! 🚀

