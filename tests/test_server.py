"""Tests for the MCP server implementation."""

import pytest
from repo_architecture_mcp.server import RepoArchitectureMCPServer


class TestRepoArchitectureMCPServer:
    """Test cases for the MCP server."""
    
    def test_server_initialization(self):
        """Test that the server initializes correctly."""
        server = RepoArchitectureMCPServer()
        assert server is not None
        assert server.server is not None
    
    def test_available_tools(self):
        """Test that all expected tools are available."""
        server = RepoArchitectureMCPServer()
        tools = server.get_available_tools()
        
        expected_tools = [
            "analyze_repository",
            "generate_dependency_diagram",
            "generate_class_diagram", 
            "generate_data_flow_diagram",
            "get_repository_summary"
        ]
        
        assert len(tools) == len(expected_tools)
        for tool in expected_tools:
            assert tool in tools