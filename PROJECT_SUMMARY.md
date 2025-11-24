# KubeVirt Performance Testing Suite - Project Summary

## Overview

This is a production-ready, open-source toolkit for KubeVirt VM performance testing on OpenShift with Portworx storage.

## Repository Structure

```
kubevirt-performance-testing/
├── README.md                    # Main documentation
├── QUICKSTART.md               # Quick start guide
├── SETUP.md                    # Detailed setup guide
├── BOOT_STORM_GUIDE.md         # Boot storm testing guide
├── CLEANUP_GUIDE.md            # Comprehensive cleanup guide
├── CONTRIBUTING.md             # Contribution guidelines
├── LICENSE                     # Apache 2.0 License
├── requirements.txt            # Python dependencies
│
├── dashboard/                  # Interactive results dashboard
│   ├── generate_dashboard.py  # Dashboard generation script
│   ├── cluster_info.yaml      # Cluster metadata template
│   ├── manual_results.yaml    # Manual test results
│   └── README.md              # Dashboard documentation
│
├── datasource-clone/           # DataSource-based VM provisioning tests
│   ├── measure-vm-creation-time.py
│   └── vm-template.yaml
│
├── migration/                  # Live migration performance tests
│   └── measure-vm-migration-time.py
│
├── failure-recovery/           # Failure and recovery tests
│   ├── measure-recovery-time.py
│   ├── run-far-test.sh
│   ├── patch-vms.sh
│   └── far-template.yaml
│
├── utils/                      # Shared utilities
│   ├── common.py              # Logging, kubectl wrappers, helpers
│   ├── validate_cluster.py    # Cluster validation script
│   └── README.md              # Utils documentation
│
└── examples/                   # Example configurations
    ├── storage-classes/
    ├── vm-templates/
    ├── ssh-pod.yaml
    ├── sequential-migration.sh
    ├── parallel-migration.sh
    ├── evacuation-scenario.sh
    └── round-robin-migration.sh
```

## Key Components

### 1. Python Scripts

#### Common Utilities Module (`utils/common.py`)
- **Logging Framework**: Structured logging with file output and colored console
- **kubectl Wrapper**: Error handling, timeouts, and debug output
- **Helper Functions**: Namespace management, VM status checks, network testing
- **Summary Tables**: Formatted output with statistics
- **Prerequisites Validation**: Pre-flight checks before running tests

#### DataSource Clone Script (`datasource-clone/measure-vm-creation-time.py`)
**Features:**
- Comprehensive command-line argument parsing
- Configurable namespace prefixes
- Optional cleanup after tests
- Detailed logging with multiple levels
- Better error handling and recovery
- Statistics and performance metrics
- Boot storm testing capability
- Single node testing for capacity validation
- Results export (JSON and CSV)
- Auto-detection of Portworx version
- Exit codes for CI/CD integration

**Command-Line Options:**
- `--log-file`: Save logs to file
- `--log-level`: DEBUG/INFO/WARNING/ERROR
- `--namespace-prefix`: Custom namespace naming
- `--cleanup`: Auto-delete resources
- `--boot-storm`: Enable boot storm testing
- `--single-node`: Pin all VMs to single node
- `--save-results`: Export results for dashboard
- `--px-version`: Specify Portworx version
- `--poll-interval`: Configurable polling
- `--ping-timeout`: Adjustable timeouts

#### Live Migration Script (`migration/measure-vm-migration-time.py`)
**Features:**
- Multiple migration scenarios (sequential, parallel, evacuation, round-robin)
- Parallel migration with configurable concurrency
- Interleaved scheduling for even load distribution
- Auto-select busiest node for evacuation
- Dual timing measurements (observed + VMIM timestamps)
- Network validation after migration
- Results export (JSON and CSV)
- Comprehensive cleanup options

**Migration Scenarios:**
- **Sequential**: Migrate VMs one by one
- **Parallel**: Migrate multiple VMs simultaneously with concurrency control
- **Evacuation**: Evacuate all VMs from a specific node
- **Round-robin**: Distribute VMs evenly across all nodes

**Advanced Options:**
- `--interleaved-scheduling`: Distribute migrations evenly across nodes from the start
- `--skip-ping`: Skip network validation for faster testing
- `--migration-timeout`: Custom timeout per migration
- `--save-results`: Export results for dashboard

#### Failure Recovery Script (`failure-recovery/measure-recovery-time.py`)
**Features:**
- Real-time VMI status monitoring
- IP address change tracking
- Detailed recovery metrics
- Parallel monitoring with configurable concurrency
- Better error handling for network issues

**Capabilities:**
- Continuous IP refresh during recovery
- Running + Ready state validation
- Comprehensive recovery statistics
- Max/min/average time calculations

#### Dashboard Generator (`dashboard/generate_dashboard.py`)
**Features:**
- Interactive HTML dashboard with Bootstrap and Plotly
- Multi-level organization (PX Version → Disk Count → VM Size)
- Automatic results discovery from directory structure
- Time-based filtering (e.g., last N days)
- Cluster information display
- Manual results integration

**Dashboard Components:**
- **Performance Charts**: Bar charts showing creation, boot storm, and migration durations
- **Detailed Tables**: Sortable, searchable DataTables with all metrics
- **Summary Statistics**: Aggregated metrics across test runs
- **Cluster Info Tab**: Display cluster metadata and configuration
- **Manual Results Tab**: Include manually collected test data

**Configuration:**
- `--days`: Filter results by date range
- `--base-dir`: Results directory location
- `--cluster-info`: Cluster metadata YAML file
- `--manual-results`: Manual test results YAML file
- `--output-html`: Output dashboard file path

### 2. Shell Scripts

#### FAR Test Orchestration (`failure-recovery/run-far-test.sh`)
**Features:**
- Complete FAR test automation
- Colored output for better readability
- Dry-run mode for testing
- Prerequisites validation
- Configurable parameters
- Error handling and cleanup
- Usage documentation

#### VM Patching Script (`failure-recovery/patch-vms.sh`)
**Features:**
- Parallel VM patching
- Dry-run support
- Progress tracking
- Error handling
- Configurable parallelism

### 3. Documentation

#### README.md (Comprehensive)
- Project overview and features
- Prerequisites and requirements
- Repository structure
- Quick start guide
- Testing scenarios with examples
- Configuration options table
- Output and results format
- Troubleshooting section
- Best practices
- Contributing guidelines

#### SETUP.md (Detailed Setup Guide)
- Step-by-step setup instructions
- Storage class configuration
- SSH pod deployment
- Golden image creation
- FAR configuration
- Verification steps
- Troubleshooting for each component
- Production considerations

#### QUICKSTART.md (5-Minute Guide)
- Minimal steps to get started
- Quick test examples
- Common commands
- Basic troubleshooting
- Next steps

#### CONTRIBUTING.md (Developer Guide)
- Code of conduct
- How to contribute
- Coding standards (Python and Bash)
- Testing guidelines
- Documentation standards
- Pull request process
- Development setup

#### CHANGELOG.md
- Version history
- Feature list
- Planned features

### 4. Example Configurations

#### Storage Classes
- `portworx-raw-sc.yaml`: Standard Portworx configuration
- `portworx-fada-sc.yaml`: Pure FlashArray Direct Access

#### VM Templates
- `rhel9-vm-registry.yaml`: Registry-based VM
- `rhel9-vm-datasource.yaml`: DataSource-based VM

#### Supporting Resources
- `ssh-pod.yaml`: SSH test pod for network testing
- `far-template.yaml`: FAR configuration template
- `create-golden-images.yaml`: 10 golden image PVCs

### 5. Project Files

- **LICENSE**: Apache 2.0 license
- **requirements.txt**: Python dependencies (none - uses stdlib)
- **.gitignore**: Proper exclusions for Python, logs, secrets
- **CHANGELOG.md**: Version history and features

## Key Features Summary

### Code Quality
✅ Professional error handling
✅ Comprehensive logging
✅ Type hints and docstrings
✅ Modular, reusable code
✅ Consistent naming conventions
✅ PEP 8 compliance

### User Experience
✅ Clear, helpful error messages
✅ Colored console output
✅ Progress indicators
✅ Detailed statistics
✅ Flexible configuration
✅ Dry-run modes

### Documentation
✅ Multiple documentation levels (Quick Start, Setup, Contributing)
✅ Extensive examples
✅ Troubleshooting guides
✅ Inline code documentation

### Production Readiness
✅ Exit codes for automation
✅ Log file support
✅ Prerequisites validation
✅ Cleanup options
✅ Timeout handling
✅ Resource management

### Maintainability
✅ Shared utilities module
✅ Consistent structure
✅ Version control ready
✅ Contributing guidelines
✅ Change log

## Testing Capabilities

### VM Creation Performance
- **DataSource Clone Method**: Test VM provisioning from KubeVirt DataSources
- **Boot Storm Testing**: Simultaneous VM startup performance testing
- **Single Node Testing**: Node-level capacity validation
- **Metrics**: Time to Running, Time to Network Ready, Success Rate
- **Scale**: Support for 100+ VMs in parallel
- **Results Export**: JSON and CSV format for dashboard generation

### Live Migration Performance
- **Sequential Migration**: One-by-one VM migration
- **Parallel Migration**: Concurrent migrations with configurable concurrency
- **Evacuation Scenario**: Evacuate all VMs from a node (manual or auto-select busiest)
- **Round-Robin Migration**: Distribute VMs evenly across all nodes
- **Interleaved Scheduling**: Even load distribution across nodes from the start
- **Metrics**: Migration duration (observed + VMIM timestamps), success rate
- **Network Validation**: Post-migration connectivity testing
- **Scale**: Support for 400+ VMs with high concurrency

### Failure Recovery
- **FAR Integration**: Automated node failure simulation
- **Recovery Metrics**: Time to Running, Time to Ping, IP changes
- **Monitoring**: Real-time VMI status tracking

### Network Testing
- **Ping Tests**: Verify VM network connectivity
- **IP Tracking**: Monitor IP address changes
- **Timeout Handling**: Configurable timeouts

### Results Visualization
- **Interactive Dashboard**: HTML dashboard with charts and tables
- **Multi-level Organization**: Results organized by PX version, disk count, VM size
- **Performance Trends**: Compare metrics across multiple test runs
- **Cluster Context**: Display cluster configuration alongside results

## Usage Examples

### Basic VM Creation Test
```bash
cd datasource-clone
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 10 \
  --save-results
```

### Boot Storm Test
```bash
python3 measure-vm-creation-time.py \
  --start 1 \
  --end 100 \
  --boot-storm \
  --save-results \
  --log-file boot-storm-$(date +%Y%m%d).log
```

### Live Migration Test
```bash
cd migration
python3 measure-vm-migration-time.py \
  --start 1 \
  --end 200 \
  --parallel \
  --concurrency 50 \
  --skip-ping \
  --save-results \
  --migration-timeout 1000 \
  --interleaved-scheduling
```

### FAR Test
```bash
cd failure-recovery
./run-far-test.sh \
  --node-name worker-1 \
  --start 1 \
  --end 60 \
  --vm-name rhel-9-vm
```

### Generate Dashboard
```bash
python3 dashboard/generate_dashboard.py \
  --days 50 \
  --base-dir results \
  --cluster-info dashboard/cluster_info.yaml \
  --manual-results dashboard/manual_results.yaml \
  --output-html results_dashboard.html
```

## File Statistics

- **Python Scripts**: 5 main scripts + 1 utilities module
  - VM Creation/Boot Storm: `datasource-clone/measure-vm-creation-time.py`
  - Live Migration: `migration/measure-vm-migration-time.py`
  - Failure Recovery: `failure-recovery/measure-recovery-time.py`
  - Dashboard Generator: `dashboard/generate_dashboard.py`
  - Cluster Validation: `utils/validate_cluster.py`
  - Common Utilities: `utils/common.py`
- **Shell Scripts**: 3 automation scripts
- **YAML Files**: 30+ configuration files
- **Documentation**: 8+ comprehensive guides
- **Total Lines of Code**: ~4,500+ lines
- **Total Documentation**: ~3,500+ lines

## Next Steps for Open Sourcing

1. **Repository Setup**
   - Create GitHub repository
   - Add repository description and topics
   - Configure branch protection
   - Set up issue templates

2. **CI/CD** (Optional)
   - Add GitHub Actions for linting
   - Add automated testing
   - Add documentation building

3. **Community**
   - Add CODE_OF_CONDUCT.md
   - Create issue templates
   - Set up discussions
   - Add badges to README

4. **Release**
   - Tag version 1.0.0
   - Create release notes
   - Announce to community

## Maintenance Plan

### Regular Updates
- Bug fixes and improvements
- New features based on feedback
- Documentation updates
- Example updates for new OCP/Portworx versions

### Community Engagement
- Respond to issues
- Review pull requests
- Update documentation
- Share best practices

## Success Metrics

Track these metrics after open sourcing:
- GitHub stars and forks
- Issue resolution time
- Pull request acceptance rate
- Documentation clarity (feedback)
- Adoption rate (downloads/clones)

## Contact and Support

For questions or support:
- GitHub Issues for bugs and features
- GitHub Discussions for questions
- Contributing guide for development

---

**Status**: ✅ Ready for Open Source Release

**Version**: 1.0.0

**License**: Apache 2.0

**Last Updated**: 2024-01-15

