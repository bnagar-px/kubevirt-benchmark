package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// getRepoRoot returns the root directory of the repository
func getRepoRoot() (string, error) {
	// Get the directory where the virtbench binary is located
	execPath, err := os.Executable()
	if err != nil {
		return "", fmt.Errorf("failed to get executable path: %w", err)
	}

	// Resolve symlinks
	execPath, err = filepath.EvalSymlinks(execPath)
	if err != nil {
		return "", fmt.Errorf("failed to resolve symlinks: %w", err)
	}

	// Get the directory containing the binary
	binDir := filepath.Dir(execPath)

	// If binary is in cmd/virtbench or bin/, go up to repo root
	if strings.HasSuffix(binDir, "cmd/virtbench") {
		return filepath.Abs(filepath.Join(binDir, "../.."))
	} else if strings.HasSuffix(binDir, "bin") {
		return filepath.Abs(filepath.Join(binDir, ".."))
	}

	// Otherwise assume we're already at repo root or in a subdirectory
	return filepath.Abs(binDir)
}

// runPythonScript executes a Python script with the given arguments
func runPythonScript(scriptPath string, args []string) error {
	repoRoot, err := getRepoRoot()
	if err != nil {
		return fmt.Errorf("failed to get repo root: %w", err)
	}

	fullScriptPath := filepath.Join(repoRoot, scriptPath)

	// Check if script exists
	if _, err := os.Stat(fullScriptPath); os.IsNotExist(err) {
		return fmt.Errorf("script not found: %s", fullScriptPath)
	}

	// Prepare command
	cmdArgs := append([]string{fullScriptPath}, args...)
	cmd := exec.Command("python3", cmdArgs...)
	cmd.Dir = filepath.Dir(fullScriptPath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin

	// Set environment variables
	cmd.Env = os.Environ()
	if kubeconfig != "" {
		cmd.Env = append(cmd.Env, fmt.Sprintf("KUBECONFIG=%s", kubeconfig))
	}

	fmt.Printf("Running: python3 %s\n", strings.Join(cmdArgs, " "))
	fmt.Println(strings.Repeat("=", 80))

	// Run the command
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("script execution failed: %w", err)
	}

	return nil
}

// buildPythonArgs constructs Python script arguments from flags
func buildPythonArgs(flagMap map[string]interface{}) []string {
	var args []string

	for flag, value := range flagMap {
		if value == nil {
			continue
		}

		switch v := value.(type) {
		case string:
			if v != "" {
				args = append(args, fmt.Sprintf("--%s", flag), v)
			}
		case int:
			if v > 0 {
				args = append(args, fmt.Sprintf("--%s", flag), fmt.Sprintf("%d", v))
			}
		case bool:
			if v {
				args = append(args, fmt.Sprintf("--%s", flag))
			}
		case []string:
			if len(v) > 0 {
				for _, item := range v {
					args = append(args, fmt.Sprintf("--%s", flag), item)
				}
			}
		}
	}

	return args
}

// generateLogFileName generates a log file name with timestamp
func generateLogFileName(prefix string) string {
	timestamp := time.Now().Format("20060102-150405")
	return fmt.Sprintf("%s-%s.log", prefix, timestamp)
}

// printBanner prints a formatted banner
func printBanner(title string) {
	fmt.Println()
	fmt.Println(strings.Repeat("=", 80))
	fmt.Printf("  %s\n", title)
	fmt.Println(strings.Repeat("=", 80))
	fmt.Println()
}
