"""Tests for the JavaScript parser."""

import pytest
from repo_architecture_mcp.parsers.javascript_parser import JavaScriptParser
from repo_architecture_mcp.models import Visibility


class TestJavaScriptParser:
    """Test cases for the JavaScript parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = JavaScriptParser()
    
    def test_supported_extensions(self):
        """Test supported file extensions."""
        assert self.parser.supported_extensions == ['.js', '.jsx', '.mjs']
    
    def test_language_name(self):
        """Test language name."""
        assert self.parser.language_name == 'javascript'
    
    @pytest.mark.asyncio
    async def test_parse_imports(self):
        """Test parsing various import statements."""
        code = '''
import React from 'react';
import { Component, useState } from 'react';
import * as utils from './utils';
import './styles.css';
'''
        
        result = await self.parser.parse_file('test.js', code)
        
        assert len(result.imports) == 4
        
        # Default import
        react_import = next(imp for imp in result.imports if imp.module == 'react' and imp.alias)
        assert react_import.alias == 'React'
        
        # Named imports
        named_import = next(imp for imp in result.imports if imp.module == 'react' and imp.imported_names)
        assert set(named_import.imported_names) == {'Component', 'useState'}
        
        # Namespace import
        namespace_import = next(imp for imp in result.imports if imp.module == './utils')
        assert namespace_import.alias == 'utils'
        
        # Side-effect import
        side_effect = next(imp for imp in result.imports if imp.module == './styles.css')
        assert side_effect.alias is None
        assert side_effect.imported_names == []
    
    @pytest.mark.asyncio
    async def test_parse_exports(self):
        """Test parsing export statements."""
        code = '''
export const API_URL = 'https://api.example.com';
export function helper() {}
export class MyClass {}
export default MyComponent;
export { utils, config };
'''
        
        result = await self.parser.parse_file('test.js', code)
        
        assert len(result.exports) >= 3  # At least the explicit exports
        
        export_names = [exp.name for exp in result.exports]
        assert 'API_URL' in export_names
        assert 'helper' in export_names
        assert 'MyClass' in export_names
        assert 'MyComponent' in export_names
    
    @pytest.mark.asyncio
    async def test_parse_classes(self):
        """Test parsing class definitions."""
        code = '''
class SimpleClass {
    constructor(name) {
        this.name = name;
    }
    
    getName() {
        return this.name;
    }
    
    static create(name) {
        return new SimpleClass(name);
    }
}

class ExtendedClass extends SimpleClass {
    constructor(name, age) {
        super(name);
        this.age = age;
    }
    
    async getInfo() {
        return `${this.name} is ${this.age}`;
    }
}
'''
        
        result = await self.parser.parse_file('test.js', code)
        
        assert len(result.classes) == 2
        
        simple_class = next(cls for cls in result.classes if cls.name == 'SimpleClass')
        assert simple_class.inheritance == []
        assert len(simple_class.methods) == 2  # getName and create (constructor excluded)
        
        # Check static method
        static_method = next(m for m in simple_class.methods if m.name == 'create')
        assert static_method.is_static is True
        
        extended_class = next(cls for cls in result.classes if cls.name == 'ExtendedClass')
        assert extended_class.inheritance == ['SimpleClass']
        
        # Check async method
        async_method = next(m for m in extended_class.methods if m.name == 'getInfo')
        assert async_method.is_async is True
    
    @pytest.mark.asyncio
    async def test_parse_functions(self):
        """Test parsing function definitions."""
        code = '''
function regularFunction(param1, param2) {
    return param1 + param2;
}

async function asyncFunction() {
    return await fetch('/api');
}

const arrowFunction = (x, y) => {
    return x * y;
};

const singleParamArrow = x => {
    return x * 2;
};

const constFunction = function(a, b = 5) {
    return a + b;
};
'''
        
        result = await self.parser.parse_file('test.js', code)
        
        assert len(result.functions) >= 4
        
        function_names = [func.name for func in result.functions]
        assert 'regularFunction' in function_names
        assert 'asyncFunction' in function_names
        assert 'arrowFunction' in function_names
        assert 'singleParamArrow' in function_names
        assert 'constFunction' in function_names
        
        # Check async function
        async_func = next(f for f in result.functions if f.name == 'asyncFunction')
        assert async_func.is_async is True
        
        # Check parameters
        regular_func = next(f for f in result.functions if f.name == 'regularFunction')
        assert len(regular_func.parameters) == 2
        assert regular_func.parameters[0].name == 'param1'
        assert regular_func.parameters[1].name == 'param2'
    
    @pytest.mark.asyncio
    async def test_parse_variables(self):
        """Test parsing global variables."""
        code = '''
const API_URL = 'https://api.example.com';
let counter = 0;
var oldStyle = true;
const config = {
    debug: true,
    timeout: 5000
};

function myFunction() {
    const localVar = 'not global';
}
'''
        
        result = await self.parser.parse_file('test.js', code)
        
        var_names = [var.name for var in result.global_variables]
        assert 'API_URL' in var_names
        assert 'counter' in var_names
        assert 'oldStyle' in var_names
        assert 'config' in var_names
        
        # Local variables should not be included
        assert 'localVar' not in var_names
        
        # Check default values
        api_var = next(v for v in result.global_variables if v.name == 'API_URL')
        assert api_var.default_value == "'https://api.example.com'"
    
    @pytest.mark.asyncio
    async def test_parse_method_visibility(self):
        """Test parsing method visibility based on naming conventions."""
        code = '''
class VisibilityClass {
    publicMethod() {}
    _protectedMethod() {}
    __privateMethod() {}
}
'''
        
        result = await self.parser.parse_file('test.js', code)
        
        cls = result.classes[0]
        methods = {m.name: m for m in cls.methods}
        
        assert methods['publicMethod'].visibility == Visibility.PUBLIC
        assert methods['_protectedMethod'].visibility == Visibility.PRIVATE  # JS treats _ as private
        assert methods['__privateMethod'].visibility == Visibility.PRIVATE
    
    @pytest.mark.asyncio
    async def test_parse_with_comments(self):
        """Test parsing code with comments."""
        code = '''
// Single line comment
/* Multi-line
   comment */
   
class CommentedClass {
    // Method comment
    method() {
        /* inline comment */ return true;
    }
}

/**
 * JSDoc comment
 */
function documentedFunction() {}
'''
        
        result = await self.parser.parse_file('test.js', code)
        
        # Should still parse correctly despite comments
        assert len(result.classes) == 1
        assert result.classes[0].name == 'CommentedClass'
        assert len(result.functions) >= 1
    
    @pytest.mark.asyncio
    async def test_parse_complex_inheritance(self):
        """Test parsing complex class hierarchies."""
        code = '''
class Animal {
    constructor(name) {
        this.name = name;
    }
    
    speak() {
        console.log(`${this.name} makes a sound`);
    }
}

class Dog extends Animal {
    constructor(name, breed) {
        super(name);
        this.breed = breed;
    }
    
    speak() {
        console.log(`${this.name} barks`);
    }
    
    wagTail() {
        console.log(`${this.name} wags tail`);
    }
}
'''
        
        result = await self.parser.parse_file('test.js', code)
        
        assert len(result.classes) == 2
        
        animal = next(cls for cls in result.classes if cls.name == 'Animal')
        assert animal.inheritance == []
        
        dog = next(cls for cls in result.classes if cls.name == 'Dog')
        assert dog.inheritance == ['Animal']
        assert len(dog.methods) == 2  # speak and wagTail (constructor excluded)
    
    @pytest.mark.asyncio
    async def test_parse_empty_file(self):
        """Test parsing an empty file."""
        result = await self.parser.parse_file('test.js', '')
        
        assert result.language == 'javascript'
        assert result.classes == []
        assert result.functions == []
        assert result.imports == []
        assert result.exports == []
        assert result.global_variables == []
        assert result.parse_errors == []
    
    @pytest.mark.asyncio
    async def test_parse_malformed_code(self):
        """Test parsing malformed JavaScript code."""
        code = '''
class MalformedClass {
    method() {
        // Missing closing brace
    
function orphanFunction() {}
'''
        
        result = await self.parser.parse_file('test.js', code)
        
        # Should not crash, may have partial results
        assert result.language == 'javascript'
        # The parser should handle malformed code gracefully
        # Exact results may vary based on how malformed the code is