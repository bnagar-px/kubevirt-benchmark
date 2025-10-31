package main

import (
	"github.com/spf13/cobra"
)

var capacityBenchmarkCmd = &cobra.Command{
	Use:   "capacity-benchmark",
	Short: "Run capacity benchmark",
	Long: `Run comprehensive capacity benchmark testing cluster limits.

This workload runs VM operations in a loop until failure or reaching maximum iterations,
testing VM creation, volume resize, VM restart, snapshots, and live migration.`,
	Example: `  # Run capacity test with 5 VMs per iteration
  virtbench capacity-benchmark --storage-class fada-raw-sc --vms 5 --max-iterations 10

  # Run with skip options
  virtbench capacity-benchmark --storage-class fada-raw-sc --vms 5 --skip-resize-job --skip-migration-job

  # Run cleanup only
  virtbench capacity-benchmark --cleanup-only`,
	RunE: runCapacityBenchmark,
}

var (
	capStorageClass        []string
	capNamespace           string
	capMaxIterations       int
	capVMs                 int
	capDataVolumeCount     int
	capMinVolSize          string
	capMinVolIncSize       string
	capVMYaml              string
	capVMName              string
	capDatasourceName      string
	capDatasourceNamespace string
	capVMMemory            string
	capVMCPUCores          int
	capSkipResizeJob       bool
	capSkipMigrationJob    bool
	capSkipSnapshotJob     bool
	capSkipRestartJob      bool
	capConcurrency         int
	capPollInterval        int
	capCleanup             bool
	capCleanupOnly         bool
)

func init() {
	rootCmd.AddCommand(capacityBenchmarkCmd)

	// Required flags
	capacityBenchmarkCmd.Flags().StringSliceVar(&capStorageClass, "storage-class", []string{}, "storage class name(s) - can specify multiple (required)")
	capacityBenchmarkCmd.MarkFlagRequired("storage-class")

	// Test configuration
	capacityBenchmarkCmd.Flags().StringVar(&capNamespace, "namespace", "virt-capacity-benchmark", "namespace for capacity test")
	capacityBenchmarkCmd.Flags().IntVar(&capMaxIterations, "max-iterations", 10, "maximum number of iterations")
	capacityBenchmarkCmd.Flags().IntVar(&capVMs, "vms", 5, "number of VMs per iteration")
	capacityBenchmarkCmd.Flags().IntVar(&capDataVolumeCount, "data-volume-count", 0, "number of additional data volumes per VM")
	capacityBenchmarkCmd.Flags().StringVar(&capMinVolSize, "min-vol-size", "30Gi", "minimum volume size")
	capacityBenchmarkCmd.Flags().StringVar(&capMinVolIncSize, "min-vol-inc-size", "10Gi", "volume size increment for resize")

	// VM template configuration
	capacityBenchmarkCmd.Flags().StringVar(&capVMYaml, "vm-yaml", "../examples/vm-templates/vm-template.yaml", "path to VM template YAML")
	capacityBenchmarkCmd.Flags().StringVar(&capVMName, "vm-name", "capacity-vm", "VM name prefix")
	capacityBenchmarkCmd.Flags().StringVar(&capDatasourceName, "datasource-name", "rhel9", "DataSource name")
	capacityBenchmarkCmd.Flags().StringVar(&capDatasourceNamespace, "datasource-namespace", "openshift-virtualization-os-images", "DataSource namespace")
	capacityBenchmarkCmd.Flags().StringVar(&capVMMemory, "vm-memory", "2048M", "VM memory")
	capacityBenchmarkCmd.Flags().IntVar(&capVMCPUCores, "vm-cpu-cores", 1, "number of CPU cores")

	// Skip options
	capacityBenchmarkCmd.Flags().BoolVar(&capSkipResizeJob, "skip-resize-job", false, "skip volume resize phase")
	capacityBenchmarkCmd.Flags().BoolVar(&capSkipMigrationJob, "skip-migration-job", false, "skip VM migration phase")
	capacityBenchmarkCmd.Flags().BoolVar(&capSkipSnapshotJob, "skip-snapshot-job", false, "skip VM snapshot phase")
	capacityBenchmarkCmd.Flags().BoolVar(&capSkipRestartJob, "skip-restart-job", false, "skip VM restart phase")

	// Execution configuration
	capacityBenchmarkCmd.Flags().IntVar(&capConcurrency, "concurrency", 10, "number of concurrent operations")
	capacityBenchmarkCmd.Flags().IntVar(&capPollInterval, "poll-interval", 5, "polling interval in seconds")

	// Cleanup options
	capacityBenchmarkCmd.Flags().BoolVar(&capCleanup, "cleanup", false, "cleanup resources after test")
	capacityBenchmarkCmd.Flags().BoolVar(&capCleanupOnly, "cleanup-only", false, "only cleanup resources from previous run")
}

func runCapacityBenchmark(cmd *cobra.Command, args []string) error {
	printBanner("Capacity Benchmark")

	// Build arguments for Python script
	flagMap := map[string]interface{}{
		"storage-class":        capStorageClass,
		"namespace":            capNamespace,
		"max-iterations":       capMaxIterations,
		"vms":                  capVMs,
		"data-volume-count":    capDataVolumeCount,
		"min-vol-size":         capMinVolSize,
		"min-vol-inc-size":     capMinVolIncSize,
		"vm-yaml":              capVMYaml,
		"vm-name":              capVMName,
		"datasource-name":      capDatasourceName,
		"datasource-namespace": capDatasourceNamespace,
		"vm-memory":            capVMMemory,
		"vm-cpu-cores":         capVMCPUCores,
		"skip-resize-job":      capSkipResizeJob,
		"skip-migration-job":   capSkipMigrationJob,
		"skip-snapshot-job":    capSkipSnapshotJob,
		"skip-restart-job":     capSkipRestartJob,
		"concurrency":          capConcurrency,
		"poll-interval":        capPollInterval,
		"cleanup":              capCleanup,
		"cleanup-only":         capCleanupOnly,
		"log-level":            logLevel,
	}

	// Add log file if specified
	if logFile != "" {
		flagMap["log-file"] = logFile
	} else {
		flagMap["log-file"] = generateLogFileName("capacity-benchmark")
	}

	pythonArgs := buildPythonArgs(flagMap)

	// Run the Python script
	return runPythonScript("capacity-benchmark/measure-capacity.py", pythonArgs)
}
