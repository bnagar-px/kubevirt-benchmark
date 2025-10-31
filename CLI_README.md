# virtbench CLI

A unified command-line interface for the KubeVirt Benchmark Suite.

## Overview

`virtbench` is a Go-based CLI that provides a unified interface to all benchmark workloads in the kubevirt-benchmark-suite. It wraps the existing Python scripts with a professional, kubectl-like command structure.

## Features

 **Unified Interface** - Single binary for all benchmarks  
 **Shell Completion** - Auto-completion for bash/zsh/fish  
 **Consistent UX** - Similar to kubectl and kube-burner-ocp  
 **Easy Distribution** - Single binary, no Python environment needed  
 **Professional CLI** - Built with Cobra framework  

## Installation

### Quick Install

```bash
# Clone the repository
git clone https://github.com/your-org/kubevirt-benchmark-suite.git
cd kubevirt-benchmark-suite

# Run the installation script
./install.sh
```

### Manual Installation

```bash
# Install Go dependencies
make deps

# Build the binary
make build

# Install to /usr/local/bin
make install
```

### Build from Source

```bash
# Build for current platform
make build

# Build for all platforms
make build-all

# The binary will be in bin/virtbench
```

## Usage

### Basic Commands

```bash
# Show help
virtbench --help

# Show version
virtbench version

# Validate cluster
virtbench validate-cluster --storage-class fada-raw-sc
```

### Available Subcommands

| Command | Description |
|---------|-------------|
| `datasource-clone` | Run DataSource clone benchmark |
| `migration` | Run VM migration benchmark |
| `capacity-benchmark` | Run capacity benchmark |
| `failure-recovery` | Run failure recovery benchmark |
| `validate-cluster` | Validate cluster prerequisites |
| `version` | Print version information |
| `completion` | Generate shell completion script |

### Examples

#### 1. DataSource Clone Benchmark

```bash
# Run with 50 VMs across 10 namespaces
virtbench datasource-clone \
  --storage-class fada-raw-sc \
  --vms 50 \
  --namespaces 10

# Run with custom DataSource
virtbench datasource-clone \
  --storage-class fada-raw-sc \
  --datasource-name rhel9 \
  --datasource-namespace openshift-virtualization-os-images \
  --vms 20

# Run with cleanup after test
virtbench datasource-clone \
  --storage-class fada-raw-sc \
  --vms 20 \
  --cleanup
```

#### 2. VM Migration Benchmark

```bash
# Run migration test with 10 namespaces
virtbench migration \
  --storage-class fada-raw-sc \
  --namespaces 10

# Run with custom VM configuration
virtbench migration \
  --storage-class fada-raw-sc \
  --vm-name rhel-9-vm \
  --vm-memory 4096M \
  --vm-cpu-cores 2 \
  --namespaces 5
```

#### 3. Capacity Benchmark

```bash
# Run capacity test with 5 VMs per iteration
virtbench capacity-benchmark \
  --storage-class fada-raw-sc \
  --vms 5 \
  --max-iterations 10

# Run with skip options
virtbench capacity-benchmark \
  --storage-class fada-raw-sc \
  --vms 5 \
  --skip-resize-job \
  --skip-migration-job

# Run with multiple storage classes (round-robin)
virtbench capacity-benchmark \
  --storage-class fada-raw-sc \
  --storage-class fada-replicated-sc \
  --vms 5 \
  --max-iterations 10

# Run cleanup only
virtbench capacity-benchmark --cleanup-only
```

#### 4. Failure Recovery Benchmark

```bash
# Run failure recovery test
virtbench failure-recovery \
  --storage-class fada-raw-sc \
  --namespaces 5

# Run with custom VM configuration
virtbench failure-recovery \
  --storage-class fada-raw-sc \
  --vm-name test-vm \
  --namespaces 3 \
  --cleanup
```

#### 5. Cluster Validation

```bash
# Validate cluster with specific storage class
virtbench validate-cluster --storage-class fada-raw-sc

# Validate all aspects
virtbench validate-cluster \
  --storage-class fada-raw-sc \
  --all

# Quick validation (skip optional checks)
virtbench validate-cluster \
  --storage-class fada-raw-sc \
  --quick
```

### Global Flags

All commands support these global flags:

```bash
--log-level string      # Logging level: debug, info, warn, error (default "info")
--log-file string       # Log file path (auto-generated if not specified)
--kubeconfig string     # Path to kubeconfig file
--timeout duration      # Benchmark timeout (default 4h)
--uuid string           # Benchmark UUID (auto-generated if not specified)
--config string         # Config file (default is $HOME/.virtbench.yaml)
```

### Shell Completion

#### Bash

```bash
# Load completion for current session
source <(virtbench completion bash)

# Install permanently (Linux)
virtbench completion bash > /etc/bash_completion.d/virtbench

# Install permanently (macOS)
virtbench completion bash > /usr/local/etc/bash_completion.d/virtbench
```

#### Zsh

```bash
# Enable completion
echo "autoload -U compinit; compinit" >> ~/.zshrc

# Install completion
virtbench completion zsh > "${fpath[1]}/_virtbench"

# Restart shell
exec zsh
```

#### Fish

```bash
# Load completion for current session
virtbench completion fish | source

# Install permanently
virtbench completion fish > ~/.config/fish/completions/virtbench.fish
```

## Configuration File

You can create a configuration file at `~/.virtbench.yaml` to set default values:

```yaml
log-level: info
kubeconfig: /path/to/kubeconfig
timeout: 4h
```

## Development

### Building

```bash
# Install dependencies
make deps

# Build binary
make build

# Run tests
make test

# Format code
make fmt

# Lint code
make lint
```

### Project Structure

```
cmd/virtbench/
├── main.go                  # Entry point
├── root.go                  # Root command
├── common.go                # Common utilities
├── datasource_clone.go      # DataSource clone subcommand
├── migration.go             # Migration subcommand
├── capacity_benchmark.go    # Capacity benchmark subcommand
├── failure_recovery.go      # Failure recovery subcommand
├── validate_cluster.go      # Cluster validation subcommand
├── version.go               # Version subcommand
└── completion.go            # Shell completion subcommand
```

## Troubleshooting

### Binary not found after installation

Make sure `/usr/local/bin` is in your PATH:

```bash
echo $PATH | grep /usr/local/bin
```

If not, add it to your shell profile:

```bash
export PATH="/usr/local/bin:$PATH"
```

### Python script errors

The CLI requires Python 3.6+ and the dependencies in `requirements.txt`:

```bash
pip3 install -r requirements.txt
```

### Permission denied

If you get permission errors during installation:

```bash
sudo make install
```

