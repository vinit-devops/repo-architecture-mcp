"""Repository Architecture MCP Server

An MCP server for analyzing GitHub repositories and generating architectural diagrams.
"""

__version__ = "0.1.0"

# Import main components
from .server import RepoArchitectureMCPServer
from .repository_manager import RepositoryManager
from .architecture_analyzer import ArchitectureAnalyzer
from .diagram_generator import DiagramGenerator

# Import performance optimization components
from .cache_manager import CacheManager
from .parallel_processor import ParallelProcessor, ProgressTracker
from .memory_manager import MemoryMonitor, StreamingProcessor, StreamingConfig
from .performance_optimizer import PerformanceOptimizer

# Import data models
from .models import (
    CodeStructure, RepositoryStructure, ClassInfo, MethodInfo, 
    FunctionInfo, ImportInfo, DependencyRelation
)

__all__ = [
    # Main components
    "RepoArchitectureMCPServer",
    "RepositoryManager", 
    "ArchitectureAnalyzer",
    "DiagramGenerator",
    
    # Performance optimization
    "CacheManager",
    "ParallelProcessor",
    "ProgressTracker", 
    "MemoryMonitor",
    "StreamingProcessor",
    "StreamingConfig",
    "PerformanceOptimizer",
    
    # Data models
    "CodeStructure",
    "RepositoryStructure", 
    "ClassInfo",
    "MethodInfo",
    "FunctionInfo", 
    "ImportInfo",
    "DependencyRelation"
]