package main

import (
	"github.com/spf13/cobra"
)

var datasourceCloneCmd = &cobra.Command{
	Use:   "datasource-clone",
	Short: "Run DataSource clone benchmark",
	Long: `Benchmark VM creation time from DataSource cloning.

This workload tests the performance of creating VMs by cloning from a DataSource,
which is the recommended approach for VM provisioning in KubeVirt.`,
	Example: `  # Run with 50 VMs across 10 namespaces
  virtbench datasource-clone --storage-class fada-raw-sc --vms 50 --namespaces 10

  # Run with custom DataSource
  virtbench datasource-clone --storage-class fada-raw-sc --datasource-name rhel9 --datasource-namespace openshift-virtualization-os-images

  # Run with cleanup after test
  virtbench datasource-clone --storage-class fada-raw-sc --vms 20 --cleanup`,
	RunE: runDatasourceClone,
}

var (
	dsStorageClass        string
	dsVMs                 int
	dsNamespaces          int
	dsNamespacePrefix     string
	dsVMName              string
	dsDatasourceName      string
	dsDatasourceNamespace string
	dsStorageSize         string
	dsVMMemory            string
	dsVMCPUCores          int
	dsConcurrency         int
	dsPollInterval        int
	dsCleanup             bool
	dsCleanupOnly         bool
)

func init() {
	rootCmd.AddCommand(datasourceCloneCmd)

	// Required flags
	datasourceCloneCmd.Flags().StringVar(&dsStorageClass, "storage-class", "", "storage class name (required)")
	datasourceCloneCmd.MarkFlagRequired("storage-class")

	// Test configuration
	datasourceCloneCmd.Flags().IntVar(&dsVMs, "vms", 50, "number of VMs to create")
	datasourceCloneCmd.Flags().IntVar(&dsNamespaces, "namespaces", 10, "number of namespaces to create")
	datasourceCloneCmd.Flags().StringVar(&dsNamespacePrefix, "namespace-prefix", "datasource-clone", "namespace prefix")

	// VM template configuration
	datasourceCloneCmd.Flags().StringVar(&dsVMName, "vm-name", "test-vm", "VM name prefix")
	datasourceCloneCmd.Flags().StringVar(&dsDatasourceName, "datasource-name", "rhel9", "DataSource name")
	datasourceCloneCmd.Flags().StringVar(&dsDatasourceNamespace, "datasource-namespace", "openshift-virtualization-os-images", "DataSource namespace")
	datasourceCloneCmd.Flags().StringVar(&dsStorageSize, "storage-size", "30Gi", "storage size for VM disk")
	datasourceCloneCmd.Flags().StringVar(&dsVMMemory, "vm-memory", "2048M", "VM memory")
	datasourceCloneCmd.Flags().IntVar(&dsVMCPUCores, "vm-cpu-cores", 1, "number of CPU cores")

	// Execution configuration
	datasourceCloneCmd.Flags().IntVar(&dsConcurrency, "concurrency", 10, "number of concurrent operations")
	datasourceCloneCmd.Flags().IntVar(&dsPollInterval, "poll-interval", 5, "polling interval in seconds")

	// Cleanup options
	datasourceCloneCmd.Flags().BoolVar(&dsCleanup, "cleanup", false, "cleanup resources after test")
	datasourceCloneCmd.Flags().BoolVar(&dsCleanupOnly, "cleanup-only", false, "only cleanup resources from previous run")
}

func runDatasourceClone(cmd *cobra.Command, args []string) error {
	printBanner("DataSource Clone Benchmark")

	// Build arguments for Python script
	flagMap := map[string]interface{}{
		"storage-class":        dsStorageClass,
		"vms":                  dsVMs,
		"namespaces":           dsNamespaces,
		"namespace-prefix":     dsNamespacePrefix,
		"vm-name":              dsVMName,
		"datasource-name":      dsDatasourceName,
		"datasource-namespace": dsDatasourceNamespace,
		"storage-size":         dsStorageSize,
		"vm-memory":            dsVMMemory,
		"vm-cpu-cores":         dsVMCPUCores,
		"concurrency":          dsConcurrency,
		"poll-interval":        dsPollInterval,
		"cleanup":              dsCleanup,
		"cleanup-only":         dsCleanupOnly,
		"log-level":            logLevel,
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
