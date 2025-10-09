"""Simplified integration tests for the Repository Architecture MCP Server.

These tests focus on core functionality and MCP protocol compliance without
complex mocking that depends on internal implementation details.
"""

import pytest
from repo_architecture_mcp.server import RepoArchitectureMCPServer
from repo_architecture_mcp.models import AnalysisConfig
from repo_architecture_mcp.errors import MCPError, ErrorCode


class TestMCPServerIntegration:
    """Integration tests for MCP server functionality."""
    
    @pytest.fixture
    def server_config(self):
        """Create test server configuration."""
        return AnalysisConfig(
            max_workers=2,
            memory_limit_mb=512,
            cache_enabled=False,
            parallel_processing=True,
            max_depth=5,
            max_nodes=50,
            output_format="mermaid"
        )
    
    @pytest.fixture
    def server(self, server_config):
        """Create test server instance."""
        return RepoArchitectureMCPServer(config=server_config)
    
    def test_server_initialization(self, server):
        """Test that the server initializes correctly."""
        assert server is not None
        assert server.server is not None
        assert server.config is not None
    
    def test_available_tools(self, server):
        """Test that all expected tools are available."""
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
    
    def test_server_configuration(self, server):
        """Test server configuration is properly set."""
        config = server.config
        
        assert config.max_workers == 2
        assert config.memory_limit_mb == 512
        assert config.cache_enabled is False
        assert config.parallel_processing is True
        assert config.max_depth == 5
        assert config.max_nodes == 50
        assert config.output_format == "mermaid"
    
    def test_error_handling_structure(self):
        """Test error handling structure and format."""
        # Test MCPError creation and formatting
        error = MCPError(
            message="Test error message",
            code=ErrorCode.INVALID_INPUT,
            details={"field": "test_field", "value": "test_value"}
        )
        
        # Test MCP response format
        mcp_response = error.to_mcp_response()
        assert "error" in mcp_response
        assert "code" in mcp_response["error"]
        assert "message" in mcp_response["error"]
        assert "data" in mcp_response["error"]
        
        # Test dictionary format
        dict_response = error.to_dict()
        assert "error" in dict_response
        assert "error_code" in dict_response
        assert "error_type" in dict_response
        assert dict_response["error_code"] == ErrorCode.INVALID_INPUT.value
    
    def test_error_code_coverage(self):
        """Test that all error codes are properly defined."""
        # Test that all expected error codes exist
        expected_codes = [
            "INVALID_INPUT", "INVALID_URL", "INVALID_FORMAT", "INVALID_PARAMETERS",
            "AUTH_FAILED", "AUTH_TOKEN_INVALID", "AUTH_PERMISSION_DENIED",
            "REPO_NOT_FOUND", "REPO_ACCESS_DENIED", "REPO_CLONE_FAILED", "REPO_INVALID",
            "PARSE_FAILED", "PARSE_SYNTAX_ERROR", "PARSE_UNSUPPORTED_LANGUAGE",
            "ANALYSIS_FAILED", "ANALYSIS_NO_DATA", "ANALYSIS_TIMEOUT",
            "GENERATION_FAILED", "GENERATION_FORMAT_ERROR", "GENERATION_SIZE_LIMIT",
            "NETWORK_ERROR", "NETWORK_TIMEOUT", "NETWORK_CONNECTION_FAILED",
            "MEMORY_LIMIT_EXCEEDED", "DISK_SPACE_ERROR", "RESOURCE_UNAVAILABLE",
            "INTERNAL_ERROR", "CONFIGURATION_ERROR", "DEPENDENCY_ERROR"
        ]
        
        for code_name in expected_codes:
            assert hasattr(ErrorCode, code_name), f"ErrorCode.{code_name} not found"
            code = getattr(ErrorCode, code_name)
            assert isinstance(code.value, str), f"ErrorCode.{code_name} value should be string"
    
    def test_server_cleanup(self, server):
        """Test server cleanup functionality."""
        # Test that cleanup method exists and can be called
        assert hasattr(server, 'cleanup')
        
        # Test cleanup doesn't raise exceptions
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.cleanup())
        finally:
            loop.close()


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance."""
    
    @pytest.fixture
    def server(self):
        """Create server for protocol testing."""
        return RepoArchitectureMCPServer()
    
    def test_tool_registration_format(self, server):
        """Test that tools are registered in the correct format."""
        # Verify server has the FastMCP server instance
        assert hasattr(server, 'server')
        assert server.server is not None
        
        # Verify tools are available
        tools = server.get_available_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        
        # Verify all tools are strings
        for tool in tools:
            assert isinstance(tool, str)
            assert len(tool) > 0
    
    def test_server_has_required_methods(self, server):
        """Test that server has all required methods for MCP compliance."""
        required_methods = [
            'get_available_tools',
            'run',
            'cleanup'
        ]
        
        for method in required_methods:
            assert hasattr(server, method), f"Server missing required method: {method}"
            assert callable(getattr(server, method)), f"Server method {method} is not callable"
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        # Test valid configuration
        valid_config = AnalysisConfig(
            max_workers=4,
            memory_limit_mb=1024,
            cache_enabled=True,
            parallel_processing=True,
            max_depth=10,
            max_nodes=100,
            output_format="mermaid"
        )
        
        server = RepoArchitectureMCPServer(config=valid_config)
        assert server.config.max_workers == 4
        assert server.config.memory_limit_mb == 1024
        assert server.config.cache_enabled is True
    
    def test_default_configuration(self):
        """Test server with default configuration."""
        server = RepoArchitectureMCPServer()
        
        # Verify server initializes with default config
        assert server.config is not None
        assert isinstance(server.config, AnalysisConfig)
        
        # Verify default values are reasonable
        assert server.config.max_workers > 0
        assert server.config.memory_limit_mb > 0
        assert server.config.max_depth > 0
        assert server.config.max_nodes > 0
        assert server.config.output_format in ["mermaid", "plantuml", "svg", "png"]


class TestErrorHandling:
    """Test error handling functionality."""
    
    def test_validation_error_creation(self):
        """Test validation error creation and formatting."""
        from repo_architecture_mcp.errors import ValidationError
        
        error = ValidationError(
            message="Invalid input provided",
            field="url",
            value="invalid-url"
        )
        
        assert error.code == ErrorCode.INVALID_INPUT
        assert "field" in error.details
        assert error.details["field"] == "url"
        assert error.details["invalid_value"] == "invalid-url"
    
    def test_repository_error_creation(self):
        """Test repository error creation and formatting."""
        from repo_architecture_mcp.errors import RepositoryError, RepositoryNotFoundError
        
        # Test generic repository error
        repo_error = RepositoryError(
            message="Repository access failed",
            repo_url="https://github.com/user/repo",
            operation="clone"
        )
        
        assert repo_error.code == ErrorCode.REPO_ACCESS_DENIED
        assert "repository_url" in repo_error.details
        assert "operation" in repo_error.details
        
        # Test specific repository not found error
        not_found_error = RepositoryNotFoundError("https://github.com/user/nonexistent")
        assert not_found_error.code == ErrorCode.REPO_NOT_FOUND
    
    def test_error_handler_validation(self):
        """Test ErrorHandler validation methods."""
        from repo_architecture_mcp.errors import ErrorHandler, ValidationError
        
        # Test valid GitHub URL
        try:
            ErrorHandler.validate_github_url("https://github.com/user/repo")
            # Should not raise exception
        except ValidationError:
            pytest.fail("Valid GitHub URL should not raise ValidationError")
        
        # Test invalid GitHub URL
        with pytest.raises(ValidationError):
            ErrorHandler.validate_github_url("invalid-url")
        
        # Test empty URL
        with pytest.raises(ValidationError):
            ErrorHandler.validate_github_url("")
        
        # Test None URL
        with pytest.raises(ValidationError):
            ErrorHandler.validate_github_url(None)
    
    def test_format_validation(self):
        """Test format validation."""
        from repo_architecture_mcp.errors import ErrorHandler, ValidationError
        
        valid_formats = ["mermaid", "svg", "png"]
        
        # Test valid format
        try:
            ErrorHandler.validate_format("mermaid", valid_formats)
            # Should not raise exception
        except ValidationError:
            pytest.fail("Valid format should not raise ValidationError")
        
        # Test invalid format
        with pytest.raises(ValidationError):
            ErrorHandler.validate_format("invalid", valid_formats)
        
        # Test empty format
        with pytest.raises(ValidationError):
            ErrorHandler.validate_format("", valid_formats)
    
    def test_positive_integer_validation(self):
        """Test positive integer validation."""
        from repo_architecture_mcp.errors import ErrorHandler, ValidationError
        
        # Test valid positive integer
        try:
            ErrorHandler.validate_positive_integer(5, "test_field")
            # Should not raise exception
        except ValidationError:
            pytest.fail("Valid positive integer should not raise ValidationError")
        
        # Test zero
        with pytest.raises(ValidationError):
            ErrorHandler.validate_positive_integer(0, "test_field")
        
        # Test negative number
        with pytest.raises(ValidationError):
            ErrorHandler.validate_positive_integer(-1, "test_field")
        
        # Test with max value
        try:
            ErrorHandler.validate_positive_integer(5, "test_field", max_value=10)
            # Should not raise exception
        except ValidationError:
            pytest.fail("Valid integer within max should not raise ValidationError")
        
        # Test exceeding max value
        with pytest.raises(ValidationError):
            ErrorHandler.validate_positive_integer(15, "test_field", max_value=10)


class TestModelIntegration:
    """Test integration with data models."""
    
    def test_analysis_config_creation(self):
        """Test AnalysisConfig creation and validation."""
        config = AnalysisConfig(
            max_workers=4,
            memory_limit_mb=1024,
            cache_enabled=True,
            parallel_processing=True,
            max_depth=10,
            max_nodes=100,
            output_format="mermaid",
            github_token="test-token"
        )
        
        assert config.max_workers == 4
        assert config.memory_limit_mb == 1024
        assert config.cache_enabled is True
        assert config.parallel_processing is True
        assert config.max_depth == 10
        assert config.max_nodes == 100
        assert config.output_format == "mermaid"
        assert config.github_token == "test-token"
    
    def test_analysis_config_defaults(self):
        """Test AnalysisConfig default values."""
        config = AnalysisConfig()
        
        # Verify defaults are set
        assert config.max_workers > 0
        assert config.memory_limit_mb > 0
        assert config.max_depth > 0
        assert config.max_nodes > 0
        assert config.output_format in ["mermaid", "plantuml", "svg", "png"]
        assert isinstance(config.cache_enabled, bool)
        assert isinstance(config.parallel_processing, bool)
    
    def test_config_serialization(self):
        """Test configuration serialization."""
        config = AnalysisConfig(
            max_workers=4,
            memory_limit_mb=1024,
            output_format="svg"
        )
        
        # Test to_dict method if available
        if hasattr(config, 'to_dict'):
            config_dict = config.to_dict()
            assert isinstance(config_dict, dict)
            assert config_dict['max_workers'] == 4
            assert config_dict['memory_limit_mb'] == 1024
            assert config_dict['output_format'] == "svg"
        
        # Test from_dict method if available
        if hasattr(AnalysisConfig, 'from_dict'):
            test_dict = {
                'max_workers': 8,
                'memory_limit_mb': 2048,
                'output_format': 'png'
            }
            new_config = AnalysisConfig.from_dict(test_dict)
            assert new_config.max_workers == 8
            assert new_config.memory_limit_mb == 2048
            assert new_config.output_format == "png"


class TestServerLifecycle:
    """Test server lifecycle management."""
    
    def test_server_creation_and_destruction(self):
        """Test server can be created and destroyed properly."""
        # Test server creation
        server = RepoArchitectureMCPServer()
        assert server is not None
        
        # Test server has required attributes
        assert hasattr(server, 'server')
        assert hasattr(server, 'config')
        
        # Test server cleanup
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Should not raise exceptions
            loop.run_until_complete(server.cleanup())
        finally:
            loop.close()
    
    def test_multiple_server_instances(self):
        """Test that multiple server instances can coexist."""
        server1 = RepoArchitectureMCPServer()
        server2 = RepoArchitectureMCPServer()
        
        # Verify they are different instances
        assert server1 is not server2
        assert server1.server is not server2.server
        
        # Verify both have the same tools available
        tools1 = server1.get_available_tools()
        tools2 = server2.get_available_tools()
        assert tools1 == tools2
    
    def test_server_with_custom_config(self):
        """Test server creation with custom configuration."""
        custom_config = AnalysisConfig(
            max_workers=8,
            memory_limit_mb=2048,
            cache_enabled=False,
            output_format="svg"
        )
        
        server = RepoArchitectureMCPServer(config=custom_config)
        
        # Verify custom config is used
        assert server.config.max_workers == 8
        assert server.config.memory_limit_mb == 2048
        assert server.config.cache_enabled is False
        assert server.config.output_format == "svg"