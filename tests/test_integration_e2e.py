"""End-to-end integration tests for the Repository Architecture MCP Server.

These tests verify the complete workflow from repository URL to diagram generation,
ensuring MCP protocol compliance and testing with various repository types and sizes.
"""

import asyncio
import json
import os
import tempfile
import pytest
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, patch, MagicMock

from repo_architecture_mcp.server import RepoArchitectureMCPServer
from repo_architecture_mcp.models import AnalysisConfig
from repo_architecture_mcp.errors import MCPError, ErrorCode


class MockMCPClient:
    """Mock MCP client for testing protocol compliance."""
    
    def __init__(self, server: RepoArchitectureMCPServer):
        self.server = server
        self.tools = {}
        self.call_history = []
    
    async def initialize(self):
        """Initialize client and get available tools."""
        self.tools = {tool: True for tool in self.server.get_available_tools()}
        return self.tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool and record the interaction."""
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not available")
        
        # Record the call
        call_record = {
            "tool": tool_name,
            "arguments": arguments,
            "timestamp": asyncio.get_event_loop().time()
        }
        self.call_history.append(call_record)
        
        # Get the tool function from server
        tool_func = getattr(self.server.server, f"_{tool_name}", None)
        if not tool_func:
            # Try to find the tool in registered tools
            for registered_tool in self.server.server._tools:
                if registered_tool.name == tool_name:
                    tool_func = registered_tool.func
                    break
        
        if not tool_func:
            raise ValueError(f"Tool function {tool_name} not found")
        
        # Call the tool
        try:
            result = await tool_func(**arguments)
            call_record["result"] = "success"
            call_record["response_size"] = len(str(result))
            return result
        except Exception as e:
            call_record["result"] = "error"
            call_record["error"] = str(e)
            raise


class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    @pytest.fixture
    def server_config(self):
        """Create test server configuration."""
        return AnalysisConfig(
            max_workers=2,
            memory_limit_mb=512,
            cache_enabled=False,  # Disable cache for consistent testing
            parallel_processing=True,
            max_depth=5,
            max_nodes=50,
            output_format="mermaid"
        )
    
    @pytest.fixture
    def server(self, server_config):
        """Create test server instance."""
        return RepoArchitectureMCPServer(config=server_config)
    
    @pytest.fixture
    def mock_client(self, server):
        """Create mock MCP client."""
        return MockMCPClient(server)
    
    @pytest.fixture
    def sample_repo_structure(self):
        """Create a sample repository structure for testing."""
        return {
            "name": "test-repo",
            "full_name": "user/test-repo",
            "description": "Test repository for integration testing",
            "private": False,
            "default_branch": "main",
            "size": 1024,
            "analysis_path": "/tmp/test-repo",
            "file_tree": {
                "files": [
                    {
                        "path": "main.py",
                        "absolute_path": "/tmp/test-repo/main.py",
                        "language": "Python",
                        "size": 500
                    },
                    {
                        "path": "utils.py", 
                        "absolute_path": "/tmp/test-repo/utils.py",
                        "language": "Python",
                        "size": 300
                    }
                ],
                "directories": ["src", "tests"],
                "languages": {"Python": 2},
                "total_size": 800,
                "access_errors": []
            }
        }
    
    @pytest.mark.asyncio
    async def test_complete_workflow_public_repository(self, mock_client, sample_repo_structure):
        """Test complete workflow from repository URL to diagram generation."""
        
        # Mock repository manager and parser components
        with patch('repo_architecture_mcp.repository_manager.RepositoryManager') as mock_repo_mgr, \
             patch('repo_architecture_mcp.parsers.CodeParserFactory') as mock_parser_factory:
            
            # Setup repository manager mock
            mock_repo_instance = AsyncMock()
            mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
            mock_repo_instance.get_repository_info.return_value = sample_repo_structure
            
            # Setup parser factory mock
            mock_parser = AsyncMock()
            mock_parser_instance = AsyncMock()
            mock_parser_factory.return_value = mock_parser_instance
            mock_parser_instance.get_parser.return_value = mock_parser
            
            # Mock parsed code structure
            from repo_architecture_mcp.models import CodeStructure, ClassInfo, FunctionInfo
            mock_code_structure = CodeStructure(
                file_path="/tmp/test-repo/main.py",
                language="Python",
                classes=[
                    ClassInfo(
                        name="TestClass",
                        methods=[],
                        attributes=[],
                        inheritance=[],
                        decorators=[],
                        visibility="public"
                    )
                ],
                functions=[
                    FunctionInfo(
                        name="main",
                        parameters=[],
                        return_type="None",
                        decorators=[],
                        visibility="public"
                    )
                ],
                imports=[],
                exports=[]
            )
            mock_parser.parse_file.return_value = mock_code_structure
            
            # Initialize client
            await mock_client.initialize()
            
            # Test 1: Analyze repository
            repo_url = "https://github.com/user/test-repo"
            analysis_result = await mock_client.call_tool("analyze_repository", {
                "url": repo_url
            })
            
            # Verify analysis result structure
            assert "repository_info" in analysis_result
            assert "analysis_metadata" in analysis_result
            assert "code_statistics" in analysis_result
            assert analysis_result["repository_info"]["url"] == repo_url
            assert analysis_result["analysis_metadata"]["files_parsed"] >= 0
            
            # Test 2: Generate dependency diagram
            dependency_result = await mock_client.call_tool("generate_dependency_diagram", {
                "url": repo_url,
                "format": "mermaid"
            })
            
            # Verify dependency diagram result
            assert "diagram" in dependency_result
            assert "metadata" in dependency_result
            assert "statistics" in dependency_result
            assert dependency_result["diagram"]["format"] == "mermaid"
            assert "content" in dependency_result["diagram"]
            
            # Test 3: Generate class diagram
            class_result = await mock_client.call_tool("generate_class_diagram", {
                "url": repo_url,
                "format": "mermaid"
            })
            
            # Verify class diagram result
            assert "diagram" in class_result
            assert class_result["diagram"]["format"] == "mermaid"
            
            # Test 4: Get repository summary
            summary_result = await mock_client.call_tool("get_repository_summary", {
                "url": repo_url
            })
            
            # Verify summary result
            assert "repository_info" in summary_result
            assert "summary_statistics" in summary_result
            
            # Verify all calls were recorded
            assert len(mock_client.call_history) == 4
            assert all(call["result"] == "success" for call in mock_client.call_history)
    
    @pytest.mark.asyncio
    async def test_mcp_protocol_compliance(self, server):
        """Test MCP protocol compliance with tool registration and responses."""
        
        # Test tool availability
        available_tools = server.get_available_tools()
        expected_tools = [
            "analyze_repository",
            "generate_dependency_diagram",
            "generate_class_diagram", 
            "generate_data_flow_diagram",
            "get_repository_summary"
        ]
        
        assert len(available_tools) == len(expected_tools)
        for tool in expected_tools:
            assert tool in available_tools
        
        # Test server initialization
        assert server.server is not None
        assert server.config is not None
    
    @pytest.mark.asyncio
    async def test_error_handling_and_graceful_degradation(self, mock_client):
        """Test error handling and graceful degradation scenarios."""
        
        # Test invalid repository URL
        with pytest.raises(Exception):
            await mock_client.call_tool("analyze_repository", {
                "url": "invalid-url"
            })
        
        # Test missing required parameters
        with pytest.raises(Exception):
            await mock_client.call_tool("analyze_repository", {})
        
        # Test invalid format parameter
        with pytest.raises(Exception):
            await mock_client.call_tool("generate_dependency_diagram", {
                "url": "https://github.com/user/test-repo",
                "format": "invalid-format"
            })
    
    @pytest.mark.asyncio
    async def test_authentication_scenarios(self, mock_client):
        """Test authentication scenarios with GitHub tokens."""
        
        with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr:
            mock_repo_instance = AsyncMock()
            mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
            mock_repo_instance.authenticate.return_value = True
            mock_repo_instance.get_repository_info.return_value = {
                "name": "private-repo",
                "private": True,
                "analysis_path": "/tmp/private-repo",
                "file_tree": {"files": [], "directories": [], "languages": {}, "total_size": 0}
            }
            
            # Test with valid token
            result = await mock_client.call_tool("analyze_repository", {
                "url": "https://github.com/user/private-repo",
                "token": "valid-token"
            })
            
            # Verify authentication was called
            mock_repo_instance.authenticate.assert_called_once_with("valid-token")
            assert "repository_info" in result
    
    @pytest.mark.asyncio
    async def test_large_repository_handling(self, mock_client):
        """Test handling of large repositories with performance considerations."""
        
        # Create mock large repository structure
        large_repo_structure = {
            "name": "large-repo",
            "full_name": "user/large-repo", 
            "description": "Large repository for performance testing",
            "private": False,
            "default_branch": "main",
            "size": 50000,  # 50MB
            "analysis_path": "/tmp/large-repo",
            "file_tree": {
                "files": [
                    {
                        "path": f"module_{i}.py",
                        "absolute_path": f"/tmp/large-repo/module_{i}.py",
                        "language": "Python",
                        "size": 1000
                    }
                    for i in range(100)  # 100 files
                ],
                "directories": [f"package_{i}" for i in range(10)],
                "languages": {"Python": 100},
                "total_size": 100000,
                "access_errors": []
            }
        }
        
        with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr, \
             patch('repo_architecture_mcp.server.CodeParserFactory') as mock_parser_factory:
            
            mock_repo_instance = AsyncMock()
            mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
            mock_repo_instance.get_repository_info.return_value = large_repo_structure
            
            # Mock parser to simulate processing time
            mock_parser = AsyncMock()
            mock_parser_instance = AsyncMock()
            mock_parser_factory.return_value = mock_parser_instance
            mock_parser_instance.get_parser.return_value = mock_parser
            
            from repo_architecture_mcp.models import CodeStructure
            mock_parser.parse_file.return_value = CodeStructure(
                file_path="test.py",
                language="Python",
                classes=[],
                functions=[],
                imports=[],
                exports=[]
            )
            
            # Test analysis with large repository
            result = await mock_client.call_tool("analyze_repository", {
                "url": "https://github.com/user/large-repo"
            })
            
            # Verify result contains expected structure
            assert "repository_info" in result
            assert "analysis_metadata" in result
            assert result["analysis_metadata"]["total_files_found"] == 100
    
    @pytest.mark.asyncio
    async def test_different_repository_types(self, mock_client):
        """Test with different repository types and programming languages."""
        
        test_cases = [
            {
                "name": "python-repo",
                "language": "Python",
                "files": ["main.py", "utils.py", "models.py"]
            },
            {
                "name": "javascript-repo", 
                "language": "JavaScript",
                "files": ["index.js", "utils.js", "components.js"]
            },
            {
                "name": "typescript-repo",
                "language": "TypeScript", 
                "files": ["main.ts", "types.ts", "services.ts"]
            },
            {
                "name": "java-repo",
                "language": "Java",
                "files": ["Main.java", "Utils.java", "Model.java"]
            }
        ]
        
        for test_case in test_cases:
            with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr, \
                 patch('repo_architecture_mcp.server.CodeParserFactory') as mock_parser_factory:
                
                # Create repository structure for this language
                repo_structure = {
                    "name": test_case["name"],
                    "full_name": f"user/{test_case['name']}",
                    "description": f"Test {test_case['language']} repository",
                    "private": False,
                    "default_branch": "main",
                    "size": 2048,
                    "analysis_path": f"/tmp/{test_case['name']}",
                    "file_tree": {
                        "files": [
                            {
                                "path": filename,
                                "absolute_path": f"/tmp/{test_case['name']}/{filename}",
                                "language": test_case["language"],
                                "size": 500
                            }
                            for filename in test_case["files"]
                        ],
                        "directories": ["src"],
                        "languages": {test_case["language"]: len(test_case["files"])},
                        "total_size": 1500,
                        "access_errors": []
                    }
                }
                
                mock_repo_instance = AsyncMock()
                mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
                mock_repo_instance.get_repository_info.return_value = repo_structure
                
                mock_parser = AsyncMock()
                mock_parser_instance = AsyncMock()
                mock_parser_factory.return_value = mock_parser_instance
                mock_parser_instance.get_parser.return_value = mock_parser
                
                from repo_architecture_mcp.models import CodeStructure
                mock_parser.parse_file.return_value = CodeStructure(
                    file_path="test_file",
                    language=test_case["language"],
                    classes=[],
                    functions=[],
                    imports=[],
                    exports=[]
                )
                
                # Test analysis for this repository type
                result = await mock_client.call_tool("analyze_repository", {
                    "url": f"https://github.com/user/{test_case['name']}"
                })
                
                # Verify language-specific analysis
                assert "code_statistics" in result
                assert test_case["language"] in result["code_statistics"]["language_breakdown"]
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, server):
        """Test handling of concurrent requests to the server."""
        
        async def make_request(client, repo_name):
            """Make a single request."""
            with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr:
                mock_repo_instance = AsyncMock()
                mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
                mock_repo_instance.get_repository_info.return_value = {
                    "name": repo_name,
                    "analysis_path": f"/tmp/{repo_name}",
                    "file_tree": {"files": [], "directories": [], "languages": {}, "total_size": 0}
                }
                
                return await client.call_tool("analyze_repository", {
                    "url": f"https://github.com/user/{repo_name}"
                })
        
        # Create multiple clients
        clients = [MockMCPClient(server) for _ in range(3)]
        
        # Initialize all clients
        for client in clients:
            await client.initialize()
        
        # Make concurrent requests
        tasks = [
            make_request(clients[0], "repo1"),
            make_request(clients[1], "repo2"), 
            make_request(clients[2], "repo3")
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all requests completed successfully
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent request failed: {result}")
            assert "repository_info" in result
    
    @pytest.mark.asyncio
    async def test_memory_and_resource_management(self, mock_client):
        """Test memory and resource management during analysis."""
        
        # Test with memory-intensive repository structure
        memory_intensive_repo = {
            "name": "memory-test-repo",
            "full_name": "user/memory-test-repo",
            "description": "Repository for memory testing",
            "private": False,
            "default_branch": "main", 
            "size": 100000,  # 100MB
            "analysis_path": "/tmp/memory-test-repo",
            "file_tree": {
                "files": [
                    {
                        "path": f"large_file_{i}.py",
                        "absolute_path": f"/tmp/memory-test-repo/large_file_{i}.py",
                        "language": "Python",
                        "size": 10000  # 10KB each
                    }
                    for i in range(500)  # 500 files
                ],
                "directories": [f"package_{i}" for i in range(50)],
                "languages": {"Python": 500},
                "total_size": 5000000,  # 5MB total
                "access_errors": []
            }
        }
        
        with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr, \
             patch('repo_architecture_mcp.server.CodeParserFactory') as mock_parser_factory:
            
            mock_repo_instance = AsyncMock()
            mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
            mock_repo_instance.get_repository_info.return_value = memory_intensive_repo
            
            mock_parser = AsyncMock()
            mock_parser_instance = AsyncMock()
            mock_parser_factory.return_value = mock_parser_instance
            mock_parser_instance.get_parser.return_value = mock_parser
            
            from repo_architecture_mcp.models import CodeStructure
            mock_parser.parse_file.return_value = CodeStructure(
                file_path="test.py",
                language="Python",
                classes=[],
                functions=[],
                imports=[],
                exports=[]
            )
            
            # Test analysis completes without memory issues
            result = await mock_client.call_tool("analyze_repository", {
                "url": "https://github.com/user/memory-test-repo"
            })
            
            # Verify analysis completed successfully
            assert "repository_info" in result
            assert "analysis_metadata" in result
            assert result["analysis_metadata"]["total_files_found"] == 500


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance specifically."""
    
    @pytest.fixture
    def server(self):
        """Create server for protocol testing."""
        return RepoArchitectureMCPServer()
    
    def test_tool_registration(self, server):
        """Test that all tools are properly registered."""
        available_tools = server.get_available_tools()
        
        # Verify all expected tools are available
        expected_tools = [
            "analyze_repository",
            "generate_dependency_diagram",
            "generate_class_diagram",
            "generate_data_flow_diagram", 
            "get_repository_summary"
        ]
        
        assert len(available_tools) == len(expected_tools)
        for tool in expected_tools:
            assert tool in available_tools
    
    def test_server_initialization(self, server):
        """Test server initializes correctly."""
        assert server is not None
        assert server.server is not None
        assert server.config is not None
    
    def test_error_response_format(self, server):
        """Test that error responses follow MCP format."""
        from repo_architecture_mcp.errors import MCPError, ErrorCode
        
        # Create a test error
        error = MCPError(
            message="Test error message",
            code=ErrorCode.INVALID_INPUT,
            details={"field": "test_field", "value": "test_value"}
        )
        
        # Convert to MCP response format
        response = error.to_dict()
        
        # Verify response structure
        assert "error" in response
        assert "code" in response["error"]
        assert "message" in response["error"]
        assert response["error"]["message"] == "The provided input is invalid. Please check your parameters and try again."
        assert response["error"]["code"] == ErrorCode.INVALID_INPUT.value
    
    @pytest.mark.asyncio
    async def test_tool_parameter_validation(self, server):
        """Test that tools properly validate parameters."""
        
        # Test with mock client to avoid actual network calls
        mock_client = MockMCPClient(server)
        await mock_client.initialize()
        
        # Test missing required parameter
        with pytest.raises(Exception):
            await mock_client.call_tool("analyze_repository", {})
        
        # Test invalid parameter type
        with pytest.raises(Exception):
            await mock_client.call_tool("analyze_repository", {
                "url": 123  # Should be string
            })