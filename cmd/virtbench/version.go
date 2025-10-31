package main

import (
	"fmt"

	"github.com/spf13/cobra"
)

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print version information",
	Long:  `Print the version information for virtbench CLI.`,
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("virtbench version 1.0.0")
		fmt.Println("KubeVirt Benchmark Suite")
		fmt.Println("https://github.com/kubevirt-benchmark-suite")
	},
}

func init() {
	rootCmd.AddCommand(versionCmd)
}
