#!/bin/bash
#"""
#Orchestrate a manual node failure recovery test (without FAR operator).
#
#This script monitors VM recovery after a manual node failure (e.g., power off via BMC).
#
#Prerequisites:
#  - kubectl configured and connected to your cluster
#  - VMs already created and running on the target node
#  - Access to node BMC/IPMI or cloud console to power off the node
#  - (Optional) patch-vms.sh script if using --remove-node-selectors
#
#Workflow:
#  1. Validates prerequisites and checks VMs exist
#  2. (Optional) Removes node selectors from VMs to allow rescheduling
#  3. Waits for you to manually power off the node via BMC/IPMI
#  4. Monitors node status until it becomes NotReady/Unknown
#  5. Measures VM recovery time using measure-recovery-time.py
#
#Usage:
#    ./run-manual-failure-test.sh --node-name <worker-node> --start 1 --end 60 --vm-name rhel-9-vm
#
#Required Arguments:
#    --node-name NAME          Name of the worker node to fail
#
#Optional Arguments:
#    --start NUM               Start namespace index (default: 1)
#    --end NUM                 End namespace index (default: 60)
#    --vm-name NAME            VM name to monitor (default: rhel-9-vm)
#    --namespace-prefix PREFIX Namespace prefix (default: kubevirt-perf-test)
#    --concurrency NUM         Monitoring concurrency (default: 128)
#    --poll-interval NUM       Poll interval in seconds (default: 1)
#    --log-file FILE           Log file path (optional)
#    --remove-node-selectors   Remove node selectors before test (allows VM rescheduling)
#    --skip-ping               Skip ping tests (faster, only check VMI Running state)
#
#Examples:
#    # Basic test - power off node manually, script monitors recovery
#    ./run-manual-failure-test.sh --node-name worker-1 --start 1 --end 60 --vm-name rhel-9-vm
#
#    # Test with node selector removal and logging
#    ./run-manual-failure-test.sh --node-name worker-1 --start 1 --end 100 \
#      --remove-node-selectors \
#      --log-file recovery-$(date +%Y%m%d-%H%M%S).log
#
#    # Fast test - skip ping validation
#    ./run-manual-failure-test.sh --node-name worker-1 --start 1 --end 60 --skip-ping
#
#Author: KubeVirt Benchmark Suite Contributors
#License: Apache 2.0
#"""

set -euo pipefail

# Default values
START=1
END=60
VM_NAME="rhel-9-vm"
NODE_NAME=""
SSH_POD="ssh-test-pod"
SSH_POD_NS="default"
CONCURRENCY=128
POLL_INTERVAL=1
LOG_FILE=""
NAMESPACE_PREFIX="kubevirt-perf-test"
DRY_RUN=false
REMOVE_NODE_SELECTORS=false
SKIP_PING=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Print usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Orchestrate a manual node failure recovery test for KubeVirt VMs (no FAR operator required).

Required Options:
  --node-name NAME          Name of the node to fail

Optional Options:
  --start NUM               Start namespace index (default: 1)
  --end NUM                 End namespace index (default: 60)
  --vm-name NAME            VM name to monitor (default: rhel-9-vm)
  --namespace-prefix PREFIX Namespace prefix (default: kubevirt-perf-test)
  --ssh-pod NAME            SSH pod name for ping tests (default: ssh-test-pod)
  --ssh-pod-ns NAMESPACE    SSH pod namespace (default: default)
  --concurrency NUM         Monitoring concurrency (default: 128)
  --poll-interval NUM       Poll interval in seconds (default: 1)
  --log-file FILE           Log file path (optional)
  --remove-node-selectors   Remove node selectors before test (allows rescheduling)
  --skip-ping               Skip ping tests (faster, only check VMI Running state)
  --dry-run                 Show what would be done without executing
  -h, --help                Show this help message

Examples:
  # Basic test - power off node via BMC, script monitors recovery
  $0 --node-name worker-1 --start 1 --end 60 --vm-name rhel-9-vm

  # Full test with all options
  $0 --node-name worker-1 --start 1 --end 100 \\
     --remove-node-selectors \\
     --log-file recovery-\$(date +%Y%m%d-%H%M%S).log

  # Fast test - skip ping validation
  $0 --node-name worker-1 --start 1 --end 60 --skip-ping

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
        --remove-node-selectors)
            REMOVE_NODE_SELECTORS=true
            shift
            ;;
        --skip-ping)
            SKIP_PING=true
            shift
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
echo ""
log_info "Manual Node Failure Recovery Test Configuration:"
echo "  Node name:          $NODE_NAME"
echo "  Namespace range:    ${NAMESPACE_PREFIX}-${START} to ${NAMESPACE_PREFIX}-${END}"
echo "  VM name:            $VM_NAME"
echo "  SSH pod:            $SSH_POD (namespace: $SSH_POD_NS)"
echo "  Concurrency:        $CONCURRENCY"
echo "  Poll interval:      ${POLL_INTERVAL}s"
echo "  Remove node sel:    $REMOVE_NODE_SELECTORS"
echo "  Skip ping:          $SKIP_PING"
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

if ! kubectl get node "$NODE_NAME" &> /dev/null; then
    log_error "Node not found: $NODE_NAME"
    exit 1
fi

# Check if VMs exist
log_info "Checking if VMs exist in test namespaces..."
VM_COUNT=0
for i in $(seq "$START" "$END"); do
    NS="${NAMESPACE_PREFIX}-${i}"
    if kubectl get vm "$VM_NAME" -n "$NS" &> /dev/null; then
        ((VM_COUNT++))
    fi
done

if [[ $VM_COUNT -eq 0 ]]; then
    log_error "No VMs found in namespaces ${NAMESPACE_PREFIX}-${START} to ${NAMESPACE_PREFIX}-${END}"
    exit 1
fi

log_success "Found $VM_COUNT VMs in test namespaces"
log_success "Prerequisites check passed"
echo ""

# Exit if dry run
if [[ "$DRY_RUN" == "true" ]]; then
    log_info "Dry run mode - exiting without making changes"
    exit 0
fi

# Step 1: Remove node selectors (optional)
if [[ "$REMOVE_NODE_SELECTORS" == "true" ]]; then
    log_step "Step 1: Removing node selectors from VMs to allow rescheduling..."
    if [[ -f "./patch-vms.sh" ]]; then
        if ./patch-vms.sh --namespace-prefix "$NAMESPACE_PREFIX" --start "$START" --end "$END"; then
            log_success "Node selectors removed"
        else
            log_warning "Failed to remove some node selectors (may not exist)"
        fi
    else
        log_warning "patch-vms.sh not found, skipping node selector removal"
    fi
    echo ""
    sleep 2
fi

# Step 2: Monitor node status and wait for node to go down
log_step "Step 2: Monitoring Node Status (Waiting for Power-Off)"
echo ""

log_info "Monitoring node $NODE_NAME for failure (power off manually)..."
log_info "Waiting for node to become NotReady or Unknown..."

MAX_WAIT=600  # Wait up to 10 minutes for node to go down
ELAPSED=0
CHECK_INTERVAL=2

while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    NODE_STATUS=$(kubectl get node "$NODE_NAME" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
    NODE_READY=$(kubectl get node "$NODE_NAME" -o jsonpath='{.status.conditions[?(@.type=="Ready")].reason}' 2>/dev/null || echo "")

    if [[ "$NODE_STATUS" != "True" ]] || [[ "$NODE_READY" == "NodeStatusUnknown" ]]; then
        log_success "Node $NODE_NAME is down (Status: NotReady/Unknown) after ${ELAPSED}s"
        break
    fi

    if [[ $((ELAPSED % 30)) -eq 0 ]]; then
        log_info "Still waiting for node failure... (${ELAPSED}s elapsed, node status: Ready)"
    fi

    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    log_error "Node did not go down within ${MAX_WAIT}s. Exiting..."
    exit 1
fi
echo ""

# Step 3: Start recovery monitoring
log_step "Step 3: Monitoring VM Recovery"
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

if [[ "$SKIP_PING" == "true" ]]; then
    RECOVERY_CMD="$RECOVERY_CMD --skip-ping"
fi

if [[ -n "$LOG_FILE" ]]; then
    RECOVERY_CMD="$RECOVERY_CMD --log-file $LOG_FILE"
fi

log_info "Starting recovery monitoring..."
echo ""

if eval "$RECOVERY_CMD"; then
    log_success "Recovery monitoring completed successfully"
    exit 0
else
    log_error "Recovery monitoring failed"
    exit 1
fi
