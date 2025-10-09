"""Architecture analysis engine for extracting relationships and patterns from code."""

import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import networkx as nx

from .models import (
    RepositoryStructure, CodeStructure, ClassInfo, ImportInfo,
    DependencyRelation, RelationType, MethodInfo, FunctionInfo
)

logger = logging.getLogger(__name__)


@dataclass
class ClassRelationship:
    """Represents a relationship between two classes."""
    source_class: str
    target_class: str
    relationship_type: RelationType
    strength: int = 1
    source_file: Optional[str] = None
    target_file: Optional[str] = None
    line_number: Optional[int] = None
    context: Optional[str] = None


@dataclass
class ClassDiagram:
    """Data structure representing UML-style class relationships."""
    classes: Dict[str, ClassInfo] = field(default_factory=dict)
    relationships: List[ClassRelationship] = field(default_factory=list)
    packages: Dict[str, List[str]] = field(default_factory=dict)  # package -> class names
    external_dependencies: Set[str] = field(default_factory=set)


@dataclass
class DataFlowNode:
    """Represents a node in a data flow diagram."""
    name: str
    node_type: str  # 'external_entity', 'process', 'data_store'
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    description: Optional[str] = None


@dataclass
class DataFlow:
    """Represents a data flow between nodes."""
    source: str
    target: str
    data_description: str
    flow_type: str = "data"  # 'data', 'control', 'event'


@dataclass
class DataFlowDiagram:
    """Data structure representing data flow diagram following DFD notation."""
    nodes: Dict[str, DataFlowNode] = field(default_factory=dict)
    flows: List[DataFlow] = field(default_factory=list)
    external_entities: Set[str] = field(default_factory=set)
    processes: Set[str] = field(default_factory=set)
    data_stores: Set[str] = field(default_factory=set)


class ArchitectureAnalyzer:
    """Analyzes code structure and extracts architectural patterns."""
    
    def __init__(self):
        """Initialize the architecture analyzer."""
        self.logger = logging.getLogger(__name__)
    
    def build_dependency_graph(self, repo_structure: RepositoryStructure) -> nx.DiGraph:
        """Build directed graph of module dependencies.
        
        Args:
            repo_structure: Parsed repository structure
            
        Returns:
            NetworkX directed graph representing module dependencies
        """
        self.logger.info("Building dependency graph from repository structure")
        
        # Create directed graph
        graph = nx.DiGraph()
        
        # Track all modules and their file paths
        module_to_file: Dict[str, str] = {}
        file_to_module: Dict[str, str] = {}
        
        # First pass: Add all files as nodes and map modules
        for file_structure in repo_structure.files:
            file_path = file_structure.file_path
            module_name = self._get_module_name(file_path)
            

            
            # Add file as node with metadata
            graph.add_node(module_name, 
                          file_path=file_path,
                          language=file_structure.language,
                          classes=len(file_structure.classes),
                          functions=len(file_structure.functions),
                          imports=len(file_structure.imports))
            
            module_to_file[module_name] = file_path
            file_to_module[file_path] = module_name
        
        # Second pass: Add dependency edges based on imports
        for file_structure in repo_structure.files:
            source_module = self._get_module_name(file_structure.file_path)
            
            for import_info in file_structure.imports:
                target_modules = self._resolve_import_targets(
                    import_info, file_structure.file_path, module_to_file
                )
                
                for target_module in target_modules:
                    if target_module in graph.nodes:
                        # Internal dependency
                        strength = self._calculate_import_strength(import_info)
                        graph.add_edge(source_module, target_module,
                                     relation_type=RelationType.IMPORT.value,
                                     strength=strength,
                                     import_type=self._get_import_type(import_info),
                                     line_number=import_info.line_number)
                    else:
                        # External dependency - add as external node
                        if not target_module.startswith('.'):  # Skip relative imports to non-existent files
                            graph.add_node(target_module, 
                                         external=True,
                                         import_type=self._get_import_type(import_info))
                            strength = self._calculate_import_strength(import_info)
                            graph.add_edge(source_module, target_module,
                                         relation_type=RelationType.IMPORT.value,
                                         strength=strength,
                                         external=True,
                                         line_number=import_info.line_number)
        
        # Third pass: Add class inheritance relationships
        for file_structure in repo_structure.files:
            source_module = self._get_module_name(file_structure.file_path)
            
            for class_info in file_structure.classes:
                for parent_class in class_info.inheritance:
                    # Try to resolve parent class to a module
                    parent_module = self._resolve_class_to_module(
                        parent_class, file_structure, module_to_file
                    )
                    
                    if parent_module and parent_module in graph.nodes:
                        # Check if there's already an edge between these modules
                        if graph.has_edge(source_module, parent_module):
                            # Update existing edge to include inheritance info
                            edge_data = graph.edges[source_module, parent_module]
                            edge_data['has_inheritance'] = True
                            edge_data['inheritance_strength'] = 3
                            edge_data['class_name'] = class_info.name
                            edge_data['parent_class'] = parent_class
                            # Increase overall strength
                            edge_data['strength'] = max(edge_data.get('strength', 1), 3)
                        else:
                            # Add new inheritance edge
                            graph.add_edge(source_module, parent_module,
                                         relation_type=RelationType.INHERITANCE.value,
                                         strength=3,  # Higher strength for inheritance
                                         class_name=class_info.name,
                                         parent_class=parent_class,
                                         line_number=class_info.line_number)
        
        # Calculate graph metrics
        self._add_graph_metrics(graph)
        
        self.logger.info(f"Built dependency graph with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges")
        return graph
    
    def identify_strongly_connected_components(self, graph: nx.DiGraph) -> List[List[str]]:
        """Identify strongly connected components in the dependency graph.
        
        Args:
            graph: NetworkX directed graph
            
        Returns:
            List of strongly connected components (each component is a list of node names)
        """
        self.logger.info("Identifying strongly connected components")
        
        # Find strongly connected components
        sccs = list(nx.strongly_connected_components(graph))
        
        # Sort by size (largest first) and convert to lists
        sccs_sorted = sorted([list(scc) for scc in sccs], key=len, reverse=True)
        
        # Log information about significant SCCs (size > 1)
        significant_sccs = [scc for scc in sccs_sorted if len(scc) > 1]
        if significant_sccs:
            self.logger.info(f"Found {len(significant_sccs)} strongly connected components with circular dependencies")
            for i, scc in enumerate(significant_sccs[:5]):  # Log first 5
                self.logger.info(f"SCC {i+1}: {scc}")
        else:
            self.logger.info("No circular dependencies found - graph is acyclic")
        
        return sccs_sorted
    
    def extract_class_relationships(self, repo_structure: RepositoryStructure) -> ClassDiagram:
        """Extract inheritance, composition, and aggregation relationships from parsed code.
        
        Args:
            repo_structure: Parsed repository structure
            
        Returns:
            ClassDiagram data structure representing UML-style class relationships
        """
        self.logger.info("Extracting class relationships from repository structure")
        
        class_diagram = ClassDiagram()
        
        # First pass: Collect all classes and organize by packages
        for file_structure in repo_structure.files:
            package_name = self._get_package_name(file_structure.file_path)
            
            for class_info in file_structure.classes:
                # Use fully qualified class name
                full_class_name = f"{package_name}.{class_info.name}" if package_name else class_info.name
                
                # Store class information
                class_diagram.classes[full_class_name] = class_info
                
                # Organize by packages
                if package_name not in class_diagram.packages:
                    class_diagram.packages[package_name] = []
                class_diagram.packages[package_name].append(full_class_name)
        
        # Second pass: Extract relationships
        for file_structure in repo_structure.files:
            package_name = self._get_package_name(file_structure.file_path)
            
            for class_info in file_structure.classes:
                source_class = f"{package_name}.{class_info.name}" if package_name else class_info.name
                
                # Extract inheritance relationships
                for parent_class in class_info.inheritance:
                    target_class = self._resolve_class_reference(
                        parent_class, file_structure, class_diagram.classes
                    )
                    
                    if target_class:
                        relationship = ClassRelationship(
                            source_class=source_class,
                            target_class=target_class,
                            relationship_type=RelationType.INHERITANCE,
                            strength=self._calculate_relationship_strength(RelationType.INHERITANCE),
                            source_file=file_structure.file_path,
                            line_number=class_info.line_number,
                            context=f"class {class_info.name} inherits from {parent_class}"
                        )
                        class_diagram.relationships.append(relationship)
                    else:
                        # External inheritance
                        class_diagram.external_dependencies.add(parent_class)
                
                # Extract composition and aggregation from method parameters and attributes
                self._extract_composition_relationships(
                    class_info, source_class, file_structure, class_diagram
                )
        
        self.logger.info(f"Extracted {len(class_diagram.classes)} classes with {len(class_diagram.relationships)} relationships")
        return class_diagram
    
    def _get_package_name(self, file_path: str) -> str:
        """Extract package name from file path.
        
        Args:
            file_path: Path to source file
            
        Returns:
            Package name
        """
        module_name = self._get_module_name(file_path)
        parts = module_name.split('.')
        return '.'.join(parts[:-1]) if len(parts) > 1 else ""
    
    def _resolve_class_reference(self, class_name: str, file_structure: CodeStructure, 
                                all_classes: Dict[str, ClassInfo]) -> Optional[str]:
        """Resolve a class reference to its fully qualified name.
        
        Args:
            class_name: Name of the referenced class
            file_structure: Structure of the file containing the reference
            all_classes: Dictionary of all known classes
            
        Returns:
            Fully qualified class name if found, None otherwise
        """
        # First check if it's a simple name that exists in the same package
        package_name = self._get_package_name(file_structure.file_path)
        if package_name:
            full_name = f"{package_name}.{class_name}"
            if full_name in all_classes:
                return full_name
        
        # Check if it's already a fully qualified name
        if class_name in all_classes:
            return class_name
        
        # Check imports to resolve the class
        for import_info in file_structure.imports:
            if class_name in import_info.imported_names:
                # Try to construct full name from import
                if import_info.is_relative:
                    # Handle relative imports
                    base_parts = package_name.split('.') if package_name else []
                    if import_info.module.startswith('..'):
                        dots = len(import_info.module) - len(import_info.module.lstrip('.'))
                        if dots <= len(base_parts):
                            parent_parts = base_parts[:-dots] if dots > 0 else base_parts
                            relative_module = import_info.module[dots:]
                            if relative_module:
                                target_package = '.'.join(parent_parts + [relative_module])
                            else:
                                target_package = '.'.join(parent_parts)
                            full_name = f"{target_package}.{class_name}"
                            if full_name in all_classes:
                                return full_name
                else:
                    # Absolute import
                    full_name = f"{import_info.module}.{class_name}"
                    if full_name in all_classes:
                        return full_name
        
        # Check if any known class ends with this name (for simple references)
        for full_class_name in all_classes.keys():
            if full_class_name.endswith(f".{class_name}") or full_class_name == class_name:
                return full_class_name
        
        return None
    
    def _extract_composition_relationships(self, class_info: ClassInfo, source_class: str,
                                         file_structure: CodeStructure, class_diagram: ClassDiagram) -> None:
        """Extract composition and aggregation relationships from class members.
        
        Args:
            class_info: Information about the source class
            source_class: Fully qualified name of the source class
            file_structure: Structure of the file containing the class
            class_diagram: Class diagram being built
        """
        # Check attributes for composition/aggregation
        for attr in class_info.attributes:
            if attr.type_hint:
                target_class = self._extract_class_from_type_hint(attr.type_hint, file_structure, class_diagram.classes)
                if target_class:
                    # Determine if it's composition or aggregation based on naming patterns
                    relationship_type = self._determine_composition_type(attr.name, attr.type_hint)
                    
                    relationship = ClassRelationship(
                        source_class=source_class,
                        target_class=target_class,
                        relationship_type=relationship_type,
                        strength=self._calculate_relationship_strength(relationship_type),
                        source_file=file_structure.file_path,
                        context=f"attribute {attr.name}: {attr.type_hint}"
                    )
                    class_diagram.relationships.append(relationship)
        
        # Check method parameters for dependencies
        for method in class_info.methods:
            for param in method.parameters:
                if param.type_hint and param.name != 'self':
                    target_class = self._extract_class_from_type_hint(param.type_hint, file_structure, class_diagram.classes)
                    if target_class:
                        relationship = ClassRelationship(
                            source_class=source_class,
                            target_class=target_class,
                            relationship_type=RelationType.DEPENDENCY,
                            strength=self._calculate_relationship_strength(RelationType.DEPENDENCY),
                            source_file=file_structure.file_path,
                            line_number=method.line_number,
                            context=f"method {method.name} parameter {param.name}: {param.type_hint}"
                        )
                        class_diagram.relationships.append(relationship)
    
    def _extract_class_from_type_hint(self, type_hint: str, file_structure: CodeStructure,
                                    all_classes: Dict[str, ClassInfo]) -> Optional[str]:
        """Extract class name from type hint.
        
        Args:
            type_hint: Type hint string
            file_structure: Structure of the file containing the type hint
            all_classes: Dictionary of all known classes
            
        Returns:
            Fully qualified class name if found, None otherwise
        """
        # Handle common type hint patterns
        type_hint = type_hint.strip()
        
        # Remove generic type parameters (e.g., List[MyClass] -> MyClass)
        if '[' in type_hint and ']' in type_hint:
            start = type_hint.find('[')
            end = type_hint.rfind(']')
            if start < end:
                inner_type = type_hint[start+1:end].strip()
                # Handle multiple generic parameters
                if ',' in inner_type:
                    inner_type = inner_type.split(',')[0].strip()
                type_hint = inner_type
        
        # Remove Optional wrapper
        if type_hint.startswith('Optional[') and type_hint.endswith(']'):
            type_hint = type_hint[9:-1].strip()
        
        # Remove Union wrapper (take first type)
        if type_hint.startswith('Union['):
            end = type_hint.find(',')
            if end > 0:
                type_hint = type_hint[6:end].strip()
        
        # Skip built-in types
        builtin_types = {'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple', 'set', 'None'}
        if type_hint.lower() in builtin_types:
            return None
        
        # Try to resolve the class name
        return self._resolve_class_reference(type_hint, file_structure, all_classes)
    
    def _determine_composition_type(self, attr_name: str, type_hint: str) -> RelationType:
        """Determine if a relationship is composition or aggregation based on naming patterns.
        
        Args:
            attr_name: Name of the attribute
            type_hint: Type hint of the attribute
            
        Returns:
            RelationType indicating composition or aggregation
        """
        # Heuristics for determining composition vs aggregation
        composition_indicators = ['_', 'internal', 'private', 'owned']
        aggregation_indicators = ['ref', 'reference', 'link', 'shared']
        
        attr_lower = attr_name.lower()
        type_lower = type_hint.lower()
        
        # Check for composition indicators
        # Special handling for underscore - should be at the beginning for private attributes
        if attr_lower.startswith('_') or any(indicator in attr_lower for indicator in composition_indicators[1:]):
            return RelationType.COMPOSITION
        
        # Check for aggregation indicators
        if any(indicator in attr_lower for indicator in aggregation_indicators):
            return RelationType.AGGREGATION
        
        # Check type hint for collection types (usually aggregation)
        if any(collection in type_lower for collection in ['list', 'set', 'dict', 'collection']):
            return RelationType.AGGREGATION
        
        # Default to composition for single object references
        return RelationType.COMPOSITION
    
    def _calculate_relationship_strength(self, relationship_type: RelationType) -> int:
        """Calculate the strength of a relationship for diagram layout optimization.
        
        Args:
            relationship_type: Type of relationship
            
        Returns:
            Strength score (higher = stronger relationship)
        """
        strength_map = {
            RelationType.INHERITANCE: 5,      # Strongest - IS-A relationship
            RelationType.COMPOSITION: 4,      # Strong - PART-OF relationship
            RelationType.AGGREGATION: 3,      # Medium - HAS-A relationship
            RelationType.DEPENDENCY: 2,       # Weak - USES relationship
            RelationType.IMPORT: 1            # Weakest - module dependency
        }
        return strength_map.get(relationship_type, 1)
    
    def analyze_data_flow(self, repo_structure: RepositoryStructure) -> DataFlowDiagram:
        """Analyze data movement between functions and modules using call graph analysis.
        
        Args:
            repo_structure: Parsed repository structure
            
        Returns:
            DataFlowDiagram data structure following DFD notation standards
        """
        self.logger.info("Analyzing data flow from repository structure")
        
        dfd = DataFlowDiagram()
        
        # First pass: Identify all functions and methods as potential processes
        all_functions = {}  # function_name -> (file_path, function_info)
        
        for file_structure in repo_structure.files:
            module_name = self._get_module_name(file_structure.file_path)
            
            # Add standalone functions
            for func in file_structure.functions:
                func_id = f"{module_name}.{func.name}"
                all_functions[func_id] = (file_structure.file_path, func)
                
                # Create process node
                process_node = DataFlowNode(
                    name=func_id,
                    node_type="process",
                    file_path=file_structure.file_path,
                    line_number=func.line_number,
                    description=f"Function {func.name} in {module_name}"
                )
                dfd.nodes[func_id] = process_node
                dfd.processes.add(func_id)
            
            # Add class methods
            for class_info in file_structure.classes:
                for method in class_info.methods:
                    method_id = f"{module_name}.{class_info.name}.{method.name}"
                    all_functions[method_id] = (file_structure.file_path, method)
                    
                    # Create process node
                    process_node = DataFlowNode(
                        name=method_id,
                        node_type="process",
                        file_path=file_structure.file_path,
                        line_number=method.line_number,
                        description=f"Method {method.name} in class {class_info.name}"
                    )
                    dfd.nodes[method_id] = process_node
                    dfd.processes.add(method_id)
        
        # Second pass: Identify external entities and data stores
        self._identify_external_entities(repo_structure, dfd)
        self._identify_data_stores(repo_structure, dfd)
        
        # Third pass: Analyze data flows between processes
        self._analyze_function_calls(repo_structure, dfd, all_functions)
        self._analyze_data_flows_from_parameters(repo_structure, dfd, all_functions)
        
        self.logger.info(f"Analyzed data flow: {len(dfd.processes)} processes, {len(dfd.external_entities)} external entities, {len(dfd.data_stores)} data stores, {len(dfd.flows)} flows")
        return dfd
    
    def _identify_external_entities(self, repo_structure: RepositoryStructure, dfd: DataFlowDiagram) -> None:
        """Identify external entities from imports and API calls.
        
        Args:
            repo_structure: Parsed repository structure
            dfd: Data flow diagram being built
        """
        external_systems = set()
        
        for file_structure in repo_structure.files:
            # Check imports for external systems
            for import_info in file_structure.imports:
                if not import_info.is_relative:
                    # Common external system patterns
                    external_patterns = {
                        'requests': 'HTTP API',
                        'urllib': 'HTTP API',
                        'sqlite3': 'SQLite Database',
                        'psycopg2': 'PostgreSQL Database',
                        'pymongo': 'MongoDB Database',
                        'redis': 'Redis Cache',
                        'boto3': 'AWS Services',
                        'kafka': 'Kafka Message Queue',
                        'rabbitmq': 'RabbitMQ Message Queue',
                        'flask': 'Web Framework',
                        'django': 'Web Framework',
                        'fastapi': 'Web Framework'
                    }
                    
                    module_name = import_info.module.split('.')[0]
                    if module_name in external_patterns:
                        entity_name = f"{external_patterns[module_name]} ({module_name})"
                        if entity_name not in external_systems:
                            external_systems.add(entity_name)
                            
                            entity_node = DataFlowNode(
                                name=entity_name,
                                node_type="external_entity",
                                description=f"External system: {external_patterns[module_name]}"
                            )
                            dfd.nodes[entity_name] = entity_node
                            dfd.external_entities.add(entity_name)
    
    def _identify_data_stores(self, repo_structure: RepositoryStructure, dfd: DataFlowDiagram) -> None:
        """Identify data stores from file operations and database patterns.
        
        Args:
            repo_structure: Parsed repository structure
            dfd: Data flow diagram being built
        """
        # Look for common data store patterns in function names and imports
        data_store_patterns = {
            'save', 'store', 'persist', 'write', 'insert', 'update', 'delete',
            'load', 'read', 'fetch', 'get', 'find', 'query', 'select',
            'cache', 'session', 'config', 'settings'
        }
        
        identified_stores = set()
        
        for file_structure in repo_structure.files:
            module_name = self._get_module_name(file_structure.file_path)
            
            # Check for database/storage related classes
            for class_info in file_structure.classes:
                class_name_lower = class_info.name.lower()
                if any(pattern in class_name_lower for pattern in ['repository', 'dao', 'model', 'entity', 'store', 'cache']):
                    store_name = f"{module_name}.{class_info.name}"
                    if store_name not in identified_stores:
                        identified_stores.add(store_name)
                        
                        store_node = DataFlowNode(
                            name=store_name,
                            node_type="data_store",
                            file_path=file_structure.file_path,
                            line_number=class_info.line_number,
                            description=f"Data store: {class_info.name}"
                        )
                        dfd.nodes[store_name] = store_node
                        dfd.data_stores.add(store_name)
            
            # Check for functions that suggest data storage operations
            for func in file_structure.functions:
                func_name_lower = func.name.lower()
                if any(pattern in func_name_lower for pattern in data_store_patterns):
                    # This function likely interacts with data stores
                    # We'll create flows to/from this function in the next step
                    pass
    
    def _analyze_function_calls(self, repo_structure: RepositoryStructure, dfd: DataFlowDiagram, 
                               all_functions: Dict[str, Tuple[str, Any]]) -> None:
        """Analyze function calls to identify data flows.
        
        Args:
            repo_structure: Parsed repository structure
            dfd: Data flow diagram being built
            all_functions: Dictionary of all functions/methods
        """
        # This is a simplified analysis - in a real implementation, we would need
        # to parse function bodies to identify actual function calls
        # For now, we'll infer flows based on imports and method signatures
        
        for file_structure in repo_structure.files:
            module_name = self._get_module_name(file_structure.file_path)
            
            # Analyze imports to infer potential function calls
            imported_modules = set()
            for import_info in file_structure.imports:
                if not import_info.is_relative:
                    imported_modules.add(import_info.module)
            
            # For each function in this file, check if it might call functions from imported modules
            for func in file_structure.functions:
                source_func = f"{module_name}.{func.name}"
                
                # Look for potential data flows based on function name patterns
                self._infer_data_flows_from_function_name(source_func, func, dfd)
            
            # Analyze class methods
            for class_info in file_structure.classes:
                for method in class_info.methods:
                    source_method = f"{module_name}.{class_info.name}.{method.name}"
                    
                    # Look for potential data flows
                    self._infer_data_flows_from_function_name(source_method, method, dfd)
    
    def _analyze_data_flows_from_parameters(self, repo_structure: RepositoryStructure, dfd: DataFlowDiagram,
                                          all_functions: Dict[str, Tuple[str, Any]]) -> None:
        """Analyze function parameters to identify data flows.
        
        Args:
            repo_structure: Parsed repository structure
            dfd: Data flow diagram being built
            all_functions: Dictionary of all functions/methods
        """
        for func_id, (file_path, func_info) in all_functions.items():
            if hasattr(func_info, 'parameters'):
                for param in func_info.parameters:
                    if param.name != 'self' and param.type_hint:
                        # Infer data type from parameter
                        data_description = self._infer_data_description_from_type(param.type_hint, param.name)
                        
                        if data_description:
                            # Create a generic data flow into this function
                            flow = DataFlow(
                                source="External Input",
                                target=func_id,
                                data_description=data_description,
                                flow_type="data"
                            )
                            dfd.flows.append(flow)
                
                # Check return type for outgoing data flows
                if hasattr(func_info, 'return_type') and func_info.return_type:
                    data_description = self._infer_data_description_from_type(func_info.return_type, "return_value")
                    
                    if data_description:
                        flow = DataFlow(
                            source=func_id,
                            target="External Output",
                            data_description=data_description,
                            flow_type="data"
                        )
                        dfd.flows.append(flow)
    
    def _infer_data_flows_from_function_name(self, func_id: str, func_info: Any, dfd: DataFlowDiagram) -> None:
        """Infer data flows based on function naming patterns.
        
        Args:
            func_id: Function identifier
            func_info: Function information
            dfd: Data flow diagram being built
        """
        func_name = func_info.name.lower()
        
        # Read operations - data flows from data stores to function
        read_patterns = ['get', 'fetch', 'load', 'read', 'find', 'query', 'select', 'retrieve']
        if any(pattern in func_name for pattern in read_patterns):
            # Find potential data stores this function might read from
            for store_name in dfd.data_stores:
                if self._functions_likely_related(func_name, store_name):
                    flow = DataFlow(
                        source=store_name,
                        target=func_id,
                        data_description=self._infer_data_description_from_function_name(func_name),
                        flow_type="data"
                    )
                    dfd.flows.append(flow)
        
        # Write operations - data flows from function to data stores
        write_patterns = ['save', 'store', 'persist', 'write', 'insert', 'update', 'delete', 'create']
        if any(pattern in func_name for pattern in write_patterns):
            # Find potential data stores this function might write to
            for store_name in dfd.data_stores:
                if self._functions_likely_related(func_name, store_name):
                    flow = DataFlow(
                        source=func_id,
                        target=store_name,
                        data_description=self._infer_data_description_from_function_name(func_name),
                        flow_type="data"
                    )
                    dfd.flows.append(flow)
        
        # API/External operations
        api_patterns = ['send', 'post', 'put', 'patch', 'request', 'call', 'invoke']
        if any(pattern in func_name for pattern in api_patterns):
            # Find potential external entities this function might interact with
            for entity_name in dfd.external_entities:
                if 'api' in entity_name.lower() or 'http' in entity_name.lower():
                    flow = DataFlow(
                        source=func_id,
                        target=entity_name,
                        data_description=self._infer_data_description_from_function_name(func_name),
                        flow_type="data"
                    )
                    dfd.flows.append(flow)
    
    def _functions_likely_related(self, func_name: str, store_name: str) -> bool:
        """Determine if a function is likely related to a data store.
        
        Args:
            func_name: Function name (lowercase)
            store_name: Data store name
            
        Returns:
            True if they are likely related
        """
        store_name_lower = store_name.lower()
        
        # Extract key terms from both names
        func_terms = set(func_name.replace('_', ' ').split())
        store_terms = set(store_name_lower.replace('_', ' ').replace('.', ' ').split())
        
        # Check for common terms
        common_terms = func_terms.intersection(store_terms)
        
        # If they share terms, they are likely related
        if len(common_terms) > 0:
            return True
        
        # Check if function name contains key terms that match the store name
        store_key_terms = ['user', 'order', 'product', 'data', 'cache', 'session', 'config']
        for term in store_key_terms:
            if term in func_name and term in store_name_lower:
                return True
        
        return False
    
    def _infer_data_description_from_function_name(self, func_name: str) -> str:
        """Infer data description from function name.
        
        Args:
            func_name: Function name
            
        Returns:
            Description of the data being processed
        """
        # Extract meaningful terms from function name
        terms = func_name.replace('_', ' ').split()
        
        # Remove common verbs
        verbs = {'get', 'set', 'fetch', 'load', 'save', 'store', 'create', 'update', 'delete', 'find', 'query'}
        meaningful_terms = [term for term in terms if term not in verbs]
        
        if meaningful_terms:
            return f"{' '.join(meaningful_terms)} data"
        else:
            return "data"
    
    def _infer_data_description_from_type(self, type_hint: str, param_name: str) -> Optional[str]:
        """Infer data description from type hint and parameter name.
        
        Args:
            type_hint: Type hint string
            param_name: Parameter name
            
        Returns:
            Description of the data, or None if it's a basic type
        """
        # Skip basic types
        basic_types = {'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple', 'set'}
        if type_hint.lower() in basic_types:
            return None
        
        # Clean up type hint
        clean_type = type_hint.replace('Optional[', '').replace('List[', '').replace(']', '')
        
        # If it looks like a custom class, use it as data description
        if clean_type and clean_type[0].isupper():
            return f"{clean_type} data"
        
        # Use parameter name as fallback
        return f"{param_name} data"
    
    def _get_module_name(self, file_path: str) -> str:
        """Convert file path to module name.
        
        Args:
            file_path: Path to source file
            
        Returns:
            Module name derived from file path
        """
        path_obj = Path(file_path)
        
        # Remove file extension
        module_parts = []
        
        # Handle different path structures
        parts = path_obj.parts
        
        # Skip common root directories
        skip_dirs = {'src', 'lib', 'app', 'source'}
        start_idx = 0
        for i, part in enumerate(parts):
            if part in skip_dirs:
                start_idx = i + 1
                break
        
        # Build module name from remaining parts
        for part in parts[start_idx:]:
            if part.endswith('.py'):
                part = part[:-3]
            elif part.endswith('.js') or part.endswith('.ts'):
                part = part[:-3]
            elif part.endswith('.java'):
                part = part[:-5]
            elif part.endswith('.go'):
                part = part[:-3]
            
            if part and part != '__init__':
                module_parts.append(part)
        
        return '.'.join(module_parts) if module_parts else path_obj.stem
    
    def _resolve_import_targets(self, import_info: ImportInfo, source_file: str, 
                               module_to_file: Dict[str, str]) -> List[str]:
        """Resolve import statement to target module names.
        
        Args:
            import_info: Import information
            source_file: Path to file containing the import
            module_to_file: Mapping of module names to file paths
            
        Returns:
            List of target module names
        """
        targets = []
        
        if import_info.is_relative:
            # Handle relative imports
            base_module = self._get_module_name(source_file)
            base_parts = base_module.split('.')
            
            # Calculate relative path
            if import_info.module.startswith('..'):
                # Parent directory imports
                dots = len(import_info.module) - len(import_info.module.lstrip('.'))
                if dots <= len(base_parts):
                    parent_parts = base_parts[:-dots] if dots > 0 else base_parts
                    relative_module = import_info.module[dots:]
                    if relative_module:
                        target_module = '.'.join(parent_parts + [relative_module])
                    else:
                        target_module = '.'.join(parent_parts)
                    targets.append(target_module)
            else:
                # Same directory relative import
                if len(base_parts) > 1:
                    parent_parts = base_parts[:-1]
                    target_module = '.'.join(parent_parts + [import_info.module.lstrip('.')])
                    targets.append(target_module)
        else:
            # Absolute import - check if it matches any known module
            module_name = import_info.module
            
            # First try exact match
            if module_name in module_to_file:
                targets.append(module_name)
            else:
                # Try to find matching modules by checking if any module ends with this name
                for known_module in module_to_file.keys():
                    if known_module.endswith(module_name) or known_module.split('.')[-1] == module_name:
                        targets.append(known_module)
                        break
                
                # If no internal match found, treat as external
                if not targets:
                    targets.append(module_name)
        
        return targets
    
    def _calculate_import_strength(self, import_info: ImportInfo) -> int:
        """Calculate the strength of an import relationship.
        
        Args:
            import_info: Import information
            
        Returns:
            Strength score (higher = stronger dependency)
        """
        strength = 1
        
        # Increase strength based on number of imported names
        if import_info.imported_names:
            strength += len(import_info.imported_names)
        
        # Star imports are considered stronger dependencies
        if '*' in import_info.imported_names:
            strength += 5
        
        return min(strength, 10)  # Cap at 10
    
    def _get_import_type(self, import_info: ImportInfo) -> str:
        """Determine the type of import.
        
        Args:
            import_info: Import information
            
        Returns:
            Import type string
        """
        if import_info.is_relative:
            return "relative"
        elif any(name == '*' for name in import_info.imported_names):
            return "star"
        elif import_info.imported_names:
            return "selective"
        else:
            return "module"
    
    def _resolve_class_to_module(self, class_name: str, file_structure: CodeStructure,
                                module_to_file: Dict[str, str]) -> Optional[str]:
        """Resolve a class name to its containing module.
        
        Args:
            class_name: Name of the class
            file_structure: Structure of the file containing the reference
            module_to_file: Mapping of module names to file paths
            
        Returns:
            Module name containing the class, or None if not found
        """
        # First check if class is defined in the same file
        for class_info in file_structure.classes:
            if class_info.name == class_name:
                return self._get_module_name(file_structure.file_path)
        
        # Check imports to see if class is imported
        for import_info in file_structure.imports:
            if class_name in import_info.imported_names:
                targets = self._resolve_import_targets(import_info, file_structure.file_path, module_to_file)
                if targets:
                    return targets[0]
        
        # If not found, assume it's an external class
        return None
    
    def _add_graph_metrics(self, graph: nx.DiGraph) -> None:
        """Add graph-level metrics as graph attributes.
        
        Args:
            graph: NetworkX directed graph to annotate
        """
        # Basic metrics
        graph.graph['total_nodes'] = graph.number_of_nodes()
        graph.graph['total_edges'] = graph.number_of_edges()
        
        # Density
        if graph.number_of_nodes() > 1:
            graph.graph['density'] = nx.density(graph)
        else:
            graph.graph['density'] = 0.0
        
        # Strongly connected components
        sccs = list(nx.strongly_connected_components(graph))
        graph.graph['num_sccs'] = len(sccs)
        graph.graph['largest_scc_size'] = max(len(scc) for scc in sccs) if sccs else 0
        
        # Check if graph is acyclic
        graph.graph['is_dag'] = nx.is_directed_acyclic_graph(graph)
        
        # Node metrics
        in_degrees = dict(graph.in_degree())
        out_degrees = dict(graph.out_degree())
        
        for node in graph.nodes():
            graph.nodes[node]['in_degree'] = in_degrees[node]
            graph.nodes[node]['out_degree'] = out_degrees[node]
            graph.nodes[node]['total_degree'] = in_degrees[node] + out_degrees[node]