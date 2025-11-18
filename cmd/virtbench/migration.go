package main

import (
	"fmt"
	"path/filepath"

	"github.com/spf13/cobra"
)

var migrationCmd = &cobra.Command{
	Use:   "migration",
	Short: "Run VM migration benchmark",
	Long: `Benchmark VM live migration performance.

This workload tests the performance of live migrating VMs between nodes,
measuring migration time, downtime, and throughput.`,
	Example: `  # Run migration test with 10 VMs (namespaces 1-10)
  virtbench migration --start 1 --end 10 --source-node worker-1

  # Migrate VMs in parallel
  virtbench migration --start 1 --end 5 --source-node worker-1 --parallel

  # Evacuate all VMs from a node
  virtbench migration --start 1 --end 10 --evacuate --source-node worker-1

  # Create VMs first, then migrate
  virtbench migration --start 1 --end 5 --create-vms --source-node worker-1`,
	RunE: runMigration,
}

var (
	migStart             int
	migEnd               int
	migVMName            string
	migNamespacePrefix   string
	migCreateVMs         bool
	migVMTemplate        string
	migSingleNode        bool
	migNodeName          string
	migSourceNode        string
	migTargetNode        string
	migParallel          bool
	migEvacuate          bool
	migAutoSelectBusiest bool
	migRoundRobin        bool
	migConcurrency       int
	migMigrationTimeout  int
	migSSHPod            string
	migSSHPodNS          string
	migPingTimeout       int
	migSkipPing          bool
	migCleanup           bool
	migCleanupOnFailure  bool
	migDryRunCleanup     bool
	migYes               bool
)

func init() {
	rootCmd.AddCommand(migrationCmd)

	// VM range
	migrationCmd.Flags().IntVarP(&migStart, "start", "s", 1, "start index for test namespaces")
	migrationCmd.Flags().IntVarP(&migEnd, "end", "e", 10, "end index for test namespaces")
	migrationCmd.Flags().StringVarP(&migVMName, "vm-name", "n", "rhel-9-vm", "VM name")

	// Namespace configuration
	migrationCmd.Flags().StringVar(&migNamespacePrefix, "namespace-prefix", "migration-test", "prefix for test namespaces")

	// VM creation
	migrationCmd.Flags().BoolVar(&migCreateVMs, "create-vms", false, "create VMs before migration (default: use existing VMs)")
	migrationCmd.Flags().StringVar(&migVMTemplate, "vm-template", "examples/vm-templates/rhel9-vm-datasource.yaml", "VM template YAML file")
	migrationCmd.Flags().BoolVar(&migSingleNode, "single-node", false, "create all VMs on a single node (requires --create-vms)")
	migrationCmd.Flags().StringVar(&migNodeName, "node-name", "", "specific node to create VMs on (requires --single-node and --create-vms)")

	// Migration scenarios
	migrationCmd.Flags().StringVar(&migSourceNode, "source-node", "", "source node name (required for sequential/parallel/evacuate)")
	migrationCmd.Flags().StringVar(&migTargetNode, "target-node", "", "target node name (optional, auto-select if not specified)")
	migrationCmd.Flags().BoolVar(&migParallel, "parallel", false, "migrate VMs in parallel (default: sequential)")
	migrationCmd.Flags().BoolVar(&migEvacuate, "evacuate", false, "evacuate all VMs from source node to any available nodes")
	migrationCmd.Flags().BoolVar(&migAutoSelectBusiest, "auto-select-busiest", false, "auto-select the node with most VMs for evacuation (requires --evacuate)")
	migrationCmd.Flags().BoolVar(&migRoundRobin, "round-robin", false, "migrate VMs in round-robin fashion across all nodes")

	// Performance options
	migrationCmd.Flags().IntVarP(&migConcurrency, "concurrency", "c", 10, "number of concurrent migrations")
	migrationCmd.Flags().IntVar(&migMigrationTimeout, "migration-timeout", 600, "timeout for each migration in seconds")

	// Validation options
	migrationCmd.Flags().StringVar(&migSSHPod, "ssh-pod", "ssh-pod-name", "SSH test pod name for ping tests")
	migrationCmd.Flags().StringVar(&migSSHPodNS, "ssh-pod-ns", "default", "SSH test pod namespace")
	migrationCmd.Flags().IntVar(&migPingTimeout, "ping-timeout", 600, "timeout for ping test in seconds")
	migrationCmd.Flags().BoolVar(&migSkipPing, "skip-ping", false, "skip ping validation after migration")

	// Cleanup options
	migrationCmd.Flags().BoolVar(&migCleanup, "cleanup", false, "delete VMs, VMIMs, and namespaces after test")
	migrationCmd.Flags().BoolVar(&migCleanupOnFailure, "cleanup-on-failure", false, "clean up resources even if tests fail")
	migrationCmd.Flags().BoolVar(&migDryRunCleanup, "dry-run-cleanup", false, "show what would be deleted without actually deleting")
	migrationCmd.Flags().BoolVar(&migYes, "yes", false, "skip confirmation prompt for cleanup")
}

func runMigration(cmd *cobra.Command, args []string) error {
	printBanner("VM Migration Benchmark")

	// Convert vm-template path to absolute path
	vmTemplatePath := migVMTemplate
	if !filepath.IsAbs(vmTemplatePath) {
		repoRoot, err := getRepoRoot()
		if err != nil {
			return fmt.Errorf("failed to get repository root: %w", err)
		}
		vmTemplatePath = filepath.Join(repoRoot, vmTemplatePath)
	}

	// Build arguments for Python script
	flagMap := map[string]interface{}{
		"start":               migStart,
		"end":                 migEnd,
		"vm-name":             migVMName,
		"namespace-prefix":    migNamespacePrefix,
		"create-vms":          migCreateVMs,
		"vm-template":         vmTemplatePath,
		"single-node":         migSingleNode,
		"node-name":           migNodeName,
		"source-node":         migSourceNode,
		"target-node":         migTargetNode,
		"parallel":            migParallel,
		"evacuate":            migEvacuate,
		"auto-select-busiest": migAutoSelectBusiest,
		"round-robin":         migRoundRobin,
		"concurrency":         migConcurrency,
		"migration-timeout":   migMigrationTimeout,
		"ssh-pod":             migSSHPod,
		"ssh-pod-ns":          migSSHPodNS,
		"ping-timeout":        migPingTimeout,
		"skip-ping":           migSkipPing,
		"cleanup":             migCleanup,
		"cleanup-on-failure":  migCleanupOnFailure,
		"dry-run-cleanup":     migDryRunCleanup,
		"yes":                 migYes,
		"log-level":           logLevel,
	}

	// Add log file if specified
	if logFile != "" {
		flagMap["log-file"] = logFile
	} else {
		flagMap["log-file"] = generateLogFileName("migration")
	}

	pythonArgs := buildPythonArgs(flagMap)

	// Run the Python script
	return runPythonScript("migration/measure-vm-migration-time.py", pythonArgs)
}
