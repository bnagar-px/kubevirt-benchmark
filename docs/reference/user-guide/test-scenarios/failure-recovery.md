# Failure and Recovery Testing

Tests VM recovery time after simulated node failures using Fence Agents Remediation (FAR).

**Use Case**: Validates high availability and disaster recovery capabilities.

## Prerequisites for FAR Testing

!!! warning "Important"
    Before running failure and recovery tests, you must have the following operators installed and configured on your cluster.

### Required Operators

#### 1. Node Health Check Operator (NHC)

The Node Health Check Operator monitors node health and automatically creates remediation CRs when nodes become unhealthy. NHC is responsible for:

- Detecting unhealthy nodes based on configurable conditions
- Creating FenceAgentsRemediation CRs to trigger remediation
- Deleting remediation CRs after nodes recover

#### 2. Fence Agents Remediation Operator (FAR)

The Fence Agents Remediation Operator performs the actual node fencing using fence agents (e.g., IPMI, AWS, etc.). FAR is responsible for:

- Tainting unhealthy nodes to prevent workload scheduling
- Executing fence agent commands to reboot or power off nodes
- Evicting workloads from unhealthy nodes

Both operators are part of the [MedIK8s](https://www.medik8s.io/) project for Kubernetes node remediation.

### Installation & Configuration

1. Install both operators via OperatorHub (OpenShift) or follow the MedIK8s installation guides
2. Create a `FenceAgentsRemediationTemplate` CR with your fence agent configuration (IPMI, AWS, etc.)
3. Create a `NodeHealthCheck` CR that references your FAR template
4. Configure fence agent credentials (BMC/IPMI credentials, cloud provider credentials, etc.)

!!! info "Documentation"
    Configuration is environment-specific and depends on your fencing method (IPMI, AWS, etc.). Please refer to the official MedIK8s documentation for detailed setup instructions:
    
    - [Node Health Check Operator](https://www.medik8s.io/remediation/node-healthcheck-operator/node-healthcheck-operator/)
    - [Fence Agents Remediation](https://www.medik8s.io/remediation/fence-agents-remediation/fence-agents-remediation/)

### Verify Installation

```bash
# Verify CRDs are available
kubectl get crd nodehealthchecks.remediation.medik8s.io
kubectl get crd fenceagentsremediations.fence-agents-remediation.medik8s.io

# Verify your FenceAgentsRemediationTemplate exists
kubectl get fenceagentsremediationtemplates -A

# Verify your NodeHealthCheck is configured
kubectl get nodehealthchecks -A
```

## Running FAR Tests

### Using virtbench CLI

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
  --vm-name debian-vm \
  --far-name my-far-resource \
  --save-results
```

### Using Python Script

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

## What the Test Measures

The failure recovery test measures:

1. **Detection Time**: Time to detect node failure
2. **Remediation Time**: Time to execute fence agent and taint node
3. **VM Recovery Time**: Time for VMs to restart on healthy nodes
4. **Network Recovery Time**: Time for VMs to become network-reachable
5. **Total Recovery Time**: End-to-end recovery duration

## Understanding Results

### Key Metrics

- **Time to VMI Deletion**: How long until failed VMIs are deleted
- **Time to VM Restart**: How long until VMs restart on new nodes
- **Time to Running**: How long until VMs reach Running state
- **Time to Ping**: How long until VMs are network-reachable
- **Total Recovery Time**: Complete recovery duration

### Recovery Time Objectives (RTO)

| RTO Level | Total Recovery Time | Status |
|-----------|---------------------|--------|
| Excellent | < 5 minutes | HA working optimally |
| Good | 5-10 minutes | Acceptable for most workloads |
| Concerning | 10-20 minutes | Review configuration |
| Critical | > 20 minutes | HA issues need attention |

## Cleanup

### Using virtbench CLI

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

### Using Python Script

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

## Troubleshooting

### FAR CR Not Created

**Cause**: NodeHealthCheck not detecting node failure

**Solution**:
- Verify NodeHealthCheck CR is configured correctly
- Check node conditions match NHC configuration
- Review NHC operator logs

### VMs Not Recovering

**Cause**: Fence agent not executing or node not being fenced

**Solution**:
- Verify FenceAgentsRemediationTemplate is correct
- Check fence agent credentials
- Review FAR operator logs
- Verify node is actually being fenced (check BMC/cloud console)

### Slow Recovery Times

**Cause**: Various factors can slow recovery

**Solution**:
- Reduce NHC detection timeout
- Optimize fence agent timeout settings
- Ensure sufficient resources on healthy nodes
- Check storage backend performance

## See Also

- [Configuration Options](../configuration.md) - Detailed configuration reference
- [Output and Results](../output-and-results.md) - Understanding test output
- [MedIK8s Documentation](https://www.medik8s.io/) - Official operator documentation

