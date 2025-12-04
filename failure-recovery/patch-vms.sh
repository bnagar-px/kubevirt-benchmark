#!/bin/bash
"""
Remove node selectors from VMs to allow rescheduling during FAR tests.

This script patches all VMs in the specified namespace range to remove
nodeSelector constraints, allowing them to be rescheduled to any node
during failure recovery.

Usage:
    ./patch-vms.sh --namespace-prefix kubevirt-perf-test --start 1 --end 60

Author: KubeVirt Benchmark Suite Contributors
License: Apache 2.0
"""

set -euo pipefail

# Default values
NAMESPACE_PREFIX="kubevirt-perf-test"
START=1
END=60
PARALLEL_JOBS=5
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

Remove node selectors from VMs to allow rescheduling.

Options:
  --namespace-prefix PREFIX Namespace prefix (default: kubevirt-perf-test)
  --start NUM               Start namespace index (default: 1)
  --end NUM                 End namespace index (default: 60)
  --parallel NUM            Number of parallel jobs (default: 5)
  --dry-run                 Show what would be done without executing
  -h, --help                Show this help message

Examples:
  # Patch VMs in namespaces kubevirt-perf-test-1 to kubevirt-perf-test-60
  $0 --namespace-prefix kubevirt-perf-test --start 1 --end 60

  # Dry run to see what would be patched
  $0 --namespace-prefix my-test --start 1 --end 100 --dry-run

EOF
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace-prefix)
            NAMESPACE_PREFIX="$2"
            shift 2
            ;;
        --start)
            START="$2"
            shift 2
            ;;
        --end)
            END="$2"
            shift 2
            ;;
        --parallel)
            PARALLEL_JOBS="$2"
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

# Validate arguments
if [[ $START -lt 1 ]]; then
    log_error "Start index must be >= 1"
    exit 1
fi

if [[ $END -lt $START ]]; then
    log_error "End index must be >= start index"
    exit 1
fi

# Print configuration
log_info "VM Patch Configuration:"
echo "  Namespace prefix:   $NAMESPACE_PREFIX"
echo "  Namespace range:    ${NAMESPACE_PREFIX}-${START} to ${NAMESPACE_PREFIX}-${END}"
echo "  Parallel jobs:      $PARALLEL_JOBS"
if [[ "$DRY_RUN" == "true" ]]; then
    echo "  Mode:               DRY RUN"
fi
echo ""

# Check prerequisites
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found. Please install kubectl."
    exit 1
fi

if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
    exit 1
fi

# Function to patch a single VM
patch_vm() {
    local namespace=$1
    local vm_name=$2
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "[DRY RUN] Would patch VM $vm_name in namespace $namespace"
        return 0
    fi
    
    # Check if nodeSelector exists
    if ! kubectl get vm "$vm_name" -n "$namespace" -o jsonpath='{.spec.template.spec.nodeSelector}' 2>/dev/null | grep -q .; then
        log_info "[$namespace/$vm_name] No nodeSelector found, skipping"
        return 0
    fi
    
    # Patch to remove nodeSelector
    if kubectl patch vm "$vm_name" -n "$namespace" --type=json \
        -p '[{"op":"remove","path":"/spec/template/spec/nodeSelector"}]' 2>/dev/null; then
        log_success "[$namespace/$vm_name] NodeSelector removed"
        return 0
    else
        log_warning "[$namespace/$vm_name] Failed to remove nodeSelector"
        return 1
    fi
}

export -f patch_vm
export -f log_info
export -f log_success
export -f log_warning
export DRY_RUN
export RED GREEN YELLOW BLUE NC

# Get all VMs in the namespace range
log_info "Discovering VMs in namespaces ${NAMESPACE_PREFIX}-${START} to ${NAMESPACE_PREFIX}-${END}..."

VM_LIST=()
for i in $(seq "$START" "$END"); do
    namespace="${NAMESPACE_PREFIX}-${i}"
    
    # Check if namespace exists
    if ! kubectl get namespace "$namespace" &> /dev/null; then
        log_warning "Namespace $namespace does not exist, skipping"
        continue
    fi
    
    # Get VMs in this namespace
    vms=$(kubectl get vm -n "$namespace" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -n "$vms" ]]; then
        for vm in $vms; do
            VM_LIST+=("$namespace:$vm")
        done
    fi
done

if [[ ${#VM_LIST[@]} -eq 0 ]]; then
    log_warning "No VMs found in the specified namespace range"
    exit 0
fi

log_info "Found ${#VM_LIST[@]} VMs to patch"
echo ""

# Exit if dry run
if [[ "$DRY_RUN" == "true" ]]; then
    log_info "Dry run mode - showing VMs that would be patched:"
    for vm_entry in "${VM_LIST[@]}"; do
        echo "  $vm_entry"
    done
    exit 0
fi

# Patch all VMs in parallel
log_info "Patching VMs (parallel jobs: $PARALLEL_JOBS)..."

SUCCESS_COUNT=0
FAIL_COUNT=0

for vm_entry in "${VM_LIST[@]}"; do
    namespace="${vm_entry%%:*}"
    vm_name="${vm_entry##*:}"
    
    # Run in background with job control
    (
        if patch_vm "$namespace" "$vm_name"; then
            exit 0
        else
            exit 1
        fi
    ) &
    
    # Limit parallel jobs
    while [[ $(jobs -r | wc -l) -ge $PARALLEL_JOBS ]]; do
        sleep 0.1
    done
done

# Wait for all background jobs to complete
wait

log_info "Patching complete"
echo ""

# Summary
log_info "Summary:"
echo "  Total VMs:          ${#VM_LIST[@]}"
echo "  Successfully patched: Check logs above for details"
echo ""

log_success "VM patching completed"
exit 0

