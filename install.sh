#!/bin/bash
# Installation script for virtbench CLI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_banner() {
    echo -e "${CYAN}$1${NC}"
}

# Check if Python3 is installed
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 is not installed. virtbench requires Python 3.6+."
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    print_info "Found Python version: $PYTHON_VERSION"
}

# Check if pip3 is installed
check_pip() {
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 is not installed. Please install pip3."
        print_info "Visit: https://pip.pypa.io/en/stable/installation/"
        exit 1
    fi

    PIP_VERSION=$(pip3 --version | awk '{print $2}')
    print_info "Found pip version: $PIP_VERSION"
}

# Install Python dependencies
install_python_deps() {
    print_info "Installing Python dependencies from requirements.txt..."
    if [ -f "requirements.txt" ]; then
        if pip3 install -r requirements.txt; then
            print_info "✓ Python dependencies installed successfully"
        else
            print_error "Failed to install Python dependencies!"
            print_error "Please run manually: pip3 install -r requirements.txt"
            exit 1
        fi
    else
        print_error "requirements.txt not found!"
        exit 1
    fi
}

# Install virtbench CLI
install_virtbench_cli() {
    print_info "Installing virtbench CLI..."

    # Install in development mode (editable install)
    if pip3 install -e . ; then
        print_info "✓ virtbench CLI installed successfully"
    else
        print_error "Failed to install virtbench CLI"
        print_error "Please run manually: pip3 install -e ."
        exit 1
    fi
}

# Verify installation
verify_installation() {
    print_info "Verifying installation..."

    if command -v virtbench &> /dev/null; then
        print_info "✓ virtbench command is available"
        echo ""
        virtbench --version
        return 0
    else
        print_warning "virtbench command not found in PATH"
        print_info "You may need to add ~/.local/bin to your PATH"
        print_info "Add this to your ~/.bashrc or ~/.zshrc:"
        echo ""
        echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
        return 1
    fi
}

# Main installation
main() {
    echo ""
    print_banner "================================================================================"
    print_banner "  KubeVirt Benchmark Suite - virtbench CLI Installation"
    print_banner "================================================================================"
    echo ""

    # Check prerequisites
    print_info "Checking prerequisites..."
    check_python
    check_pip
    echo ""

    # Install dependencies
    install_python_deps
    echo ""

    # Install virtbench CLI
    install_virtbench_cli
    echo ""

    # Verify installation
    verify_installation
    echo ""

    # Success message
    print_banner "================================================================================"
    print_info "✓ Installation complete!"
    print_banner "================================================================================"
    echo ""
    print_info "Get started with:"
    echo ""
    echo "    virtbench --help                    # Show help"
    echo "    virtbench version                   # Show version"
    echo "    virtbench validate-cluster          # Validate your cluster"
    echo ""
    print_info "Example commands:"
    echo ""
    echo "    # Run datasource clone test"
    echo "    virtbench datasource-clone --start 1 --end 10 --storage-class fada-raw-sc"
    echo ""
    echo "    # Run capacity benchmark"
    echo "    virtbench capacity-benchmark --storage-class fada-raw-sc --vms 5"
    echo ""
    print_info "For more information, visit: https://github.com/your-org/kubevirt-benchmark-suite"
    echo ""
}

# Run main installation
main

