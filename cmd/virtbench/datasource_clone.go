package main

import (
	"fmt"
	"path/filepath"

	"github.com/spf13/cobra"
)

var datasourceCloneCmd = &cobra.Command{
	Use:   "datasource-clone",
	Short: "Run DataSource clone benchmark",
	Long: `Benchmark VM creation time from DataSource cloning.

This workload tests the performance of creating VMs by cloning from a DataSource,
which is the recommended approach for VM provisioning in KubeVirt.`,
	Example: `  # Run with 10 VMs (namespaces 1-10)
  virtbench datasource-clone --start 1 --end 10

  # Run with 50 VMs (namespaces 1-50)
  virtbench datasource-clone --start 1 --end 50

  # Run with cleanup after test
  virtbench datasource-clone --start 1 --end 20 --cleanup

  # Run boot storm test
  virtbench datasource-clone --start 1 --end 10 --boot-storm`,
	RunE: runDatasourceClone,
}

var (
	dsStart               int
	dsEnd                 int
	dsNamespacePrefix     string
	dsVMName              string
	dsVMTemplate          string
	dsConcurrency         int
	dsPollInterval        int
	dsPingTimeout         int
	dsSSHPod              string
	dsSSHPodNS            string
	dsCleanup             bool
	dsCleanupOnFailure    bool
	dsDryRunCleanup       bool
	dsYes                 bool
	dsSkipNamespaceCreate bool
	dsBootStorm           bool
	dsNamespaceBatchSize  int
	dsSingleNode          bool
	dsNodeName            string
)

func init() {
	rootCmd.AddCommand(datasourceCloneCmd)

	// Test range
	datasourceCloneCmd.Flags().IntVarP(&dsStart, "start", "s", 1, "start index for test namespaces")
	datasourceCloneCmd.Flags().IntVarP(&dsEnd, "end", "e", 10, "end index for test namespaces")

	// VM configuration
	datasourceCloneCmd.Flags().StringVarP(&dsVMName, "vm-name", "n", "rhel-9-vm", "VM resource name")
	datasourceCloneCmd.Flags().StringVar(&dsVMTemplate, "vm-template", "examples/vm-templates/rhel9-vm-datasource.yaml", "path to VM template YAML")
	datasourceCloneCmd.Flags().StringVar(&dsNamespacePrefix, "namespace-prefix", "datasource-clone", "namespace prefix")

	// Performance tuning
	datasourceCloneCmd.Flags().IntVarP(&dsConcurrency, "concurrency", "c", 10, "max parallel threads for monitoring")
	datasourceCloneCmd.Flags().IntVar(&dsPollInterval, "poll-interval", 5, "seconds between status checks")
	datasourceCloneCmd.Flags().IntVar(&dsPingTimeout, "ping-timeout", 300, "timeout for ping tests in seconds")

	// SSH pod for ping tests
	datasourceCloneCmd.Flags().StringVar(&dsSSHPod, "ssh-pod", "ssh-test-pod", "pod name for ping tests")
	datasourceCloneCmd.Flags().StringVar(&dsSSHPodNS, "ssh-pod-ns", "default", "namespace for SSH test pod")

	// Cleanup options
	datasourceCloneCmd.Flags().BoolVar(&dsCleanup, "cleanup", false, "delete test resources and namespaces after completion")
	datasourceCloneCmd.Flags().BoolVar(&dsCleanupOnFailure, "cleanup-on-failure", false, "clean up resources even if tests fail")
	datasourceCloneCmd.Flags().BoolVar(&dsDryRunCleanup, "dry-run-cleanup", false, "show what would be deleted without actually deleting")
	datasourceCloneCmd.Flags().BoolVar(&dsYes, "yes", false, "skip confirmation prompt for cleanup")
	datasourceCloneCmd.Flags().BoolVar(&dsSkipNamespaceCreate, "skip-namespace-creation", false, "skip namespace creation (use existing namespaces)")

	// Boot storm testing
	datasourceCloneCmd.Flags().BoolVar(&dsBootStorm, "boot-storm", false, "after initial test, shutdown all VMs and test boot storm")
	datasourceCloneCmd.Flags().IntVar(&dsNamespaceBatchSize, "namespace-batch-size", 5, "number of namespaces to create in parallel")

	// Single node testing
	datasourceCloneCmd.Flags().BoolVar(&dsSingleNode, "single-node", false, "run all VMs on a single node")
	datasourceCloneCmd.Flags().StringVar(&dsNodeName, "node-name", "", "specific node name for single-node testing")
}

func runDatasourceClone(cmd *cobra.Command, args []string) error {
	printBanner("DataSource Clone Benchmark")

	// Convert vm-template path to absolute path
	vmTemplatePath := dsVMTemplate
	if !filepath.IsAbs(vmTemplatePath) {
		repoRoot, err := getRepoRoot()
		if err != nil {
			return fmt.Errorf("failed to get repository root: %w", err)
		}
		vmTemplatePath = filepath.Join(repoRoot, vmTemplatePath)
	}

	// Build arguments for Python script
	flagMap := map[string]interface{}{
		"start":                   dsStart,
		"end":                     dsEnd,
		"vm-name":                 dsVMName,
		"vm-template":             vmTemplatePath,
		"namespace-prefix":        dsNamespacePrefix,
		"concurrency":             dsConcurrency,
		"poll-interval":           dsPollInterval,
		"ping-timeout":            dsPingTimeout,
		"ssh-pod":                 dsSSHPod,
		"ssh-pod-ns":              dsSSHPodNS,
		"cleanup":                 dsCleanup,
		"cleanup-on-failure":      dsCleanupOnFailure,
		"dry-run-cleanup":         dsDryRunCleanup,
		"yes":                     dsYes,
		"skip-namespace-creation": dsSkipNamespaceCreate,
		"boot-storm":              dsBootStorm,
		"namespace-batch-size":    dsNamespaceBatchSize,
		"single-node":             dsSingleNode,
		"node-name":               dsNodeName,
		"log-level":               logLevel,
	}

	// Add log file if specified
	if logFile != "" {
		flagMap["log-file"] = logFile
	} else {
		flagMap["log-file"] = generateLogFileName("datasource-clone")
	}

	pythonArgs := buildPythonArgs(flagMap)

	// Run the Python script
	return runPythonScript("datasource-clone/measure-vm-creation-time.py", pythonArgs)
}
