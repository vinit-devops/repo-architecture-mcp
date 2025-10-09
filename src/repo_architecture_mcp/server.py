"""Core MCP server implementation for repository architecture analysis."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from mcp.server import FastMCP

from .errors import (
    MCPError,
    ValidationError,
    AuthenticationError,
    RepositoryError,
    RepositoryNotFoundError,
    RepositoryAccessError,
    ParsingError,
    AnalysisError,
    DiagramGenerationError,
    NetworkError,
    ErrorHandler,
    handle_async_exception
)
from .logging_config import StructuredLogger


logger = StructuredLogger(__name__)


class RepoArchitectureMCPServer:
    """Main MCP server class implementing the protocol for repository analysis."""
    
    def __init__(self, config: Optional['AnalysisConfig'] = None) -> None:
        """Initialize the MCP server with tool registration.
        
        Args:
            config: Optional configuration for the server
        """
        from .models import AnalysisConfig
        
        self.server = FastMCP("Repository Architecture MCP Server")
        self.config = config or AnalysisConfig()
        self._register_tools()
        
    def _handle_tool_errors(self, func):
        """Decorator to handle errors in MCP tool functions and return appropriate responses."""
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except MCPError as e:
                logger.warning("MCP tool error", function=func.__name__, error_code=e.code.value, error_message=e.message)
                return e.to_dict()
            except Exception as e:
                logger.error("Unexpected error in MCP tool", function=func.__name__, error=str(e))
                from .errors import ErrorCode
                mcp_error = MCPError(
                    message=f"Unexpected error in {func.__name__}: {str(e)}",
                    code=ErrorCode.INTERNAL_ERROR,
                    cause=e
                )
                return mcp_error.to_dict()
        return wrapper
    
    def _calculate_complexity_score(self, total_classes: int, total_functions: int, total_methods: int, parsed_files: int) -> float:
        """Calculate a complexity score for the repository."""
        if parsed_files == 0:
            return 0.0
        
        # Simple complexity scoring algorithm
        class_complexity = total_classes * 2
        function_complexity = total_functions * 1.5
        method_complexity = total_methods * 1
        file_complexity = parsed_files * 0.5
        
        total_complexity = class_complexity + function_complexity + method_complexity + file_complexity
        return round(total_complexity / parsed_files, 2)
    
    def _get_largest_files(self, files: list) -> list:
        """Get the largest files by size."""
        sorted_files = sorted(files, key=lambda f: f.get('size', 0), reverse=True)
        return [
            {
                'path': f['path'],
                'size': f['size'],
                'language': f['language']
            }
            for f in sorted_files[:5]  # Top 5 largest files
        ]
    
    def get_available_tools(self) -> List[str]:
        """Get list of available MCP tools."""
        return [
            "analyze_repository",
            "generate_dependency_diagram", 
            "generate_class_diagram",
            "generate_data_flow_diagram",
            "get_repository_summary"
        ]
    
    async def run(self, transport_type: str = "stdio") -> None:
        """Run the MCP server."""
        if transport_type == "stdio":
            await self.server.run_stdio_async()
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")
    
    async def cleanup(self) -> None:
        """Perform cleanup operations before server shutdown."""
        logger.info("Performing server cleanup...")
        
        try:
            # Clean up any temporary files or resources
            # This could include clearing caches, closing connections, etc.
            
            # For now, just log that cleanup is complete
            logger.info("Server cleanup completed successfully")
            
        except Exception as e:
            logger.error(f"Error during server cleanup: {e}")
            raise
        
    def _register_tools(self) -> None:
        """Register all available MCP tools."""
        
        @self._handle_tool_errors
        async def analyze_repository(url: str, token: Optional[str] = None) -> Dict[str, Any]:
            """Analyze a GitHub repository structure.
            
            Args:
                url: GitHub repository URL
                token: Optional GitHub authentication token
                
            Returns:
                Repository analysis results as structured JSON
            """
            from .repository_manager import RepositoryManager
            from .parsers import CodeParserFactory
            from .models import RepositoryStructure
            from datetime import datetime
            
            # Validate inputs
            ErrorHandler.validate_repository_path(url)
            
            # Normalize URL if it's a GitHub URL
            if url.startswith('github.com/'):
                url = f"https://{url}"
                
            logger.info("Starting repository analysis", repository_url=url)
            
            # Initialize repository manager
            async with RepositoryManager(github_token=token) as repo_manager:
                # Authenticate if token provided
                if token:
                    await repo_manager.authenticate(token)
                
                # Get comprehensive repository information
                repo_info = await repo_manager.get_repository_info(url)
                
                # Initialize parser factory
                parser_factory = CodeParserFactory()
                
                # Parse repository structure
                repo_structure = RepositoryStructure(
                    repository_path=repo_info['analysis_path']
                )
                
                # Parse each source file with graceful error handling
                parsed_files = 0
                total_lines = 0
                language_stats = {}
                parsing_errors = []
                
                for file_info in repo_info['file_tree']['files']:
                    try:
                        file_path = file_info['absolute_path']
                        language = file_info['language']
                        
                        # Get appropriate parser
                        parser = parser_factory.registry.get_parser(file_path)
                        if parser:
                            # Parse the file
                            code_structure = await parser.parse_file(file_path)
                            repo_structure.files.append(code_structure)
                            parsed_files += 1
                            
                            # Update language statistics
                            if language not in language_stats:
                                language_stats[language] = 0
                            language_stats[language] += 1
                            
                            # Estimate lines of code (simplified)
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    file_lines = sum(1 for line in f if line.strip())
                                    total_lines += file_lines
                            except Exception:
                                pass  # Skip line counting if file can't be read
                                
                    except Exception as e:
                        error_msg = f"Failed to parse {file_info['path']}: {str(e)}"
                        parsing_errors.append(error_msg)
                        repo_structure.parse_errors.append(error_msg)
                        logger.warning("File parsing failed", file_path=file_info['path'], error=str(e))
                    
                    # Update repository structure metadata
                    repo_structure.total_files = parsed_files
                    repo_structure.total_lines = total_lines
                    repo_structure.language_stats = language_stats
                    
                    # Calculate complexity metrics
                    total_classes = sum(len(file_struct.classes) for file_struct in repo_structure.files)
                    total_functions = sum(len(file_struct.functions) for file_struct in repo_structure.files)
                    total_methods = sum(
                        sum(len(cls.methods) for cls in file_struct.classes) 
                        for file_struct in repo_structure.files
                    )
                    
                    # Build analysis summary
                    analysis_result = {
                        "repository_info": {
                            "url": url,
                            "name": repo_info.get('name', ''),
                            "full_name": repo_info.get('full_name', ''),
                            "description": repo_info.get('description', ''),
                            "private": repo_info.get('private', False),
                            "default_branch": repo_info.get('default_branch', 'main'),
                            "size_kb": repo_info.get('size', 0)
                        },
                        "analysis_metadata": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "total_files_found": len(repo_info['file_tree']['files']),
                            "files_parsed": parsed_files,
                            "parse_errors": len(repo_structure.parse_errors),
                            "analysis_path": repo_info['analysis_path']
                        },
                        "code_statistics": {
                            "total_lines_of_code": total_lines,
                            "total_classes": total_classes,
                            "total_functions": total_functions,
                            "total_methods": total_methods,
                            "language_breakdown": language_stats,
                            "files_by_language": repo_info['file_tree']['languages']
                        },
                        "architectural_complexity": {
                            "avg_methods_per_class": round(total_methods / max(total_classes, 1), 2),
                            "avg_functions_per_file": round(total_functions / max(parsed_files, 1), 2),
                            "class_to_function_ratio": round(total_classes / max(total_functions, 1), 2) if total_functions > 0 else 0,
                            "complexity_score": self._calculate_complexity_score(total_classes, total_functions, total_methods, parsed_files)
                        },
                        "file_structure": {
                            "directories": len(repo_info['file_tree']['directories']),
                            "total_size_bytes": repo_info['file_tree']['total_size'],
                            "largest_files": self._get_largest_files(repo_info['file_tree']['files'])
                        }
                    }
                    
                # Add parse errors if any (graceful degradation)
                if repo_structure.parse_errors:
                    analysis_result["parse_errors"] = repo_structure.parse_errors[:10]  # Limit to first 10 errors
                    analysis_result["warnings"] = [
                        f"Some files could not be parsed ({len(repo_structure.parse_errors)} errors). Analysis may be incomplete."
                    ]
                
                # Add file access errors from repository manager if any
                if repo_info['file_tree'].get('access_errors'):
                    if 'warnings' not in analysis_result:
                        analysis_result['warnings'] = []
                    analysis_result['warnings'].append(
                        f"Some files could not be accessed ({len(repo_info['file_tree']['access_errors'])} errors)"
                    )
                
                logger.info("Repository analysis completed", 
                          files_parsed=parsed_files, 
                          parse_errors=len(repo_structure.parse_errors),
                          repository_url=url)
                return analysis_result
        
        self.server.add_tool(analyze_repository)
        
        @self._handle_tool_errors
        async def generate_dependency_diagram(
            url: str, 
            format: str = "mermaid",
            token: Optional[str] = None,
            include_external: bool = True,
            max_depth: int = 10,
            layout: str = "hierarchical",
            filter_patterns: Optional[List[str]] = None,
            exclude_patterns: Optional[List[str]] = None
        ) -> Dict[str, Any]:
            """Generate dependency diagram from repository analysis.
            
            Args:
                url: GitHub repository URL
                format: Output format (mermaid, svg, png)
                token: Optional GitHub authentication token
                include_external: Include external dependencies
                max_depth: Maximum dependency depth
                layout: Diagram layout (hierarchical, circular, force-directed)
                filter_patterns: List of regex patterns to include
                exclude_patterns: List of regex patterns to exclude
                
            Returns:
                Generated dependency diagram with metadata
            """
            from .repository_manager import RepositoryManager
            from .parsers import CodeParserFactory
            from .models import RepositoryStructure
            from .architecture_analyzer import ArchitectureAnalyzer
            from .diagram_generator import DiagramGenerator, DiagramConfig, DiagramFormat, DiagramType
            from datetime import datetime
            
            # Validate inputs
            ErrorHandler.validate_github_url(url)
            ErrorHandler.validate_format(format, ["mermaid", "svg", "png"])
            ErrorHandler.validate_positive_integer(max_depth, "max_depth", max_value=20)
            
            # Validate layout
            valid_layouts = ["hierarchical", "circular", "force-directed"]
            if layout not in valid_layouts:
                raise ValidationError(
                    f"Layout must be one of: {', '.join(valid_layouts)}",
                    field="layout",
                    value=layout
                )
            
            # Normalize URL
            if url.startswith('github.com/'):
                url = f"https://{url}"
            
            logger.info("Generating dependency diagram", repository_url=url, format=format, layout=layout)
            
            # Initialize components
            async with RepositoryManager(github_token=token) as repo_manager:
                # Authenticate if token provided
                if token:
                    await repo_manager.authenticate(token)
                
                # Get repository information and clone
                repo_info = await repo_manager.get_repository_info(url)
                
                # Parse repository structure
                parser_factory = CodeParserFactory()
                repo_structure = RepositoryStructure(
                    repository_path=repo_info['analysis_path']
                )
                
                # Parse files with graceful error handling
                parsed_files = 0
                parsing_errors = []
                for file_info in repo_info['file_tree']['files']:
                    try:
                        file_path = file_info['absolute_path']
                        parser = parser_factory.registry.get_parser(file_path)
                        if parser:
                            code_structure = await parser.parse_file(file_path)
                            repo_structure.files.append(code_structure)
                            parsed_files += 1
                    except Exception as e:
                        error_msg = f"Failed to parse {file_info['path']}: {str(e)}"
                        parsing_errors.append(error_msg)
                        repo_structure.parse_errors.append(error_msg)
                        logger.warning("File parsing failed during diagram generation", 
                                     file_path=file_info['path'], error=str(e))
                
                # Analyze architecture to build dependency graph
                analyzer = ArchitectureAnalyzer()
                dependency_graph = analyzer.build_dependency_graph(repo_structure)
                
                # Configure diagram generation
                diagram_format = DiagramFormat.MERMAID if format == "mermaid" else DiagramFormat.SVG if format == "svg" else DiagramFormat.PNG
                
                config = DiagramConfig(
                    format=diagram_format,
                    title=f"Dependency Diagram - {repo_info.get('name', 'Repository')}",
                    include_external=include_external,
                    max_nodes=min(max_depth * 10, 100),  # Reasonable limit based on depth
                    layout=layout,
                    filter_patterns=filter_patterns or [],
                    exclude_patterns=exclude_patterns or []
                )
                
                # Generate diagram
                diagram_generator = DiagramGenerator()
                diagram_output = await diagram_generator.generate_dependency_diagram(
                    dependency_graph, config
                )
                
                # Calculate diagram statistics
                total_nodes = dependency_graph.number_of_nodes()
                total_edges = dependency_graph.number_of_edges()
                external_nodes = sum(1 for node in dependency_graph.nodes() 
                                   if dependency_graph.nodes[node].get('external', False))
                
                # Identify strongly connected components (circular dependencies)
                sccs = analyzer.identify_strongly_connected_components(dependency_graph)
                circular_dependencies = [scc for scc in sccs if len(scc) > 1]
                
                # Build response
                result = {
                    "diagram": {
                        "content": diagram_output.content,
                        "format": format,
                            "title": config.title,
                            "layout": layout
                        },
                        "metadata": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "repository_url": url,
                            "repository_name": repo_info.get('name', ''),
                            "files_analyzed": parsed_files,
                            "parse_errors": len(repo_structure.parse_errors)
                        },
                        "statistics": {
                            "total_nodes": total_nodes,
                            "internal_nodes": total_nodes - external_nodes,
                            "external_nodes": external_nodes,
                            "total_dependencies": total_edges,
                            "circular_dependencies": len(circular_dependencies),
                            "strongly_connected_components": len(sccs)
                        },
                        "configuration": {
                            "include_external": include_external,
                            "max_depth": max_depth,
                            "layout": layout,
                            "filter_patterns": filter_patterns,
                            "exclude_patterns": exclude_patterns
                        }
                }
                
                # Add circular dependency details if any
                if circular_dependencies:
                    result["circular_dependency_details"] = [
                        {"components": scc, "size": len(scc)} 
                        for scc in circular_dependencies[:5]  # Limit to first 5
                    ]
                
                # Add parse errors if any (graceful degradation)
                if repo_structure.parse_errors:
                    result["parse_errors"] = repo_structure.parse_errors[:10]
                    result["warnings"] = [
                        f"Some files could not be parsed ({len(repo_structure.parse_errors)} errors). Diagram may be incomplete."
                    ]
                
                logger.info("Dependency diagram generated", 
                          total_nodes=total_nodes, 
                          total_edges=total_edges,
                          repository_url=url)
                return result
        
        self.server.add_tool(generate_dependency_diagram)
        
        @self._handle_tool_errors
        async def generate_class_diagram(
            url: str,
            format: str = "mermaid", 
            token: Optional[str] = None,
            package_filter: Optional[str] = None,
            inheritance_depth: int = 5,
            show_attributes: bool = True,
            show_methods: bool = True,
            show_parameters: bool = False,
            group_by_package: bool = True
        ) -> Dict[str, Any]:
            """Generate UML class diagram from repository analysis.
            
            Args:
                url: GitHub repository URL
                format: Output format (mermaid, svg, png)
                token: Optional GitHub authentication token
                package_filter: Filter by package/namespace pattern (regex)
                inheritance_depth: Maximum inheritance depth to show
                show_attributes: Include class attributes in diagram
                show_methods: Include class methods in diagram
                show_parameters: Include method parameters in diagram
                group_by_package: Group classes by package/namespace
                
            Returns:
                Generated class diagram with metadata
            """
            try:
                from .repository_manager import RepositoryManager
                from .parsers import CodeParserFactory
                from .models import RepositoryStructure
                from .architecture_analyzer import ArchitectureAnalyzer
                from .diagram_generator import DiagramGenerator, DiagramConfig, DiagramFormat, DiagramType
                from datetime import datetime
                import re
                
                # Validate inputs
                if not url or not isinstance(url, str):
                    raise ValueError("Repository URL must be a non-empty string")
                
                if not url.startswith(('https://github.com/', 'http://github.com/', 'github.com/')):
                    raise ValueError("URL must be a valid GitHub repository URL")
                
                # Normalize URL
                if url.startswith('github.com/'):
                    url = f"https://{url}"
                
                # Validate format
                valid_formats = ["mermaid", "svg", "png"]
                if format not in valid_formats:
                    raise ValueError(f"Format must be one of: {', '.join(valid_formats)}")
                
                # Validate inheritance depth
                if inheritance_depth < 1 or inheritance_depth > 20:
                    raise ValueError("Inheritance depth must be between 1 and 20")
                
                logger.info(f"Generating class diagram for: {url} in {format} format")
                
                # Initialize components
                async with RepositoryManager(github_token=token) as repo_manager:
                    # Authenticate if token provided
                    if token:
                        await repo_manager.authenticate(token)
                    
                    # Get repository information and clone
                    repo_info = await repo_manager.get_repository_info(url)
                    
                    # Parse repository structure
                    parser_factory = CodeParserFactory()
                    repo_structure = RepositoryStructure(
                        repository_path=repo_info['analysis_path']
                    )
                    
                    # Parse files
                    parsed_files = 0
                    total_classes = 0
                    for file_info in repo_info['file_tree']['files']:
                        try:
                            file_path = file_info['absolute_path']
                            parser = parser_factory.registry.get_parser(file_path)
                            if parser:
                                code_structure = await parser.parse_file(file_path)
                                repo_structure.files.append(code_structure)
                                parsed_files += 1
                                total_classes += len(code_structure.classes)
                        except Exception as e:
                            error_msg = f"Failed to parse {file_info['path']}: {str(e)}"
                            repo_structure.parse_errors.append(error_msg)
                            logger.warning(error_msg)
                    
                    # Check if any classes were found
                    if total_classes == 0:
                        return {
                            "message": "No object-oriented structures found in the repository",
                            "details": "The repository does not contain classes or the code structure could not be analyzed for object-oriented patterns",
                            "metadata": {
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "repository_url": url,
                                "repository_name": repo_info.get('name', ''),
                                "files_analyzed": parsed_files,
                                "classes_found": 0
                            },
                            "suggestions": [
                                "Check if the repository contains object-oriented code",
                                "Verify that the programming languages are supported",
                                "Try analyzing a different repository with classes"
                            ]
                        }
                    
                    # Analyze architecture to extract class relationships
                    analyzer = ArchitectureAnalyzer()
                    class_diagram = analyzer.extract_class_relationships(repo_structure)
                    
                    # Apply package filter if provided
                    if package_filter:
                        try:
                            pattern = re.compile(package_filter)
                            filtered_classes = {}
                            for class_name, class_info in class_diagram.classes.items():
                                if pattern.search(class_name):
                                    filtered_classes[class_name] = class_info
                            class_diagram.classes = filtered_classes
                            
                            # Filter relationships to only include filtered classes
                            filtered_relationships = []
                            for rel in class_diagram.relationships:
                                if (rel.source_class in filtered_classes and 
                                    rel.target_class in filtered_classes):
                                    filtered_relationships.append(rel)
                            class_diagram.relationships = filtered_relationships
                            
                        except re.error as e:
                            raise ValueError(f"Invalid package filter regex: {str(e)}")
                    
                    # Configure diagram generation
                    diagram_format = DiagramFormat.MERMAID if format == "mermaid" else DiagramFormat.SVG if format == "svg" else DiagramFormat.PNG
                    
                    config = DiagramConfig(
                        format=diagram_format,
                        title=f"Class Diagram - {repo_info.get('name', 'Repository')}",
                        include_external=True,
                        max_nodes=min(len(class_diagram.classes), 50),  # Reasonable limit
                        show_attributes=show_attributes,
                        show_methods=show_methods,
                        show_parameters=show_parameters,
                        group_by_package=group_by_package
                    )
                    
                    # Generate diagram
                    diagram_generator = DiagramGenerator()
                    diagram_output = await diagram_generator.generate_class_diagram(
                        class_diagram, config
                    )
                    
                    # Calculate diagram statistics
                    total_classes_in_diagram = len(class_diagram.classes)
                    total_relationships = len(class_diagram.relationships)
                    
                    # Count relationship types
                    relationship_counts = {}
                    for rel in class_diagram.relationships:
                        rel_type = rel.relationship_type.value
                        relationship_counts[rel_type] = relationship_counts.get(rel_type, 0) + 1
                    
                    # Count classes by package
                    package_counts = {}
                    for package, classes in class_diagram.packages.items():
                        if classes:  # Only count non-empty packages
                            package_counts[package or "default"] = len(classes)
                    
                    # Build response
                    result = {
                        "diagram": {
                            "content": diagram_output.content,
                            "format": format,
                            "title": config.title
                        },
                        "metadata": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "repository_url": url,
                            "repository_name": repo_info.get('name', ''),
                            "files_analyzed": parsed_files,
                            "parse_errors": len(repo_structure.parse_errors)
                        },
                        "statistics": {
                            "total_classes": total_classes_in_diagram,
                            "total_relationships": total_relationships,
                            "relationship_types": relationship_counts,
                            "packages": len(package_counts),
                            "classes_per_package": package_counts,
                            "external_dependencies": len(class_diagram.external_dependencies)
                        },
                        "configuration": {
                            "package_filter": package_filter,
                            "inheritance_depth": inheritance_depth,
                            "show_attributes": show_attributes,
                            "show_methods": show_methods,
                            "show_parameters": show_parameters,
                            "group_by_package": group_by_package
                        }
                    }
                    
                    # Add external dependencies if any
                    if class_diagram.external_dependencies:
                        result["external_dependencies"] = list(class_diagram.external_dependencies)[:10]
                    
                    # Add parse errors if any
                    if repo_structure.parse_errors:
                        result["parse_errors"] = repo_structure.parse_errors[:10]
                    
                    logger.info(f"Class diagram generated: {total_classes_in_diagram} classes, {total_relationships} relationships")
                    return result
                    
            except ValueError as e:
                error_msg = f"Invalid input: {str(e)}"
                logger.error(error_msg)
                return {"error": error_msg, "error_type": "validation_error"}
            except Exception as e:
                error_msg = f"Error generating class diagram for {url}: {str(e)}"
                logger.error(error_msg)
                return {"error": error_msg, "error_type": "generation_error"}
        
        self.server.add_tool(generate_class_diagram)
        
        async def generate_data_flow_diagram(
            url: str,
            format: str = "mermaid",
            token: Optional[str] = None,
            dfd_level: int = 0,
            layout: str = "hierarchical",
            filter_patterns: Optional[List[str]] = None,
            exclude_patterns: Optional[List[str]] = None
        ) -> Dict[str, Any]:
            """Generate data flow diagram from repository analysis.
            
            Args:
                url: GitHub repository URL
                format: Output format (mermaid, svg, png)
                token: Optional GitHub authentication token
                dfd_level: DFD level (0=context, 1=level 1, etc.)
                layout: Diagram layout (hierarchical, circular, force-directed)
                filter_patterns: List of regex patterns to include
                exclude_patterns: List of regex patterns to exclude
                
            Returns:
                Generated data flow diagram with metadata
            """
            try:
                from .repository_manager import RepositoryManager
                from .parsers import CodeParserFactory
                from .models import RepositoryStructure
                from .architecture_analyzer import ArchitectureAnalyzer
                from .diagram_generator import DiagramGenerator, DiagramConfig, DiagramFormat, DiagramType
                from datetime import datetime
                
                # Validate inputs
                if not url or not isinstance(url, str):
                    raise ValueError("Repository URL must be a non-empty string")
                
                if not url.startswith(('https://github.com/', 'http://github.com/', 'github.com/')):
                    raise ValueError("URL must be a valid GitHub repository URL")
                
                # Normalize URL
                if url.startswith('github.com/'):
                    url = f"https://{url}"
                
                # Validate format
                valid_formats = ["mermaid", "svg", "png"]
                if format not in valid_formats:
                    raise ValueError(f"Format must be one of: {', '.join(valid_formats)}")
                
                # Validate DFD level
                if dfd_level < 0 or dfd_level > 3:
                    raise ValueError("DFD level must be between 0 (context) and 3")
                
                # Validate layout
                valid_layouts = ["hierarchical", "circular", "force-directed"]
                if layout not in valid_layouts:
                    raise ValueError(f"Layout must be one of: {', '.join(valid_layouts)}")
                
                logger.info(f"Generating data flow diagram for: {url} at level {dfd_level} in {format} format")
                
                # Initialize components
                async with RepositoryManager(github_token=token) as repo_manager:
                    # Authenticate if token provided
                    if token:
                        await repo_manager.authenticate(token)
                    
                    # Get repository information and clone
                    repo_info = await repo_manager.get_repository_info(url)
                    
                    # Parse repository structure
                    parser_factory = CodeParserFactory()
                    repo_structure = RepositoryStructure(
                        repository_path=repo_info['analysis_path']
                    )
                    
                    # Parse files
                    parsed_files = 0
                    total_functions = 0
                    for file_info in repo_info['file_tree']['files']:
                        try:
                            file_path = file_info['absolute_path']
                            parser = parser_factory.registry.get_parser(file_path)
                            if parser:
                                code_structure = await parser.parse_file(file_path)
                                repo_structure.files.append(code_structure)
                                parsed_files += 1
                                total_functions += len(code_structure.functions)
                                # Count methods in classes as functions too
                                for cls in code_structure.classes:
                                    total_functions += len(cls.methods)
                        except Exception as e:
                            error_msg = f"Failed to parse {file_info['path']}: {str(e)}"
                            repo_structure.parse_errors.append(error_msg)
                            logger.warning(error_msg)
                    
                    # Analyze architecture to extract data flow
                    analyzer = ArchitectureAnalyzer()
                    data_flow_diagram = analyzer.analyze_data_flow(repo_structure)
                    
                    # Check if data flow could be determined
                    if (len(data_flow_diagram.processes) == 0 and 
                        len(data_flow_diagram.external_entities) == 0 and 
                        len(data_flow_diagram.data_stores) == 0):
                        return {
                            "message": "Data flow cannot be determined from the repository",
                            "details": "The repository structure does not contain sufficient information to generate a meaningful data flow diagram",
                            "metadata": {
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "repository_url": url,
                                "repository_name": repo_info.get('name', ''),
                                "files_analyzed": parsed_files,
                                "functions_found": total_functions,
                                "dfd_level": dfd_level
                            },
                            "suggestions": [
                                "Ensure the repository contains functions or methods that process data",
                                "Check if the code includes database operations, API calls, or file I/O",
                                "Try analyzing a repository with more complex data processing logic",
                                "Consider using dependency or class diagrams instead for this repository"
                            ]
                        }
                    
                    # Configure diagram generation
                    diagram_format = DiagramFormat.MERMAID if format == "mermaid" else DiagramFormat.SVG if format == "svg" else DiagramFormat.PNG
                    
                    # Adjust title based on DFD level
                    level_names = {
                        0: "Context Diagram",
                        1: "Level 1 DFD",
                        2: "Level 2 DFD", 
                        3: "Level 3 DFD"
                    }
                    
                    config = DiagramConfig(
                        format=diagram_format,
                        title=f"{level_names.get(dfd_level, f'Level {dfd_level} DFD')} - {repo_info.get('name', 'Repository')}",
                        include_external=True,
                        max_nodes=50,  # Reasonable limit for DFD
                        layout=layout,
                        filter_patterns=filter_patterns or [],
                        exclude_patterns=exclude_patterns or []
                    )
                    
                    # Generate diagram
                    diagram_generator = DiagramGenerator()
                    diagram_output = await diagram_generator.generate_data_flow_diagram(
                        data_flow_diagram, config
                    )
                    
                    # Calculate diagram statistics
                    total_processes = len(data_flow_diagram.processes)
                    total_external_entities = len(data_flow_diagram.external_entities)
                    total_data_stores = len(data_flow_diagram.data_stores)
                    total_flows = len(data_flow_diagram.flows)
                    
                    # Count flow types
                    flow_type_counts = {}
                    for flow in data_flow_diagram.flows:
                        flow_type = getattr(flow, 'flow_type', 'data')
                        flow_type_counts[flow_type] = flow_type_counts.get(flow_type, 0) + 1
                    
                    # Build response
                    result = {
                        "diagram": {
                            "content": diagram_output.content,
                            "format": format,
                            "title": config.title,
                            "dfd_level": dfd_level,
                            "layout": layout
                        },
                        "metadata": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "repository_url": url,
                            "repository_name": repo_info.get('name', ''),
                            "files_analyzed": parsed_files,
                            "parse_errors": len(repo_structure.parse_errors)
                        },
                        "statistics": {
                            "total_processes": total_processes,
                            "external_entities": total_external_entities,
                            "data_stores": total_data_stores,
                            "data_flows": total_flows,
                            "flow_types": flow_type_counts
                        },
                        "configuration": {
                            "dfd_level": dfd_level,
                            "layout": layout,
                            "filter_patterns": filter_patterns,
                            "exclude_patterns": exclude_patterns
                        },
                        "dfd_explanation": {
                            "level_description": self._get_dfd_level_description(dfd_level),
                            "node_types": {
                                "processes": f"Functions and methods that transform data ({total_processes} found)",
                                "external_entities": f"External systems and APIs ({total_external_entities} found)",
                                "data_stores": f"Databases, files, and storage ({total_data_stores} found)"
                            }
                        }
                    }
                    
                    # Add parse errors if any
                    if repo_structure.parse_errors:
                        result["parse_errors"] = repo_structure.parse_errors[:10]
                    
                    logger.info(f"Data flow diagram generated: {total_processes} processes, {total_flows} flows")
                    return result
                    
            except ValueError as e:
                error_msg = f"Invalid input: {str(e)}"
                logger.error(error_msg)
                return {"error": error_msg, "error_type": "validation_error"}
            except Exception as e:
                error_msg = f"Error generating data flow diagram for {url}: {str(e)}"
                logger.error(error_msg)
                return {"error": error_msg, "error_type": "generation_error"}
        
        self.server.add_tool(generate_data_flow_diagram)
        
        async def get_repository_summary(
            url: str,
            token: Optional[str] = None,
            include_caching_info: bool = True
        ) -> Dict[str, Any]:
            """Get high-level repository statistics and summary.
            
            Args:
                url: GitHub repository URL
                token: Optional GitHub authentication token
                include_caching_info: Include caching and analysis timestamps
                
            Returns:
                Repository summary with statistics and complexity metrics
            """
            try:
                from .repository_manager import RepositoryManager
                from .parsers import CodeParserFactory
                from .models import RepositoryStructure
                from .architecture_analyzer import ArchitectureAnalyzer
                from datetime import datetime
                import os
                
                # Validate inputs
                if not url or not isinstance(url, str):
                    raise ValueError("Repository URL must be a non-empty string")
                
                if not url.startswith(('https://github.com/', 'http://github.com/', 'github.com/')):
                    raise ValueError("URL must be a valid GitHub repository URL")
                
                # Normalize URL
                if url.startswith('github.com/'):
                    url = f"https://{url}"
                
                logger.info(f"Getting repository summary for: {url}")
                
                # Initialize components
                async with RepositoryManager(github_token=token) as repo_manager:
                    # Authenticate if token provided
                    if token:
                        await repo_manager.authenticate(token)
                    
                    # Get repository information and clone
                    repo_info = await repo_manager.get_repository_info(url)
                    
                    # Parse repository structure for detailed analysis
                    parser_factory = CodeParserFactory()
                    repo_structure = RepositoryStructure(
                        repository_path=repo_info['analysis_path']
                    )
                    
                    # Parse files and collect detailed statistics
                    parsed_files = 0
                    total_lines = 0
                    language_stats = {}
                    complexity_metrics = {
                        'total_classes': 0,
                        'total_functions': 0,
                        'total_methods': 0,
                        'total_imports': 0,
                        'total_attributes': 0
                    }
                    
                    file_type_stats = {}
                    largest_files = []
                    
                    for file_info in repo_info['file_tree']['files']:
                        try:
                            file_path = file_info['absolute_path']
                            language = file_info['language']
                            file_size = file_info['size']
                            
                            # Track file type statistics
                            if language not in file_type_stats:
                                file_type_stats[language] = {'count': 0, 'total_size': 0}
                            file_type_stats[language]['count'] += 1
                            file_type_stats[language]['total_size'] += file_size
                            
                            # Track largest files
                            largest_files.append({
                                'path': file_info['path'],
                                'size': file_size,
                                'language': language
                            })
                            
                            # Parse file if supported
                            parser = parser_factory.registry.get_parser(file_path)
                            if parser:
                                code_structure = await parser.parse_file(file_path)
                                repo_structure.files.append(code_structure)
                                parsed_files += 1
                                
                                # Update complexity metrics
                                complexity_metrics['total_classes'] += len(code_structure.classes)
                                complexity_metrics['total_functions'] += len(code_structure.functions)
                                complexity_metrics['total_imports'] += len(code_structure.imports)
                                
                                # Count methods and attributes in classes
                                for cls in code_structure.classes:
                                    complexity_metrics['total_methods'] += len(cls.methods)
                                    complexity_metrics['total_attributes'] += len(cls.attributes)
                                
                                # Update language statistics
                                if language not in language_stats:
                                    language_stats[language] = 0
                                language_stats[language] += 1
                                
                                # Estimate lines of code
                                try:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        file_lines = sum(1 for line in f if line.strip())
                                        total_lines += file_lines
                                except Exception:
                                    pass
                                    
                        except Exception as e:
                            error_msg = f"Failed to parse {file_info['path']}: {str(e)}"
                            repo_structure.parse_errors.append(error_msg)
                            logger.warning(error_msg)
                    
                    # Sort largest files by size
                    largest_files.sort(key=lambda x: x['size'], reverse=True)
                    top_largest_files = largest_files[:10]
                    
                    # Calculate architectural complexity metrics
                    analyzer = ArchitectureAnalyzer()
                    
                    # Build dependency graph for complexity analysis
                    dependency_graph = None
                    dependency_stats = {}
                    try:
                        dependency_graph = analyzer.build_dependency_graph(repo_structure)
                        dependency_stats = {
                            'total_modules': dependency_graph.number_of_nodes(),
                            'total_dependencies': dependency_graph.number_of_edges(),
                            'external_dependencies': sum(1 for node in dependency_graph.nodes() 
                                                        if dependency_graph.nodes[node].get('external', False)),
                            'circular_dependencies': len([scc for scc in analyzer.identify_strongly_connected_components(dependency_graph) if len(scc) > 1])
                        }
                    except Exception as e:
                        logger.warning(f"Failed to analyze dependencies: {e}")
                        dependency_stats = {'error': str(e)}
                    
                    # Calculate overall complexity score
                    overall_complexity = self._calculate_complexity_score(
                        complexity_metrics['total_classes'],
                        complexity_metrics['total_functions'],
                        complexity_metrics['total_methods'],
                        parsed_files
                    )
                    
                    # Calculate maintainability metrics
                    maintainability_metrics = self._calculate_maintainability_metrics(
                        complexity_metrics, dependency_stats, parsed_files, total_lines
                    )
                    
                    # Build comprehensive summary
                    summary = {
                        "repository_info": {
                            "url": url,
                            "name": repo_info.get('name', ''),
                            "full_name": repo_info.get('full_name', ''),
                            "description": repo_info.get('description', ''),
                            "private": repo_info.get('private', False),
                            "default_branch": repo_info.get('default_branch', 'main'),
                            "github_size_kb": repo_info.get('size', 0)
                        },
                        "file_statistics": {
                            "total_files": len(repo_info['file_tree']['files']),
                            "total_directories": len(repo_info['file_tree']['directories']),
                            "total_size_bytes": repo_info['file_tree']['total_size'],
                            "files_parsed": parsed_files,
                            "parse_errors": len(repo_structure.parse_errors),
                            "supported_languages": list(language_stats.keys()),
                            "file_type_breakdown": file_type_stats
                        },
                        "code_metrics": {
                            "estimated_lines_of_code": total_lines,
                            "language_distribution": language_stats,
                            **complexity_metrics
                        },
                        "architectural_complexity": {
                            "overall_complexity_score": overall_complexity,
                            "complexity_level": self._get_complexity_level(overall_complexity),
                            "dependency_analysis": dependency_stats,
                            "maintainability_metrics": maintainability_metrics
                        },
                        "largest_files": top_largest_files,
                        "analysis_metadata": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "analysis_duration_estimate": "N/A",  # Could be calculated if needed
                            "supported_extensions": parser_factory.get_supported_extensions(),
                            "supported_languages": parser_factory.get_supported_languages()
                        }
                    }
                    
                    # Add caching information if requested
                    if include_caching_info:
                        cache_info = self._get_cache_info(repo_info['analysis_path'])
                        summary["caching_info"] = cache_info
                    
                    # Add parse errors if any
                    if repo_structure.parse_errors:
                        summary["parse_errors"] = repo_structure.parse_errors[:10]
                    
                    # Add recommendations based on analysis
                    summary["recommendations"] = self._generate_recommendations(
                        complexity_metrics, dependency_stats, overall_complexity, language_stats
                    )
                    
                    logger.info(f"Repository summary completed: {parsed_files} files analyzed, complexity score: {overall_complexity}")
                    return summary
                    
            except ValueError as e:
                error_msg = f"Invalid input: {str(e)}"
                logger.error(error_msg)
                return {"error": error_msg, "error_type": "validation_error"}
            except Exception as e:
                error_msg = f"Error getting repository summary for {url}: {str(e)}"
                logger.error(error_msg)
                return {"error": error_msg, "error_type": "summary_error"}
        
        self.server.add_tool(get_repository_summary)
    
    async def run(self, transport_type: str = "stdio") -> None:
        """Run the MCP server.
        
        Args:
            transport_type: Transport type for MCP communication (stdio, websocket, etc.)
        """
        logger.info("Starting Repository Architecture MCP Server")
        
        if transport_type == "stdio":
            await self.server.run_stdio_async()
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")
    
    def _calculate_complexity_score(self, total_classes: int, total_functions: int, 
                                   total_methods: int, total_files: int) -> float:
        """Calculate a complexity score for the repository.
        
        Args:
            total_classes: Total number of classes
            total_functions: Total number of standalone functions
            total_methods: Total number of methods in classes
            total_files: Total number of parsed files
            
        Returns:
            Complexity score (0-100, higher = more complex)
        """
        if total_files == 0:
            return 0.0
        
        # Base complexity from code elements
        elements_per_file = (total_classes + total_functions + total_methods) / total_files
        
        # Adjust for different factors
        class_complexity = total_classes * 2  # Classes add more complexity
        method_complexity = total_methods * 1.5  # Methods add complexity
        function_complexity = total_functions * 1  # Functions are simpler
        
        raw_score = (class_complexity + method_complexity + function_complexity) / total_files
        
        # Normalize to 0-100 scale (logarithmic to handle large repositories)
        import math
        normalized_score = min(100, math.log10(max(1, raw_score)) * 25)
        
        return round(normalized_score, 2)
    
    def _get_largest_files(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get the largest files by size.
        
        Args:
            files: List of file information dictionaries
            
        Returns:
            List of largest files (up to 5)
        """
        # Sort by size and take top 5
        sorted_files = sorted(files, key=lambda f: f.get('size', 0), reverse=True)
        
        largest_files = []
        for file_info in sorted_files[:5]:
            largest_files.append({
                "path": file_info['path'],
                "size_bytes": file_info['size'],
                "language": file_info['language']
            })
        
        return largest_files
    
    def _get_dfd_level_description(self, level: int) -> str:
        """Get description for DFD level.
        
        Args:
            level: DFD level number
            
        Returns:
            Description of what the level represents
        """
        descriptions = {
            0: "Context Diagram - Shows the system as a single process with external entities",
            1: "Level 1 DFD - Shows major processes within the system and data flows between them",
            2: "Level 2 DFD - Decomposes Level 1 processes into more detailed sub-processes",
            3: "Level 3 DFD - Further decomposes Level 2 processes into detailed operations"
        }
        return descriptions.get(level, f"Level {level} DFD - Detailed decomposition of higher-level processes")
    
    def _calculate_maintainability_metrics(self, complexity_metrics: Dict[str, int], 
                                         dependency_stats: Dict[str, Any], 
                                         parsed_files: int, total_lines: int) -> Dict[str, Any]:
        """Calculate maintainability metrics for the repository.
        
        Args:
            complexity_metrics: Code complexity metrics
            dependency_stats: Dependency analysis results
            parsed_files: Number of parsed files
            total_lines: Total lines of code
            
        Returns:
            Dictionary of maintainability metrics
        """
        if parsed_files == 0:
            return {"error": "No files parsed for maintainability analysis"}
        
        # Calculate various maintainability indicators
        avg_lines_per_file = total_lines / parsed_files if parsed_files > 0 else 0
        avg_functions_per_file = complexity_metrics['total_functions'] / parsed_files
        avg_classes_per_file = complexity_metrics['total_classes'] / parsed_files
        
        # Calculate method-to-class ratio
        method_class_ratio = (complexity_metrics['total_methods'] / 
                             max(complexity_metrics['total_classes'], 1))
        
        # Calculate import density (imports per file)
        import_density = complexity_metrics['total_imports'] / parsed_files
        
        # Determine maintainability scores (0-100)
        file_size_score = min(100, max(0, 100 - (avg_lines_per_file - 200) / 10))  # Penalty for large files
        complexity_score = min(100, max(0, 100 - method_class_ratio * 5))  # Penalty for complex classes
        dependency_score = 100  # Default if no dependency analysis
        
        if 'circular_dependencies' in dependency_stats:
            circular_deps = dependency_stats.get('circular_dependencies', 0)
            dependency_score = max(0, 100 - circular_deps * 20)  # Heavy penalty for circular deps
        
        # Overall maintainability index
        maintainability_index = (file_size_score + complexity_score + dependency_score) / 3
        
        return {
            "maintainability_index": round(maintainability_index, 2),
            "file_size_score": round(file_size_score, 2),
            "complexity_score": round(complexity_score, 2),
            "dependency_score": round(dependency_score, 2),
            "metrics": {
                "avg_lines_per_file": round(avg_lines_per_file, 2),
                "avg_functions_per_file": round(avg_functions_per_file, 2),
                "avg_classes_per_file": round(avg_classes_per_file, 2),
                "method_to_class_ratio": round(method_class_ratio, 2),
                "import_density": round(import_density, 2)
            }
        }
    
    def _get_complexity_level(self, complexity_score: float) -> str:
        """Get human-readable complexity level.
        
        Args:
            complexity_score: Numerical complexity score
            
        Returns:
            Complexity level description
        """
        if complexity_score < 20:
            return "Low - Simple structure, easy to understand"
        elif complexity_score < 40:
            return "Moderate - Well-structured with some complexity"
        elif complexity_score < 60:
            return "High - Complex structure requiring careful navigation"
        elif complexity_score < 80:
            return "Very High - Highly complex, may benefit from refactoring"
        else:
            return "Extremely High - Very complex structure, difficult to maintain"
    
    def _get_cache_info(self, analysis_path: str) -> Dict[str, Any]:
        """Get caching information for the analysis.
        
        Args:
            analysis_path: Path to the analyzed repository
            
        Returns:
            Caching information
        """
        import os
        from datetime import datetime
        
        try:
            # Get directory modification time as a proxy for cache freshness
            if os.path.exists(analysis_path):
                mod_time = os.path.getmtime(analysis_path)
                cache_timestamp = datetime.fromtimestamp(mod_time).isoformat() + "Z"
                
                # Calculate cache age
                cache_age_seconds = (datetime.now().timestamp() - mod_time)
                cache_age_minutes = cache_age_seconds / 60
                
                return {
                    "cache_available": True,
                    "cache_timestamp": cache_timestamp,
                    "cache_age_minutes": round(cache_age_minutes, 2),
                    "cache_path": analysis_path,
                    "cache_fresh": cache_age_minutes < 60  # Consider fresh if less than 1 hour
                }
            else:
                return {
                    "cache_available": False,
                    "message": "No cache available for this repository"
                }
        except Exception as e:
            return {
                "cache_available": False,
                "error": f"Failed to get cache info: {str(e)}"
            }
    
    def _generate_recommendations(self, complexity_metrics: Dict[str, int], 
                                dependency_stats: Dict[str, Any], 
                                overall_complexity: float,
                                language_stats: Dict[str, int]) -> List[str]:
        """Generate recommendations based on repository analysis.
        
        Args:
            complexity_metrics: Code complexity metrics
            dependency_stats: Dependency analysis results
            overall_complexity: Overall complexity score
            language_stats: Language distribution
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Complexity-based recommendations
        if overall_complexity > 70:
            recommendations.append("Consider refactoring to reduce complexity - break down large classes and functions")
        elif overall_complexity > 50:
            recommendations.append("Monitor complexity growth - consider establishing coding standards")
        
        # Dependency-based recommendations
        if 'circular_dependencies' in dependency_stats and dependency_stats['circular_dependencies'] > 0:
            recommendations.append(f"Address {dependency_stats['circular_dependencies']} circular dependencies to improve maintainability")
        
        # Language diversity recommendations
        if len(language_stats) > 5:
            recommendations.append("High language diversity detected - consider consolidating technologies where possible")
        elif len(language_stats) == 1:
            recommendations.append("Single-language repository - good for consistency and maintainability")
        
        # Class/function balance recommendations
        total_classes = complexity_metrics['total_classes']
        total_functions = complexity_metrics['total_functions']
        
        if total_classes > 0 and total_functions / max(total_classes, 1) > 10:
            recommendations.append("High function-to-class ratio - consider more object-oriented design patterns")
        elif total_classes > total_functions * 2:
            recommendations.append("High class-to-function ratio - ensure classes have sufficient functionality")
        
        # Method complexity recommendations
        if total_classes > 0:
            avg_methods_per_class = complexity_metrics['total_methods'] / total_classes
            if avg_methods_per_class > 15:
                recommendations.append("Classes have many methods on average - consider breaking down large classes")
            elif avg_methods_per_class < 3 and total_classes > 10:
                recommendations.append("Classes have few methods on average - consider if all classes are necessary")
        
        # Default recommendation if none generated
        if not recommendations:
            recommendations.append("Repository structure appears well-balanced - continue following current patterns")
        
        return recommendations

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names.
        
        Returns:
            List of tool names
        """
        return [
            "analyze_repository",
            "generate_dependency_diagram", 
            "generate_class_diagram",
            "generate_data_flow_diagram",
            "get_repository_summary"
        ]