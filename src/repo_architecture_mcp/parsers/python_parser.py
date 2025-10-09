"""Python AST parser for extracting code structure."""

import ast
from typing import List, Optional, Union, Any
import logging

from .base import CodeParser, ParseError
from ..models import (
    CodeStructure, ClassInfo, MethodInfo, FunctionInfo, 
    AttributeInfo, ParameterInfo, ImportInfo, Visibility
)


logger = logging.getLogger(__name__)


class PythonParser(CodeParser):
    """Parser for Python source code using the built-in AST module."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.py', '.pyw']
    
    @property
    def language_name(self) -> str:
        return 'python'
    
    async def parse_file(self, file_path: str, content: Optional[str] = None) -> CodeStructure:
        """Parse a Python source file and extract its structure."""
        try:
            if content is None:
                content = self._read_file_content(file_path)
            
            # Parse the AST
            tree = ast.parse(content, filename=file_path)
            
            # Create base structure
            structure = self._create_base_structure(file_path, content)
            
            # Extract information from AST
            visitor = PythonASTVisitor()
            visitor.visit(tree)
            
            # Populate structure
            structure.classes = visitor.classes
            structure.functions = visitor.functions
            structure.imports = visitor.imports
            structure.global_variables = visitor.global_variables
            
            return structure
            
        except SyntaxError as e:
            return self._handle_parse_error(e, file_path, e.lineno)
        except Exception as e:
            return self._handle_parse_error(e, file_path)


class PythonASTVisitor(ast.NodeVisitor):
    """AST visitor for extracting Python code structure."""
    
    def __init__(self):
        self.classes: List[ClassInfo] = []
        self.functions: List[FunctionInfo] = []
        self.imports: List[ImportInfo] = []
        self.global_variables: List[AttributeInfo] = []
        self._current_class: Optional[ClassInfo] = None
        self._class_stack: List[ClassInfo] = []
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class definition."""
        class_info = ClassInfo(
            name=node.name,
            line_number=node.lineno,
            decorators=[self._get_decorator_name(d) for d in node.decorator_list],
            inheritance=[self._get_base_name(base) for base in node.bases],
            is_abstract=self._is_abstract_class(node)
        )
        
        # Save current class context
        parent_class = self._current_class
        self._current_class = class_info
        self._class_stack.append(class_info)
        
        # Visit class body
        for child in node.body:
            self.visit(child)
        
        # Restore context
        self._class_stack.pop()
        self._current_class = parent_class
        
        # Add to appropriate collection
        if parent_class:
            # Nested class - add as method for now (could be improved)
            parent_class.methods.append(MethodInfo(
                name=f"class {class_info.name}",
                line_number=class_info.line_number
            ))
        else:
            self.classes.append(class_info)
    
    def visit_FunctionDef(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
        """Visit a function definition."""
        is_async = isinstance(node, ast.AsyncFunctionDef)
        
        # Extract parameters
        parameters = self._extract_parameters(node.args)
        
        # Extract return type annotation
        return_type = None
        if hasattr(node, 'returns') and node.returns:
            return_type = self._get_annotation_string(node.returns)
        
        # Extract decorators
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        
        if self._current_class:
            # This is a method
            visibility = self._get_method_visibility(node.name)
            is_static = any(d in ['staticmethod', 'classmethod'] for d in decorators)
            is_abstract = 'abstractmethod' in decorators
            
            method_info = MethodInfo(
                name=node.name,
                parameters=parameters,
                return_type=return_type,
                visibility=visibility,
                is_static=is_static,
                is_abstract=is_abstract,
                is_async=is_async,
                decorators=decorators,
                line_number=node.lineno
            )
            
            self._current_class.methods.append(method_info)
        else:
            # This is a standalone function
            function_info = FunctionInfo(
                name=node.name,
                parameters=parameters,
                return_type=return_type,
                is_async=is_async,
                decorators=decorators,
                line_number=node.lineno
            )
            
            self.functions.append(function_info)
        
        # Don't visit function body to avoid nested functions for now
    
    def visit_Import(self, node: ast.Import) -> None:
        """Visit an import statement."""
        for alias in node.names:
            import_info = ImportInfo(
                module=alias.name,
                alias=alias.asname,
                line_number=node.lineno
            )
            self.imports.append(import_info)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit a from...import statement."""
        if node.module is None:
            return  # Skip relative imports without module
        
        imported_names = []
        for alias in node.names:
            imported_names.append(alias.name)
        
        import_info = ImportInfo(
            module=node.module,
            imported_names=imported_names,
            is_relative=node.level > 0,
            line_number=node.lineno
        )
        self.imports.append(import_info)
    
    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit an assignment statement to extract global variables and class attributes."""
        if self._current_class:
            # This might be a class attribute
            for target in node.targets:
                if isinstance(target, ast.Name):
                    attr_info = AttributeInfo(
                        name=target.id,
                        visibility=self._get_attribute_visibility(target.id),
                        default_value=self._get_value_string(node.value)
                    )
                    self._current_class.attributes.append(attr_info)
        elif not self._is_inside_function(node):
            # This is a global variable
            for target in node.targets:
                if isinstance(target, ast.Name):
                    attr_info = AttributeInfo(
                        name=target.id,
                        default_value=self._get_value_string(node.value)
                    )
                    self.global_variables.append(attr_info)
    
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Visit an annotated assignment statement."""
        if isinstance(node.target, ast.Name):
            type_hint = self._get_annotation_string(node.annotation)
            default_value = None
            if node.value:
                default_value = self._get_value_string(node.value)
            
            attr_info = AttributeInfo(
                name=node.target.id,
                type_hint=type_hint,
                default_value=default_value,
                visibility=self._get_attribute_visibility(node.target.id) if self._current_class else Visibility.PUBLIC
            )
            
            if self._current_class:
                self._current_class.attributes.append(attr_info)
            elif not self._is_inside_function(node):
                self.global_variables.append(attr_info)
    
    def _extract_parameters(self, args: ast.arguments) -> List[ParameterInfo]:
        """Extract parameter information from function arguments."""
        parameters = []
        
        # Regular arguments
        for i, arg in enumerate(args.args):
            # Skip 'self' and 'cls' parameters
            if i == 0 and arg.arg in ['self', 'cls']:
                continue
                
            param_info = ParameterInfo(
                name=arg.arg,
                type_hint=self._get_annotation_string(arg.annotation) if arg.annotation else None
            )
            
            # Check for default values
            defaults_offset = len(args.args) - len(args.defaults)
            if i >= defaults_offset:
                default_index = i - defaults_offset
                param_info.default_value = self._get_value_string(args.defaults[default_index])
            
            parameters.append(param_info)
        
        # *args parameter
        if args.vararg:
            param_info = ParameterInfo(
                name=args.vararg.arg,
                type_hint=self._get_annotation_string(args.vararg.annotation) if args.vararg.annotation else None,
                is_varargs=True
            )
            parameters.append(param_info)
        
        # **kwargs parameter
        if args.kwarg:
            param_info = ParameterInfo(
                name=args.kwarg.arg,
                type_hint=self._get_annotation_string(args.kwarg.annotation) if args.kwarg.annotation else None,
                is_kwargs=True
            )
            parameters.append(param_info)
        
        return parameters
    
    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """Extract decorator name from AST node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{self._get_attribute_chain(decorator)}"
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return self._get_attribute_chain(decorator.func)
        return str(decorator)
    
    def _get_base_name(self, base: ast.expr) -> str:
        """Extract base class name from AST node."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return self._get_attribute_chain(base)
        return str(base)
    
    def _get_attribute_chain(self, node: ast.Attribute) -> str:
        """Get the full attribute chain (e.g., 'module.Class')."""
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        elif isinstance(node.value, ast.Attribute):
            return f"{self._get_attribute_chain(node.value)}.{node.attr}"
        return node.attr
    
    def _get_annotation_string(self, annotation: ast.expr) -> str:
        """Convert type annotation to string."""
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Attribute):
            return self._get_attribute_chain(annotation)
        elif isinstance(annotation, ast.Constant):
            return repr(annotation.value)
        elif isinstance(annotation, ast.Subscript):
            # Handle generic types like List[str]
            value = self._get_annotation_string(annotation.value)
            slice_val = self._get_annotation_string(annotation.slice)
            return f"{value}[{slice_val}]"
        return str(annotation)
    
    def _get_value_string(self, value: ast.expr) -> str:
        """Convert value node to string representation."""
        if isinstance(value, ast.Constant):
            return repr(value.value)
        elif isinstance(value, ast.Name):
            return value.id
        elif isinstance(value, ast.Attribute):
            return self._get_attribute_chain(value)
        return str(value)
    
    def _get_method_visibility(self, name: str) -> Visibility:
        """Determine method visibility based on naming convention."""
        if name.startswith('__') and not name.endswith('__'):
            return Visibility.PRIVATE
        elif name.startswith('_'):
            return Visibility.PROTECTED
        return Visibility.PUBLIC
    
    def _get_attribute_visibility(self, name: str) -> Visibility:
        """Determine attribute visibility based on naming convention."""
        if name.startswith('__') and not name.endswith('__'):
            return Visibility.PRIVATE
        elif name.startswith('_'):
            return Visibility.PROTECTED
        return Visibility.PUBLIC
    
    def _is_abstract_class(self, node: ast.ClassDef) -> bool:
        """Check if a class is abstract (has ABC as base or abstractmethod decorators)."""
        # Check if inherits from ABC
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in ['ABC', 'AbstractBase']:
                return True
            elif isinstance(base, ast.Attribute) and base.attr in ['ABC', 'AbstractBase']:
                return True
        
        # Check if has abstract methods
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in child.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == 'abstractmethod':
                        return True
                    elif isinstance(decorator, ast.Attribute) and decorator.attr == 'abstractmethod':
                        return True
        
        return False
    
    def _is_inside_function(self, node: ast.AST) -> bool:
        """Check if we're currently inside a function (simplified check)."""
        # This is a simplified implementation
        # In a more complete version, we'd track the AST context stack
        return False