# Repository Architecture MCP Server

An MCP (Model Context Protocol) server that analyzes GitHub repositories and automatically generates visual architectural diagrams including dependency graphs, class diagrams, and data flow diagrams.

## Features

- **Repository Analysis**: Analyze both GitHub repositories (public/private) and local repositories
- **Multi-language Support**: Parse Python, JavaScript, TypeScript, Java, and Go codebases
- **Dependency Diagrams**: Visualize module dependencies and service interconnections
- **Class Diagrams**: Generate UML class diagrams with inheritance relationships
- **Data Flow Diagrams**: Show how data moves through the system
- **Multiple Export Formats**: Support for Mermaid, SVG, and PNG outputs
- **Local Analysis**: No GitHub token required for local repository analysis

## Diagram Preview Tools

To preview the generated diagrams, you'll need appropriate tools or extensions depending on the output format:

### Mermaid Diagrams
Mermaid diagrams can be previewed using:

**VS Code Extensions:**
- **Mermaid Preview** by vstirbu: Install via VS Code Extensions marketplace
  - Search for "Mermaid Preview" in VS Code Extensions (Ctrl+Shift+X)
  - Click Install
  - Open any `.md` file containing Mermaid code blocks and use the preview pane

- **Markdown Preview Mermaid Support** by Matt Bierner: Enhanced markdown preview with Mermaid support
  - Search for "Markdown Preview Mermaid Support" in VS Code Extensions
  - Provides live preview of Mermaid diagrams in markdown files

**Online Tools:**
- [Mermaid Live Editor](https://mermaid.live/) - Paste your Mermaid code directly
- [Mermaid Chart](https://www.mermaidchart.com/) - Professional diagramming tool

**Browser Extensions:**
- **Mermaid Diagrams** for Chrome/Firefox - Renders Mermaid in GitHub and other platforms

### SVG Diagrams
SVG files can be viewed in:
- Any modern web browser (Chrome, Firefox, Safari, Edge)
- VS Code with SVG preview extensions
- Image viewers that support SVG format

### PNG Diagrams
PNG files can be viewed in:
- Any image viewer or web browser
- VS Code with image preview extensions
- Built-in system image viewers

### Recommended Setup
For the best experience, we recommend:
1. Install the **Mermaid Preview** extension in VS Code for live Mermaid diagram preview
2. Use the **Markdown Preview Mermaid Support** extension for enhanced markdown rendering
3. Keep a browser tab open to [Mermaid Live Editor](https://mermaid.live/) for quick diagram testing

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

### Verify Installation

Test that the server is working:
```bash
# Check command is available
repo-architecture-mcp --help

# Test server startup (Ctrl+C to stop)
repo-architecture-mcp --log-level DEBUG
```

## Usage

### As MCP Server

Run the server with stdio transport:
```bash
repo-architecture-mcp
```

With debug logging:
```bash
repo-architecture-mcp --log-level DEBUG
```

### Available MCP Tools

- `analyze_repository`: Analyze repository structure (GitHub URL or local path)
- `generate_dependency_diagram`: Create dependency visualization
- `generate_class_diagram`: Create class relationship diagram
- `generate_data_flow_diagram`: Create data flow visualization
- `get_repository_summary`: Get high-level repository statistics

### Local Repository Analysis

For local repositories, you don't need a GitHub token:

```bash
# Analyze current directory
repo-architecture-mcp --analyze-local .

# Analyze specific local path  
repo-architecture-mcp --analyze-local /path/to/project
```

## MCP Configuration

### Quick Setup

1. Copy the provided `mcp.json` to your MCP client configuration directory
2. Set your GitHub token: `export GITHUB_TOKEN=your_token_here`
3. Add the server to your MCP client

### Basic MCP Configuration

**For GitHub repositories:**
```json
{
  "mcpServers": {
    "repo-architecture": {
      "command": "repo-architecture-mcp",
      "args": ["--log-level", "INFO"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "disabled": false,
      "autoApprove": ["analyze_repository"]
    }
  }
}
```

**For local repositories (no token needed):**
```json
{
  "mcpServers": {
    "repo-architecture-local": {
      "command": "repo-architecture-mcp",
      "args": ["--log-level", "INFO"],
      "cwd": "${workspaceFolder}",
      "disabled": false,
      "autoApprove": [
        "analyze_repository",
        "generate_dependency_diagram"
      ]
    }
  }
}
```

### For Cursor IDE

**Workspace Configuration for Local Analysis** (`.cursor/settings/mcp.json`):
```json
{
  "mcpServers": {
    "repo-architecture-local": {
      "command": "repo-architecture-mcp",
      "cwd": "${workspaceFolder}",
      "disabled": false,
      "autoApprove": [
        "analyze_repository",
        "generate_dependency_diagram"
      ]
    }
  }
}
```

**User Configuration for GitHub** (`~/.cursor/settings/mcp.json`):
```json
{
  "mcpServers": {
    "repo-architecture": {
      "command": "repo-architecture-mcp",
      "args": ["--max-workers", "4"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "disabled": false,
      "autoApprove": ["analyze_repository"]
    }
  }
}
```

### For GitHub Copilot Chat

This MCP server integrates seamlessly with GitHub Copilot Chat to provide architectural insights directly in your development workflow. Use the available tools through Copilot's chat interface to analyze repositories and generate diagrams.

### Available Tools

- `analyze_repository`: Analyze repository structure and code
- `generate_dependency_diagram`: Create dependency visualizations  
- `generate_class_diagram`: Generate UML class diagrams
- `generate_data_flow_diagram`: Create data flow diagrams
- `get_repository_summary`: Get repository statistics

### Configuration Options

The server accepts these command-line arguments:

- `--config PATH`: Custom configuration file
- `--log-level LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--github-token TOKEN`: GitHub authentication token
- `--max-workers N`: Number of parallel workers (default: 4)
- `--memory-limit MB`: Memory limit in megabytes (default: 2048)
- `--cache-ttl HOURS`: Cache time-to-live (default: 24)
- `--output-format FORMAT`: Default output format (mermaid, svg, png)

### Environment Variables

- `GITHUB_TOKEN`: GitHub personal access token
- `LOG_LEVEL`: Logging level
- `REPO_ARCH_CONFIG`: Path to configuration file

See `examples/mcp-config-examples.md` for more detailed configuration examples and `examples/local-repo-config.md` for local repository setup.

## Development

### Project Structure

```
src/repo_architecture_mcp/
├── __init__.py          # Package initialization
├── main.py              # Main entry point
└── server.py            # Core MCP server implementation
```

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/ tests/
```

### Type Checking

```bash
mypy src/
```

## License

MIT License