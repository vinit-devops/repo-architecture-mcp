"""JavaScript parser for extracting code structure."""

import re
from typing import List, Optional, Dict, Any, Match
import logging

from .base import CodeParser, ParseError
from ..models import (
    CodeStructure, ClassInfo, MethodInfo, FunctionInfo, 
    AttributeInfo, ParameterInfo, ImportInfo, ExportInfo, Visibility
)


logger = logging.getLogger(__name__)


class JavaScriptParser(CodeParser):
    """Parser for JavaScript source code using regex patterns."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.js', '.jsx', '.mjs']
    
    @property
    def language_name(self) -> str:
        return 'javascript'
    
    def __init__(self):
        super().__init__()
        self._setup_patterns()
    
    def _setup_patterns(self):
        """Set up regex patterns for parsing JavaScript code."""
        # Import patterns
        self.import_patterns = [
            # import { name1, name2 } from 'module'
            re.compile(r'import\s*\{\s*([^}]+)\s*\}\s*from\s*[\'"]([^\'"]+)[\'"]', re.MULTILINE),
            # import name from 'module'
            re.compile(r'import\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE),
            # import * as name from 'module'
            re.compile(r'import\s*\*\s*as\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE),
            # import 'module'
            re.compile(r'import\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE),
        ]
        
        # Export patterns
        self.export_patterns = [
            # export { name1, name2 }
            re.compile(r'export\s*\{\s*([^}]+)\s*\}', re.MULTILINE),
            # export default name
            re.compile(r'export\s+default\s+(\w+)', re.MULTILINE),
            # export const/let/var name
            re.compile(r'export\s+(?:const|let|var)\s+(\w+)', re.MULTILINE),
            # export function name
            re.compile(r'export\s+function\s+(\w+)', re.MULTILINE),
            # export class name
            re.compile(r'export\s+class\s+(\w+)', re.MULTILINE),
        ]
        
        # Class patterns
        self.class_pattern = re.compile(
            r'class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        # Method patterns (inside classes)
        self.method_pattern = re.compile(
            r'(?:(static|async)\s+)?(\w+)\s*\([^)]*\)\s*\{',
            re.MULTILINE
        )
        
        # Function patterns
        self.function_patterns = [
            # function name(params) { }
            re.compile(r'(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*\{', re.MULTILINE),
            # const name = function(params) { }
            re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function\s*\(([^)]*)\)\s*\{', re.MULTILINE),
            # const name = (params) => { }
            re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>\s*\{', re.MULTILINE),
            # const name = param => { }
            re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(\w+)\s*=>\s*\{', re.MULTILINE),
        ]
        
        # Variable patterns
        self.variable_pattern = re.compile(
            r'(?:const|let|var)\s+(\w+)(?:\s*=\s*([^;,\n]+))?',
            re.MULTILINE
        )
    
    async def parse_file(self, file_path: str, content: Optional[str] = None) -> CodeStructure:
        """Parse a JavaScript source file and extract its structure."""
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
            structure.classes = self._extract_classes(cleaned_content)
            structure.functions = self._extract_functions(cleaned_content)
            structure.global_variables = self._extract_global_variables(cleaned_content)
            
            return structure
            
        except Exception as e:
            return self._handle_parse_error(e, file_path)
    
    def _remove_comments(self, content: str) -> str:
        """Remove JavaScript comments from content."""
        # Remove single-line comments
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        # Remove multi-line comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        return content
    
    def _extract_imports(self, content: str) -> List[ImportInfo]:
        """Extract import statements from JavaScript code."""
        imports = []
        
        for pattern in self.import_patterns:
            for match in pattern.finditer(content):
                if len(match.groups()) == 2:
                    # Named imports or default import
                    names_or_default = match.group(1)
                    module = match.group(2)
                    
                    if '{' in names_or_default or '}' in names_or_default:
                        # Named imports
                        names = [name.strip() for name in names_or_default.split(',')]
                        imports.append(ImportInfo(
                            module=module,
                            imported_names=names,
                            line_number=self._get_line_number(content, match.start())
                        ))
                    else:
                        # Default import or namespace import
                        imports.append(ImportInfo(
                            module=module,
                            alias=names_or_default,
                            line_number=self._get_line_number(content, match.start())
                        ))
                elif len(match.groups()) == 1:
                    # Side-effect import
                    module = match.group(1)
                    imports.append(ImportInfo(
                        module=module,
                        line_number=self._get_line_number(content, match.start())
                    ))
        
        return imports
    
    def _extract_exports(self, content: str) -> List[ExportInfo]:
        """Extract export statements from JavaScript code."""
        exports = []
        
        for pattern in self.export_patterns:
            for match in pattern.finditer(content):
                name = match.group(1)
                is_default = 'default' in match.group(0)
                
                if '{' in name and '}' in name:
                    # Named exports
                    names = [n.strip() for n in name.replace('{', '').replace('}', '').split(',')]
                    for n in names:
                        exports.append(ExportInfo(
                            name=n,
                            is_default=False,
                            line_number=self._get_line_number(content, match.start())
                        ))
                else:
                    exports.append(ExportInfo(
                        name=name,
                        is_default=is_default,
                        line_number=self._get_line_number(content, match.start())
                    ))
        
        return exports
    
    def _extract_classes(self, content: str) -> List[ClassInfo]:
        """Extract class definitions from JavaScript code."""
        classes = []
        
        for match in self.class_pattern.finditer(content):
            class_name = match.group(1)
            parent_class = match.group(2) if match.group(2) else None
            class_body = match.group(3)
            
            class_info = ClassInfo(
                name=class_name,
                inheritance=[parent_class] if parent_class else [],
                line_number=self._get_line_number(content, match.start())
            )
            
            # Extract methods from class body
            class_info.methods = self._extract_methods(class_body)
            
            classes.append(class_info)
        
        return classes
    
    def _extract_methods(self, class_body: str) -> List[MethodInfo]:
        """Extract method definitions from class body."""
        methods = []
        
        for match in self.method_pattern.finditer(class_body):
            modifier = match.group(1)  # static or async
            method_name = match.group(2)
            
            # Skip constructor
            if method_name == 'constructor':
                continue
            
            method_info = MethodInfo(
                name=method_name,
                is_static=modifier == 'static',
                is_async=modifier == 'async',
                visibility=self._get_visibility(method_name),
                line_number=self._get_line_number(class_body, match.start())
            )
            
            methods.append(method_info)
        
        return methods
    
    def _extract_functions(self, content: str) -> List[FunctionInfo]:
        """Extract function definitions from JavaScript code."""
        functions = []
        
        for pattern in self.function_patterns:
            for match in pattern.finditer(content):
                func_name = match.group(1)
                params_str = match.group(2) if len(match.groups()) > 1 else ''
                
                # Skip if this is inside a class (simplified check)
                if self._is_inside_class(content, match.start()):
                    continue
                
                function_info = FunctionInfo(
                    name=func_name,
                    parameters=self._parse_parameters(params_str),
                    is_async='async' in match.group(0),
                    line_number=self._get_line_number(content, match.start())
                )
                
                functions.append(function_info)
        
        return functions
    
    def _extract_global_variables(self, content: str) -> List[AttributeInfo]:
        """Extract global variable declarations."""
        variables = []
        
        for match in self.variable_pattern.finditer(content):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) else None
            
            # Skip if this is inside a function or class (simplified check)
            if self._is_inside_function_or_class(content, match.start()):
                continue
            
            variable_info = AttributeInfo(
                name=var_name,
                default_value=default_value.strip() if default_value else None,
                visibility=self._get_visibility(var_name)
            )
            
            variables.append(variable_info)
        
        return variables
    
    def _parse_parameters(self, params_str: str) -> List[ParameterInfo]:
        """Parse function parameters from parameter string."""
        if not params_str.strip():
            return []
        
        parameters = []
        param_parts = [p.strip() for p in params_str.split(',')]
        
        for param in param_parts:
            if not param:
                continue
            
            # Handle default values
            if '=' in param:
                name, default = param.split('=', 1)
                parameters.append(ParameterInfo(
                    name=name.strip(),
                    default_value=default.strip()
                ))
            else:
                parameters.append(ParameterInfo(name=param))
        
        return parameters
    
    def _get_visibility(self, name: str) -> Visibility:
        """Determine visibility based on naming convention."""
        if name.startswith('_'):
            return Visibility.PRIVATE
        return Visibility.PUBLIC
    
    def _get_line_number(self, content: str, position: int) -> int:
        """Get line number for a given position in content."""
        return content[:position].count('\n') + 1
    
    def _is_inside_class(self, content: str, position: int) -> bool:
        """Check if position is inside a class definition (simplified)."""
        # This is a simplified implementation
        # Count class keywords before this position
        before_content = content[:position]
        class_count = len(re.findall(r'\bclass\s+\w+', before_content))
        
        # Count closing braces that might end classes
        # This is very simplified and may not be accurate in all cases
        return class_count > 0
    
    def _is_inside_function_or_class(self, content: str, position: int) -> bool:
        """Check if position is inside a function or class (simplified)."""
        # This is a very simplified implementation
        before_content = content[:position]
        
        # Count function and class keywords
        func_count = len(re.findall(r'\b(?:function|class)\s+\w+', before_content))
        
        return func_count > 0