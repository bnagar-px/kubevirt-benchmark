package main

import (
	"github.com/spf13/cobra"
)

var validateClusterCmd = &cobra.Command{
	Use:   "validate-cluster",
	Short: "Validate cluster prerequisites",
	Long: `Validate that the cluster meets all prerequisites for running benchmarks.

This command checks:
- OpenShift Virtualization installation
- Storage class availability and configuration
- CDI (Containerized Data Importer) status
- DataSource availability
- Node resources and capacity`,
	Example: `  # Validate cluster with specific storage class
  virtbench validate-cluster --storage-class fada-raw-sc

  # Validate all aspects
  virtbench validate-cluster --storage-class fada-raw-sc --all

  # Quick validation (skip optional checks)
  virtbench validate-cluster --storage-class fada-raw-sc --quick`,
	RunE: runValidateCluster,
}

var (
	valStorageClass []string
	valAll          bool
	valQuick        bool
)

func init() {
	rootCmd.AddCommand(validateClusterCmd)

	// Flags
	validateClusterCmd.Flags().StringSliceVar(&valStorageClass, "storage-class", []string{}, "storage class name(s) to validate")
	validateClusterCmd.Flags().BoolVar(&valAll, "all", false, "run all validation checks")
	validateClusterCmd.Flags().BoolVar(&valQuick, "quick", false, "run quick validation (skip optional checks)")
}

func runValidateCluster(cmd *cobra.Command, args []string) error {
	printBanner("Cluster Validation")

	// Build arguments for Python script
	flagMap := map[string]interface{}{
		"storage-class": valStorageClass,
		"all":           valAll,
		"quick":         valQuick,
		"log-level":     logLevel,
	}

	// Add log file if specified
	if logFile != "" {
		flagMap["log-file"] = logFile
	}

	pythonArgs := buildPythonArgs(flagMap)

	// Run the Python script
	return runPythonScript("utils/validate_cluster.py", pythonArgs)
}
