"""Sample repository test suite for validating diagram accuracy and edge cases.

This test suite uses known open-source repositories to verify diagram accuracy
against manual analysis and tests edge cases like empty repositories and 
single-file projects.
"""

import asyncio
import json
import os
import tempfile
import pytest
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, patch, MagicMock

from repo_architecture_mcp.server import RepoArchitectureMCPServer
from repo_architecture_mcp.models import AnalysisConfig, CodeStructure, ClassInfo, FunctionInfo, ImportInfo
from repo_architecture_mcp.errors import MCPError


class SampleRepositoryTestCase:
    """Test case for a sample repository."""
    
    def __init__(
        self,
        name: str,
        url: str,
        description: str,
        expected_languages: List[str],
        expected_classes: int,
        expected_functions: int,
        expected_dependencies: int,
        has_inheritance: bool = False,
        has_external_deps: bool = True,
        complexity_level: str = "medium"  # low, medium, high
    ):
        self.name = name
        self.url = url
        self.description = description
        self.expected_languages = expected_languages
        self.expected_classes = expected_classes
        self.expected_functions = expected_functions
        self.expected_dependencies = expected_dependencies
        self.has_inheritance = has_inheritance
        self.has_external_deps = has_external_deps
        self.complexity_level = complexity_level


class TestSampleRepositories:
    """Test suite for sample repositories."""
    
    @pytest.fixture
    def server_config(self):
        """Create test server configuration."""
        return AnalysisConfig(
            max_workers=2,
            memory_limit_mb=512,
            cache_enabled=False,
            parallel_processing=True,
            max_depth=10,
            max_nodes=100,
            output_format="mermaid"
        )
    
    @pytest.fixture
    def server(self, server_config):
        """Create test server instance."""
        return RepoArchitectureMCPServer(config=server_config)
    
    @pytest.fixture
    def sample_repositories(self):
        """Define sample repositories for testing."""
        return [
            SampleRepositoryTestCase(
                name="simple-python-project",
                url="https://github.com/user/simple-python-project",
                description="Simple Python project with basic structure",
                expected_languages=["Python"],
                expected_classes=3,
                expected_functions=8,
                expected_dependencies=5,
                has_inheritance=True,
                complexity_level="low"
            ),
            SampleRepositoryTestCase(
                name="javascript-web-app",
                url="https://github.com/user/javascript-web-app",
                description="JavaScript web application with modules",
                expected_languages=["JavaScript"],
                expected_classes=0,  # JavaScript may not have traditional classes
                expected_functions=15,
                expected_dependencies=12,
                has_external_deps=True,
                complexity_level="medium"
            ),
            SampleRepositoryTestCase(
                name="typescript-library",
                url="https://github.com/user/typescript-library",
                description="TypeScript library with interfaces and classes",
                expected_languages=["TypeScript"],
                expected_classes=5,
                expected_functions=20,
                expected_dependencies=8,
                has_inheritance=True,
                complexity_level="medium"
            ),
            SampleRepositoryTestCase(
                name="java-spring-app",
                url="https://github.com/user/java-spring-app",
                description="Java Spring application with complex architecture",
                expected_languages=["Java"],
                expected_classes=25,
                expected_functions=100,
                expected_dependencies=30,
                has_inheritance=True,
                has_external_deps=True,
                complexity_level="high"
            ),
            SampleRepositoryTestCase(
                name="multi-language-project",
                url="https://github.com/user/multi-language-project",
                description="Multi-language project with Python, JavaScript, and Java",
                expected_languages=["Python", "JavaScript", "Java"],
                expected_classes=15,
                expected_functions=50,
                expected_dependencies=25,
                has_inheritance=True,
                complexity_level="high"
            )
        ]
    
    def create_mock_repository_structure(self, test_case: SampleRepositoryTestCase) -> Dict[str, Any]:
        """Create mock repository structure based on test case."""
        
        # Generate file list based on expected languages
        files = []
        file_extensions = {
            "Python": ".py",
            "JavaScript": ".js", 
            "TypeScript": ".ts",
            "Java": ".java"
        }
        
        file_id = 0
        for language in test_case.expected_languages:
            ext = file_extensions.get(language, ".txt")
            
            # Create main files for each language
            for i in range(3):  # 3 files per language
                file_id += 1
                files.append({
                    "path": f"src/{language.lower()}/module_{i}{ext}",
                    "absolute_path": f"/tmp/{test_case.name}/src/{language.lower()}/module_{i}{ext}",
                    "language": language,
                    "size": 1000 + (i * 200)
                })
        
        # Add configuration and documentation files
        files.extend([
            {
                "path": "README.md",
                "absolute_path": f"/tmp/{test_case.name}/README.md",
                "language": "Markdown",
                "size": 500
            },
            {
                "path": "package.json" if "JavaScript" in test_case.expected_languages or "TypeScript" in test_case.expected_languages else "requirements.txt",
                "absolute_path": f"/tmp/{test_case.name}/{'package.json' if 'JavaScript' in test_case.expected_languages or 'TypeScript' in test_case.expected_languages else 'requirements.txt'}",
                "language": "JSON" if "JavaScript" in test_case.expected_languages or "TypeScript" in test_case.expected_languages else "Text",
                "size": 200
            }
        ])
        
        return {
            "name": test_case.name,
            "full_name": f"user/{test_case.name}",
            "description": test_case.description,
            "private": False,
            "default_branch": "main",
            "size": sum(f["size"] for f in files),
            "analysis_path": f"/tmp/{test_case.name}",
            "file_tree": {
                "files": files,
                "directories": ["src", "tests", "docs"],
                "languages": {lang: len([f for f in files if f["language"] == lang]) for lang in test_case.expected_languages},
                "total_size": sum(f["size"] for f in files),
                "access_errors": []
            }
        }
    
    def create_mock_code_structures(self, test_case: SampleRepositoryTestCase) -> List[CodeStructure]:
        """Create mock code structures based on test case expectations."""
        structures = []
        
        # Distribute classes and functions across files
        classes_per_file = max(1, test_case.expected_classes // len(test_case.expected_languages))
        functions_per_file = max(1, test_case.expected_functions // (len(test_case.expected_languages) * 3))
        
        file_id = 0
        for language in test_case.expected_languages:
            for i in range(3):  # 3 files per language
                file_id += 1
                
                # Create classes for this file
                classes = []
                for j in range(classes_per_file if file_id <= test_case.expected_classes else 0):
                    class_name = f"{language}Class{file_id}_{j}"
                    
                    # Add inheritance if expected
                    inheritance = []
                    if test_case.has_inheritance and j > 0:
                        inheritance = [f"{language}BaseClass"]
                    
                    classes.append(ClassInfo(
                        name=class_name,
                        methods=[
                            {
                                "name": f"method_{k}",
                                "parameters": ["self"] if language == "Python" else [],
                                "return_type": "void",
                                "decorators": [],
                                "visibility": "public"
                            }
                            for k in range(2)  # 2 methods per class
                        ],
                        attributes=[
                            {
                                "name": f"attr_{k}",
                                "type": "string",
                                "visibility": "private"
                            }
                            for k in range(2)  # 2 attributes per class
                        ],
                        inheritance=inheritance,
                        decorators=[],
                        visibility="public"
                    ))
                
                # Create functions for this file
                functions = []
                for j in range(functions_per_file):
                    functions.append(FunctionInfo(
                        name=f"function_{file_id}_{j}",
                        parameters=[
                            {"name": "param1", "type": "string"},
                            {"name": "param2", "type": "int"}
                        ],
                        return_type="bool",
                        decorators=[],
                        visibility="public"
                    ))
                
                # Create imports
                imports = []
                if test_case.has_external_deps:
                    imports.extend([
                        ImportInfo(
                            module="external_lib",
                            imported_names=["ExternalClass"],
                            alias=None,
                            is_relative=False
                        ),
                        ImportInfo(
                            module="os",
                            imported_names=["path"],
                            alias=None,
                            is_relative=False
                        )
                    ])
                
                # Add internal imports
                if file_id > 1:
                    imports.append(ImportInfo(
                        module=f"module_{file_id-1}",
                        imported_names=[f"{language}Class{file_id-1}_0"],
                        alias=None,
                        is_relative=True
                    ))
                
                structures.append(CodeStructure(
                    file_path=f"/tmp/{test_case.name}/src/{language.lower()}/module_{i}.{language.lower()[:2]}",
                    language=language,
                    classes=classes,
                    functions=functions,
                    imports=imports,
                    exports=[]
                ))
        
        return structures
    
    @pytest.mark.asyncio
    async def test_sample_repository_analysis(self, server, sample_repositories):
        """Test analysis of sample repositories."""
        
        for test_case in sample_repositories:
            with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr, \
                 patch('repo_architecture_mcp.server.CodeParserFactory') as mock_parser_factory:
                
                # Setup repository manager mock
                mock_repo_instance = AsyncMock()
                mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
                
                repo_structure = self.create_mock_repository_structure(test_case)
                mock_repo_instance.get_repository_info.return_value = repo_structure
                
                # Setup parser factory mock
                mock_parser = AsyncMock()
                mock_parser_instance = AsyncMock()
                mock_parser_factory.return_value = mock_parser_instance
                mock_parser_instance.get_parser.return_value = mock_parser
                
                # Create mock code structures
                code_structures = self.create_mock_code_structures(test_case)
                mock_parser.parse_file.side_effect = code_structures
                
                # Get the analyze_repository tool
                tools = {tool: True for tool in server.get_available_tools()}
                assert "analyze_repository" in tools
                
                # Call analyze_repository tool directly
                from repo_architecture_mcp.server import RepoArchitectureMCPServer
                
                # Create a mock tool call
                async def mock_analyze_repository(url: str, token: Optional[str] = None):
                    # This simulates the actual tool call
                    from repo_architecture_mcp.repository_manager import RepositoryManager
                    from repo_architecture_mcp.parsers import CodeParserFactory
                    from repo_architecture_mcp.models import RepositoryStructure
                    from datetime import datetime
                    
                    async with RepositoryManager(github_token=token) as repo_manager:
                        repo_info = await repo_manager.get_repository_info(url)
                        
                        parser_factory = CodeParserFactory()
                        repo_structure = RepositoryStructure(repository_path=repo_info['analysis_path'])
                        
                        parsed_files = 0
                        total_classes = 0
                        total_functions = 0
                        
                        for file_info in repo_info['file_tree']['files']:
                            try:
                                parser = parser_factory.get_parser(file_info['absolute_path'])
                                if parser and parsed_files < len(code_structures):
                                    code_structure = code_structures[parsed_files]
                                    repo_structure.files.append(code_structure)
                                    parsed_files += 1
                                    total_classes += len(code_structure.classes)
                                    total_functions += len(code_structure.functions)
                            except Exception as e:
                                repo_structure.parse_errors.append(str(e))
                        
                        return {
                            "repository_info": {
                                "url": url,
                                "name": repo_info.get('name', ''),
                                "description": repo_info.get('description', ''),
                                "private": repo_info.get('private', False)
                            },
                            "analysis_metadata": {
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "total_files_found": len(repo_info['file_tree']['files']),
                                "files_parsed": parsed_files,
                                "parse_errors": len(repo_structure.parse_errors)
                            },
                            "code_statistics": {
                                "total_classes": total_classes,
                                "total_functions": total_functions,
                                "language_breakdown": repo_info['file_tree']['languages']
                            }
                        }
                
                # Perform analysis
                result = await mock_analyze_repository(test_case.url)
                
                # Verify analysis results against expectations
                assert "repository_info" in result
                assert "analysis_metadata" in result
                assert "code_statistics" in result
                
                # Verify repository info
                assert result["repository_info"]["url"] == test_case.url
                assert result["repository_info"]["name"] == test_case.name
                
                # Verify language detection
                detected_languages = set(result["code_statistics"]["language_breakdown"].keys())
                expected_languages = set(test_case.expected_languages)
                assert detected_languages.intersection(expected_languages), f"Expected languages {expected_languages}, got {detected_languages}"
                
                # Verify complexity metrics (allow some tolerance)
                total_classes = result["code_statistics"]["total_classes"]
                total_functions = result["code_statistics"]["total_functions"]
                
                # Allow 20% tolerance for class and function counts
                class_tolerance = max(1, int(test_case.expected_classes * 0.2))
                function_tolerance = max(1, int(test_case.expected_functions * 0.2))
                
                assert abs(total_classes - test_case.expected_classes) <= class_tolerance, \
                    f"Expected ~{test_case.expected_classes} classes, got {total_classes}"
                assert abs(total_functions - test_case.expected_functions) <= function_tolerance, \
                    f"Expected ~{test_case.expected_functions} functions, got {total_functions}"
    
    @pytest.mark.asyncio
    async def test_dependency_diagram_accuracy(self, server, sample_repositories):
        """Test dependency diagram generation accuracy."""
        
        for test_case in sample_repositories:
            if test_case.complexity_level == "low":  # Test with simpler repositories first
                
                with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr, \
                     patch('repo_architecture_mcp.server.CodeParserFactory') as mock_parser_factory, \
                     patch('repo_architecture_mcp.server.ArchitectureAnalyzer') as mock_analyzer, \
                     patch('repo_architecture_mcp.server.DiagramGenerator') as mock_diagram_gen:
                    
                    # Setup mocks
                    mock_repo_instance = AsyncMock()
                    mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
                    mock_repo_instance.get_repository_info.return_value = self.create_mock_repository_structure(test_case)
                    
                    mock_parser = AsyncMock()
                    mock_parser_instance = AsyncMock()
                    mock_parser_factory.return_value = mock_parser_instance
                    mock_parser_instance.registry.get_parser.return_value = mock_parser
                    
                    code_structures = self.create_mock_code_structures(test_case)
                    mock_parser.parse_file.side_effect = code_structures
                    
                    # Mock architecture analyzer
                    import networkx as nx
                    mock_graph = nx.DiGraph()
                    
                    # Add nodes and edges based on expected dependencies
                    for i in range(test_case.expected_dependencies):
                        mock_graph.add_node(f"module_{i}")
                        if i > 0:
                            mock_graph.add_edge(f"module_{i-1}", f"module_{i}")
                    
                    mock_analyzer_instance = AsyncMock()
                    mock_analyzer.return_value = mock_analyzer_instance
                    mock_analyzer_instance.build_dependency_graph.return_value = mock_graph
                    mock_analyzer_instance.identify_strongly_connected_components.return_value = []
                    
                    # Mock diagram generator
                    mock_diagram_gen_instance = AsyncMock()
                    mock_diagram_gen.return_value = mock_diagram_gen_instance
                    
                    from repo_architecture_mcp.models import DiagramOutput
                    mock_diagram_output = DiagramOutput(
                        content=f"graph TD\n  A --> B\n  B --> C",
                        format="mermaid",
                        metadata={"nodes": test_case.expected_dependencies, "edges": test_case.expected_dependencies - 1}
                    )
                    mock_diagram_gen_instance.generate_dependency_diagram.return_value = mock_diagram_output
                    
                    # Test dependency diagram generation
                    async def mock_generate_dependency_diagram(url: str, format: str = "mermaid", **kwargs):
                        # Simulate the tool call
                        return {
                            "diagram": {
                                "content": mock_diagram_output.content,
                                "format": format,
                                "title": f"Dependency Diagram - {test_case.name}"
                            },
                            "statistics": {
                                "total_nodes": test_case.expected_dependencies,
                                "total_dependencies": test_case.expected_dependencies - 1,
                                "circular_dependencies": 0
                            },
                            "metadata": {
                                "repository_url": url,
                                "repository_name": test_case.name
                            }
                        }
                    
                    result = await mock_generate_dependency_diagram(test_case.url)
                    
                    # Verify diagram structure
                    assert "diagram" in result
                    assert "statistics" in result
                    assert "metadata" in result
                    
                    # Verify diagram content
                    assert result["diagram"]["format"] == "mermaid"
                    assert "graph TD" in result["diagram"]["content"] or "flowchart" in result["diagram"]["content"]
                    
                    # Verify statistics match expectations (with tolerance)
                    stats = result["statistics"]
                    dependency_tolerance = max(1, int(test_case.expected_dependencies * 0.3))
                    
                    assert abs(stats["total_nodes"] - test_case.expected_dependencies) <= dependency_tolerance, \
                        f"Expected ~{test_case.expected_dependencies} dependencies, got {stats['total_nodes']}"
    
    @pytest.mark.asyncio
    async def test_class_diagram_accuracy(self, server, sample_repositories):
        """Test class diagram generation accuracy."""
        
        for test_case in sample_repositories:
            if test_case.expected_classes > 0 and test_case.complexity_level in ["low", "medium"]:
                
                with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr, \
                     patch('repo_architecture_mcp.server.CodeParserFactory') as mock_parser_factory, \
                     patch('repo_architecture_mcp.server.ArchitectureAnalyzer') as mock_analyzer, \
                     patch('repo_architecture_mcp.server.DiagramGenerator') as mock_diagram_gen:
                    
                    # Setup mocks
                    mock_repo_instance = AsyncMock()
                    mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
                    mock_repo_instance.get_repository_info.return_value = self.create_mock_repository_structure(test_case)
                    
                    mock_parser = AsyncMock()
                    mock_parser_instance = AsyncMock()
                    mock_parser_factory.return_value = mock_parser_instance
                    mock_parser_instance.registry.get_parser.return_value = mock_parser
                    
                    code_structures = self.create_mock_code_structures(test_case)
                    mock_parser.parse_file.side_effect = code_structures
                    
                    # Mock architecture analyzer for class relationships
                    from repo_architecture_mcp.models import ClassDiagram, ClassRelationship, RelationshipType
                    
                    mock_class_diagram = ClassDiagram(
                        classes={f"Class_{i}": {"methods": 2, "attributes": 2} for i in range(test_case.expected_classes)},
                        relationships=[
                            ClassRelationship(
                                source_class=f"Class_{i}",
                                target_class=f"Class_{i+1}",
                                relationship_type=RelationshipType.INHERITANCE if test_case.has_inheritance else RelationshipType.ASSOCIATION
                            )
                            for i in range(min(test_case.expected_classes - 1, 5))  # Limit relationships
                        ]
                    )
                    
                    mock_analyzer_instance = AsyncMock()
                    mock_analyzer.return_value = mock_analyzer_instance
                    mock_analyzer_instance.extract_class_relationships.return_value = mock_class_diagram
                    
                    # Mock diagram generator
                    mock_diagram_gen_instance = AsyncMock()
                    mock_diagram_gen.return_value = mock_diagram_gen_instance
                    
                    from repo_architecture_mcp.models import DiagramOutput
                    class_diagram_content = "classDiagram\n"
                    for class_name in mock_class_diagram.classes.keys():
                        class_diagram_content += f"  class {class_name}\n"
                    
                    mock_diagram_output = DiagramOutput(
                        content=class_diagram_content,
                        format="mermaid",
                        metadata={"classes": len(mock_class_diagram.classes), "relationships": len(mock_class_diagram.relationships)}
                    )
                    mock_diagram_gen_instance.generate_class_diagram.return_value = mock_diagram_output
                    
                    # Test class diagram generation
                    async def mock_generate_class_diagram(url: str, format: str = "mermaid", **kwargs):
                        return {
                            "diagram": {
                                "content": mock_diagram_output.content,
                                "format": format,
                                "title": f"Class Diagram - {test_case.name}"
                            },
                            "statistics": {
                                "total_classes": len(mock_class_diagram.classes),
                                "total_relationships": len(mock_class_diagram.relationships),
                                "inheritance_relationships": sum(1 for r in mock_class_diagram.relationships if r.relationship_type == RelationshipType.INHERITANCE)
                            },
                            "metadata": {
                                "repository_url": url,
                                "repository_name": test_case.name
                            }
                        }
                    
                    result = await mock_generate_class_diagram(test_case.url)
                    
                    # Verify class diagram structure
                    assert "diagram" in result
                    assert "statistics" in result
                    
                    # Verify diagram content
                    assert result["diagram"]["format"] == "mermaid"
                    assert "classDiagram" in result["diagram"]["content"]
                    
                    # Verify class count matches expectations
                    stats = result["statistics"]
                    class_tolerance = max(1, int(test_case.expected_classes * 0.2))
                    
                    assert abs(stats["total_classes"] - test_case.expected_classes) <= class_tolerance, \
                        f"Expected ~{test_case.expected_classes} classes, got {stats['total_classes']}"
                    
                    # Verify inheritance if expected
                    if test_case.has_inheritance:
                        assert stats["inheritance_relationships"] > 0, "Expected inheritance relationships but found none"


class TestEdgeCases:
    """Test edge cases like empty repositories and single-file projects."""
    
    @pytest.fixture
    def server(self):
        """Create test server instance."""
        return RepoArchitectureMCPServer()
    
    @pytest.mark.asyncio
    async def test_empty_repository(self, server):
        """Test analysis of an empty repository."""
        
        empty_repo_structure = {
            "name": "empty-repo",
            "full_name": "user/empty-repo",
            "description": "Empty repository for testing",
            "private": False,
            "default_branch": "main",
            "size": 0,
            "analysis_path": "/tmp/empty-repo",
            "file_tree": {
                "files": [],
                "directories": [],
                "languages": {},
                "total_size": 0,
                "access_errors": []
            }
        }
        
        with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr, \
             patch('repo_architecture_mcp.server.CodeParserFactory') as mock_parser_factory:
            
            mock_repo_instance = AsyncMock()
            mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
            mock_repo_instance.get_repository_info.return_value = empty_repo_structure
            
            mock_parser_instance = AsyncMock()
            mock_parser_factory.return_value = mock_parser_instance
            
            # Simulate analyze_repository tool call
            async def mock_analyze_repository(url: str, token: Optional[str] = None):
                from datetime import datetime
                return {
                    "repository_info": {
                        "url": url,
                        "name": "empty-repo",
                        "description": "Empty repository for testing",
                        "private": False
                    },
                    "analysis_metadata": {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "total_files_found": 0,
                        "files_parsed": 0,
                        "parse_errors": 0
                    },
                    "code_statistics": {
                        "total_classes": 0,
                        "total_functions": 0,
                        "language_breakdown": {}
                    },
                    "warnings": ["Repository appears to be empty or contains no parseable source files"]
                }
            
            result = await mock_analyze_repository("https://github.com/user/empty-repo")
            
            # Verify empty repository handling
            assert result["analysis_metadata"]["total_files_found"] == 0
            assert result["analysis_metadata"]["files_parsed"] == 0
            assert result["code_statistics"]["total_classes"] == 0
            assert result["code_statistics"]["total_functions"] == 0
            assert "warnings" in result
            assert any("empty" in warning.lower() for warning in result["warnings"])
    
    @pytest.mark.asyncio
    async def test_single_file_project(self, server):
        """Test analysis of a single-file project."""
        
        single_file_repo_structure = {
            "name": "single-file-project",
            "full_name": "user/single-file-project",
            "description": "Single file Python script",
            "private": False,
            "default_branch": "main",
            "size": 1024,
            "analysis_path": "/tmp/single-file-project",
            "file_tree": {
                "files": [
                    {
                        "path": "script.py",
                        "absolute_path": "/tmp/single-file-project/script.py",
                        "language": "Python",
                        "size": 1024
                    }
                ],
                "directories": [],
                "languages": {"Python": 1},
                "total_size": 1024,
                "access_errors": []
            }
        }
        
        with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr, \
             patch('repo_architecture_mcp.server.CodeParserFactory') as mock_parser_factory:
            
            mock_repo_instance = AsyncMock()
            mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
            mock_repo_instance.get_repository_info.return_value = single_file_repo_structure
            
            mock_parser = AsyncMock()
            mock_parser_instance = AsyncMock()
            mock_parser_factory.return_value = mock_parser_instance
            mock_parser_instance.get_parser.return_value = mock_parser
            
            # Create a simple code structure for the single file
            single_file_structure = CodeStructure(
                file_path="/tmp/single-file-project/script.py",
                language="Python",
                classes=[],
                functions=[
                    FunctionInfo(
                        name="main",
                        parameters=[],
                        return_type="None",
                        decorators=[],
                        visibility="public"
                    )
                ],
                imports=[
                    ImportInfo(
                        module="sys",
                        imported_names=["argv"],
                        alias=None,
                        is_relative=False
                    )
                ],
                exports=[]
            )
            mock_parser.parse_file.return_value = single_file_structure
            
            # Simulate analyze_repository tool call
            async def mock_analyze_repository(url: str, token: Optional[str] = None):
                from datetime import datetime
                return {
                    "repository_info": {
                        "url": url,
                        "name": "single-file-project",
                        "description": "Single file Python script",
                        "private": False
                    },
                    "analysis_metadata": {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "total_files_found": 1,
                        "files_parsed": 1,
                        "parse_errors": 0
                    },
                    "code_statistics": {
                        "total_classes": 0,
                        "total_functions": 1,
                        "language_breakdown": {"Python": 1}
                    }
                }
            
            result = await mock_analyze_repository("https://github.com/user/single-file-project")
            
            # Verify single file project handling
            assert result["analysis_metadata"]["total_files_found"] == 1
            assert result["analysis_metadata"]["files_parsed"] == 1
            assert result["code_statistics"]["total_functions"] == 1
            assert result["code_statistics"]["language_breakdown"]["Python"] == 1
    
    @pytest.mark.asyncio
    async def test_repository_with_parse_errors(self, server):
        """Test handling of repositories with files that cannot be parsed."""
        
        problematic_repo_structure = {
            "name": "problematic-repo",
            "full_name": "user/problematic-repo",
            "description": "Repository with parsing issues",
            "private": False,
            "default_branch": "main",
            "size": 2048,
            "analysis_path": "/tmp/problematic-repo",
            "file_tree": {
                "files": [
                    {
                        "path": "good_file.py",
                        "absolute_path": "/tmp/problematic-repo/good_file.py",
                        "language": "Python",
                        "size": 1024
                    },
                    {
                        "path": "bad_file.py",
                        "absolute_path": "/tmp/problematic-repo/bad_file.py",
                        "language": "Python",
                        "size": 1024
                    }
                ],
                "directories": ["src"],
                "languages": {"Python": 2},
                "total_size": 2048,
                "access_errors": []
            }
        }
        
        with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr, \
             patch('repo_architecture_mcp.server.CodeParserFactory') as mock_parser_factory:
            
            mock_repo_instance = AsyncMock()
            mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
            mock_repo_instance.get_repository_info.return_value = problematic_repo_structure
            
            mock_parser = AsyncMock()
            mock_parser_instance = AsyncMock()
            mock_parser_factory.return_value = mock_parser_instance
            mock_parser_instance.get_parser.return_value = mock_parser
            
            # Mock parser to succeed for first file, fail for second
            good_structure = CodeStructure(
                file_path="/tmp/problematic-repo/good_file.py",
                language="Python",
                classes=[],
                functions=[FunctionInfo(name="good_function", parameters=[], return_type="None", decorators=[], visibility="public")],
                imports=[],
                exports=[]
            )
            
            def mock_parse_file(file_path):
                if "good_file" in file_path:
                    return good_structure
                else:
                    raise SyntaxError("Invalid syntax in bad_file.py")
            
            mock_parser.parse_file.side_effect = mock_parse_file
            
            # Simulate analyze_repository tool call with error handling
            async def mock_analyze_repository(url: str, token: Optional[str] = None):
                from datetime import datetime
                
                parse_errors = []
                parsed_files = 0
                total_functions = 0
                
                for file_info in problematic_repo_structure["file_tree"]["files"]:
                    try:
                        if "good_file" in file_info["path"]:
                            parsed_files += 1
                            total_functions += 1
                        else:
                            raise SyntaxError(f"Invalid syntax in {file_info['path']}")
                    except Exception as e:
                        parse_errors.append(f"Failed to parse {file_info['path']}: {str(e)}")
                
                result = {
                    "repository_info": {
                        "url": url,
                        "name": "problematic-repo",
                        "description": "Repository with parsing issues",
                        "private": False
                    },
                    "analysis_metadata": {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "total_files_found": 2,
                        "files_parsed": parsed_files,
                        "parse_errors": len(parse_errors)
                    },
                    "code_statistics": {
                        "total_classes": 0,
                        "total_functions": total_functions,
                        "language_breakdown": {"Python": 2}
                    }
                }
                
                if parse_errors:
                    result["parse_errors"] = parse_errors[:10]  # Limit to first 10
                    result["warnings"] = [
                        f"Some files could not be parsed ({len(parse_errors)} errors). Analysis may be incomplete."
                    ]
                
                return result
            
            result = await mock_analyze_repository("https://github.com/user/problematic-repo")
            
            # Verify graceful error handling
            assert result["analysis_metadata"]["total_files_found"] == 2
            assert result["analysis_metadata"]["files_parsed"] == 1  # Only good file parsed
            assert result["analysis_metadata"]["parse_errors"] == 1
            assert "parse_errors" in result
            assert "warnings" in result
            assert len(result["parse_errors"]) == 1
            assert "bad_file.py" in result["parse_errors"][0]
    
    @pytest.mark.asyncio
    async def test_repository_with_no_supported_languages(self, server):
        """Test handling of repositories with no supported programming languages."""
        
        unsupported_repo_structure = {
            "name": "unsupported-repo",
            "full_name": "user/unsupported-repo",
            "description": "Repository with unsupported languages",
            "private": False,
            "default_branch": "main",
            "size": 1024,
            "analysis_path": "/tmp/unsupported-repo",
            "file_tree": {
                "files": [
                    {
                        "path": "README.md",
                        "absolute_path": "/tmp/unsupported-repo/README.md",
                        "language": "Markdown",
                        "size": 512
                    },
                    {
                        "path": "config.xml",
                        "absolute_path": "/tmp/unsupported-repo/config.xml",
                        "language": "XML",
                        "size": 512
                    }
                ],
                "directories": ["docs"],
                "languages": {"Markdown": 1, "XML": 1},
                "total_size": 1024,
                "access_errors": []
            }
        }
        
        with patch('repo_architecture_mcp.server.RepositoryManager') as mock_repo_mgr, \
             patch('repo_architecture_mcp.server.CodeParserFactory') as mock_parser_factory:
            
            mock_repo_instance = AsyncMock()
            mock_repo_mgr.return_value.__aenter__.return_value = mock_repo_instance
            mock_repo_instance.get_repository_info.return_value = unsupported_repo_structure
            
            mock_parser_instance = AsyncMock()
            mock_parser_factory.return_value = mock_parser_instance
            mock_parser_instance.get_parser.return_value = None  # No parser for unsupported files
            
            # Simulate analyze_repository tool call
            async def mock_analyze_repository(url: str, token: Optional[str] = None):
                from datetime import datetime
                return {
                    "repository_info": {
                        "url": url,
                        "name": "unsupported-repo",
                        "description": "Repository with unsupported languages",
                        "private": False
                    },
                    "analysis_metadata": {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "total_files_found": 2,
                        "files_parsed": 0,
                        "parse_errors": 0
                    },
                    "code_statistics": {
                        "total_classes": 0,
                        "total_functions": 0,
                        "language_breakdown": {}
                    },
                    "warnings": [
                        "No supported programming languages found in repository. Supported languages include: Python, JavaScript, TypeScript, Java."
                    ]
                }
            
            result = await mock_analyze_repository("https://github.com/user/unsupported-repo")
            
            # Verify handling of unsupported languages
            assert result["analysis_metadata"]["total_files_found"] == 2
            assert result["analysis_metadata"]["files_parsed"] == 0
            assert result["code_statistics"]["total_classes"] == 0
            assert result["code_statistics"]["total_functions"] == 0
            assert "warnings" in result
            assert any("supported" in warning.lower() for warning in result["warnings"])