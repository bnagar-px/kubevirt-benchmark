#!/bin/bash
# Installation script for virtbench CLI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if Go is installed
check_go() {
    if ! command -v go &> /dev/null; then
        print_error "Go is not installed. Please install Go 1.21 or later."
        print_info "Visit: https://golang.org/doc/install"
        exit 1
    fi
    
    GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
    print_info "Found Go version: $GO_VERSION"
}

# Check if Python3 is installed
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 is not installed. The benchmark scripts require Python3."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    print_info "Found Python version: $PYTHON_VERSION"
}

# Install Python dependencies
install_python_deps() {
    print_info "Installing Python dependencies..."
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt || print_warning "Failed to install some Python dependencies"
    else
        print_warning "requirements.txt not found, skipping Python dependencies"
    fi
}

# Build the binary
build_binary() {
    print_info "Building virtbench binary..."
    make build
    
    if [ ! -f "bin/virtbench" ]; then
        print_error "Build failed. Binary not found."
        exit 1
    fi
    
    print_info "Build successful!"
}

# Install the binary
install_binary() {
    print_info "Installing virtbench to /usr/local/bin..."
    
    if [ -w "/usr/local/bin" ]; then
        cp bin/virtbench /usr/local/bin/
        chmod +x /usr/local/bin/virtbench
    else
        sudo cp bin/virtbench /usr/local/bin/
        sudo chmod +x /usr/local/bin/virtbench
    fi
    
    print_info "Installation complete!"
}

# Setup shell completion
setup_completion() {
    print_info "Setting up shell completion..."
    
    SHELL_NAME=$(basename "$SHELL")
    
    case "$SHELL_NAME" in
        bash)
            if [ -d "/usr/local/etc/bash_completion.d" ]; then
                virtbench completion bash > /usr/local/etc/bash_completion.d/virtbench 2>/dev/null || true
                print_info "Bash completion installed to /usr/local/etc/bash_completion.d/virtbench"
            elif [ -d "/etc/bash_completion.d" ]; then
                sudo virtbench completion bash > /etc/bash_completion.d/virtbench 2>/dev/null || true
                print_info "Bash completion installed to /etc/bash_completion.d/virtbench"
            else
                print_warning "Bash completion directory not found. Run manually: source <(virtbench completion bash)"
            fi
            ;;
        zsh)
            print_info "For Zsh completion, run: virtbench completion zsh > \"\${fpath[1]}/_virtbench\""
            ;;
        fish)
            if [ -d "$HOME/.config/fish/completions" ]; then
                virtbench completion fish > "$HOME/.config/fish/completions/virtbench.fish" 2>/dev/null || true
                print_info "Fish completion installed to ~/.config/fish/completions/virtbench.fish"
            else
                print_warning "Fish completion directory not found. Run manually: virtbench completion fish | source"
            fi
            ;;
        *)
            print_warning "Unknown shell: $SHELL_NAME. Shell completion not configured."
            ;;
    esac
}

# Main installation
main() {
    print_info "Starting virtbench installation..."
    echo ""
    
    # Check prerequisites
    check_go
    check_python
    echo ""
    
    # Install dependencies
    print_info "Installing Go dependencies..."
    make deps
    echo ""
    
    install_python_deps
    echo ""
    
    # Build and install
    build_binary
    echo ""
    
    install_binary
    echo ""
    
    # Setup completion (optional)
    read -p "Do you want to setup shell completion? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        setup_completion
        echo ""
    fi
    
    # Verify installation
    if command -v virtbench &> /dev/null; then
        print_info "✓ Installation successful!"
        echo ""
        print_info "Run 'virtbench --help' to get started."
        print_info "Run 'virtbench version' to verify the installation."
    else
        print_error "Installation verification failed. virtbench command not found."
        exit 1
    fi
}

# Run main installation
main

