# Local Repository Configuration

For analyzing local repositories (without needing GitHub tokens), you can use the Repository Architecture MCP Server in several ways:

## MCP Configuration for Local Repositories

### Basic Local Configuration

```json
{
  "mcpServers": {
    "repo-architecture-local": {
      "command": "repo-architecture-mcp",
      "args": [
        "--log-level", "INFO",
        "--no-cache"
      ],
      "disabled": false,
      "autoApprove": [
        "analyze_local_repository",
        "get_repository_summary"
      ]
    }
  }
}
```

### For Kiro IDE (Local Development)

**Workspace Configuration** (`.kiro/settings/mcp.json`):
```json
{
  "mcpServers": {
    "repo-architecture-local": {
      "command": "repo-architecture-mcp",
      "args": ["--log-level", "DEBUG"],
      "cwd": "${workspaceFolder}",
      "disabled": false,
      "autoApprove": [
        "analyze_local_repository",
        "generate_dependency_diagram",
        "get_repository_summary"
      ]
    }
  }
}
```

## Usage Examples

### Analyze Current Directory
```bash
# The server can analyze the current working directory
repo-architecture-mcp --analyze-local .
```

### Analyze Specific Local Path
```bash
# Analyze a specific local repository
repo-architecture-mcp --analyze-local /path/to/your/project
```

### MCP Tool Calls for Local Repositories

When using the MCP tools, instead of providing a GitHub URL, you can provide local paths:

#### Using `analyze_repository` with Local Paths
```json
{
  "tool": "analyze_repository",
  "arguments": {
    "url": "/path/to/local/repository",
    "token": null
  }
}
```

#### Using `analyze_repository` with Relative Paths
```json
{
  "tool": "analyze_repository", 
  "arguments": {
    "url": "./",
    "token": null
  }
}
```

#### Using `analyze_repository` with Current Directory
```json
{
  "tool": "analyze_repository",
  "arguments": {
    "url": ".",
    "token": null
  }
}
```

## Configuration Without GitHub Token

### Minimal Configuration
```json
{
  "mcpServers": {
    "repo-architecture": {
      "command": "repo-architecture-mcp",
      "disabled": false,
      "autoApprove": ["analyze_repository"]
    }
  }
}
```

### Development Configuration
```json
{
  "mcpServers": {
    "repo-architecture-dev": {
      "command": "repo-architecture-mcp",
      "args": [
        "--log-level", "DEBUG",
        "--max-workers", "2",
        "--no-cache"
      ],
      "cwd": "${workspaceFolder}",
      "disabled": false,
      "autoApprove": [
        "analyze_repository",
        "generate_dependency_diagram",
        "generate_class_diagram"
      ]
    }
  }
}
```

## Local Repository Features

### Supported Local Path Formats
- Absolute paths: `/home/user/project`
- Relative paths: `./my-project`
- Current directory: `.`
- Home directory: `~/projects/my-app`

### What Works Without GitHub Token
- ✅ Code parsing and analysis
- ✅ Dependency diagram generation
- ✅ Class diagram generation
- ✅ Data flow diagram generation
- ✅ Repository statistics
- ✅ Multi-language support
- ✅ All export formats (Mermaid, SVG, PNG)

### What Requires GitHub Token
- ❌ Cloning remote repositories
- ❌ Accessing private GitHub repositories
- ❌ GitHub API metadata (stars, forks, etc.)

## Performance Optimizations for Local Analysis

### Fast Local Analysis Configuration
```json
{
  "mcpServers": {
    "repo-architecture-fast": {
      "command": "repo-architecture-mcp",
      "args": [
        "--max-workers", "8",
        "--memory-limit", "4096",
        "--parallel-processing",
        "--cache-ttl", "1"
      ],
      "disabled": false,
      "autoApprove": ["analyze_repository"]
    }
  }
}
```

### Memory-Efficient Configuration
```json
{
  "mcpServers": {
    "repo-architecture-efficient": {
      "command": "repo-architecture-mcp", 
      "args": [
        "--max-workers", "2",
        "--memory-limit", "1024",
        "--no-parallel"
      ],
      "disabled": false,
      "autoApprove": ["analyze_repository"]
    }
  }
}
```

## Environment Variables for Local Use

```bash
# Optional: Set custom cache directory
export REPO_ARCH_CACHE_DIR=/tmp/repo-cache

# Optional: Set log level
export LOG_LEVEL=INFO

# Optional: Set max workers
export REPO_ARCH_MAX_WORKERS=4
```

## Command Line Usage for Local Repositories

```bash
# Analyze current directory
repo-architecture-mcp --analyze-local .

# Analyze with specific output format
repo-architecture-mcp --analyze-local . --output-format svg

# Analyze with custom output directory
repo-architecture-mcp --analyze-local . --output-dir ./diagrams

# Analyze with debug logging
repo-architecture-mcp --analyze-local . --log-level DEBUG
```

## Integration with IDEs

### VS Code Configuration
Add to your VS Code settings for local repository analysis:

```json
{
  "mcp.servers": {
    "repo-architecture": {
      "command": "repo-architecture-mcp",
      "args": ["--log-level", "INFO"],
      "autoApprove": ["analyze_repository"]
    }
  }
}
```

### JetBrains IDEs
Configure as an external tool:

```xml
<tool name="Repository Architecture Analysis"
      program="repo-architecture-mcp"
      parameters="--analyze-local $ProjectFileDir$"
      workingDir="$ProjectFileDir$" />
```

## Troubleshooting Local Analysis

### Common Issues
1. **Permission errors**: Ensure read access to the repository directory
2. **Large repositories**: Use `--memory-limit` and `--max-workers` to control resource usage
3. **Parsing errors**: Use `--log-level DEBUG` to see detailed parsing information

### Debug Configuration
```json
{
  "mcpServers": {
    "repo-architecture-debug": {
      "command": "repo-architecture-mcp",
      "args": [
        "--log-level", "DEBUG",
        "--log-file", "/tmp/repo-debug.log",
        "--max-workers", "1",
        "--no-cache"
      ],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```