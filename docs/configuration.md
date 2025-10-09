# Configuration and CLI Usage

This document describes how to configure and use the Repository Architecture MCP Server.

## Command Line Interface

The server provides a comprehensive CLI with support for configuration files, environment variables, and command-line arguments.

### Basic Usage

```bash
# Run with default settings
repo-architecture-mcp

# Run with specific configuration file
repo-architecture-mcp --config config.yaml

# Run with debug logging
repo-architecture-mcp --log-level DEBUG

# Create a sample configuration file
repo-architecture-mcp --create-config my-config.yaml
```

### CLI Options

#### Server Operation
- `--transport {stdio}`: Transport type for MCP communication (default: stdio)

#### Configuration
- `--config CONFIG`: Path to configuration file (JSON or YAML)
- `--create-config PATH`: Create a sample configuration file and exit

#### Authentication
- `--github-token TOKEN`: GitHub personal access token for private repositories

#### Performance Settings
- `--max-workers N`: Maximum number of worker threads for parallel processing
- `--memory-limit MB`: Memory limit in megabytes
- `--cache-ttl HOURS`: Cache time-to-live in hours
- `--no-cache`: Disable caching
- `--no-parallel`: Disable parallel processing

#### Analysis Settings
- `--max-depth N`: Maximum analysis depth
- `--max-nodes N`: Maximum number of nodes in generated diagrams
- `--output-format {mermaid,plantuml,svg,png}`: Default output format for diagrams
- `--output-dir DIR`: Output directory for generated files

#### Logging
- `--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}`: Logging level
- `--log-format {simple,detailed,json}`: Log message format
- `--log-file FILE`: Log file path
- `--no-console`: Disable console logging

## Configuration Files

The server supports configuration files in JSON and YAML formats. Configuration files are loaded in the following order of precedence:

1. File specified with `--config` option
2. `repo-architecture-mcp.json` in current directory
3. `repo-architecture-mcp.yaml` in current directory
4. `~/.config/repo-architecture-mcp/config.json`
5. `~/.config/repo-architecture-mcp/config.yaml`
6. `~/.repo-architecture-mcp.json`
7. `~/.repo-architecture-mcp.yaml`

### Configuration Options

#### File Filtering
```yaml
include_patterns:
  - "**/*.py"
  - "**/*.js"
  - "**/*.ts"
  # ... more patterns

exclude_patterns:
  - "**/node_modules/**"
  - "**/__pycache__/**"
  # ... more patterns
```

#### Analysis Parameters
```yaml
max_depth: 10                    # Maximum analysis depth
max_file_size_mb: 10            # Skip files larger than this
include_external_deps: true      # Include external dependencies
include_test_files: false       # Include test files in analysis
```

#### Diagram Generation
```yaml
diagram_layout: "hierarchical"   # Layout algorithm: hierarchical, circular, force-directed
max_nodes: 100                  # Maximum nodes in diagrams
show_attributes: true           # Show class attributes
show_methods: true              # Show class methods
show_private_members: false     # Show private members
```

#### Performance Settings
```yaml
parallel_processing: true       # Enable parallel processing
max_workers: 4                 # Number of worker threads
cache_enabled: true            # Enable result caching
cache_ttl_hours: 24           # Cache time-to-live
memory_limit_mb: 1024         # Memory limit
```

#### GitHub Settings
```yaml
github_token: "your_token_here"  # GitHub personal access token
clone_timeout_seconds: 300      # Repository clone timeout
api_timeout_seconds: 30         # GitHub API timeout
```

#### Output Settings
```yaml
output_format: "mermaid"        # Default output format
output_directory: "/path/to/output"  # Output directory
```

## Environment Variables

Configuration can be overridden using environment variables:

- `GITHUB_TOKEN`: GitHub personal access token
- `REPO_ARCH_MAX_WORKERS`: Maximum number of worker threads
- `REPO_ARCH_MEMORY_LIMIT`: Memory limit in MB
- `REPO_ARCH_CACHE_TTL`: Cache TTL in hours
- `REPO_ARCH_OUTPUT_DIR`: Output directory
- `REPO_ARCH_OUTPUT_FORMAT`: Output format
- `REPO_ARCH_MAX_DEPTH`: Maximum analysis depth
- `REPO_ARCH_MAX_NODES`: Maximum nodes in diagrams
- `REPO_ARCH_PARALLEL`: Enable parallel processing (true/false)
- `REPO_ARCH_CACHE_ENABLED`: Enable caching (true/false)

## Configuration Precedence

Settings are applied in the following order (later values override earlier ones):

1. Default configuration values
2. Configuration file settings
3. Environment variables
4. Command-line arguments

## Examples

### Basic Configuration File (YAML)

```yaml
# Basic configuration for small repositories
max_workers: 2
memory_limit_mb: 512
cache_enabled: true
output_format: "mermaid"

include_patterns:
  - "**/*.py"
  - "**/*.js"

exclude_patterns:
  - "**/node_modules/**"
  - "**/__pycache__/**"
```

### Advanced Configuration File (JSON)

```json
{
  "max_workers": 8,
  "memory_limit_mb": 2048,
  "cache_enabled": true,
  "cache_ttl_hours": 48,
  "parallel_processing": true,
  
  "max_depth": 15,
  "max_nodes": 200,
  "include_external_deps": true,
  "include_test_files": true,
  
  "diagram_layout": "force-directed",
  "show_attributes": true,
  "show_methods": true,
  "show_private_members": false,
  
  "output_format": "svg",
  "output_directory": "./diagrams",
  
  "include_patterns": [
    "**/*.py",
    "**/*.js",
    "**/*.ts",
    "**/*.java",
    "**/*.go"
  ],
  
  "exclude_patterns": [
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/venv/**",
    "**/build/**",
    "**/dist/**"
  ]
}
```

### Running with Different Configurations

```bash
# Use environment variables
export GITHUB_TOKEN="your_token_here"
export REPO_ARCH_MAX_WORKERS=8
repo-architecture-mcp

# Override with CLI arguments
repo-architecture-mcp \
  --config production.yaml \
  --max-workers 16 \
  --memory-limit 4096 \
  --log-level DEBUG

# Create and use a custom config
repo-architecture-mcp --create-config my-config.yaml
# Edit my-config.yaml as needed
repo-architecture-mcp --config my-config.yaml
```

## Server Lifecycle

The server includes proper startup and shutdown procedures:

### Startup
1. Parse command-line arguments
2. Load configuration from file and environment
3. Merge CLI arguments with configuration
4. Initialize logging
5. Create and configure server components
6. Start MCP server

### Shutdown
1. Receive shutdown signal (SIGINT/SIGTERM)
2. Stop accepting new requests
3. Complete ongoing operations
4. Clean up resources and temporary files
5. Exit gracefully

### Signal Handling

The server handles the following signals for graceful shutdown:
- `SIGINT` (Ctrl+C): Graceful shutdown
- `SIGTERM`: Graceful shutdown

## Troubleshooting

### Configuration Issues

If you encounter configuration errors:

1. Check the configuration file syntax (valid JSON/YAML)
2. Verify all required fields are present
3. Check file permissions
4. Use `--create-config` to generate a valid sample

### Performance Issues

For large repositories:

1. Increase `memory_limit_mb`
2. Increase `max_workers` (but not beyond CPU cores)
3. Enable caching with appropriate `cache_ttl_hours`
4. Use `exclude_patterns` to skip unnecessary files
5. Reduce `max_depth` and `max_nodes` for complex repositories

### Authentication Issues

For private repositories:

1. Generate a GitHub personal access token
2. Set it via `--github-token`, environment variable, or config file
3. Ensure the token has appropriate repository access permissions