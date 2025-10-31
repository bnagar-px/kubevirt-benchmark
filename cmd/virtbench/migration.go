package main

import (
	"github.com/spf13/cobra"
)

var migrationCmd = &cobra.Command{
	Use:   "migration",
	Short: "Run VM migration benchmark",
	Long: `Benchmark VM live migration performance.

This workload tests the performance of live migrating VMs between nodes,
measuring migration time, downtime, and throughput.`,
	Example: `  # Run migration test with 10 namespaces
  virtbench migration --storage-class fada-raw-sc --namespaces 10

  # Run with custom VM name
  virtbench migration --storage-class fada-raw-sc --vm-name rhel-9-vm --namespaces 5

  # Run with cleanup after test
  virtbench migration --storage-class fada-raw-sc --namespaces 10 --cleanup`,
	RunE: runMigration,
}

var (
	migStorageClass        string
	migNamespaces          int
	migNamespacePrefix     string
	migVMName              string
	migDatasourceName      string
	migDatasourceNamespace string
	migStorageSize         string
	migVMMemory            string
	migVMCPUCores          int
	migConcurrency         int
	migPollInterval        int
	migCleanup             bool
	migCleanupOnly         bool
)

func init() {
	rootCmd.AddCommand(migrationCmd)

	// Required flags
	migrationCmd.Flags().StringVar(&migStorageClass, "storage-class", "", "storage class name (required)")
	migrationCmd.MarkFlagRequired("storage-class")

	// Test configuration
	migrationCmd.Flags().IntVar(&migNamespaces, "namespaces", 10, "number of namespaces to create")
	migrationCmd.Flags().StringVar(&migNamespacePrefix, "namespace-prefix", "migration-test", "namespace prefix")

	// VM template configuration
	migrationCmd.Flags().StringVar(&migVMName, "vm-name", "test-vm", "VM name prefix")
	migrationCmd.Flags().StringVar(&migDatasourceName, "datasource-name", "rhel9", "DataSource name")
	migrationCmd.Flags().StringVar(&migDatasourceNamespace, "datasource-namespace", "openshift-virtualization-os-images", "DataSource namespace")
	migrationCmd.Flags().StringVar(&migStorageSize, "storage-size", "30Gi", "storage size for VM disk")
	migrationCmd.Flags().StringVar(&migVMMemory, "vm-memory", "2048M", "VM memory")
	migrationCmd.Flags().IntVar(&migVMCPUCores, "vm-cpu-cores", 1, "number of CPU cores")

	// Execution configuration
	migrationCmd.Flags().IntVar(&migConcurrency, "concurrency", 10, "number of concurrent operations")
	migrationCmd.Flags().IntVar(&migPollInterval, "poll-interval", 5, "polling interval in seconds")

	// Cleanup options
	migrationCmd.Flags().BoolVar(&migCleanup, "cleanup", false, "cleanup resources after test")
	migrationCmd.Flags().BoolVar(&migCleanupOnly, "cleanup-only", false, "only cleanup resources from previous run")
}

func runMigration(cmd *cobra.Command, args []string) error {
	printBanner("VM Migration Benchmark")

	// Build arguments for Python script
	flagMap := map[string]interface{}{
		"storage-class":        migStorageClass,
		"namespaces":           migNamespaces,
		"namespace-prefix":     migNamespacePrefix,
		"vm-name":              migVMName,
		"datasource-name":      migDatasourceName,
		"datasource-namespace": migDatasourceNamespace,
		"storage-size":         migStorageSize,
		"vm-memory":            migVMMemory,
		"vm-cpu-cores":         migVMCPUCores,
		"concurrency":          migConcurrency,
		"poll-interval":        migPollInterval,
		"cleanup":              migCleanup,
		"cleanup-only":         migCleanupOnly,
		"log-level":            logLevel,
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
