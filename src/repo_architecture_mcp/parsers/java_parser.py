"""Java parser for extracting code structure."""

import re
from typing import List, Optional, Dict, Any, Match
import logging

from .base import CodeParser, ParseError
from ..models import (
    CodeStructure, ClassInfo, MethodInfo, FunctionInfo, 
    AttributeInfo, ParameterInfo, ImportInfo, Visibility
)


logger = logging.getLogger(__name__)


class JavaParser(CodeParser):
    """Parser for Java source code using regex patterns."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.java']
    
    @property
    def language_name(self) -> str:
        return 'java'
    
    def __init__(self):
        super().__init__()
        self._setup_patterns()
    
    def _setup_patterns(self):
        """Set up regex patterns for parsing Java code."""
        # Package pattern
        self.package_pattern = re.compile(r'package\s+([\w.]+)\s*;', re.MULTILINE)
        
        # Import patterns
        self.import_pattern = re.compile(r'import\s+(?:static\s+)?([\w.*]+)\s*;', re.MULTILINE)
        
        # Class patterns
        self.class_pattern = re.compile(
            r'(?:(public|private|protected|abstract|final)\s+)*'
            r'(class|interface|enum)\s+(\w+)'
            r'(?:\s+extends\s+([\w<>,\s]+))?'
            r'(?:\s+implements\s+([\w<>,\s]+))?'
            r'\s*\{',
            re.MULTILINE
        )
        
        # Method patterns
        self.method_pattern = re.compile(
            r'(?:(public|private|protected|static|abstract|final|synchronized|native)\s+)*'
            r'(?:(<[^>]+>)\s+)?'  # Generic type parameters
            r'([\w<>\[\]]+)\s+'   # Return type
            r'(\w+)\s*'           # Method name
            r'\(([^)]*)\)'        # Parameters
            r'(?:\s+throws\s+([\w,\s]+))?'  # Throws clause
            r'\s*[{;]',           # Body start or semicolon for abstract
            re.MULTILINE
        )
        
        # Field patterns
        self.field_pattern = re.compile(
            r'(?:(public|private|protected|static|final|volatile|transient)\s+)*'
            r'([\w<>\[\]]+)\s+'   # Type
            r'(\w+)'              # Name
            r'(?:\s*=\s*([^;]+))?'  # Optional initializer
            r'\s*;',
            re.MULTILINE
        )
        
        # Constructor patterns
        self.constructor_pattern = re.compile(
            r'(?:(public|private|protected)\s+)?'
            r'(\w+)\s*'           # Constructor name (same as class)
            r'\(([^)]*)\)'        # Parameters
            r'(?:\s+throws\s+([\w,\s]+))?'  # Throws clause
            r'\s*\{',
            re.MULTILINE
        )
    
    async def parse_file(self, file_path: str, content: Optional[str] = None) -> CodeStructure:
        """Parse a Java source file and extract its structure."""
        try:
            if content is None:
                content = self._read_file_content(file_path)
            
            # Create base structure
            structure = self._create_base_structure(file_path, content)
            
            # Remove comments to avoid false matches
            cleaned_content = self._remove_comments(content)
            
            # Extract package information
            structure.namespace = self._extract_package(cleaned_content)
            
            # Extract different code elements
            structure.imports = self._extract_imports(cleaned_content)
            structure.classes = self._extract_classes(cleaned_content)
            
            return structure
            
        except Exception as e:
            return self._handle_parse_error(e, file_path)
    
    def _remove_comments(self, content: str) -> str:
        """Remove Java comments from content."""
        # Remove single-line comments
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        # Remove multi-line comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        # Remove Javadoc comments
        content = re.sub(r'/\*\*.*?\*/', '', content, flags=re.DOTALL)
        return content
    
    def _extract_package(self, content: str) -> Optional[str]:
        """Extract package declaration from Java code."""
        match = self.package_pattern.search(content)
        return match.group(1) if match else None
    
    def _extract_imports(self, content: str) -> List[ImportInfo]:
        """Extract import statements from Java code."""
        imports = []
        
        for match in self.import_pattern.finditer(content):
            import_path = match.group(1)
            
            # Check if it's a static import
            is_static = 'static' in match.group(0)
            
            # Extract the imported name
            if import_path.endswith('.*'):
                # Wildcard import
                module = import_path[:-2]
                imported_names = ['*']
            else:
                # Specific import
                parts = import_path.split('.')
                if is_static:
                    # Static import: package.Class.method
                    module = '.'.join(parts[:-1])
                    imported_names = [parts[-1]]
                else:
                    # Regular import: package.Class
                    module = '.'.join(parts[:-1]) if len(parts) > 1 else import_path
                    imported_names = [parts[-1]] if len(parts) > 1 else []
            
            imports.append(ImportInfo(
                module=module,
                imported_names=imported_names,
                line_number=self._get_line_number(content, match.start())
            ))
        
        return imports
    
    def _extract_classes(self, content: str) -> List[ClassInfo]:
        """Extract class, interface, and enum definitions from Java code."""
        classes = []
        
        for match in self.class_pattern.finditer(content):
            modifiers = match.group(1) if match.group(1) else ''
            class_type = match.group(2)  # class, interface, or enum
            class_name = match.group(3)
            extends = match.group(4) if match.group(4) else None
            implements = match.group(5) if match.group(5) else None
            
            # Determine visibility
            visibility = Visibility.PUBLIC if 'public' in modifiers else Visibility.PRIVATE
            if 'protected' in modifiers:
                visibility = Visibility.PROTECTED
            
            # Create class info
            class_info = ClassInfo(
                name=class_name,
                visibility=visibility,
                is_abstract='abstract' in modifiers or class_type == 'interface',
                inheritance=[extends.strip()] if extends else [],
                interfaces=[i.strip() for i in implements.split(',')] if implements else [],
                line_number=self._get_line_number(content, match.start())
            )
            
            # Find the class body
            class_body = self._extract_class_body(content, match.end())
            if class_body:
                # Extract methods and fields from class body
                class_info.methods = self._extract_methods(class_body, class_name)
                class_info.attributes = self._extract_fields(class_body)
            
            classes.append(class_info)
        
        return classes
    
    def _extract_class_body(self, content: str, start_pos: int) -> Optional[str]:
        """Extract the body of a class from the opening brace to the closing brace."""
        # Find the opening brace
        brace_pos = content.find('{', start_pos - 50)  # Look back a bit for the brace
        if brace_pos == -1:
            return None
        
        # Count braces to find the matching closing brace
        brace_count = 0
        pos = brace_pos
        
        while pos < len(content):
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    return content[brace_pos + 1:pos]
            pos += 1
        
        return None
    
    def _extract_methods(self, class_body: str, class_name: str) -> List[MethodInfo]:
        """Extract method definitions from class body."""
        methods = []
        
        # Extract regular methods
        for match in self.method_pattern.finditer(class_body):
            modifiers = match.group(1) if match.group(1) else ''
            generic_params = match.group(2) if match.group(2) else None
            return_type = match.group(3)
            method_name = match.group(4)
            params_str = match.group(5)
            throws_clause = match.group(6) if match.group(6) else None
            
            # Skip if this looks like a field declaration
            if ';' in match.group(0) and 'abstract' not in modifiers:
                continue
            
            # Parse visibility and other modifiers
            visibility = self._parse_visibility(modifiers)
            is_static = 'static' in modifiers
            is_abstract = 'abstract' in modifiers
            
            method_info = MethodInfo(
                name=method_name,
                parameters=self._parse_parameters(params_str),
                return_type=return_type,
                visibility=visibility,
                is_static=is_static,
                is_abstract=is_abstract,
                line_number=self._get_line_number(class_body, match.start())
            )
            
            methods.append(method_info)
        
        # Extract constructors
        for match in self.constructor_pattern.finditer(class_body):
            modifiers = match.group(1) if match.group(1) else ''
            constructor_name = match.group(2)
            params_str = match.group(3)
            throws_clause = match.group(4) if match.group(4) else None
            
            # Only include if constructor name matches class name
            if constructor_name == class_name:
                visibility = self._parse_visibility(modifiers)
                
                constructor_info = MethodInfo(
                    name=constructor_name,
                    parameters=self._parse_parameters(params_str),
                    return_type=None,  # Constructors don't have return types
                    visibility=visibility,
                    line_number=self._get_line_number(class_body, match.start())
                )
                
                methods.append(constructor_info)
        
        return methods
    
    def _extract_fields(self, class_body: str) -> List[AttributeInfo]:
        """Extract field definitions from class body."""
        fields = []
        
        for match in self.field_pattern.finditer(class_body):
            modifiers = match.group(1) if match.group(1) else ''
            field_type = match.group(2)
            field_name = match.group(3)
            initializer = match.group(4) if match.group(4) else None
            
            # Parse visibility and other modifiers
            visibility = self._parse_visibility(modifiers)
            is_static = 'static' in modifiers
            
            field_info = AttributeInfo(
                name=field_name,
                type_hint=field_type,
                default_value=initializer.strip() if initializer else None,
                visibility=visibility,
                is_static=is_static
            )
            
            fields.append(field_info)
        
        return fields
    
    def _parse_parameters(self, params_str: str) -> List[ParameterInfo]:
        """Parse Java method parameters."""
        if not params_str.strip():
            return []
        
        parameters = []
        
        # Split parameters, handling generic types
        param_parts = self._split_parameters(params_str)
        
        for param in param_parts:
            param = param.strip()
            if not param:
                continue
            
            # Handle final modifier
            if param.startswith('final '):
                param = param[6:].strip()
            
            # Split type and name
            parts = param.split()
            if len(parts) >= 2:
                param_type = ' '.join(parts[:-1])  # Handle generic types with spaces
                param_name = parts[-1]
                
                parameters.append(ParameterInfo(
                    name=param_name,
                    type_hint=param_type
                ))
        
        return parameters
    
    def _split_parameters(self, params_str: str) -> List[str]:
        """Split parameter string, handling generic types correctly."""
        parameters = []
        current_param = ''
        angle_bracket_count = 0
        
        for char in params_str:
            if char == '<':
                angle_bracket_count += 1
            elif char == '>':
                angle_bracket_count -= 1
            elif char == ',' and angle_bracket_count == 0:
                parameters.append(current_param.strip())
                current_param = ''
                continue
            
            current_param += char
        
        if current_param.strip():
            parameters.append(current_param.strip())
        
        return parameters
    
    def _parse_visibility(self, modifiers: str) -> Visibility:
        """Parse visibility from modifiers string."""
        if 'public' in modifiers:
            return Visibility.PUBLIC
        elif 'private' in modifiers:
            return Visibility.PRIVATE
        elif 'protected' in modifiers:
            return Visibility.PROTECTED
        else:
            return Visibility.PUBLIC  # Package-private, treat as public for simplicity
    
    def _get_line_number(self, content: str, position: int) -> int:
        """Get line number for a given position in content."""
        return content[:position].count('\n') + 1