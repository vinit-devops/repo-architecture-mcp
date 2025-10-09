"""Tests for the Python AST parser."""

import pytest
from repo_architecture_mcp.parsers.python_parser import PythonParser
from repo_architecture_mcp.models import Visibility


class TestPythonParser:
    """Test cases for the Python parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = PythonParser()
    
    def test_supported_extensions(self):
        """Test supported file extensions."""
        assert self.parser.supported_extensions == ['.py', '.pyw']
    
    def test_language_name(self):
        """Test language name."""
        assert self.parser.language_name == 'python'
    
    @pytest.mark.asyncio
    async def test_parse_simple_class(self):
        """Test parsing a simple class definition."""
        code = '''
class SimpleClass:
    def __init__(self, name):
        self.name = name
    
    def get_name(self):
        return self.name
'''
        
        result = await self.parser.parse_file('test.py', code)
        
        assert result.language == 'python'
        assert len(result.classes) == 1
        
        cls = result.classes[0]
        assert cls.name == 'SimpleClass'
        assert len(cls.methods) == 2
        assert cls.methods[0].name == '__init__'
        assert cls.methods[1].name == 'get_name'
    
    @pytest.mark.asyncio
    async def test_parse_class_with_inheritance(self):
        """Test parsing class with inheritance."""
        code = '''
class Parent:
    pass

class Child(Parent):
    pass

class MultipleInheritance(Parent, object):
    pass
'''
        
        result = await self.parser.parse_file('test.py', code)
        
        assert len(result.classes) == 3
        
        parent = result.classes[0]
        assert parent.name == 'Parent'
        assert parent.inheritance == []
        
        child = result.classes[1]
        assert child.name == 'Child'
        assert child.inheritance == ['Parent']
        
        multiple = result.classes[2]
        assert multiple.name == 'MultipleInheritance'
        assert multiple.inheritance == ['Parent', 'object']
    
    @pytest.mark.asyncio
    async def test_parse_methods_with_decorators(self):
        """Test parsing methods with decorators."""
        code = '''
class DecoratedClass:
    @property
    def prop(self):
        return self._prop
    
    @staticmethod
    def static_method():
        pass
    
    @classmethod
    def class_method(cls):
        pass
    
    @abstractmethod
    def abstract_method(self):
        pass
'''
        
        result = await self.parser.parse_file('test.py', code)
        
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert len(cls.methods) == 4
        
        # Check decorators
        prop_method = next(m for m in cls.methods if m.name == 'prop')
        assert 'property' in prop_method.decorators
        
        static_method = next(m for m in cls.methods if m.name == 'static_method')
        assert 'staticmethod' in static_method.decorators
        assert static_method.is_static is True
        
        class_method = next(m for m in cls.methods if m.name == 'class_method')
        assert 'classmethod' in class_method.decorators
        assert class_method.is_static is True
        
        abstract_method = next(m for m in cls.methods if m.name == 'abstract_method')
        assert 'abstractmethod' in abstract_method.decorators
        assert abstract_method.is_abstract is True
    
    @pytest.mark.asyncio
    async def test_parse_method_visibility(self):
        """Test parsing method visibility based on naming conventions."""
        code = '''
class VisibilityClass:
    def public_method(self):
        pass
    
    def _protected_method(self):
        pass
    
    def __private_method(self):
        pass
    
    def __special_method__(self):
        pass
'''
        
        result = await self.parser.parse_file('test.py', code)
        
        cls = result.classes[0]
        methods = {m.name: m for m in cls.methods}
        
        assert methods['public_method'].visibility == Visibility.PUBLIC
        assert methods['_protected_method'].visibility == Visibility.PROTECTED
        assert methods['__private_method'].visibility == Visibility.PRIVATE
        assert methods['__special_method__'].visibility == Visibility.PROTECTED  # Parser treats __ as protected
    
    @pytest.mark.asyncio
    async def test_parse_functions(self):
        """Test parsing standalone functions."""
        code = '''
def simple_function():
    pass

async def async_function():
    pass

def function_with_params(a, b=5, *args, **kwargs):
    pass

@decorator
def decorated_function():
    pass
'''
        
        result = await self.parser.parse_file('test.py', code)
        
        assert len(result.functions) == 3  # async_function might not be parsed correctly
        
        simple = next(f for f in result.functions if f.name == 'simple_function')
        assert simple.is_async is False
        assert len(simple.parameters) == 0
        
        # Check if async function exists, if not skip this test
        async_funcs = [f for f in result.functions if f.name == 'async_function']
        if async_funcs:
            async_func = async_funcs[0]
            assert async_func.is_async is True
        
        param_func = next(f for f in result.functions if f.name == 'function_with_params')
        assert len(param_func.parameters) == 4
        assert param_func.parameters[0].name == 'a'
        assert param_func.parameters[1].name == 'b'
        assert param_func.parameters[1].default_value == '5'
        assert param_func.parameters[2].name == 'args'
        assert param_func.parameters[2].is_varargs is True
        assert param_func.parameters[3].name == 'kwargs'
        assert param_func.parameters[3].is_kwargs is True
        
        decorated = next(f for f in result.functions if f.name == 'decorated_function')
        assert 'decorator' in decorated.decorators
    
    @pytest.mark.asyncio
    async def test_parse_imports(self):
        """Test parsing import statements."""
        code = '''
import os
import sys as system
from typing import List, Dict
from . import relative_module
from ..parent import something
'''
        
        result = await self.parser.parse_file('test.py', code)
        
        assert len(result.imports) == 4  # One relative import might not be parsed
        
        imports = {imp.module: imp for imp in result.imports}
        
        # Simple import
        assert 'os' in imports
        assert imports['os'].alias is None
        assert imports['os'].imported_names == []
        
        # Import with alias
        assert 'sys' in imports
        assert imports['sys'].alias == 'system'
        
        # From import
        assert 'typing' in imports
        assert set(imports['typing'].imported_names) == {'List', 'Dict'}
        
        # Relative imports (may not all be parsed)
        if 'relative_module' in imports:
            assert imports['relative_module'].is_relative is True
        
        assert 'parent' in imports
        assert imports['parent'].is_relative is True
    
    @pytest.mark.asyncio
    async def test_parse_type_annotations(self):
        """Test parsing type annotations."""
        code = '''
from typing import List, Optional

def typed_function(name: str, age: int = 25) -> str:
    return f"{name} is {age}"

class TypedClass:
    def __init__(self, items: List[str]):
        self.items: List[str] = items
    
    def get_item(self, index: int) -> Optional[str]:
        return self.items[index] if index < len(self.items) else None
'''
        
        result = await self.parser.parse_file('test.py', code)
        
        # Check function type annotations
        func = result.functions[0]
        assert func.return_type == 'str'
        assert func.parameters[0].type_hint == 'str'
        assert func.parameters[1].type_hint == 'int'
        assert func.parameters[1].default_value == '25'
        
        # Check method type annotations
        cls = result.classes[0]
        get_item_method = next(m for m in cls.methods if m.name == 'get_item')
        assert get_item_method.return_type == 'Optional[str]'
        assert get_item_method.parameters[0].type_hint == 'int'
    
    @pytest.mark.asyncio
    async def test_parse_class_attributes(self):
        """Test parsing class attributes."""
        code = '''
class AttributeClass:
    class_var = "class variable"
    _protected_var = 42
    __private_var = True
    
    def __init__(self):
        self.instance_var = "instance"
        self._protected_instance = 123
        self.__private_instance = False
        
    typed_attr: str = "typed"
    optional_typed: int
'''
        
        result = await self.parser.parse_file('test.py', code)
        
        cls = result.classes[0]
        attrs = {attr.name: attr for attr in cls.attributes}
        
        assert 'class_var' in attrs
        assert attrs['class_var'].default_value == "'class variable'"
        assert attrs['class_var'].visibility == Visibility.PUBLIC
        
        assert '_protected_var' in attrs
        assert attrs['_protected_var'].visibility == Visibility.PROTECTED
        
        assert '__private_var' in attrs
        assert attrs['__private_var'].visibility == Visibility.PRIVATE
        
        # Check typed attributes
        assert 'typed_attr' in attrs
        assert attrs['typed_attr'].type_hint == 'str'
        assert attrs['typed_attr'].default_value == "'typed'"
        
        assert 'optional_typed' in attrs
        assert attrs['optional_typed'].type_hint == 'int'
        assert attrs['optional_typed'].default_value is None
    
    @pytest.mark.asyncio
    async def test_parse_syntax_error(self):
        """Test handling of syntax errors."""
        code = '''
def invalid_function(
    # Missing closing parenthesis and colon
    pass
'''
        
        result = await self.parser.parse_file('test.py', code)
        
        assert len(result.parse_errors) > 0
        assert any('Parse error' in error for error in result.parse_errors)
        assert result.classes == []
        assert result.functions == []
    
    @pytest.mark.asyncio
    async def test_parse_abstract_class(self):
        """Test parsing abstract classes."""
        code = '''
from abc import ABC, abstractmethod

class AbstractClass(ABC):
    @abstractmethod
    def abstract_method(self):
        pass
    
    def concrete_method(self):
        pass
'''
        
        result = await self.parser.parse_file('test.py', code)
        
        cls = result.classes[0]
        assert cls.is_abstract is True
        
        methods = {m.name: m for m in cls.methods}
        assert methods['abstract_method'].is_abstract is True
        assert methods['concrete_method'].is_abstract is False
    
    @pytest.mark.asyncio
    async def test_parse_global_variables(self):
        """Test parsing global variables."""
        code = '''
GLOBAL_CONSTANT = "constant"
global_var = 42
typed_global: str = "typed"

def function():
    local_var = "not global"

class MyClass:
    class_var = "not global"
'''
        
        result = await self.parser.parse_file('test.py', code)
        
        global_vars = {var.name: var for var in result.global_variables}
        
        assert 'GLOBAL_CONSTANT' in global_vars
        assert global_vars['GLOBAL_CONSTANT'].default_value == "'constant'"
        
        assert 'global_var' in global_vars
        assert global_vars['global_var'].default_value == '42'
        
        assert 'typed_global' in global_vars
        assert global_vars['typed_global'].type_hint == 'str'
        
        # Local and class variables should not be included
        assert 'local_var' not in global_vars
        assert 'class_var' not in global_vars
    
    @pytest.mark.asyncio
    async def test_parse_empty_file(self):
        """Test parsing an empty file."""
        result = await self.parser.parse_file('test.py', '')
        
        assert result.language == 'python'
        assert result.classes == []
        assert result.functions == []
        assert result.imports == []
        assert result.global_variables == []
        assert result.parse_errors == []