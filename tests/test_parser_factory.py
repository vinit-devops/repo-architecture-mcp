"""Tests for the parser factory and registry."""

import pytest
from unittest.mock import Mock, AsyncMock

from repo_architecture_mcp.parsers import (
    ParserRegistry, CodeParserFactory, parse_file, can_parse,
    get_supported_extensions, get_supported_languages
)
from repo_architecture_mcp.parsers.base import CodeParser
from repo_architecture_mcp.models import CodeStructure


class MockParser(CodeParser):
    """Mock parser for testing."""
    
    def __init__(self, language, extensions):
        super().__init__()
        self._language = language
        self._extensions = extensions
    
    @property
    def supported_extensions(self):
        return self._extensions
    
    @property
    def language_name(self):
        return self._language
    
    async def parse_file(self, file_path: str, content=None):
        return CodeStructure(
            file_path=file_path,
            language=self._language
        )


class TestParserRegistry:
    """Test cases for the ParserRegistry class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.registry = ParserRegistry()
    
    def test_register_parser(self):
        """Test registering a parser."""
        mock_parser_class = Mock()
        mock_parser = MockParser('test', ['.test'])
        mock_parser_class.return_value = mock_parser
        
        self.registry.register_parser(mock_parser_class)
        
        assert 'test' in self.registry.get_supported_languages()
        assert '.test' in self.registry.get_supported_extensions()
    
    def test_register_duplicate_parser(self):
        """Test registering a parser for an already registered language."""
        parser1_class = Mock()
        parser1 = MockParser('test', ['.test'])
        parser1_class.return_value = parser1
        
        parser2_class = Mock()
        parser2 = MockParser('test', ['.test2'])
        parser2_class.return_value = parser2
        
        self.registry.register_parser(parser1_class)
        self.registry.register_parser(parser2_class)  # Should overwrite
        
        # Should have the second parser
        parser = self.registry.get_parser('test.test2')
        assert parser is not None
        assert parser.language_name == 'test'
    
    def test_get_parser_by_extension(self):
        """Test getting parser by file extension."""
        mock_parser_class = Mock()
        mock_parser = MockParser('test', ['.test', '.tst'])
        mock_parser_class.return_value = mock_parser
        
        self.registry.register_parser(mock_parser_class)
        
        parser1 = self.registry.get_parser('file.test')
        parser2 = self.registry.get_parser('file.tst')
        parser3 = self.registry.get_parser('file.unknown')
        
        assert parser1 is not None
        assert parser1.language_name == 'test'
        assert parser2 is not None
        assert parser2.language_name == 'test'
        assert parser3 is None
    
    def test_get_parser_case_insensitive(self):
        """Test getting parser with case-insensitive extension matching."""
        mock_parser_class = Mock()
        mock_parser = MockParser('test', ['.test'])
        mock_parser_class.return_value = mock_parser
        
        self.registry.register_parser(mock_parser_class)
        
        parser1 = self.registry.get_parser('file.TEST')
        parser2 = self.registry.get_parser('file.Test')
        
        assert parser1 is not None
        assert parser2 is not None
    
    def test_can_parse(self):
        """Test checking if a file can be parsed."""
        mock_parser_class = Mock()
        mock_parser = MockParser('test', ['.test'])
        mock_parser_class.return_value = mock_parser
        
        self.registry.register_parser(mock_parser_class)
        
        assert self.registry.can_parse('file.test') is True
        assert self.registry.can_parse('file.unknown') is False
    
    def test_get_supported_extensions(self):
        """Test getting all supported extensions."""
        parser1_class = Mock()
        parser1 = MockParser('lang1', ['.ext1', '.ext2'])
        parser1_class.return_value = parser1
        
        parser2_class = Mock()
        parser2 = MockParser('lang2', ['.ext3'])
        parser2_class.return_value = parser2
        
        self.registry.register_parser(parser1_class)
        self.registry.register_parser(parser2_class)
        
        extensions = self.registry.get_supported_extensions()
        assert set(extensions) == {'.ext1', '.ext2', '.ext3'}
    
    def test_get_supported_languages(self):
        """Test getting all supported languages."""
        parser1_class = Mock()
        parser1 = MockParser('lang1', ['.ext1'])
        parser1_class.return_value = parser1
        
        parser2_class = Mock()
        parser2 = MockParser('lang2', ['.ext2'])
        parser2_class.return_value = parser2
        
        self.registry.register_parser(parser1_class)
        self.registry.register_parser(parser2_class)
        
        languages = self.registry.get_supported_languages()
        assert set(languages) == {'lang1', 'lang2'}


class TestCodeParserFactory:
    """Test cases for the CodeParserFactory class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.factory = CodeParserFactory()
    
    def test_initialization(self):
        """Test factory initialization loads parsers."""
        # The factory should have loaded the built-in parsers
        languages = self.factory.get_supported_languages()
        extensions = self.factory.get_supported_extensions()
        
        # Should have at least some parsers loaded
        assert len(languages) > 0
        assert len(extensions) > 0
        
        # Should include the main languages we implemented
        expected_languages = {'python', 'javascript', 'typescript', 'java'}
        assert expected_languages.issubset(set(languages))
    
    @pytest.mark.asyncio
    async def test_parse_file_with_parser(self):
        """Test parsing a file with an available parser."""
        # Test with Python file
        code = '''
def test_function():
    pass
'''
        
        result = await self.factory.parse_file('test.py', code)
        
        assert result is not None
        assert result.language == 'python'
        assert result.file_path == 'test.py'
    
    @pytest.mark.asyncio
    async def test_parse_file_no_parser(self):
        """Test parsing a file with no available parser."""
        result = await self.factory.parse_file('test.unknown', 'content')
        
        assert result is None
    
    def test_can_parse(self):
        """Test checking if factory can parse a file."""
        assert self.factory.can_parse('test.py') is True
        assert self.factory.can_parse('test.js') is True
        assert self.factory.can_parse('test.ts') is True
        assert self.factory.can_parse('test.java') is True
        assert self.factory.can_parse('test.unknown') is False
    
    def test_get_supported_extensions(self):
        """Test getting supported extensions from factory."""
        extensions = self.factory.get_supported_extensions()
        
        expected_extensions = {'.py', '.pyw', '.js', '.jsx', '.mjs', '.ts', '.tsx', '.java'}
        assert expected_extensions.issubset(set(extensions))
    
    def test_get_supported_languages(self):
        """Test getting supported languages from factory."""
        languages = self.factory.get_supported_languages()
        
        expected_languages = {'python', 'javascript', 'typescript', 'java'}
        assert expected_languages.issubset(set(languages))


class TestGlobalFunctions:
    """Test cases for the global convenience functions."""
    
    @pytest.mark.asyncio
    async def test_parse_file_function(self):
        """Test the global parse_file function."""
        code = '''
class TestClass:
    pass
'''
        
        result = await parse_file('test.py', code)
        
        assert result is not None
        assert result.language == 'python'
        assert len(result.classes) == 1
    
    @pytest.mark.asyncio
    async def test_parse_file_function_no_parser(self):
        """Test the global parse_file function with unsupported file."""
        result = await parse_file('test.unknown', 'content')
        
        assert result is None
    
    def test_can_parse_function(self):
        """Test the global can_parse function."""
        assert can_parse('test.py') is True
        assert can_parse('test.js') is True
        assert can_parse('test.unknown') is False
    
    def test_get_supported_extensions_function(self):
        """Test the global get_supported_extensions function."""
        extensions = get_supported_extensions()
        
        assert isinstance(extensions, list)
        assert '.py' in extensions
        assert '.js' in extensions
        assert '.ts' in extensions
        assert '.java' in extensions
    
    def test_get_supported_languages_function(self):
        """Test the global get_supported_languages function."""
        languages = get_supported_languages()
        
        assert isinstance(languages, list)
        assert 'python' in languages
        assert 'javascript' in languages
        assert 'typescript' in languages
        assert 'java' in languages


class TestParserIntegration:
    """Integration tests for the complete parser system."""
    
    @pytest.mark.asyncio
    async def test_parse_multiple_languages(self):
        """Test parsing files in different languages."""
        test_files = {
            'test.py': '''
class PythonClass:
    def method(self):
        pass
''',
            'test.js': '''
class JavaScriptClass {
    method() {}
}
''',
            'test.ts': '''
class TypeScriptClass {
    method(): void {}
}
''',
            'test.java': '''
public class JavaClass {
    public void method() {}
}
'''
        }
        
        results = {}
        for filename, code in test_files.items():
            result = await parse_file(filename, code)
            results[filename] = result
        
        # All files should be parsed successfully
        for filename, result in results.items():
            assert result is not None, f"Failed to parse {filename}"
            assert len(result.classes) >= 1, f"No classes found in {filename}"
            assert result.classes[0].name.endswith('Class'), f"Unexpected class name in {filename}"
    
    @pytest.mark.asyncio
    async def test_error_handling_across_parsers(self):
        """Test error handling consistency across different parsers."""
        malformed_files = {
            'test.py': 'class MalformedClass:\n    def method(\n        # Missing closing paren',
            'test.js': 'class MalformedClass {\n    method() {\n        // Missing closing brace',
            'test.java': 'public class MalformedClass {\n    public void method() {\n        // Missing closing brace'
        }
        
        for filename, code in malformed_files.items():
            result = await parse_file(filename, code)
            
            # Should not crash and should return a result
            assert result is not None, f"Parser crashed on {filename}"
            assert result.language is not None, f"Language not set for {filename}"
            
            # May have parse errors or partial results
            # The exact behavior depends on the parser implementation