"""TypeScript parser for extracting code structure."""

import re
from typing import List, Optional, Dict, Any
import logging

from .javascript_parser import JavaScriptParser
from ..models import (
    CodeStructure, ClassInfo, MethodInfo, FunctionInfo, 
    AttributeInfo, ParameterInfo, ImportInfo, ExportInfo, Visibility
)


logger = logging.getLogger(__name__)


class TypeScriptParser(JavaScriptParser):
    """Parser for TypeScript source code, extending JavaScript parser."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.ts', '.tsx']
    
    @property
    def language_name(self) -> str:
        return 'typescript'
    
    def __init__(self):
        super().__init__()
        self._setup_typescript_patterns()
    
    def _setup_typescript_patterns(self):
        """Set up additional regex patterns for TypeScript-specific features."""
        # Interface patterns
        self.interface_pattern = re.compile(
            r'interface\s+(\w+)(?:\s+extends\s+([\w,\s]+))?\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        # Type alias patterns
        self.type_pattern = re.compile(
            r'type\s+(\w+)\s*=\s*([^;]+);?',
            re.MULTILINE
        )
        
        # Enum patterns
        self.enum_pattern = re.compile(
            r'enum\s+(\w+)\s*\{([^{}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        # Class with TypeScript features
        self.ts_class_pattern = re.compile(
            r'(?:(abstract|export)\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        # Method with TypeScript features
        self.ts_method_pattern = re.compile(
            r'(?:(public|private|protected|static|abstract|async)\s+)*(\w+)\s*\([^)]*\)(?:\s*:\s*([^{;]+))?\s*[{;]',
            re.MULTILINE
        )
        
        # Property patterns
        self.property_pattern = re.compile(
            r'(?:(public|private|protected|static|readonly)\s+)*(\w+)(?:\s*:\s*([^=;]+))?(?:\s*=\s*([^;]+))?;?',
            re.MULTILINE
        )
        
        # Function with TypeScript features
        self.ts_function_patterns = [
            # function name(params): returnType { }
            re.compile(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{', re.MULTILINE),
            # const name = (params): returnType => { }
            re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)(?:\s*:\s*([^=]+))?\s*=>\s*\{', re.MULTILINE),
        ]
    
    async def parse_file(self, file_path: str, content: Optional[str] = None) -> CodeStructure:
        """Parse a TypeScript source file and extract its structure."""
        try:
            if content is None:
                content = self._read_file_content(file_path)
            
            # Create base structure
            structure = self._create_base_structure(file_path, content)
            
            # Remove comments to avoid false matches
            cleaned_content = self._remove_comments(content)
            
            # Extract different code elements
            structure.imports = self._extract_imports(cleaned_content)
            structure.exports = self._extract_exports(cleaned_content)
            structure.classes = self._extract_typescript_classes(cleaned_content)
            structure.functions = self._extract_typescript_functions(cleaned_content)
            structure.global_variables = self._extract_global_variables(cleaned_content)
            
            # Add TypeScript-specific elements as classes for now
            interfaces = self._extract_interfaces(cleaned_content)
            structure.classes.extend(interfaces)
            
            return structure
            
        except Exception as e:
            return self._handle_parse_error(e, file_path)
    
    def _extract_typescript_classes(self, content: str) -> List[ClassInfo]:
        """Extract class definitions with TypeScript features."""
        classes = []
        
        for match in self.ts_class_pattern.finditer(content):
            modifier = match.group(1)  # abstract or export
            class_name = match.group(2)
            parent_class = match.group(3) if match.group(3) else None
            interfaces = match.group(4) if match.group(4) else None
            class_body = match.group(5)
            
            class_info = ClassInfo(
                name=class_name,
                inheritance=[parent_class] if parent_class else [],
                interfaces=[i.strip() for i in interfaces.split(',')] if interfaces else [],
                is_abstract=modifier == 'abstract',
                line_number=self._get_line_number(content, match.start())
            )
            
            # Extract methods and properties from class body
            class_info.methods = self._extract_typescript_methods(class_body)
            class_info.attributes = self._extract_typescript_properties(class_body)
            
            classes.append(class_info)
        
        return classes
    
    def _extract_typescript_methods(self, class_body: str) -> List[MethodInfo]:
        """Extract method definitions with TypeScript features."""
        methods = []
        
        for match in self.ts_method_pattern.finditer(class_body):
            modifiers = match.group(1) if match.group(1) else ''
            method_name = match.group(2)
            return_type = match.group(3) if match.group(3) else None
            
            # Skip constructor
            if method_name == 'constructor':
                continue
            
            # Parse modifiers
            visibility = Visibility.PUBLIC
            is_static = False
            is_abstract = False
            is_async = False
            
            if modifiers:
                if 'private' in modifiers:
                    visibility = Visibility.PRIVATE
                elif 'protected' in modifiers:
                    visibility = Visibility.PROTECTED
                is_static = 'static' in modifiers
                is_abstract = 'abstract' in modifiers
                is_async = 'async' in modifiers
            
            method_info = MethodInfo(
                name=method_name,
                return_type=return_type.strip() if return_type else None,
                visibility=visibility,
                is_static=is_static,
                is_abstract=is_abstract,
                is_async=is_async,
                line_number=self._get_line_number(class_body, match.start())
            )
            
            methods.append(method_info)
        
        return methods
    
    def _extract_typescript_properties(self, class_body: str) -> List[AttributeInfo]:
        """Extract property definitions with TypeScript features."""
        properties = []
        
        for match in self.property_pattern.finditer(class_body):
            modifiers = match.group(1) if match.group(1) else ''
            prop_name = match.group(2)
            type_hint = match.group(3) if match.group(3) else None
            default_value = match.group(4) if match.group(4) else None
            
            # Parse modifiers
            visibility = Visibility.PUBLIC
            is_static = False
            
            if modifiers:
                if 'private' in modifiers:
                    visibility = Visibility.PRIVATE
                elif 'protected' in modifiers:
                    visibility = Visibility.PROTECTED
                is_static = 'static' in modifiers
            
            prop_info = AttributeInfo(
                name=prop_name,
                type_hint=type_hint.strip() if type_hint else None,
                default_value=default_value.strip() if default_value else None,
                visibility=visibility,
                is_static=is_static
            )
            
            properties.append(prop_info)
        
        return properties
    
    def _extract_typescript_functions(self, content: str) -> List[FunctionInfo]:
        """Extract function definitions with TypeScript features."""
        functions = []
        
        for pattern in self.ts_function_patterns:
            for match in pattern.finditer(content):
                func_name = match.group(1)
                params_str = match.group(2) if len(match.groups()) > 1 else ''
                return_type = match.group(3) if len(match.groups()) > 2 and match.group(3) else None
                
                # Skip if this is inside a class (simplified check)
                if self._is_inside_class(content, match.start()):
                    continue
                
                function_info = FunctionInfo(
                    name=func_name,
                    parameters=self._parse_typescript_parameters(params_str),
                    return_type=return_type.strip() if return_type else None,
                    is_async='async' in match.group(0),
                    line_number=self._get_line_number(content, match.start())
                )
                
                functions.append(function_info)
        
        return functions
    
    def _extract_interfaces(self, content: str) -> List[ClassInfo]:
        """Extract interface definitions as class-like structures."""
        interfaces = []
        
        for match in self.interface_pattern.finditer(content):
            interface_name = match.group(1)
            extends = match.group(2) if match.group(2) else None
            interface_body = match.group(3)
            
            interface_info = ClassInfo(
                name=interface_name,
                inheritance=[e.strip() for e in extends.split(',')] if extends else [],
                line_number=self._get_line_number(content, match.start())
            )
            
            # Extract interface members as methods/properties
            interface_info.methods = self._extract_interface_methods(interface_body)
            interface_info.attributes = self._extract_interface_properties(interface_body)
            
            interfaces.append(interface_info)
        
        return interfaces
    
    def _extract_interface_methods(self, interface_body: str) -> List[MethodInfo]:
        """Extract method signatures from interface body."""
        methods = []
        
        # Method signatures in interfaces: methodName(params): returnType;
        method_pattern = re.compile(r'(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^;]+))?\s*;?', re.MULTILINE)
        
        for match in method_pattern.finditer(interface_body):
            method_name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3) if match.group(3) else None
            
            method_info = MethodInfo(
                name=method_name,
                parameters=self._parse_typescript_parameters(params_str),
                return_type=return_type.strip() if return_type else None,
                is_abstract=True,  # Interface methods are abstract
                line_number=self._get_line_number(interface_body, match.start())
            )
            
            methods.append(method_info)
        
        return methods
    
    def _extract_interface_properties(self, interface_body: str) -> List[AttributeInfo]:
        """Extract property signatures from interface body."""
        properties = []
        
        # Property signatures in interfaces: propertyName: type;
        prop_pattern = re.compile(r'(\w+)(?:\?)?:\s*([^;]+);?', re.MULTILINE)
        
        for match in prop_pattern.finditer(interface_body):
            prop_name = match.group(1)
            type_hint = match.group(2)
            
            prop_info = AttributeInfo(
                name=prop_name,
                type_hint=type_hint.strip() if type_hint else None
            )
            
            properties.append(prop_info)
        
        return properties
    
    def _parse_typescript_parameters(self, params_str: str) -> List[ParameterInfo]:
        """Parse TypeScript function parameters with type annotations."""
        if not params_str.strip():
            return []
        
        parameters = []
        param_parts = [p.strip() for p in params_str.split(',')]
        
        for param in param_parts:
            if not param:
                continue
            
            # Handle TypeScript parameter patterns: name: type = default
            param_info = ParameterInfo(name=param)
            
            # Check for default value
            if '=' in param:
                param_part, default = param.split('=', 1)
                param_info.default_value = default.strip()
                param = param_part.strip()
            
            # Check for type annotation
            if ':' in param:
                name_part, type_part = param.split(':', 1)
                param_info.name = name_part.strip()
                param_info.type_hint = type_part.strip()
            else:
                param_info.name = param
            
            parameters.append(param_info)
        
        return parameters