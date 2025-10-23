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
        "analyze_repository",
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
        "analyze_repository",
        "generate_dependency_diagram",
        "get_repository_summary"
      ]
    }
  }
}
```

## Usage Examples

### Analyze Current Directory
When using the MCP server, you can analyze local repositories by providing local paths instead of GitHub URLs to any of the analysis tools.

### Analyze Specific Local Path
All MCP tools (`analyze_repository`, `generate_dependency_diagram`, `generate_class_diagram`, etc.) now accept local paths in addition to GitHub URLs.

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

## MCP Tool Usage for Local Repositories

All MCP tools now accept local paths. Simply use a local path instead of a GitHub URL:

```json
// Analyze current directory
{"tool": "analyze_repository", "arguments": {"url": "."}}

// Generate dependency diagram for local repo
{"tool": "generate_dependency_diagram", "arguments": {"url": "/path/to/project", "format": "svg"}}

// Get summary of local repository
{"tool": "get_repository_summary", "arguments": {"url": "./my-project"}}
```

### File Saving Feature

All diagram generation tools support automatic file saving:

```json
// Save diagram to auto-generated filename
{
  "tool": "generate_dependency_diagram", 
  "arguments": {
    "url": ".", 
    "format": "mermaid",
    "save_to_file": true
  }
}

// Save diagram to custom path
{
  "tool": "generate_class_diagram",
  "arguments": {
    "url": "./src",
    "format": "svg", 
    "save_to_file": true,
    "output_path": "./docs/diagrams/classes.svg"
  }
}

// Save data flow diagram
{
  "tool": "generate_data_flow_diagram",
  "arguments": {
    "url": ".",
    "format": "png",
    "save_to_file": true,
    "output_path": "~/Desktop/dataflow.png"
  }
}
```

**File Naming Convention:**
When `output_path` is not specified, files are auto-generated with the format:
`{repo_name}_{diagram_type}_{timestamp}.{extension}`

**Supported Extensions:**
- Mermaid: `.mmd`
- SVG: `.svg`
- PNG: `.png`

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