"""Tests for the base parser functionality."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from repo_architecture_mcp.parsers.base import CodeParser, ParseError
from repo_architecture_mcp.models import CodeStructure


class MockParser(CodeParser):
    """Mock parser for testing base functionality."""
    
    @property
    def supported_extensions(self):
        return ['.mock']
    
    @property
    def language_name(self):
        return 'mock'
    
    async def parse_file(self, file_path: str, content=None):
        if content is None:
            content = self._read_file_content(file_path)
        return self._create_base_structure(file_path, content)


class TestCodeParser:
    """Test cases for the base CodeParser class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = MockParser()
    
    def test_supported_extensions(self):
        """Test that supported extensions are returned correctly."""
        assert self.parser.supported_extensions == ['.mock']
    
    def test_language_name(self):
        """Test that language name is returned correctly."""
        assert self.parser.language_name == 'mock'
    
    def test_can_parse_supported_extension(self):
        """Test that parser can handle supported extensions."""
        assert self.parser.can_parse('test.mock') is True
        assert self.parser.can_parse('test.MOCK') is True  # Case insensitive
    
    def test_can_parse_unsupported_extension(self):
        """Test that parser rejects unsupported extensions."""
        assert self.parser.can_parse('test.py') is False
        assert self.parser.can_parse('test.js') is False
        assert self.parser.can_parse('test.txt') is False
    
    def test_can_parse_no_extension(self):
        """Test that parser rejects files without extensions."""
        assert self.parser.can_parse('test') is False
        assert self.parser.can_parse('README') is False
    
    @patch('builtins.open')
    def test_read_file_content_utf8(self, mock_open):
        """Test reading file content with UTF-8 encoding."""
        mock_open.return_value.__enter__.return_value.read.return_value = "test content"
        
        content = self.parser._read_file_content('test.mock')
        
        assert content == "test content"
        mock_open.assert_called_once_with('test.mock', 'r', encoding='utf-8')
    
    @patch('builtins.open')
    def test_read_file_content_fallback_encoding(self, mock_open):
        """Test reading file content with fallback encoding."""
        from unittest.mock import mock_open as mock_open_func
        
        # First call raises UnicodeDecodeError, second call succeeds
        def side_effect(*args, **kwargs):
            if 'utf-8' in str(kwargs.get('encoding', '')):
                raise UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid')
            else:
                return mock_open_func(read_data="test content").return_value
        
        mock_open.side_effect = side_effect
        
        content = self.parser._read_file_content('test.mock')
        
        assert content == "test content"
        assert mock_open.call_count == 2
    
    @patch('builtins.open')
    def test_read_file_content_file_not_found(self, mock_open):
        """Test reading non-existent file raises ParseError."""
        mock_open.side_effect = FileNotFoundError("File not found")
        
        with pytest.raises(ParseError) as exc_info:
            self.parser._read_file_content('nonexistent.mock')
        
        assert "Failed to read file" in str(exc_info.value)
        assert "nonexistent.mock" in str(exc_info.value)
    
    def test_create_base_structure(self):
        """Test creating base code structure."""
        structure = self.parser._create_base_structure('test.mock', 'content')
        
        assert isinstance(structure, CodeStructure)
        assert structure.file_path == 'test.mock'
        assert structure.language == 'mock'
        assert structure.encoding == 'utf-8'
        assert structure.classes == []
        assert structure.functions == []
        assert structure.imports == []
        assert structure.exports == []
        assert structure.global_variables == []
        assert structure.parse_errors == []
    
    def test_handle_parse_error(self):
        """Test error handling creates structure with error info."""
        error = ValueError("Test error")
        structure = self.parser._handle_parse_error(error, 'test.mock', 42)
        
        assert isinstance(structure, CodeStructure)
        assert structure.file_path == 'test.mock'
        assert structure.language == 'mock'
        assert len(structure.parse_errors) == 1
        assert "Parse error: Test error at line 42" in structure.parse_errors[0]
    
    def test_handle_parse_error_no_line_number(self):
        """Test error handling without line number."""
        error = ValueError("Test error")
        structure = self.parser._handle_parse_error(error, 'test.mock')
        
        assert len(structure.parse_errors) == 1
        assert "Parse error: Test error" in structure.parse_errors[0]
        assert "at line" not in structure.parse_errors[0]


class TestParseError:
    """Test cases for ParseError exception."""
    
    def test_parse_error_with_line_number(self):
        """Test ParseError with line number."""
        error = ParseError("Test message", "test.py", 42)
        
        assert error.message == "Test message"
        assert error.file_path == "test.py"
        assert error.line_number == 42
        assert str(error) == "Test message in test.py at line 42"
    
    def test_parse_error_without_line_number(self):
        """Test ParseError without line number."""
        error = ParseError("Test message", "test.py")
        
        assert error.message == "Test message"
        assert error.file_path == "test.py"
        assert error.line_number is None
        assert str(error) == "Test message in test.py"