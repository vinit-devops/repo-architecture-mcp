"""Data models for code structure representation."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class Visibility(Enum):
    """Visibility levels for class members."""
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"


class RelationType(Enum):
    """Types of relationships between code elements."""
    IMPORT = "import"
    INHERITANCE = "inheritance"
    COMPOSITION = "composition"
    AGGREGATION = "aggregation"
    DEPENDENCY = "dependency"


@dataclass
class AttributeInfo:
    """Information about a class attribute."""
    name: str
    type_hint: Optional[str] = None
    visibility: Visibility = Visibility.PUBLIC
    is_static: bool = False
    default_value: Optional[str] = None


@dataclass
class ParameterInfo:
    """Information about a function/method parameter."""
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    is_varargs: bool = False
    is_kwargs: bool = False


@dataclass
class MethodInfo:
    """Information about a class method."""
    name: str
    parameters: List[ParameterInfo] = field(default_factory=list)
    return_type: Optional[str] = None
    visibility: Visibility = Visibility.PUBLIC
    is_static: bool = False
    is_abstract: bool = False
    is_async: bool = False
    decorators: List[str] = field(default_factory=list)
    line_number: Optional[int] = None


@dataclass
class FunctionInfo:
    """Information about a standalone function."""
    name: str
    parameters: List[ParameterInfo] = field(default_factory=list)
    return_type: Optional[str] = None
    is_async: bool = False
    decorators: List[str] = field(default_factory=list)
    line_number: Optional[int] = None


@dataclass
class ClassInfo:
    """Information about a class definition."""
    name: str
    methods: List[MethodInfo] = field(default_factory=list)
    attributes: List[AttributeInfo] = field(default_factory=list)
    inheritance: List[str] = field(default_factory=list)
    interfaces: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    visibility: Visibility = Visibility.PUBLIC
    is_abstract: bool = False
    line_number: Optional[int] = None
    namespace: Optional[str] = None


@dataclass
class ImportInfo:
    """Information about an import statement."""
    module: str
    imported_names: List[str] = field(default_factory=list)
    alias: Optional[str] = None
    is_relative: bool = False
    line_number: Optional[int] = None


@dataclass
class ExportInfo:
    """Information about an export statement (for languages that support it)."""
    name: str
    is_default: bool = False
    line_number: Optional[int] = None


@dataclass
class CodeStructure:
    """Represents the parsed structure of a source code file."""
    file_path: str
    language: str
    classes: List[ClassInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)
    exports: List[ExportInfo] = field(default_factory=list)
    global_variables: List[AttributeInfo] = field(default_factory=list)
    namespace: Optional[str] = None
    encoding: str = "utf-8"
    parse_errors: List[str] = field(default_factory=list)


@dataclass
class DependencyRelation:
    """Represents a dependency relationship between code elements."""
    source: str
    target: str
    relation_type: RelationType
    strength: int = 1
    line_number: Optional[int] = None
    context: Optional[str] = None


@dataclass
class RepositoryStructure:
    """Represents the complete structure of a parsed repository."""
    repository_path: str
    files: List[CodeStructure] = field(default_factory=list)
    dependencies: List[DependencyRelation] = field(default_factory=list)
    language_stats: Dict[str, int] = field(default_factory=dict)
    total_files: int = 0
    total_lines: int = 0
    parse_errors: List[str] = field(default_factory=list)


@dataclass
class AnalysisConfig:
    """Configuration for code analysis and diagram generation."""
    # File filtering
    include_patterns: List[str] = field(default_factory=lambda: [
        "**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx",
        "**/*.java", "**/*.go", "**/*.rs", "**/*.cpp", "**/*.c",
        "**/*.h", "**/*.hpp", "**/*.cs", "**/*.php", "**/*.rb"
    ])
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "**/node_modules/**", "**/__pycache__/**", "**/venv/**",
        "**/env/**", "**/.git/**", "**/build/**", "**/dist/**",
        "**/target/**", "**/.pytest_cache/**", "**/.mypy_cache/**"
    ])
    
    # Analysis parameters
    max_depth: int = 10
    max_file_size_mb: int = 10
    include_external_deps: bool = True
    include_test_files: bool = False
    
    # Diagram generation
    diagram_layout: str = "hierarchical"  # hierarchical, circular, force-directed
    max_nodes: int = 100
    show_attributes: bool = True
    show_methods: bool = True
    show_private_members: bool = False
    
    # Performance settings
    parallel_processing: bool = True
    max_workers: int = 4
    cache_enabled: bool = True
    cache_ttl_hours: int = 24
    memory_limit_mb: int = 1024
    
    # GitHub settings
    github_token: Optional[str] = None
    clone_timeout_seconds: int = 300
    api_timeout_seconds: int = 30
    
    # Output settings
    output_format: str = "mermaid"  # mermaid, plantuml, svg, png
    output_directory: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            field.name: getattr(self, field.name)
            for field in self.__dataclass_fields__.values()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisConfig':
        """Create config from dictionary."""
        # Filter out unknown fields
        valid_fields = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)