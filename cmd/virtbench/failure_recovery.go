package main

import (
	"github.com/spf13/cobra"
)

var failureRecoveryCmd = &cobra.Command{
	Use:   "failure-recovery",
	Short: "Run failure recovery benchmark",
	Long: `Benchmark VM failure recovery time.

This workload tests the time it takes for VMs to recover after node failures,
measuring recovery time and data integrity.`,
	Example: `  # Run failure recovery test
  virtbench failure-recovery --storage-class fada-raw-sc --namespaces 5

  # Run with custom VM configuration
  virtbench failure-recovery --storage-class fada-raw-sc --vm-name test-vm --namespaces 3

  # Run with cleanup after test
  virtbench failure-recovery --storage-class fada-raw-sc --namespaces 5 --cleanup`,
	RunE: runFailureRecovery,
}

var (
	farStorageClass        string
	farNamespaces          int
	farNamespacePrefix     string
	farVMName              string
	farDatasourceName      string
	farDatasourceNamespace string
	farStorageSize         string
	farVMMemory            string
	farVMCPUCores          int
	farConcurrency         int
	farPollInterval        int
	farCleanup             bool
	farCleanupOnly         bool
)

func init() {
	rootCmd.AddCommand(failureRecoveryCmd)

	// Required flags
	failureRecoveryCmd.Flags().StringVar(&farStorageClass, "storage-class", "", "storage class name (required)")
	failureRecoveryCmd.MarkFlagRequired("storage-class")

	// Test configuration
	failureRecoveryCmd.Flags().IntVar(&farNamespaces, "namespaces", 5, "number of namespaces to create")
	failureRecoveryCmd.Flags().StringVar(&farNamespacePrefix, "namespace-prefix", "failure-recovery", "namespace prefix")

	// VM template configuration
	failureRecoveryCmd.Flags().StringVar(&farVMName, "vm-name", "test-vm", "VM name prefix")
	failureRecoveryCmd.Flags().StringVar(&farDatasourceName, "datasource-name", "rhel9", "DataSource name")
	failureRecoveryCmd.Flags().StringVar(&farDatasourceNamespace, "datasource-namespace", "openshift-virtualization-os-images", "DataSource namespace")
	failureRecoveryCmd.Flags().StringVar(&farStorageSize, "storage-size", "30Gi", "storage size for VM disk")
	failureRecoveryCmd.Flags().StringVar(&farVMMemory, "vm-memory", "2048M", "VM memory")
	failureRecoveryCmd.Flags().IntVar(&farVMCPUCores, "vm-cpu-cores", 1, "number of CPU cores")

	// Execution configuration
	failureRecoveryCmd.Flags().IntVar(&farConcurrency, "concurrency", 10, "number of concurrent operations")
	failureRecoveryCmd.Flags().IntVar(&farPollInterval, "poll-interval", 5, "polling interval in seconds")

	// Cleanup options
	failureRecoveryCmd.Flags().BoolVar(&farCleanup, "cleanup", false, "cleanup resources after test")
	failureRecoveryCmd.Flags().BoolVar(&farCleanupOnly, "cleanup-only", false, "only cleanup resources from previous run")
}

func runFailureRecovery(cmd *cobra.Command, args []string) error {
	printBanner("Failure Recovery Benchmark")

	// Build arguments for Python script
	flagMap := map[string]interface{}{
		"storage-class":        farStorageClass,
		"namespaces":           farNamespaces,
		"namespace-prefix":     farNamespacePrefix,
		"vm-name":              farVMName,
		"datasource-name":      farDatasourceName,
		"datasource-namespace": farDatasourceNamespace,
		"storage-size":         farStorageSize,
		"vm-memory":            farVMMemory,
		"vm-cpu-cores":         farVMCPUCores,
		"concurrency":          farConcurrency,
		"poll-interval":        farPollInterval,
		"cleanup":              farCleanup,
		"cleanup-only":         farCleanupOnly,
		"log-level":            logLevel,
	}

	// Add log file if specified
	if logFile != "" {
		flagMap["log-file"] = logFile
	} else {
		flagMap["log-file"] = generateLogFileName("failure-recovery")
	}

	pythonArgs := buildPythonArgs(flagMap)

	// Run the Python script
	return runPythonScript("failure-recovery/measure-recovery-time.py", pythonArgs)
}
