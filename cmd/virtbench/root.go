package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var (
	cfgFile    string
	logLevel   string
	logFile    string
	kubeconfig string
	timeout    string
	uuid       string
)

var rootCmd = &cobra.Command{
	Use:   "virtbench",
	Short: "KubeVirt Benchmark Suite - Performance testing toolkit for KubeVirt VMs",
	Long: `virtbench is a comprehensive performance testing toolkit for KubeVirt virtual machines
running on OpenShift Container Platform (OCP).

It provides multiple benchmark workloads to test VM creation, migration, capacity,
failure recovery, and more.`,
	Version: "1.0.0",
	CompletionOptions: cobra.CompletionOptions{
		DisableDefaultCmd: true,
	},
}

func init() {
	cobra.OnInitialize(initConfig)

	// Global flags
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default is $HOME/.virtbench.yaml)")
	rootCmd.PersistentFlags().StringVar(&logLevel, "log-level", "info", "log level: debug, info, warn, error")
	rootCmd.PersistentFlags().StringVar(&logFile, "log-file", "", "log file path (auto-generated if not specified)")
	rootCmd.PersistentFlags().StringVar(&kubeconfig, "kubeconfig", "", "path to kubeconfig file")
	rootCmd.PersistentFlags().StringVar(&timeout, "timeout", "4h", "benchmark timeout")
	rootCmd.PersistentFlags().StringVar(&uuid, "uuid", "", "benchmark UUID (auto-generated if not specified)")

	// Bind flags to viper
	viper.BindPFlag("log-level", rootCmd.PersistentFlags().Lookup("log-level"))
	viper.BindPFlag("log-file", rootCmd.PersistentFlags().Lookup("log-file"))
	viper.BindPFlag("kubeconfig", rootCmd.PersistentFlags().Lookup("kubeconfig"))
	viper.BindPFlag("timeout", rootCmd.PersistentFlags().Lookup("timeout"))
	viper.BindPFlag("uuid", rootCmd.PersistentFlags().Lookup("uuid"))
}

func initConfig() {
	if cfgFile != "" {
		viper.SetConfigFile(cfgFile)
	} else {
		home, err := os.UserHomeDir()
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error getting home directory: %v\n", err)
			os.Exit(1)
		}

		viper.AddConfigPath(home)
		viper.SetConfigType("yaml")
		viper.SetConfigName(".virtbench")
	}

	viper.AutomaticEnv()

	if err := viper.ReadInConfig(); err == nil {
		fmt.Fprintln(os.Stderr, "Using config file:", viper.ConfigFileUsed())
	}
}
