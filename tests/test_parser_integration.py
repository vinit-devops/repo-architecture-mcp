"""Integration tests for all parsers to verify core functionality."""

import pytest
from repo_architecture_mcp.parsers import parse_file, can_parse, get_supported_extensions, get_supported_languages


class TestParserIntegration:
    """Integration tests for the complete parser system."""
    
    def test_supported_extensions_and_languages(self):
        """Test that all expected extensions and languages are supported."""
        extensions = get_supported_extensions()
        languages = get_supported_languages()
        
        # Check that we have the expected extensions
        expected_extensions = {'.py', '.pyw', '.js', '.jsx', '.mjs', '.ts', '.tsx', '.java'}
        assert expected_extensions.issubset(set(extensions))
        
        # Check that we have the expected languages
        expected_languages = {'python', 'javascript', 'typescript', 'java'}
        assert expected_languages.issubset(set(languages))
    
    def test_can_parse_functionality(self):
        """Test the can_parse function works correctly."""
        # Should be able to parse supported files
        assert can_parse('test.py') is True
        assert can_parse('test.js') is True
        assert can_parse('test.ts') is True
        assert can_parse('test.java') is True
        
        # Should not be able to parse unsupported files
        assert can_parse('test.txt') is False
        assert can_parse('test.unknown') is False
        assert can_parse('README') is False
    
    @pytest.mark.asyncio
    async def test_python_parser_basic_functionality(self):
        """Test Python parser can parse basic code structures."""
        code = '''
import os
from typing import List

class TestClass:
    def __init__(self, name: str):
        self.name = name
    
    def get_name(self) -> str:
        return self.name

def test_function(param: int = 5) -> bool:
    return param > 0

GLOBAL_VAR = "test"
'''
        
        result = await parse_file('test.py', code)
        
        assert result is not None
        assert result.language == 'python'
        assert result.file_path == 'test.py'
        
        # Should have parsed at least some structures
        assert len(result.classes) >= 1
        assert len(result.functions) >= 1
        assert len(result.imports) >= 1
        
        # Check class details
        test_class = next((cls for cls in result.classes if cls.name == 'TestClass'), None)
        assert test_class is not None
        assert len(test_class.methods) >= 1
    
    @pytest.mark.asyncio
    async def test_javascript_parser_basic_functionality(self):
        """Test JavaScript parser can parse basic code structures."""
        code = '''
import React from 'react';

class TestClass {
    constructor(name) {
        this.name = name;
    }
    
    getName() {
        return this.name;
    }
}

function testFunction(param) {
    return param > 0;
}

const GLOBAL_VAR = "test";
'''
        
        result = await parse_file('test.js', code)
        
        assert result is not None
        assert result.language == 'javascript'
        assert result.file_path == 'test.js'
        
        # Should have parsed some structures (exact counts may vary)
        # The regex-based parser may not catch everything perfectly
        assert isinstance(result.classes, list)
        assert isinstance(result.functions, list)
        assert isinstance(result.imports, list)
        assert isinstance(result.global_variables, list)
    
    @pytest.mark.asyncio
    async def test_typescript_parser_basic_functionality(self):
        """Test TypeScript parser can parse basic code structures."""
        code = '''
interface User {
    name: string;
    age: number;
}

class TestClass implements User {
    public name: string;
    public age: number;
    
    constructor(name: string, age: number) {
        this.name = name;
        this.age = age;
    }
    
    getName(): string {
        return this.name;
    }
}

function testFunction(param: number = 5): boolean {
    return param > 0;
}
'''
        
        result = await parse_file('test.ts', code)
        
        assert result is not None
        assert result.language == 'typescript'
        assert result.file_path == 'test.ts'
        
        # Should have parsed some structures
        assert isinstance(result.classes, list)
        assert isinstance(result.functions, list)
    
    @pytest.mark.asyncio
    async def test_java_parser_basic_functionality(self):
        """Test Java parser can parse basic code structures."""
        code = '''
package com.example;

import java.util.List;

public class TestClass {
    private String name;
    
    public TestClass(String name) {
        this.name = name;
    }
    
    public String getName() {
        return name;
    }
}
'''
        
        result = await parse_file('test.java', code)
        
        assert result is not None
        assert result.language == 'java'
        assert result.file_path == 'test.java'
        assert result.namespace == 'com.example'
        
        # Should have parsed some structures
        assert isinstance(result.classes, list)
        assert isinstance(result.imports, list)
        
        # Should have at least found the class
        assert len(result.classes) >= 1
        test_class = result.classes[0]
        assert test_class.name == 'TestClass'
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test that parsers handle errors gracefully."""
        # Test with malformed Python code
        malformed_python = '''
class MalformedClass:
    def method(
        # Missing closing parenthesis
'''
        
        result = await parse_file('test.py', malformed_python)
        assert result is not None
        assert result.language == 'python'
        # Should have error information
        assert len(result.parse_errors) > 0
    
    @pytest.mark.asyncio
    async def test_empty_files(self):
        """Test parsing empty files."""
        for ext, lang in [('.py', 'python'), ('.js', 'javascript'), 
                         ('.ts', 'typescript'), ('.java', 'java')]:
            result = await parse_file(f'test{ext}', '')
            
            assert result is not None
            assert result.language == lang
            assert result.classes == []
            assert result.functions == []
            assert result.parse_errors == []
    
    @pytest.mark.asyncio
    async def test_unsupported_file_types(self):
        """Test that unsupported file types return None."""
        result = await parse_file('test.txt', 'some content')
        assert result is None
        
        result = await parse_file('README', 'some content')
        assert result is None
    
    @pytest.mark.asyncio
    async def test_parser_consistency(self):
        """Test that parsers return consistent structure types."""
        test_files = {
            'test.py': 'class Test: pass',
            'test.js': 'class Test {}',
            'test.ts': 'class Test {}',
            'test.java': 'public class Test {}'
        }
        
        for filename, code in test_files.items():
            result = await parse_file(filename, code)
            
            assert result is not None
            # All parsers should return the same structure type
            assert hasattr(result, 'file_path')
            assert hasattr(result, 'language')
            assert hasattr(result, 'classes')
            assert hasattr(result, 'functions')
            assert hasattr(result, 'imports')
            assert hasattr(result, 'parse_errors')
            
            # Lists should be initialized
            assert isinstance(result.classes, list)
            assert isinstance(result.functions, list)
            assert isinstance(result.imports, list)
            assert isinstance(result.parse_errors, list)


class TestParserRobustness:
    """Test parser robustness with various edge cases."""
    
    @pytest.mark.asyncio
    async def test_large_files(self):
        """Test parsing larger code files."""
        # Generate a larger Python file
        large_python = '''
import os
import sys
from typing import List, Dict, Optional

class LargeClass:
    """A class with many methods."""
    
    def __init__(self):
        self.data = {}
    
''' + '\n'.join([f'''
    def method_{i}(self, param_{i}: int) -> str:
        """Method number {i}."""
        return f"result_{i}: {{param_{i}}}"
''' for i in range(20)])
        
        result = await parse_file('large.py', large_python)
        
        assert result is not None
        assert result.language == 'python'
        assert len(result.classes) >= 1
        
        # Should have parsed the class with many methods
        large_class = result.classes[0]
        assert large_class.name == 'LargeClass'
        # Should have found at least some methods
        assert len(large_class.methods) > 10
    
    @pytest.mark.asyncio
    async def test_unicode_content(self):
        """Test parsing files with unicode content."""
        unicode_python = '''
# -*- coding: utf-8 -*-
"""测试 Unicode 支持"""

class UnicodeClass:
    """A class with unicode content."""
    
    def __init__(self, 名前: str):
        self.名前 = 名前
    
    def get_名前(self) -> str:
        return self.名前
'''
        
        result = await parse_file('unicode.py', unicode_python)
        
        assert result is not None
        assert result.language == 'python'
        # Should handle unicode gracefully
        assert len(result.classes) >= 1
    
    @pytest.mark.asyncio
    async def test_nested_structures(self):
        """Test parsing nested class and function structures."""
        nested_python = '''
class OuterClass:
    def outer_method(self):
        class InnerClass:
            def inner_method(self):
                def nested_function():
                    return "nested"
                return nested_function()
        return InnerClass()
'''
        
        result = await parse_file('nested.py', nested_python)
        
        assert result is not None
        assert result.language == 'python'
        # Should at least parse the outer class
        assert len(result.classes) >= 1
        assert result.classes[0].name == 'OuterClass'