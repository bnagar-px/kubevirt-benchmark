# VM Template Guide

This guide explains how to use the templated VM configurations in the KubeVirt Benchmark Suite.

## Overview

The VM templates use placeholder variables (e.g., `{{VM_NAME}}`, `{{STORAGE_CLASS_NAME}}`) that can be replaced with actual values before deployment. This provides flexibility to customize VMs without editing the template files directly.

## Template Variables

The following variables are available in `examples/vm-templates/vm-template.yaml`:

| Variable | Description | Example Values |
|----------|-------------|----------------|
| `{{VM_NAME}}` | VM name | `rhel-9-vm`, `my-test-vm` |
| `{{STORAGE_CLASS_NAME}}` | Storage class name | `portworx-fada-sc`, `portworx-raw-sc` |
| `{{DATASOURCE_NAME}}` | DataSource name | `rhel9`, `fedora`, `centos` |
| `{{DATASOURCE_NAMESPACE}}` | DataSource namespace | `openshift-virtualization-os-images` |
| `{{STORAGE_SIZE}}` | Root disk storage size | `30Gi`, `50Gi`, `100Gi` |
| `{{VM_MEMORY}}` | VM memory allocation | `2048M`, `4Gi`, `8Gi` |
| `{{VM_CPU_CORES}}` | Number of CPU cores | `1`, `2`, `4`, `8` |

## Method 1: Using the Helper Script (Recommended)

The `utils/apply_template.sh` script makes it easy to apply template variables:

### Basic Usage

```bash
cd utils

# Create a VM with custom name and storage class
./apply_template.sh \
  --output /tmp/my-vm.yaml \
  --vm-name my-test-vm \
  --storage-class portworx-fada-sc
```

### Advanced Usage

```bash
# Fully customized VM
./apply_template.sh \
  --output /tmp/custom-vm.yaml \
  --vm-name high-performance-vm \
  --storage-class portworx-raw-sc \
  --datasource fedora \
  --storage-size 100Gi \
  --memory 8Gi \
  --cpu-cores 4
```

### Apply Directly to Cluster

```bash
# Generate and apply in one command
./apply_template.sh \
  --output /tmp/vm.yaml \
  --vm-name test-vm \
  --storage-class portworx-fada-sc && \
kubectl apply -f /tmp/vm.yaml -n test-namespace
```

### Available Options

```bash
./apply_template.sh --help
```

Options:
- `-t, --template FILE` - Template file path (default: ../examples/vm-templates/vm-template.yaml)
- `-o, --output FILE` - Output file path (required)
- `-n, --vm-name NAME` - VM name (default: rhel-9-vm)
- `-s, --storage-class NAME` - Storage class name (default: portworx-fada-sc)
- `-d, --datasource NAME` - DataSource name (default: rhel9)
- `--datasource-namespace NS` - DataSource namespace
- `--storage-size SIZE` - Storage size (default: 30Gi)
- `--memory SIZE` - VM memory (default: 2048M)
- `--cpu-cores NUM` - Number of CPU cores (default: 1)

## Method 2: Using sed Directly

For simple replacements, you can use sed:

```bash
# Replace storage class only
sed 's/{{STORAGE_CLASS_NAME}}/portworx-fada-sc/g' \
  examples/vm-templates/vm-template.yaml > /tmp/vm.yaml

# Replace multiple variables
cat examples/vm-templates/vm-template.yaml | \
  sed 's/{{VM_NAME}}/my-vm/g' | \
  sed 's/{{STORAGE_CLASS_NAME}}/portworx-fada-sc/g' | \
  sed 's/{{STORAGE_SIZE}}/50Gi/g' | \
  sed 's/{{VM_MEMORY}}/4Gi/g' | \
  sed 's/{{VM_CPU_CORES}}/2/g' \
  > /tmp/my-vm.yaml
```

## Method 3: Manual Editing

You can also copy the template and manually edit it:

```bash
cp examples/vm-templates/vm-template.yaml /tmp/my-vm.yaml
vim /tmp/my-vm.yaml
# Replace {{VARIABLE}} placeholders with actual values
```

## Integration with Benchmark Scripts

The benchmark scripts can use templates programmatically:

### Python Example

```python
import subprocess

def apply_template(vm_name, storage_class, output_file):
    """Apply template variables using the helper script"""
    cmd = [
        './utils/apply_template.sh',
        '--output', output_file,
        '--vm-name', vm_name,
        '--storage-class', storage_class,
    ]
    subprocess.run(cmd, check=True)
    return output_file

# Use in your script
vm_yaml = apply_template('test-vm-1', 'portworx-fada-sc', '/tmp/vm-1.yaml')
# Now apply the VM
subprocess.run(['kubectl', 'apply', '-f', vm_yaml, '-n', 'test-ns'], check=True)
```

## Common Use Cases

### 1. Testing Different Storage Classes

```bash
# Test with FADA storage
./apply_template.sh -o /tmp/vm-fada.yaml -n test-vm -s portworx-fada-sc

# Test with standard Portworx
./apply_template.sh -o /tmp/vm-raw.yaml -n test-vm -s portworx-raw-sc
```

### 2. Creating VMs with Different Sizes

```bash
# Small VM
./apply_template.sh -o /tmp/vm-small.yaml -n small-vm \
  --storage-size 20Gi --memory 1Gi --cpu-cores 1

# Medium VM
./apply_template.sh -o /tmp/vm-medium.yaml -n medium-vm \
  --storage-size 50Gi --memory 4Gi --cpu-cores 2

# Large VM
./apply_template.sh -o /tmp/vm-large.yaml -n large-vm \
  --storage-size 100Gi --memory 8Gi --cpu-cores 4
```

### 3. Testing Different OS Images

```bash
# RHEL 9
./apply_template.sh -o /tmp/vm-rhel9.yaml -n rhel9-vm -d rhel9

# Fedora
./apply_template.sh -o /tmp/vm-fedora.yaml -n fedora-vm -d fedora

# CentOS
./apply_template.sh -o /tmp/vm-centos.yaml -n centos-vm -d centos
```

### 4. Batch VM Creation

```bash
# Create 10 VMs with different names
for i in {1..10}; do
  ./apply_template.sh \
    --output /tmp/vm-$i.yaml \
    --vm-name test-vm-$i \
    --storage-class portworx-fada-sc
  kubectl apply -f /tmp/vm-$i.yaml -n test-namespace
done
```

## Best Practices

1. **Always validate templates** before applying to production:
   ```bash
   kubectl apply -f /tmp/vm.yaml --dry-run=client
   ```

2. **Use descriptive VM names** that include purpose and iteration:
   ```bash
   --vm-name perf-test-rhel9-001
   ```

3. **Keep generated files** for debugging:
   ```bash
   mkdir -p generated-vms
   ./apply_template.sh --output generated-vms/vm-$i.yaml ...
   ```

4. **Validate storage class exists** before creating VMs:
   ```bash
   kubectl get storageclass portworx-fada-sc
   ```

5. **Use consistent naming conventions** across your tests:
   ```bash
   # Good: test-vm-001, test-vm-002, test-vm-003
   # Bad: vm1, myvm, test_vm_2
   ```

## Troubleshooting

### Template variables not replaced

**Problem**: VM creation fails with errors about `{{VARIABLE}}`

**Solution**: Ensure all template variables are replaced:
```bash
# Check for remaining template variables
grep -E '\{\{.*\}\}' /tmp/vm.yaml
```

### Storage class not found

**Problem**: PVC remains in Pending state

**Solution**: Verify storage class exists:
```bash
kubectl get storageclass
# Use the exact name from the output
```

### DataSource not found

**Problem**: DataVolume fails to clone

**Solution**: Check DataSource availability:
```bash
kubectl get datasource -n openshift-virtualization-os-images
```

### Invalid resource values

**Problem**: VM fails to start with resource errors

**Solution**: Use valid Kubernetes resource formats:
- Memory: `512M`, `1Gi`, `2Gi`, `4Gi`, `8Gi`
- Storage: `10Gi`, `20Gi`, `30Gi`, `50Gi`, `100Gi`
- CPU: Integer values only: `1`, `2`, `4`, `8`

## See Also

- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [SETUP.md](SETUP.md) - Detailed setup instructions
- [README.md](README.md) - Main documentation
- [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md) - Cluster validation guide

