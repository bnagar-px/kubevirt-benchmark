package main

import (
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// getRepoRoot returns the root directory of the repository
func getRepoRoot() (string, error) {
	// First, check if VIRTBENCH_REPO environment variable is set
	if repoPath := os.Getenv("VIRTBENCH_REPO"); repoPath != "" {
		if _, err := os.Stat(repoPath); err == nil {
			return filepath.Abs(repoPath)
		}
	}

	// Second, check current working directory
	cwd, err := os.Getwd()
	if err == nil {
		// Check if we're in the repo (look for capacity-benchmark directory)
		if _, err := os.Stat(filepath.Join(cwd, "capacity-benchmark")); err == nil {
			return filepath.Abs(cwd)
		}
		// Check if we're in a subdirectory of the repo
		parent := filepath.Dir(cwd)
		if _, err := os.Stat(filepath.Join(parent, "capacity-benchmark")); err == nil {
			return filepath.Abs(parent)
		}
	}

	// Third, get the directory where the virtbench binary is located
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

	// If we can't find the repo, return an error with helpful message
	return "", fmt.Errorf("cannot find repository root. Please either:\n" +
		"  1. Run virtbench from the repository directory, or\n" +
		"  2. Set VIRTBENCH_REPO environment variable to the repository path, or\n" +
		"  3. Use the binary from bin/ directory instead of installing to /usr/local/bin")
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
				// Convert log-level to uppercase for Python scripts
				if flag == "log-level" {
					v = strings.ToUpper(v)
				}
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

// modifyStorageClassInYAML modifies the storageClassName in a VM template YAML file in-memory
// and returns the modified YAML content as a string
func modifyStorageClassInYAML(templatePath, storageClass string) (string, error) {
	// Read the YAML file
	data, err := ioutil.ReadFile(templatePath)
	if err != nil {
		return "", fmt.Errorf("failed to read template file: %w", err)
	}

	// Simple string replacement approach - faster and cleaner
	content := string(data)

	// Replace {{STORAGE_CLASS_NAME}} placeholder
	if strings.Contains(content, "{{STORAGE_CLASS_NAME}}") {
		content = strings.ReplaceAll(content, "{{STORAGE_CLASS_NAME}}", storageClass)
		return content, nil
	}

	// If no placeholder, parse YAML and modify the field
	var doc map[string]interface{}
	if err := yaml.Unmarshal(data, &doc); err != nil {
		return "", fmt.Errorf("failed to parse YAML: %w", err)
	}

	// Navigate to dataVolumeTemplates and update storageClassName
	modified := false
	if spec, ok := doc["spec"].(map[string]interface{}); ok {
		if dvTemplates, ok := spec["dataVolumeTemplates"].([]interface{}); ok {
			for _, dvTemplate := range dvTemplates {
				if dvt, ok := dvTemplate.(map[string]interface{}); ok {
					if dvSpec, ok := dvt["spec"].(map[string]interface{}); ok {
						if storage, ok := dvSpec["storage"].(map[string]interface{}); ok {
							storage["storageClassName"] = storageClass
							modified = true
						}
					}
				}
			}
		}
	}

	if !modified {
		return "", fmt.Errorf("could not find storageClassName field or {{STORAGE_CLASS_NAME}} placeholder in template")
	}

	// Marshal back to YAML
	modifiedData, err := yaml.Marshal(&doc)
	if err != nil {
		return "", fmt.Errorf("failed to marshal modified YAML: %w", err)
	}

	return string(modifiedData), nil
}
