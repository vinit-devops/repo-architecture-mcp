"""Tests for architecture analyzer functionality."""

import pytest
import networkx as nx
from pathlib import Path

from src.repo_architecture_mcp.architecture_analyzer import ArchitectureAnalyzer, ClassRelationship
from src.repo_architecture_mcp.models import (
    RepositoryStructure, CodeStructure, ClassInfo, ImportInfo, 
    MethodInfo, FunctionInfo, RelationType, AttributeInfo, ParameterInfo, Visibility
)


class TestArchitectureAnalyzer:
    """Test cases for ArchitectureAnalyzer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = ArchitectureAnalyzer()
    
    def test_build_dependency_graph_simple(self):
        """Test building dependency graph with simple module structure."""
        # Create test repository structure
        repo_structure = RepositoryStructure(
            repository_path="/test/repo",
            files=[
                CodeStructure(
                    file_path="src/main.py",
                    language="python",
                    imports=[
                        ImportInfo(module="utils", imported_names=["helper_func"]),
                        ImportInfo(module="config", imported_names=["settings"])
                    ],
                    functions=[
                        FunctionInfo(name="main", line_number=10)
                    ]
                ),
                CodeStructure(
                    file_path="src/utils.py", 
                    language="python",
                    imports=[
                        ImportInfo(module="os", imported_names=["path"])
                    ],
                    functions=[
                        FunctionInfo(name="helper_func", line_number=5)
                    ]
                ),
                CodeStructure(
                    file_path="src/config.py",
                    language="python",
                    global_variables=[],
                    functions=[],
                    classes=[]
                )
            ]
        )
        
        # Build dependency graph
        graph = self.analyzer.build_dependency_graph(repo_structure)
        
        # Verify graph structure
        assert isinstance(graph, nx.DiGraph)
        assert graph.number_of_nodes() >= 3  # At least our 3 modules
        assert graph.number_of_edges() >= 2  # At least 2 internal dependencies
        
        # Check specific nodes exist
        assert "main" in graph.nodes
        assert "utils" in graph.nodes  
        assert "config" in graph.nodes
        
        # Check dependencies
        assert graph.has_edge("main", "utils")
        assert graph.has_edge("main", "config")
        
        # Check node attributes
        main_node = graph.nodes["main"]
        assert main_node["file_path"] == "src/main.py"
        assert main_node["language"] == "python"
        assert main_node["functions"] == 1
        
        # Check edge attributes
        edge_data = graph.edges["main", "utils"]
        assert edge_data["relation_type"] == RelationType.IMPORT.value
        assert edge_data["strength"] >= 1
    
    def test_build_dependency_graph_with_inheritance(self):
        """Test dependency graph with class inheritance relationships."""
        repo_structure = RepositoryStructure(
            repository_path="/test/repo",
            files=[
                CodeStructure(
                    file_path="src/base.py",
                    language="python", 
                    classes=[
                        ClassInfo(name="BaseClass", line_number=5)
                    ]
                ),
                CodeStructure(
                    file_path="src/derived.py",
                    language="python",
                    imports=[
                        ImportInfo(module="base", imported_names=["BaseClass"])
                    ],
                    classes=[
                        ClassInfo(
                            name="DerivedClass", 
                            inheritance=["BaseClass"],
                            line_number=10
                        )
                    ]
                )
            ]
        )
        
        graph = self.analyzer.build_dependency_graph(repo_structure)
        
        # Should have both import and inheritance edges
        edges = list(graph.edges(data=True))
        relation_types = [edge[2]["relation_type"] for edge in edges]
        
        assert RelationType.IMPORT.value in relation_types
        
        # Check that inheritance information is captured in the edge
        import_edges = [edge for edge in edges if edge[2]["relation_type"] == RelationType.IMPORT.value]
        assert len(import_edges) > 0
        
        # Find the edge that has inheritance information
        inheritance_edge = None
        for edge in import_edges:
            if edge[2].get("has_inheritance", False):
                inheritance_edge = edge
                break
        
        assert inheritance_edge is not None, "Should have an edge with inheritance information"
        assert inheritance_edge[2]["inheritance_strength"] == 3
        assert inheritance_edge[2]["class_name"] == "DerivedClass"
        assert inheritance_edge[2]["parent_class"] == "BaseClass"
    
    def test_identify_strongly_connected_components(self):
        """Test identification of strongly connected components."""
        # Create a graph with circular dependencies
        graph = nx.DiGraph()
        graph.add_edges_from([
            ("A", "B"), ("B", "C"), ("C", "A"),  # Circular dependency
            ("D", "E"), ("E", "F"),              # Linear dependency
            ("G", "G")                           # Self-loop
        ])
        
        sccs = self.analyzer.identify_strongly_connected_components(graph)
        
        # Should find the circular dependency
        assert len(sccs) >= 3
        
        # Largest SCC should be the 3-node cycle
        largest_scc = max(sccs, key=len)
        assert len(largest_scc) == 3
        assert set(largest_scc) == {"A", "B", "C"}
    
    def test_get_module_name(self):
        """Test module name extraction from file paths."""
        test_cases = [
            ("src/main.py", "main"),
            ("src/utils/helper.py", "utils.helper"),
            ("lib/package/module.py", "package.module"),
            ("app/models/__init__.py", "models"),
            ("service.js", "service"),
            ("com/example/Service.java", "com.example.Service")
        ]
        
        for file_path, expected in test_cases:
            result = self.analyzer._get_module_name(file_path)
            assert result == expected, f"Expected {expected}, got {result} for {file_path}"
    
    def test_resolve_import_targets_absolute(self):
        """Test resolving absolute import targets."""
        import_info = ImportInfo(module="os.path", imported_names=["join"])
        module_to_file = {"main": "src/main.py"}
        
        targets = self.analyzer._resolve_import_targets(import_info, "src/main.py", module_to_file)
        
        assert targets == ["os.path"]
    
    def test_resolve_import_targets_relative(self):
        """Test resolving relative import targets."""
        import_info = ImportInfo(module=".utils", imported_names=["helper"], is_relative=True)
        module_to_file = {"package.main": "src/package/main.py", "package.utils": "src/package/utils.py"}
        
        targets = self.analyzer._resolve_import_targets(import_info, "src/package/main.py", module_to_file)
        
        assert "package.utils" in targets
    
    def test_calculate_import_strength(self):
        """Test import strength calculation."""
        # Simple import
        simple_import = ImportInfo(module="os", imported_names=["path"])
        assert self.analyzer._calculate_import_strength(simple_import) == 2  # 1 + 1 name
        
        # Multiple imports
        multi_import = ImportInfo(module="utils", imported_names=["func1", "func2", "func3"])
        assert self.analyzer._calculate_import_strength(multi_import) == 4  # 1 + 3 names
        
        # Star import
        star_import = ImportInfo(module="package", imported_names=["*"])
        assert self.analyzer._calculate_import_strength(star_import) == 7  # 1 + 1 name + 5 star bonus
    
    def test_get_import_type(self):
        """Test import type classification."""
        # Relative import
        relative = ImportInfo(module=".utils", is_relative=True)
        assert self.analyzer._get_import_type(relative) == "relative"
        
        # Star import
        star = ImportInfo(module="package", imported_names=["*"])
        assert self.analyzer._get_import_type(star) == "star"
        
        # Selective import
        selective = ImportInfo(module="os", imported_names=["path", "environ"])
        assert self.analyzer._get_import_type(selective) == "selective"
        
        # Module import
        module = ImportInfo(module="json", imported_names=[])
        assert self.analyzer._get_import_type(module) == "module"
    
    def test_add_graph_metrics(self):
        """Test addition of graph metrics."""
        graph = nx.DiGraph()
        graph.add_edges_from([("A", "B"), ("B", "C"), ("C", "D")])
        
        self.analyzer._add_graph_metrics(graph)
        
        # Check graph-level metrics
        assert graph.graph["total_nodes"] == 4
        assert graph.graph["total_edges"] == 3
        assert "density" in graph.graph
        assert "is_dag" in graph.graph
        assert graph.graph["is_dag"] is True  # No cycles
        
        # Check node-level metrics
        for node in graph.nodes():
            node_data = graph.nodes[node]
            assert "in_degree" in node_data
            assert "out_degree" in node_data
            assert "total_degree" in node_data
    
    def test_empty_repository(self):
        """Test handling of empty repository."""
        repo_structure = RepositoryStructure(repository_path="/empty", files=[])
        
        graph = self.analyzer.build_dependency_graph(repo_structure)
        
        assert graph.number_of_nodes() == 0
        assert graph.number_of_edges() == 0
    
    def test_external_dependencies(self):
        """Test handling of external dependencies."""
        repo_structure = RepositoryStructure(
            repository_path="/test/repo",
            files=[
                CodeStructure(
                    file_path="src/main.py",
                    language="python",
                    imports=[
                        ImportInfo(module="requests", imported_names=["get"]),  # External
                        ImportInfo(module="json", imported_names=["loads"])     # External
                    ]
                )
            ]
        )
        
        graph = self.analyzer.build_dependency_graph(repo_structure)
        
        # Should have main module plus external dependencies
        assert "main" in graph.nodes
        assert "requests" in graph.nodes
        assert "json" in graph.nodes
        
        # External nodes should be marked
        assert graph.nodes["requests"].get("external", False) is True
        assert graph.nodes["json"].get("external", False) is True
        
        # Should have edges to external dependencies
        assert graph.has_edge("main", "requests")
        assert graph.has_edge("main", "json")
    
    def test_extract_class_relationships_inheritance(self):
        """Test extraction of inheritance relationships."""
        repo_structure = RepositoryStructure(
            repository_path="/test/repo",
            files=[
                CodeStructure(
                    file_path="src/animals/base.py",
                    language="python",
                    classes=[
                        ClassInfo(name="Animal", line_number=5)
                    ]
                ),
                CodeStructure(
                    file_path="src/animals/dog.py",
                    language="python",
                    imports=[
                        ImportInfo(module="base", imported_names=["Animal"])
                    ],
                    classes=[
                        ClassInfo(
                            name="Dog",
                            inheritance=["Animal"],
                            line_number=10
                        )
                    ]
                )
            ]
        )
        
        class_diagram = self.analyzer.extract_class_relationships(repo_structure)
        
        # Check classes are captured
        assert "animals.Animal" in class_diagram.classes
        assert "animals.Dog" in class_diagram.classes
        
        # Check packages
        assert "animals" in class_diagram.packages
        assert "animals.Animal" in class_diagram.packages["animals"]
        assert "animals.Dog" in class_diagram.packages["animals"]
        
        # Check inheritance relationship
        inheritance_rels = [rel for rel in class_diagram.relationships 
                           if rel.relationship_type == RelationType.INHERITANCE]
        assert len(inheritance_rels) == 1
        
        rel = inheritance_rels[0]
        assert rel.source_class == "animals.Dog"
        assert rel.target_class == "animals.Animal"
        assert rel.strength == 5  # Inheritance has highest strength
    
    def test_extract_class_relationships_composition(self):
        """Test extraction of composition relationships."""
        repo_structure = RepositoryStructure(
            repository_path="/test/repo",
            files=[
                CodeStructure(
                    file_path="src/models/user.py",
                    language="python",
                    classes=[
                        ClassInfo(name="User", line_number=5)
                    ]
                ),
                CodeStructure(
                    file_path="src/models/account.py",
                    language="python",
                    imports=[
                        ImportInfo(module="user", imported_names=["User"])
                    ],
                    classes=[
                        ClassInfo(
                            name="Account",
                            attributes=[
                                AttributeInfo(name="_owner", type_hint="User"),
                                AttributeInfo(name="users", type_hint="List[User]")
                            ],
                            line_number=10
                        )
                    ]
                )
            ]
        )
        
        class_diagram = self.analyzer.extract_class_relationships(repo_structure)
        
        # Check composition relationships
        composition_rels = [rel for rel in class_diagram.relationships 
                           if rel.relationship_type == RelationType.COMPOSITION]
        aggregation_rels = [rel for rel in class_diagram.relationships 
                           if rel.relationship_type == RelationType.AGGREGATION]
        
        # Should have both composition and aggregation
        assert len(composition_rels) >= 1  # _owner (private attribute)
        assert len(aggregation_rels) >= 1  # users (collection)
        
        # Check composition relationship
        comp_rel = composition_rels[0]
        assert comp_rel.source_class == "models.Account"
        assert comp_rel.target_class == "models.User"
        assert comp_rel.strength == 4  # Composition strength
    
    def test_extract_class_relationships_dependency(self):
        """Test extraction of dependency relationships from method parameters."""
        repo_structure = RepositoryStructure(
            repository_path="/test/repo",
            files=[
                CodeStructure(
                    file_path="src/services/logger.py",
                    language="python",
                    classes=[
                        ClassInfo(name="Logger", line_number=5)
                    ]
                ),
                CodeStructure(
                    file_path="src/services/processor.py",
                    language="python",
                    imports=[
                        ImportInfo(module="logger", imported_names=["Logger"])
                    ],
                    classes=[
                        ClassInfo(
                            name="Processor",
                            methods=[
                                MethodInfo(
                                    name="process",
                                    parameters=[
                                        ParameterInfo(name="self"),
                                        ParameterInfo(name="logger", type_hint="Logger")
                                    ],
                                    line_number=15
                                )
                            ],
                            line_number=10
                        )
                    ]
                )
            ]
        )
        
        class_diagram = self.analyzer.extract_class_relationships(repo_structure)
        
        # Check dependency relationships
        dependency_rels = [rel for rel in class_diagram.relationships 
                          if rel.relationship_type == RelationType.DEPENDENCY]
        assert len(dependency_rels) >= 1
        
        dep_rel = dependency_rels[0]
        assert dep_rel.source_class == "services.Processor"
        assert dep_rel.target_class == "services.Logger"
        assert dep_rel.strength == 2  # Dependency strength
        assert "method process parameter logger" in dep_rel.context
    
    def test_get_package_name(self):
        """Test package name extraction from file paths."""
        test_cases = [
            ("src/models/user.py", "models"),
            ("src/services/auth/handler.py", "services.auth"),
            ("main.py", ""),
            ("lib/utils/helper.py", "utils")
        ]
        
        for file_path, expected in test_cases:
            result = self.analyzer._get_package_name(file_path)
            assert result == expected, f"Expected {expected}, got {result} for {file_path}"
    
    def test_extract_class_from_type_hint(self):
        """Test class extraction from type hints."""
        # Create a simple file structure for context
        file_structure = CodeStructure(
            file_path="src/test.py",
            language="python",
            imports=[
                ImportInfo(module="models", imported_names=["User"])
            ]
        )
        
        all_classes = {
            "models.User": ClassInfo(name="User"),
            "services.Logger": ClassInfo(name="Logger")
        }
        
        test_cases = [
            ("User", "models.User"),
            ("List[User]", "models.User"),
            ("Optional[User]", "models.User"),
            ("Union[User, None]", "models.User"),
            ("str", None),  # Built-in type
            ("int", None),  # Built-in type
        ]
        
        for type_hint, expected in test_cases:
            result = self.analyzer._extract_class_from_type_hint(type_hint, file_structure, all_classes)
            assert result == expected, f"Expected {expected}, got {result} for {type_hint}"
    
    def test_determine_composition_type(self):
        """Test composition vs aggregation determination."""
        test_cases = [
            ("_owner", "User", RelationType.COMPOSITION),      # Private attribute
            ("internal_data", "Data", RelationType.COMPOSITION),  # Internal naming
            ("users", "List[User]", RelationType.AGGREGATION),    # Collection
            ("user_ref", "User", RelationType.AGGREGATION),       # Reference naming
            ("owner", "User", RelationType.COMPOSITION),          # Default to composition
        ]
        
        for attr_name, type_hint, expected in test_cases:
            result = self.analyzer._determine_composition_type(attr_name, type_hint)
            assert result == expected, f"Expected {expected}, got {result} for {attr_name}:{type_hint}"
    
    def test_calculate_relationship_strength(self):
        """Test relationship strength calculation."""
        test_cases = [
            (RelationType.INHERITANCE, 5),
            (RelationType.COMPOSITION, 4),
            (RelationType.AGGREGATION, 3),
            (RelationType.DEPENDENCY, 2),
            (RelationType.IMPORT, 1),
        ]
        
        for rel_type, expected_strength in test_cases:
            result = self.analyzer._calculate_relationship_strength(rel_type)
            assert result == expected_strength, f"Expected {expected_strength}, got {result} for {rel_type}"
    
    def test_analyze_data_flow_basic(self):
        """Test basic data flow analysis."""
        repo_structure = RepositoryStructure(
            repository_path="/test/repo",
            files=[
                CodeStructure(
                    file_path="src/services/user_service.py",
                    language="python",
                    imports=[
                        ImportInfo(module="requests", imported_names=["get", "post"])
                    ],
                    functions=[
                        FunctionInfo(
                            name="get_user",
                            parameters=[
                                ParameterInfo(name="user_id", type_hint="int")
                            ],
                            return_type="User",
                            line_number=10
                        ),
                        FunctionInfo(
                            name="save_user",
                            parameters=[
                                ParameterInfo(name="user", type_hint="User")
                            ],
                            line_number=20
                        )
                    ],
                    classes=[
                        ClassInfo(
                            name="UserRepository",
                            methods=[
                                MethodInfo(
                                    name="find_by_id",
                                    parameters=[
                                        ParameterInfo(name="self"),
                                        ParameterInfo(name="user_id", type_hint="int")
                                    ],
                                    return_type="User",
                                    line_number=30
                                )
                            ],
                            line_number=25
                        )
                    ]
                )
            ]
        )
        
        dfd = self.analyzer.analyze_data_flow(repo_structure)
        
        # Check that processes were identified
        assert len(dfd.processes) >= 3  # get_user, save_user, find_by_id
        assert "services.user_service.get_user" in dfd.processes
        assert "services.user_service.save_user" in dfd.processes
        assert "services.user_service.UserRepository.find_by_id" in dfd.processes
        
        # Check that external entities were identified
        assert len(dfd.external_entities) >= 1  # requests -> HTTP API
        external_entity_names = [node.name for node in dfd.nodes.values() if node.node_type == "external_entity"]
        assert any("HTTP API" in name for name in external_entity_names)
        
        # Check that data stores were identified
        assert len(dfd.data_stores) >= 1  # UserRepository
        assert "services.user_service.UserRepository" in dfd.data_stores
        
        # Check that some data flows were created
        assert len(dfd.flows) > 0
    
    def test_identify_external_entities(self):
        """Test identification of external entities from imports."""
        repo_structure = RepositoryStructure(
            repository_path="/test/repo",
            files=[
                CodeStructure(
                    file_path="src/main.py",
                    language="python",
                    imports=[
                        ImportInfo(module="requests", imported_names=["get"]),
                        ImportInfo(module="sqlite3", imported_names=["connect"]),
                        ImportInfo(module="boto3", imported_names=["client"]),
                        ImportInfo(module="internal_module", imported_names=["func"])  # Should be ignored
                    ]
                )
            ]
        )
        
        from src.repo_architecture_mcp.architecture_analyzer import DataFlowDiagram
        dfd = DataFlowDiagram()
        
        self.analyzer._identify_external_entities(repo_structure, dfd)
        
        # Check that external entities were identified
        assert len(dfd.external_entities) >= 3
        
        entity_names = [node.name for node in dfd.nodes.values() if node.node_type == "external_entity"]
        assert any("HTTP API" in name for name in entity_names)
        assert any("SQLite Database" in name for name in entity_names)
        assert any("AWS Services" in name for name in entity_names)
    
    def test_identify_data_stores(self):
        """Test identification of data stores from class names."""
        repo_structure = RepositoryStructure(
            repository_path="/test/repo",
            files=[
                CodeStructure(
                    file_path="src/repositories/user_repository.py",
                    language="python",
                    classes=[
                        ClassInfo(name="UserRepository", line_number=5),
                        ClassInfo(name="OrderDAO", line_number=15),
                        ClassInfo(name="ProductModel", line_number=25),
                        ClassInfo(name="CacheStore", line_number=35),
                        ClassInfo(name="RegularClass", line_number=45)  # Should not be identified
                    ]
                )
            ]
        )
        
        from src.repo_architecture_mcp.architecture_analyzer import DataFlowDiagram
        dfd = DataFlowDiagram()
        
        self.analyzer._identify_data_stores(repo_structure, dfd)
        
        # Check that data stores were identified
        assert len(dfd.data_stores) >= 4
        assert "repositories.user_repository.UserRepository" in dfd.data_stores
        assert "repositories.user_repository.OrderDAO" in dfd.data_stores
        assert "repositories.user_repository.ProductModel" in dfd.data_stores
        assert "repositories.user_repository.CacheStore" in dfd.data_stores
        assert "repositories.user_repository.RegularClass" not in dfd.data_stores
    
    def test_infer_data_flows_from_function_name(self):
        """Test data flow inference from function names."""
        from src.repo_architecture_mcp.architecture_analyzer import DataFlowDiagram, DataFlowNode
        
        dfd = DataFlowDiagram()
        
        # Add a data store
        store_node = DataFlowNode(name="test.UserStore", node_type="data_store")
        dfd.nodes["test.UserStore"] = store_node
        dfd.data_stores.add("test.UserStore")
        
        # Test read function
        read_func = FunctionInfo(name="get_user_by_id", line_number=10)
        self.analyzer._infer_data_flows_from_function_name("test.get_user_by_id", read_func, dfd)
        
        # Should create flow from data store to function
        read_flows = [flow for flow in dfd.flows if flow.target == "test.get_user_by_id"]
        assert len(read_flows) >= 1
        assert read_flows[0].source == "test.UserStore"
        
        # Test write function
        write_func = FunctionInfo(name="save_user", line_number=20)
        self.analyzer._infer_data_flows_from_function_name("test.save_user", write_func, dfd)
        
        # Should create flow from function to data store
        write_flows = [flow for flow in dfd.flows if flow.source == "test.save_user"]
        assert len(write_flows) >= 1
        assert write_flows[0].target == "test.UserStore"
    
    def test_functions_likely_related(self):
        """Test function-store relationship detection."""
        test_cases = [
            ("get_user", "UserRepository", True),
            ("save_order", "OrderStore", True),
            ("fetch_product", "ProductDAO", True),
            ("get_user", "OrderRepository", False),
            ("process_data", "DataStore", True),
            ("random_function", "UserRepository", False),
        ]
        
        for func_name, store_name, expected in test_cases:
            result = self.analyzer._functions_likely_related(func_name, store_name)
            assert result == expected, f"Expected {expected}, got {result} for {func_name} vs {store_name}"
    
    def test_infer_data_description_from_function_name(self):
        """Test data description inference from function names."""
        test_cases = [
            ("get_user_by_id", "user by id data"),
            ("save_order", "order data"),
            ("fetch_product_details", "product details data"),
            ("create", "data"),  # No meaningful terms
            ("update_user_profile", "user profile data"),
        ]
        
        for func_name, expected in test_cases:
            result = self.analyzer._infer_data_description_from_function_name(func_name)
            assert result == expected, f"Expected {expected}, got {result} for {func_name}"
    
    def test_infer_data_description_from_type(self):
        """Test data description inference from type hints."""
        test_cases = [
            ("User", "user_param", "User data"),
            ("List[Order]", "orders", "Order data"),
            ("Optional[Product]", "product", "Product data"),
            ("str", "name", None),  # Basic type
            ("int", "count", None),  # Basic type
            ("CustomClass", "obj", "CustomClass data"),
        ]
        
        for type_hint, param_name, expected in test_cases:
            result = self.analyzer._infer_data_description_from_type(type_hint, param_name)
            assert result == expected, f"Expected {expected}, got {result} for {type_hint}:{param_name}"