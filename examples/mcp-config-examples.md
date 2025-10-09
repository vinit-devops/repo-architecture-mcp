# MCP Configuration Examples

This document provides examples of how to configure the Repository Architecture MCP Server in various MCP clients and environments.

## Workspace-Level Configuration (.kiro/settings/mcp.json)

For Kiro IDE workspace-specific configuration:

```json
{
  "mcpServers": {
    "repo-architecture": {
      "command": "python",
      "args": ["-m", "repo_architecture_mcp"],
      "cwd": "/path/to/repo-architecture-mcp-server",
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "LOG_LEVEL": "INFO"
      },
      "disabled": false,
      "autoApprove": [
        "analyze_repository",
        "get_repository_summary"
      ]
    }
  }
}
```

## User-Level Configuration (~/.kiro/settings/mcp.json)

For global user configuration across all workspaces:

```json
{
  "mcpServers": {
    "repo-architecture": {
      "command": "repo-architecture-mcp",
      "args": [
        "--log-level", "INFO",
        "--max-workers", "4",
        "--memory-limit", "2048"
      ],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "disabled": false,
      "autoApprove": [
        "analyze_repository",
        "get_repository_summary",
        "generate_dependency_diagram"
      ]
    }
  }
}
```

## Development Configuration

For development with debug logging and custom configuration:

```json
{
  "mcpServers": {
    "repo-architecture-dev": {
      "command": "python",
      "args": [
        "-m", "repo_architecture_mcp",
        "--log-level", "DEBUG",
        "--log-file", "/tmp/repo-arch-mcp.log",
        "--config", "./config/dev-config.yaml",
        "--max-workers", "2",
        "--no-cache"
      ],
      "cwd": "/path/to/repo-architecture-mcp-server",
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "PYTHONPATH": "/path/to/repo-architecture-mcp-server/src"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

## Production Configuration

For production use with optimized settings:

```json
{
  "mcpServers": {
    "repo-architecture-prod": {
      "command": "repo-architecture-mcp",
      "args": [
        "--log-level", "WARNING",
        "--log-file", "/var/log/repo-arch-mcp.log",
        "--max-workers", "8",
        "--memory-limit", "4096",
        "--cache-ttl", "24",
        "--output-format", "mermaid"
      ],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "disabled": false,
      "autoApprove": [
        "analyze_repository",
        "get_repository_summary"
      ]
    }
  }
}
```

## Docker Configuration

For running the server in a Docker container:

```json
{
  "mcpServers": {
    "repo-architecture-docker": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--env", "GITHUB_TOKEN=${GITHUB_TOKEN}",
        "--volume", "/tmp:/tmp",
        "repo-architecture-mcp:latest"
      ],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "disabled": false,
      "autoApprove": [
        "analyze_repository"
      ]
    }
  }
}
```

## Virtual Environment Configuration

For use with Python virtual environments:

```json
{
  "mcpServers": {
    "repo-architecture-venv": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "repo_architecture_mcp"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "VIRTUAL_ENV": "/path/to/venv"
      },
      "disabled": false,
      "autoApprove": [
        "analyze_repository",
        "get_repository_summary"
      ]
    }
  }
}
```

## Configuration with Custom Settings File

Using a custom configuration file for server settings:

```json
{
  "mcpServers": {
    "repo-architecture-custom": {
      "command": "repo-architecture-mcp",
      "args": [
        "--config", "/path/to/custom-config.yaml"
      ],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

## Multiple Server Instances

Running multiple instances for different purposes:

```json
{
  "mcpServers": {
    "repo-architecture-public": {
      "command": "repo-architecture-mcp",
      "args": [
        "--log-level", "INFO",
        "--max-workers", "4"
      ],
      "disabled": false,
      "autoApprove": [
        "analyze_repository",
        "get_repository_summary"
      ]
    },
    "repo-architecture-private": {
      "command": "repo-architecture-mcp",
      "args": [
        "--log-level", "INFO",
        "--max-workers", "2",
        "--memory-limit", "1024"
      ],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_PRIVATE_TOKEN}"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

## Environment Variables

The server supports the following environment variables:

- `GITHUB_TOKEN`: GitHub personal access token for private repositories
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `REPO_ARCH_CONFIG`: Path to configuration file
- `REPO_ARCH_CACHE_DIR`: Custom cache directory
- `REPO_ARCH_MAX_WORKERS`: Maximum number of worker threads
- `REPO_ARCH_MEMORY_LIMIT`: Memory limit in MB

## Command Line Arguments

Available command line arguments for the server:

- `--config PATH`: Configuration file path
- `--log-level LEVEL`: Logging level
- `--log-file PATH`: Log file path
- `--github-token TOKEN`: GitHub token
- `--max-workers N`: Number of worker threads
- `--memory-limit MB`: Memory limit in megabytes
- `--cache-ttl HOURS`: Cache time-to-live
- `--no-cache`: Disable caching
- `--no-parallel`: Disable parallel processing
- `--output-format FORMAT`: Default output format
- `--output-dir PATH`: Output directory

## Auto-Approve Settings

The `autoApprove` array can include any of these tool names:

- `analyze_repository`: Analyze repository structure
- `generate_dependency_diagram`: Generate dependency diagrams
- `generate_class_diagram`: Generate class diagrams
- `generate_data_flow_diagram`: Generate data flow diagrams
- `get_repository_summary`: Get repository summary

## Security Considerations

1. **GitHub Tokens**: Store tokens in environment variables, not in configuration files
2. **Auto-Approve**: Only auto-approve tools you trust for automated execution
3. **Resource Limits**: Set appropriate memory and worker limits for your environment
4. **Logging**: Be careful with debug logging in production as it may expose sensitive information

## Troubleshooting

### Common Issues

1. **Server not starting**: Check that the command path is correct and the package is installed
2. **GitHub authentication**: Verify the GITHUB_TOKEN environment variable is set
3. **Permission errors**: Ensure the server has write access to cache and log directories
4. **Memory issues**: Reduce max-workers or increase memory-limit for large repositories

### Debug Configuration

For troubleshooting, use this configuration:

```json
{
  "mcpServers": {
    "repo-architecture-debug": {
      "command": "repo-architecture-mcp",
      "args": [
        "--log-level", "DEBUG",
        "--log-file", "/tmp/debug.log",
        "--no-cache",
        "--max-workers", "1"
      ],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

This configuration will provide detailed logging and disable optimizations that might hide issues.