#!/bin/bash
"""
Orchestrate a complete Fence Agents Remediation (FAR) test.

This script:
1. Removes node selectors from VMs to allow rescheduling
2. Applies FAR configuration to trigger node failure
3. Waits for node remediation
4. Removes FAR configuration
5. Measures VM recovery time

Usage:
    ./run-far-test.sh --start 1 --end 60 --node-name worker-1 --vm-name rhel-9-vm

Author: KubeVirt Benchmark Suite Contributors
License: Apache 2.0
"""

set -euo pipefail

# Default values
START=1
END=60
VM_NAME="rhel-9-vm"
NODE_NAME=""
FAR_CONFIG="far-config.yaml"
SSH_POD="ssh-test-pod"
SSH_POD_NS="default"
CONCURRENCY=50
POLL_INTERVAL=1
LOG_FILE=""
NAMESPACE_PREFIX="kubevirt-perf-test"
DRY_RUN=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Orchestrate a complete FAR (Fence Agents Remediation) test for KubeVirt VMs.

Required Options:
  --node-name NAME          Name of the node to trigger FAR on

Optional Options:
  --start NUM               Start namespace index (default: 1)
  --end NUM                 End namespace index (default: 60)
  --vm-name NAME            VM name to monitor (default: rhel-9-vm)
  --namespace-prefix PREFIX Namespace prefix (default: kubevirt-perf-test)
  --far-config FILE         FAR configuration file (default: far-config.yaml)
  --ssh-pod NAME            SSH pod name for ping tests (default: ssh-test-pod)
  --ssh-pod-ns NAMESPACE    SSH pod namespace (default: default)
  --concurrency NUM         Monitoring concurrency (default: 50)
  --poll-interval NUM       Poll interval in seconds (default: 1)
  --log-file FILE           Log file path (optional)
  --dry-run                 Show what would be done without executing
  -h, --help                Show this help message

Examples:
  # Basic FAR test
  $0 --node-name worker-1 --start 1 --end 60 --vm-name rhel-9-vm

  # FAR test with custom configuration
  $0 --node-name worker-2 --start 1 --end 100 --far-config my-far.yaml

  # Dry run to see what would happen
  $0 --node-name worker-1 --dry-run

EOF
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --start)
            START="$2"
            shift 2
            ;;
        --end)
            END="$2"
            shift 2
            ;;
        --vm-name)
            VM_NAME="$2"
            shift 2
            ;;
        --node-name)
            NODE_NAME="$2"
            shift 2
            ;;
        --namespace-prefix)
            NAMESPACE_PREFIX="$2"
            shift 2
            ;;
        --far-config)
            FAR_CONFIG="$2"
            shift 2
            ;;
        --ssh-pod)
            SSH_POD="$2"
            shift 2
            ;;
        --ssh-pod-ns)
            SSH_POD_NS="$2"
            shift 2
            ;;
        --concurrency)
            CONCURRENCY="$2"
            shift 2
            ;;
        --poll-interval)
            POLL_INTERVAL="$2"
            shift 2
            ;;
        --log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$NODE_NAME" ]]; then
    log_error "Missing required argument: --node-name"
    usage
fi

# Print configuration
log_info "FAR Test Configuration:"
echo "  Node name:          $NODE_NAME"
echo "  Namespace range:    ${NAMESPACE_PREFIX}-${START} to ${NAMESPACE_PREFIX}-${END}"
echo "  VM name:            $VM_NAME"
echo "  FAR config:         $FAR_CONFIG"
echo "  SSH pod:            $SSH_POD (namespace: $SSH_POD_NS)"
echo "  Concurrency:        $CONCURRENCY"
echo "  Poll interval:      ${POLL_INTERVAL}s"
if [[ -n "$LOG_FILE" ]]; then
    echo "  Log file:           $LOG_FILE"
fi
if [[ "$DRY_RUN" == "true" ]]; then
    echo "  Mode:               DRY RUN"
fi
echo ""

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found. Please install kubectl."
    exit 1
fi

if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
    exit 1
fi

if [[ ! -f "$FAR_CONFIG" ]]; then
    log_error "FAR configuration file not found: $FAR_CONFIG"
    exit 1
fi

if ! kubectl get node "$NODE_NAME" &> /dev/null; then
    log_error "Node not found: $NODE_NAME"
    exit 1
fi

log_success "Prerequisites check passed"
echo ""

# Exit if dry run
if [[ "$DRY_RUN" == "true" ]]; then
    log_info "Dry run mode - exiting without making changes"
    exit 0
fi

# Step 1: Remove node selectors from VMs
log_info "Step 1: Removing node selectors from VMs to allow rescheduling..."
if ./patch-vms.sh --namespace-prefix "$NAMESPACE_PREFIX" --start "$START" --end "$END"; then
    log_success "Node selectors removed"
else
    log_warning "Failed to remove some node selectors (may not exist)"
fi
echo ""

# Wait a bit for changes to propagate
sleep 5

# Step 2: Apply FAR configuration
log_info "Step 2: Applying FAR configuration to trigger node failure..."
if kubectl apply -f "$FAR_CONFIG"; then
    log_success "FAR configuration applied"
else
    log_error "Failed to apply FAR configuration"
    exit 1
fi
echo ""

# Wait for FAR to take effect
log_info "Waiting 20 seconds for FAR to take effect..."
sleep 20

# Step 3: Remove FAR configuration
log_info "Step 3: Removing FAR configuration to allow recovery..."
if kubectl delete -f "$FAR_CONFIG"; then
    log_success "FAR configuration removed"
else
    log_warning "Failed to remove FAR configuration (may have been auto-removed)"
fi
echo ""

# Step 4: Measure recovery time
log_info "Step 4: Measuring VM recovery time..."
echo ""

RECOVERY_CMD="python3 measure-recovery-time.py \
    --start $START \
    --end $END \
    --vm-name $VM_NAME \
    --namespace-prefix $NAMESPACE_PREFIX \
    --ssh-pod $SSH_POD \
    --ssh-pod-ns $SSH_POD_NS \
    --concurrency $CONCURRENCY \
    --poll-interval $POLL_INTERVAL"

if [[ -n "$LOG_FILE" ]]; then
    RECOVERY_CMD="$RECOVERY_CMD --log-file $LOG_FILE"
fi

if eval "$RECOVERY_CMD"; then
    log_success "Recovery test completed successfully"
    exit 0
else
    log_error "Recovery test failed"
    exit 1
fi

