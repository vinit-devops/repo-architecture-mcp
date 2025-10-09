"""Diagram generation system with multiple format support."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Protocol
from enum import Enum
import asyncio
from pathlib import Path
import tempfile
import subprocess
import shutil
import json

from .models import RepositoryStructure
from .architecture_analyzer import ClassDiagram, DataFlowDiagram
import networkx as nx

logger = logging.getLogger(__name__)


class DiagramFormat(Enum):
    """Supported diagram output formats."""
    MERMAID = "mermaid"
    SVG = "svg"
    PNG = "png"
    PLANTUML = "plantuml"


class DiagramType(Enum):
    """Types of diagrams that can be generated."""
    DEPENDENCY = "dependency"
    CLASS = "class"
    DATA_FLOW = "data_flow"


@dataclass
class DiagramOutput:
    """Standardized output format for generated diagrams."""
    content: str
    format: DiagramFormat
    diagram_type: DiagramType
    metadata: Dict[str, Any] = field(default_factory=dict)
    title: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "content": self.content,
            "format": self.format.value,
            "diagram_type": self.diagram_type.value,
            "metadata": self.metadata,
            "title": self.title,
            "description": self.description
        }


@dataclass
class DiagramConfig:
    """Configuration options for diagram generation."""
    format: DiagramFormat = DiagramFormat.MERMAID
    title: Optional[str] = None
    include_external: bool = True
    max_nodes: int = 50
    layout: str = "hierarchical"  # hierarchical, circular, force-directed
    filter_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    show_attributes: bool = True
    show_methods: bool = True
    show_parameters: bool = False
    group_by_package: bool = True
    # Readability options
    high_contrast: bool = True  # Use high contrast colors and bold text
    use_emojis: bool = True     # Use emojis in node labels for better visual distinction
    font_size: str = "16px"     # Font size for better readability
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "format": self.format.value,
            "title": self.title,
            "include_external": self.include_external,
            "max_nodes": self.max_nodes,
            "layout": self.layout,
            "filter_patterns": self.filter_patterns,
            "exclude_patterns": self.exclude_patterns,
            "show_attributes": self.show_attributes,
            "show_methods": self.show_methods,
            "show_parameters": self.show_parameters,
            "group_by_package": self.group_by_package,
            "high_contrast": self.high_contrast,
            "use_emojis": self.use_emojis,
            "font_size": self.font_size
        }


class DiagramRenderer(ABC):
    """Abstract base class for diagram format renderers."""
    
    @abstractmethod
    def get_supported_format(self) -> DiagramFormat:
        """Get the format this renderer supports."""
        pass
    
    @abstractmethod
    async def render_dependency_diagram(self, graph: nx.DiGraph, config: DiagramConfig) -> str:
        """Render a dependency diagram."""
        pass
    
    @abstractmethod
    async def render_class_diagram(self, class_diagram: ClassDiagram, config: DiagramConfig) -> str:
        """Render a class diagram."""
        pass
    
    @abstractmethod
    async def render_data_flow_diagram(self, dfd: DataFlowDiagram, config: DiagramConfig) -> str:
        """Render a data flow diagram."""
        pass


class MermaidRenderer(DiagramRenderer):
    """Mermaid syntax renderer for diagrams."""
    
    def get_supported_format(self) -> DiagramFormat:
        """Get the format this renderer supports."""
        return DiagramFormat.MERMAID
    
    async def render_dependency_diagram(self, graph: nx.DiGraph, config: DiagramConfig) -> str:
        """Render a dependency diagram in Mermaid syntax with advanced layout and grouping."""
        logger.info("Rendering dependency diagram in Mermaid format")
        
        # Apply layout-specific rendering
        if config.layout == "hierarchical":
            return await self._render_hierarchical_dependency_diagram(graph, config)
        elif config.layout == "circular":
            return await self._render_circular_dependency_diagram(graph, config)
        else:
            return await self._render_force_directed_dependency_diagram(graph, config)
    
    async def _render_hierarchical_dependency_diagram(self, graph: nx.DiGraph, config: DiagramConfig) -> str:
        """Render dependency diagram with hierarchical layout."""
        lines = ["graph TD"]
        
        # Add title if provided
        if config.title:
            lines.append(f"    title[{config.title}]")
        
        # Filter and group nodes
        filtered_nodes = self._filter_nodes(graph, config)
        grouped_nodes = self._group_nodes_by_package(filtered_nodes, config) if config.group_by_package else {"": filtered_nodes}
        
        # Render grouped nodes
        for package, nodes in grouped_nodes.items():
            if package and len(nodes) > 1:
                # Create subgraph for package
                package_id = self._sanitize_id(package)
                lines.append(f"    subgraph {package_id} [\"{package}\"]")
                
                for node in nodes:
                    node_data = graph.nodes.get(node, {})
                    label = self._create_node_label(node, node_data, config)
                    is_external = node_data.get('external', False)
                    
                    if is_external:
                        lines.append(f"        {self._sanitize_id(node)}[{label}]:::external")
                    else:
                        lines.append(f"        {self._sanitize_id(node)}[{label}]:::internal")
                
                lines.append("    end")
            else:
                # Render individual nodes
                for node in nodes:
                    node_data = graph.nodes.get(node, {})
                    label = self._create_node_label(node, node_data, config)
                    is_external = node_data.get('external', False)
                    
                    if is_external:
                        lines.append(f"    {self._sanitize_id(node)}[{label}]:::external")
                    else:
                        lines.append(f"    {self._sanitize_id(node)}[{label}]:::internal")
        
        # Add edges with relationship-specific styling
        self._add_dependency_edges(lines, graph, filtered_nodes)
        
        # Add styling classes
        self._add_dependency_styling(lines)
        
        return "\n".join(lines)
    
    async def _render_circular_dependency_diagram(self, graph: nx.DiGraph, config: DiagramConfig) -> str:
        """Render dependency diagram with circular layout for highlighting cycles."""
        lines = ["graph LR"]  # Left-to-right for better circular visualization
        
        if config.title:
            lines.append(f"    title[{config.title}]")
        
        filtered_nodes = self._filter_nodes(graph, config)
        
        # Identify strongly connected components for circular layout
        sccs = list(nx.strongly_connected_components(graph.subgraph(filtered_nodes)))
        circular_components = [list(scc) for scc in sccs if len(scc) > 1]
        
        # Render circular components first
        for i, component in enumerate(circular_components):
            if len(component) > 1:
                comp_id = f"cycle_{i}"
                lines.append(f"    subgraph {comp_id} [\"Circular Dependency {i+1}\"]")
                
                for node in component:
                    node_data = graph.nodes.get(node, {})
                    label = self._create_node_label(node, node_data, config)
                    lines.append(f"        {self._sanitize_id(node)}[{label}]:::circular")
                
                lines.append("    end")
        
        # Render remaining nodes
        remaining_nodes = [node for node in filtered_nodes 
                          if not any(node in comp for comp in circular_components)]
        
        for node in remaining_nodes:
            node_data = graph.nodes.get(node, {})
            label = self._create_node_label(node, node_data, config)
            is_external = node_data.get('external', False)
            
            if is_external:
                lines.append(f"    {self._sanitize_id(node)}[{label}]:::external")
            else:
                lines.append(f"    {self._sanitize_id(node)}[{label}]:::internal")
        
        # Add edges
        self._add_dependency_edges(lines, graph, filtered_nodes)
        
        # Add styling with circular component highlighting
        lines.extend([
            "",
            "    classDef external fill:#ffcccc,stroke:#ff6666,stroke-width:2px",
            "    classDef internal fill:#ccffcc,stroke:#66cc66,stroke-width:2px",
            "    classDef circular fill:#ffcc99,stroke:#ff9900,stroke-width:3px"
        ])
        
        return "\n".join(lines)
    
    async def _render_force_directed_dependency_diagram(self, graph: nx.DiGraph, config: DiagramConfig) -> str:
        """Render dependency diagram optimized for force-directed layout."""
        lines = ["graph TB"]
        
        if config.title:
            lines.append(f"    title[{config.title}]")
        
        filtered_nodes = self._filter_nodes(graph, config)
        
        # Calculate node importance for sizing
        node_importance = {}
        for node in filtered_nodes:
            in_degree = graph.in_degree(node)
            out_degree = graph.out_degree(node)
            node_importance[node] = in_degree + out_degree * 0.5  # Weight outgoing edges less
        
        # Render nodes with size based on importance
        for node in filtered_nodes:
            node_data = graph.nodes.get(node, {})
            label = self._create_node_label(node, node_data, config)
            is_external = node_data.get('external', False)
            importance = node_importance.get(node, 0)
            
            # Choose node style based on importance
            if importance > 5:
                style_class = "hub"
            elif is_external:
                style_class = "external"
            else:
                style_class = "internal"
            
            lines.append(f"    {self._sanitize_id(node)}[{label}]:::{style_class}")
        
        # Add edges with strength-based styling
        self._add_dependency_edges(lines, graph, filtered_nodes)
        
        # Add styling for force-directed layout
        lines.extend([
            "",
            "    classDef external fill:#ffcccc,stroke:#ff6666,stroke-width:2px",
            "    classDef internal fill:#ccffcc,stroke:#66cc66,stroke-width:2px",
            "    classDef hub fill:#ccccff,stroke:#6666ff,stroke-width:4px"
        ])
        
        return "\n".join(lines)
    
    def _group_nodes_by_package(self, nodes: List[str], config: DiagramConfig) -> Dict[str, List[str]]:
        """Group nodes by package for hierarchical display."""
        groups = {}
        
        for node in nodes:
            # Extract package from module name
            parts = node.split('.')
            if len(parts) > 1:
                package = '.'.join(parts[:-1])
            else:
                package = ""
            
            if package not in groups:
                groups[package] = []
            groups[package].append(node)
        
        return groups
    
    def _add_dependency_edges(self, lines: List[str], graph: nx.DiGraph, filtered_nodes: List[str]) -> None:
        """Add dependency edges with appropriate styling."""
        for source, target in graph.edges():
            if source in filtered_nodes and target in filtered_nodes:
                edge_data = graph.edges[source, target]
                strength = edge_data.get('strength', 1)
                relation_type = edge_data.get('relation_type', 'dependency')
                is_external = edge_data.get('external', False)
                
                # Create edge with appropriate styling
                edge_style = self._get_dependency_edge_style(relation_type, strength, is_external)
                
                # Add edge label for important relationships
                if strength > 2 or relation_type == 'inheritance':
                    label = self._get_edge_label(relation_type, edge_data)
                    if label:
                        lines.append(f"    {self._sanitize_id(source)} {edge_style}|{label}| {self._sanitize_id(target)}")
                    else:
                        lines.append(f"    {self._sanitize_id(source)} {edge_style} {self._sanitize_id(target)}")
                else:
                    lines.append(f"    {self._sanitize_id(source)} {edge_style} {self._sanitize_id(target)}")
    
    def _get_dependency_edge_style(self, relation_type: str, strength: int, is_external: bool) -> str:
        """Get edge style for dependency relationships."""
        if relation_type == 'inheritance':
            return '-->'
        elif relation_type == 'composition':
            return '==>'
        elif is_external:
            return '-.->|ext|'
        elif strength > 3:
            return '==>'
        elif strength > 1:
            return '-->'
        else:
            return '-.->'
    
    def _get_edge_label(self, relation_type: str, edge_data: Dict[str, Any]) -> Optional[str]:
        """Get label for edge based on relationship type and data."""
        if relation_type == 'inheritance':
            class_name = edge_data.get('class_name', '')
            parent_class = edge_data.get('parent_class', '')
            if class_name and parent_class:
                return f"{class_name} extends {parent_class}"
            return "inherits"
        elif relation_type == 'import':
            import_type = edge_data.get('import_type', '')
            if import_type:
                return import_type
        
        return None
    
    def _add_dependency_styling(self, lines: List[str]) -> None:
        """Add styling classes for dependency diagrams."""
        lines.extend([
            "",
            "    classDef external fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#000,font-weight:bold",
            "    classDef internal fill:#e8f5e8,stroke:#388e3c,stroke-width:3px,color:#000,font-weight:bold",
            "    classDef circular fill:#fff3e0,stroke:#f57c00,stroke-width:3px,color:#000,font-weight:bold",
            "    classDef hub fill:#fce4ec,stroke:#c2185b,stroke-width:4px,color:#000,font-weight:bold"
        ])
    
    async def render_class_diagram(self, class_diagram: ClassDiagram, config: DiagramConfig) -> str:
        """Render a UML-compliant class diagram in Mermaid syntax."""
        logger.info("Rendering class diagram in Mermaid format")
        
        lines = ["classDiagram"]
        
        # Add title if provided
        if config.title:
            lines.append(f"    title {config.title}")
        
        # Filter classes based on configuration
        filtered_classes = self._filter_classes(class_diagram, config)
        
        # Group classes by package if configured
        if config.group_by_package:
            grouped_classes = self._group_classes_by_package(filtered_classes, class_diagram)
            lines.extend(self._render_grouped_classes(grouped_classes, class_diagram, config))
        else:
            # Render classes individually
            for class_name in filtered_classes:
                class_info = class_diagram.classes[class_name]
                lines.extend(self._render_class_definition(class_name, class_info, config))
        
        # Add relationships with proper UML notation
        filtered_relationships = self._filter_relationships(class_diagram.relationships, filtered_classes)
        for relationship in filtered_relationships:
            lines.append(self._render_class_relationship(relationship))
        
        # Add notes for external dependencies
        if class_diagram.external_dependencies and config.include_external:
            lines.extend(self._render_external_dependencies(class_diagram.external_dependencies))
        
        # Add styling for different class types
        lines.extend(self._get_class_diagram_styling())
        
        return "\n".join(lines)
    
    def _filter_classes(self, class_diagram: ClassDiagram, config: DiagramConfig) -> List[str]:
        """Filter classes based on configuration."""
        classes = list(class_diagram.classes.keys())
        
        # Apply include patterns
        if config.filter_patterns:
            import re
            filtered_classes = []
            for class_name in classes:
                if any(re.search(pattern, class_name) for pattern in config.filter_patterns):
                    filtered_classes.append(class_name)
            classes = filtered_classes
        
        # Apply exclude patterns
        if config.exclude_patterns:
            import re
            classes = [class_name for class_name in classes 
                      if not any(re.search(pattern, class_name) for pattern in config.exclude_patterns)]
        
        # Limit number of classes
        if len(classes) > config.max_nodes:
            # Sort by importance (number of relationships)
            class_importance = {}
            for class_name in classes:
                importance = sum(1 for rel in class_diagram.relationships 
                               if rel.source_class == class_name or rel.target_class == class_name)
                class_importance[class_name] = importance
            
            sorted_classes = sorted(class_importance.items(), key=lambda x: x[1], reverse=True)
            classes = [class_name for class_name, _ in sorted_classes[:config.max_nodes]]
        
        return classes
    
    def _group_classes_by_package(self, classes: List[str], class_diagram: ClassDiagram) -> Dict[str, List[str]]:
        """Group classes by package."""
        groups = {}
        
        for class_name in classes:
            # Extract package from class name
            parts = class_name.split('.')
            if len(parts) > 1:
                package = '.'.join(parts[:-1])
            else:
                package = "default"
            
            if package not in groups:
                groups[package] = []
            groups[package].append(class_name)
        
        return groups
    
    def _render_grouped_classes(self, grouped_classes: Dict[str, List[str]], 
                               class_diagram: ClassDiagram, config: DiagramConfig) -> List[str]:
        """Render classes grouped by package."""
        lines = []
        
        for package, classes in grouped_classes.items():
            if len(classes) > 1 and package != "default":
                # Create namespace for package
                lines.append(f"    namespace {self._sanitize_id(package)} {{")
                
                for class_name in classes:
                    class_info = class_diagram.classes[class_name]
                    class_lines = self._render_class_definition(class_name, class_info, config)
                    # Indent class definition
                    indented_lines = ["    " + line for line in class_lines]
                    lines.extend(indented_lines)
                
                lines.append("    }")
            else:
                # Render individual classes
                for class_name in classes:
                    class_info = class_diagram.classes[class_name]
                    lines.extend(self._render_class_definition(class_name, class_info, config))
        
        return lines
    
    def _filter_relationships(self, relationships: List, filtered_classes: List[str]) -> List:
        """Filter relationships to only include those between filtered classes."""
        return [rel for rel in relationships 
                if rel.source_class in filtered_classes and rel.target_class in filtered_classes]
    
    async def render_data_flow_diagram(self, dfd: DataFlowDiagram, config: DiagramConfig) -> str:
        """Render a data flow diagram using standard DFD notation in Mermaid syntax."""
        logger.info("Rendering data flow diagram in Mermaid format")
        
        # Choose diagram direction based on layout
        if config.layout == "hierarchical":
            lines = ["flowchart TD"]  # Top-down for hierarchical
        elif config.layout == "circular":
            lines = ["flowchart LR"]  # Left-right for circular
        else:
            lines = ["flowchart TB"]  # Top-bottom default
        
        # Add title if provided
        if config.title:
            lines.append(f"    title[{config.title}]")
        
        # Filter nodes based on configuration
        filtered_nodes = self._filter_dfd_nodes(dfd, config)
        
        # Group nodes by type for better organization
        grouped_nodes = self._group_dfd_nodes_by_type(filtered_nodes, dfd)
        
        # Render nodes with proper DFD shapes and styling
        self._render_dfd_node_groups(lines, grouped_nodes, dfd)
        
        # Add data flows with descriptive labels
        filtered_flows = self._filter_dfd_flows(dfd.flows, filtered_nodes)
        self._render_dfd_flows(lines, filtered_flows)
        
        # Add DFD-specific styling
        lines.extend(self._get_dfd_styling())
        
        return "\n".join(lines)
    
    def _filter_dfd_nodes(self, dfd: DataFlowDiagram, config: DiagramConfig) -> List[str]:
        """Filter DFD nodes based on configuration."""
        nodes = list(dfd.nodes.keys())
        
        # Apply include patterns
        if config.filter_patterns:
            import re
            filtered_nodes = []
            for node in nodes:
                if any(re.search(pattern, node) for pattern in config.filter_patterns):
                    filtered_nodes.append(node)
            nodes = filtered_nodes
        
        # Apply exclude patterns
        if config.exclude_patterns:
            import re
            nodes = [node for node in nodes 
                    if not any(re.search(pattern, node) for pattern in config.exclude_patterns)]
        
        # Limit number of nodes
        if len(nodes) > config.max_nodes:
            # Prioritize nodes with more connections
            node_importance = {}
            for node in nodes:
                connections = sum(1 for flow in dfd.flows 
                                if flow.source == node or flow.target == node)
                node_importance[node] = connections
            
            sorted_nodes = sorted(node_importance.items(), key=lambda x: x[1], reverse=True)
            nodes = [node for node, _ in sorted_nodes[:config.max_nodes]]
        
        return nodes
    
    def _group_dfd_nodes_by_type(self, nodes: List[str], dfd: DataFlowDiagram) -> Dict[str, List[str]]:
        """Group DFD nodes by their type."""
        groups = {
            'external_entity': [],
            'process': [],
            'data_store': []
        }
        
        for node in nodes:
            node_info = dfd.nodes.get(node)
            if node_info:
                node_type = node_info.node_type
                if node_type in groups:
                    groups[node_type].append(node)
                else:
                    groups['process'].append(node)  # Default to process
        
        return groups
    
    def _render_dfd_node_groups(self, lines: List[str], grouped_nodes: Dict[str, List[str]], dfd: DataFlowDiagram) -> None:
        """Render DFD nodes grouped by type with proper shapes."""
        
        # Render external entities first (rectangles)
        if grouped_nodes['external_entity']:
            lines.append("")
            lines.append("    %% External Entities")
            for node in grouped_nodes['external_entity']:
                node_info = dfd.nodes[node]
                display_name = self._get_dfd_node_display_name(node, node_info)
                lines.append(f"    {self._sanitize_id(node)}[{display_name}]:::external")
        
        # Render processes (circles/rounded rectangles)
        if grouped_nodes['process']:
            lines.append("")
            lines.append("    %% Processes")
            for node in grouped_nodes['process']:
                node_info = dfd.nodes[node]
                display_name = self._get_dfd_node_display_name(node, node_info)
                # Use rounded rectangle for processes
                lines.append(f"    {self._sanitize_id(node)}({display_name}):::process")
        
        # Render data stores (open rectangles)
        if grouped_nodes['data_store']:
            lines.append("")
            lines.append("    %% Data Stores")
            for node in grouped_nodes['data_store']:
                node_info = dfd.nodes[node]
                display_name = self._get_dfd_node_display_name(node, node_info)
                # Use special notation for data stores
                lines.append(f"    {self._sanitize_id(node)}[({display_name})]:::datastore")
    
    def _get_dfd_node_display_name(self, node_name: str, node_info) -> str:
        """Get display name for DFD node."""
        # Use simple name for cleaner display
        parts = node_name.split('.')
        simple_name = parts[-1] if parts else node_name
        
        # Add node type prefix for clarity
        if node_info.node_type == 'external_entity':
            prefix = "EXT: "
        elif node_info.node_type == 'data_store':
            prefix = "DS: "
        else:
            prefix = ""
        
        display_name = f"{prefix}{simple_name}"
        
        # Add description if available and short
        if hasattr(node_info, 'description') and node_info.description:
            desc = node_info.description
            if len(desc) < 20:
                display_name += f"\\n{desc}"
        
        # Truncate very long names
        if len(display_name) > 40:
            display_name = display_name[:37] + "..."
        
        return display_name
    
    def _filter_dfd_flows(self, flows: List, filtered_nodes: List[str]) -> List:
        """Filter data flows to only include those between filtered nodes."""
        return [flow for flow in flows 
                if flow.source in filtered_nodes and flow.target in filtered_nodes]
    
    def _render_dfd_flows(self, lines: List[str], flows: List) -> None:
        """Render data flows with descriptive labels."""
        if flows:
            lines.append("")
            lines.append("    %% Data Flows")
            
            for flow in flows:
                source = self._sanitize_id(flow.source)
                target = self._sanitize_id(flow.target)
                
                # Create flow label
                flow_label = self._get_dfd_flow_label(flow)
                
                # Choose arrow style based on flow type
                if hasattr(flow, 'flow_type'):
                    if flow.flow_type == 'control':
                        arrow_style = "-.->|"
                    elif flow.flow_type == 'event':
                        arrow_style = "==>|"
                    else:
                        arrow_style = "-->|"
                else:
                    arrow_style = "-->|"
                
                if flow_label:
                    lines.append(f"    {source} {arrow_style}{flow_label}| {target}")
                else:
                    lines.append(f"    {source} --> {target}")
    
    def _get_dfd_flow_label(self, flow) -> str:
        """Get descriptive label for data flow."""
        if hasattr(flow, 'data_description') and flow.data_description:
            label = flow.data_description
            
            # Truncate long labels
            if len(label) > 15:
                label = label[:12] + "..."
            
            return label
        
        # Generate generic label based on flow type
        if hasattr(flow, 'flow_type'):
            if flow.flow_type == 'control':
                return "control"
            elif flow.flow_type == 'event':
                return "event"
        
        return "data"
    
    def _get_dfd_styling(self) -> List[str]:
        """Get styling classes for data flow diagrams."""
        return [
            "",
            "    %% DFD Styling",
            "    classDef external fill:#ffe0b2,stroke:#f57c00,stroke-width:3px,color:#000,font-weight:bold",
            "    classDef process fill:#c8e6c9,stroke:#388e3c,stroke-width:3px,color:#000,font-weight:bold",
            "    classDef datastore fill:#e1bee7,stroke:#8e24aa,stroke-width:3px,color:#000,font-weight:bold",
            "",
            "    %% Flow styling",
            "    linkStyle default stroke:#666,stroke-width:2px"
        ]
    
    def _filter_nodes(self, graph: nx.DiGraph, config: DiagramConfig) -> List[str]:
        """Filter nodes based on configuration with advanced filtering options."""
        nodes = list(graph.nodes())
        
        # Apply include patterns with regex support
        if config.filter_patterns:
            import re
            filtered_nodes = []
            for node in nodes:
                if any(re.search(pattern, node) for pattern in config.filter_patterns):
                    filtered_nodes.append(node)
            nodes = filtered_nodes
        
        # Apply exclude patterns with regex support
        if config.exclude_patterns:
            import re
            nodes = [node for node in nodes 
                    if not any(re.search(pattern, node) for pattern in config.exclude_patterns)]
        
        # Filter external nodes if not included
        if not config.include_external:
            nodes = [node for node in nodes 
                    if not graph.nodes.get(node, {}).get('external', False)]
        
        # Advanced filtering: remove isolated nodes (no connections)
        connected_nodes = []
        for node in nodes:
            if graph.degree(node) > 0:
                connected_nodes.append(node)
        nodes = connected_nodes
        
        # Limit number of nodes with smart selection
        if len(nodes) > config.max_nodes:
            nodes = self._select_most_important_nodes(graph, nodes, config.max_nodes)
        
        return nodes
    
    def _select_most_important_nodes(self, graph: nx.DiGraph, nodes: List[str], max_nodes: int) -> List[str]:
        """Select most important nodes using multiple criteria."""
        # Calculate importance scores
        node_scores = {}
        
        for node in nodes:
            score = 0
            
            # Degree centrality (number of connections)
            degree = graph.degree(node)
            score += degree * 2
            
            # Betweenness centrality (how often node appears on shortest paths)
            try:
                subgraph = graph.subgraph(nodes)
                betweenness = nx.betweenness_centrality(subgraph).get(node, 0)
                score += betweenness * 10
            except:
                pass  # Skip if calculation fails
            
            # PageRank (importance based on incoming links)
            try:
                pagerank = nx.pagerank(graph.subgraph(nodes)).get(node, 0)
                score += pagerank * 100
            except:
                pass  # Skip if calculation fails
            
            # Boost score for non-external nodes
            if not graph.nodes.get(node, {}).get('external', False):
                score *= 1.5
            
            node_scores[node] = score
        
        # Sort by score and take top nodes
        sorted_nodes = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)
        selected_nodes = [node for node, _ in sorted_nodes[:max_nodes]]
        
        # Ensure we include nodes that are connected to selected nodes
        # to maintain graph connectivity
        final_nodes = set(selected_nodes)
        for node in selected_nodes:
            # Add immediate neighbors if they're in the original node list
            neighbors = set(graph.neighbors(node)) | set(graph.predecessors(node))
            for neighbor in neighbors:
                if neighbor in nodes and len(final_nodes) < max_nodes * 1.2:  # Allow 20% more for connectivity
                    final_nodes.add(neighbor)
        
        return list(final_nodes)[:max_nodes]
    
    def _create_node_label(self, node: str, node_data: Dict[str, Any], config: DiagramConfig = None) -> str:
        """Create an enhanced label for a node with metadata."""
        # Use the last part of the module name for cleaner display
        parts = node.split('.')
        display_name = parts[-1] if parts else node
        
        # Clean up the display name
        display_name = display_name.replace('_', ' ').title()
        
        # Add metadata if available (simplified for readability)
        metadata_parts = []
        
        if 'language' in node_data:
            lang = node_data['language']
            if config and config.use_emojis:
                if lang == 'Python':
                    metadata_parts.append('🐍')
                elif lang == 'JavaScript':
                    metadata_parts.append('🟨')
                elif lang == 'TypeScript':
                    metadata_parts.append('🔷')
                elif lang == 'Java':
                    metadata_parts.append('☕')
                else:
                    metadata_parts.append(lang[:3].upper())
            else:
                metadata_parts.append(lang[:3].upper())
        
        if 'classes' in node_data and node_data['classes'] > 0:
            metadata_parts.append(f"{node_data['classes']}C")
        
        if 'functions' in node_data and node_data['functions'] > 0:
            metadata_parts.append(f"{node_data['functions']}F")
        
        if node_data.get('external', False):
            metadata_parts.append("EXT")
        
        if metadata_parts:
            display_name += f"\\n{' '.join(metadata_parts)}"
        
        # Truncate very long names but keep them readable
        if len(display_name) > 25:
            display_name = display_name[:22] + "..."
        
        return display_name
    
    def _sanitize_id(self, identifier: str) -> str:
        """Sanitize identifier for Mermaid syntax."""
        # Replace dots and other special characters with underscores
        return identifier.replace('.', '_').replace('-', '_').replace('/', '_')
    
    def _get_edge_style(self, relation_type: str, strength: int) -> str:
        """Get edge style based on relationship type and strength."""
        if relation_type == 'inheritance':
            return '-->'
        elif relation_type == 'composition':
            return '==>'
        elif strength > 2:
            return '-->'
        else:
            return '-.->'
    
    def _should_include_class(self, class_name: str, config: DiagramConfig) -> bool:
        """Check if a class should be included based on configuration."""
        # Apply include patterns
        if config.filter_patterns:
            if not any(pattern in class_name for pattern in config.filter_patterns):
                return False
        
        # Apply exclude patterns
        if config.exclude_patterns:
            if any(pattern in class_name for pattern in config.exclude_patterns):
                return False
        
        return True
    
    def _render_class_definition(self, class_name: str, class_info, config: DiagramConfig) -> List[str]:
        """Render a comprehensive class definition in Mermaid syntax."""
        lines = []
        sanitized_name = self._sanitize_id(class_name)
        simple_name = class_name.split('.')[-1]  # Use simple name for display
        
        # Determine class type and add appropriate annotation
        class_type = self._determine_class_type(class_info)
        if class_type == "abstract":
            lines.append(f"    class {sanitized_name} {{")
            lines.append(f"        <<abstract>>")
        elif class_type == "interface":
            lines.append(f"    class {sanitized_name} {{")
            lines.append(f"        <<interface>>")
        else:
            lines.append(f"    class {sanitized_name} {{")
        
        # Add attributes if configured
        if config.show_attributes and hasattr(class_info, 'attributes'):
            # Sort attributes by visibility (public first)
            sorted_attributes = sorted(class_info.attributes, 
                                     key=lambda x: self._get_visibility_order(x.visibility))
            
            for attr in sorted_attributes:
                visibility = self._get_visibility_symbol(attr.visibility)
                type_hint = f" : {self._format_type_hint(attr.type_hint)}" if attr.type_hint else ""
                
                # Add static indicator
                static_indicator = " {static}" if getattr(attr, 'is_static', False) else ""
                
                # Add default value if available
                default_value = f" = {attr.default_value}" if getattr(attr, 'default_value', None) else ""
                
                lines.append(f"        {visibility}{attr.name}{type_hint}{static_indicator}{default_value}")
        
        # Add separator between attributes and methods
        if (config.show_attributes and hasattr(class_info, 'attributes') and class_info.attributes and
            config.show_methods and hasattr(class_info, 'methods') and class_info.methods):
            lines.append("        ---")
        
        # Add methods if configured
        if config.show_methods and hasattr(class_info, 'methods'):
            # Sort methods by visibility and type
            sorted_methods = sorted(class_info.methods, 
                                  key=lambda x: (self._get_visibility_order(x.visibility), x.name))
            
            for method in sorted_methods:
                visibility = self._get_visibility_symbol(method.visibility)
                
                # Format parameters
                params = self._format_method_parameters(method, config)
                
                # Format return type
                return_type = f" : {self._format_type_hint(method.return_type)}" if method.return_type else ""
                
                # Add method modifiers
                modifiers = []
                if getattr(method, 'is_static', False):
                    modifiers.append("static")
                if getattr(method, 'is_abstract', False):
                    modifiers.append("abstract")
                if getattr(method, 'is_async', False):
                    modifiers.append("async")
                
                modifier_str = " {" + ", ".join(modifiers) + "}" if modifiers else ""
                
                lines.append(f"        {visibility}{method.name}{params}{return_type}{modifier_str}")
        
        lines.append("    }")
        
        # Add class-level annotations
        if hasattr(class_info, 'decorators') and class_info.decorators:
            for decorator in class_info.decorators:
                lines.append(f"    {sanitized_name} : <<{decorator}>>")
        
        return lines
    
    def _determine_class_type(self, class_info) -> str:
        """Determine the type of class (regular, abstract, interface)."""
        if getattr(class_info, 'is_abstract', False):
            return "abstract"
        
        # Check if all methods are abstract (interface-like)
        if hasattr(class_info, 'methods') and class_info.methods:
            all_abstract = all(getattr(method, 'is_abstract', False) for method in class_info.methods)
            if all_abstract:
                return "interface"
        
        return "regular"
    
    def _get_visibility_order(self, visibility) -> int:
        """Get sort order for visibility (public first)."""
        if hasattr(visibility, 'value'):
            visibility = visibility.value
        
        order_map = {
            'public': 0,
            'protected': 1,
            'private': 2
        }
        return order_map.get(visibility, 0)
    
    def _format_type_hint(self, type_hint: Optional[str]) -> str:
        """Format type hint for display."""
        if not type_hint:
            return ""
        
        # Simplify common generic types
        type_hint = type_hint.replace('typing.', '')
        type_hint = type_hint.replace('Optional[', '?')
        type_hint = type_hint.replace(']', '')
        
        # Truncate very long type hints
        if len(type_hint) > 20:
            type_hint = type_hint[:17] + "..."
        
        return type_hint
    
    def _format_method_parameters(self, method, config: DiagramConfig) -> str:
        """Format method parameters for display."""
        if not config.show_parameters or not hasattr(method, 'parameters') or not method.parameters:
            return "()"
        
        param_strs = []
        for param in method.parameters:
            if param.name in ['self', 'cls']:  # Skip self and cls parameters
                continue
            
            param_str = param.name
            
            # Add type hint
            if param.type_hint:
                param_str += f": {self._format_type_hint(param.type_hint)}"
            
            # Add default value
            if getattr(param, 'default_value', None):
                param_str += f" = {param.default_value}"
            
            # Add parameter modifiers
            if getattr(param, 'is_varargs', False):
                param_str = "*" + param_str
            elif getattr(param, 'is_kwargs', False):
                param_str = "**" + param_str
            
            param_strs.append(param_str)
        
        # Limit parameter display to avoid clutter
        if len(param_strs) > 3:
            param_strs = param_strs[:3] + ["..."]
        
        return f"({', '.join(param_strs)})"
    
    def _get_visibility_symbol(self, visibility) -> str:
        """Get UML visibility symbol."""
        if hasattr(visibility, 'value'):
            visibility = visibility.value
        
        visibility_map = {
            'public': '+',
            'private': '-',
            'protected': '#'
        }
        return visibility_map.get(visibility, '+')
    
    def _render_class_relationship(self, relationship) -> str:
        """Render a class relationship with proper UML notation in Mermaid syntax."""
        source = self._sanitize_id(relationship.source_class)
        target = self._sanitize_id(relationship.target_class)
        
        # Get relationship type
        if hasattr(relationship.relationship_type, 'value'):
            rel_type = relationship.relationship_type.value
        else:
            rel_type = str(relationship.relationship_type)
        
        # Create relationship with proper UML notation and labels
        relationship_lines = []
        
        if rel_type == 'inheritance':
            # Inheritance: hollow triangle arrow
            relationship_lines.append(f"    {source} --|> {target} : inherits")
        elif rel_type == 'composition':
            # Composition: filled diamond (strong ownership)
            multiplicity = self._get_multiplicity_label(relationship)
            relationship_lines.append(f"    {source} *-- {target} : {multiplicity}")
        elif rel_type == 'aggregation':
            # Aggregation: hollow diamond (weak ownership)
            multiplicity = self._get_multiplicity_label(relationship)
            relationship_lines.append(f"    {source} o-- {target} : {multiplicity}")
        elif rel_type == 'dependency':
            # Dependency: dashed arrow
            context = getattr(relationship, 'context', '')
            label = self._extract_dependency_label(context)
            relationship_lines.append(f"    {source} ..> {target} : {label}")
        else:
            # Generic association
            relationship_lines.append(f"    {source} --> {target}")
        
        return "\n".join(relationship_lines)
    
    def _get_multiplicity_label(self, relationship) -> str:
        """Extract multiplicity information from relationship context."""
        context = getattr(relationship, 'context', '')
        
        # Try to infer multiplicity from context
        if 'List[' in context or 'list' in context.lower():
            return "1..*"
        elif 'Dict[' in context or 'dict' in context.lower():
            return "0..*"
        elif 'Optional[' in context or '?' in context:
            return "0..1"
        else:
            return "1"
    
    def _extract_dependency_label(self, context: str) -> str:
        """Extract meaningful label from dependency context."""
        if not context:
            return "uses"
        
        # Extract meaningful parts from context
        if 'parameter' in context:
            return "uses"
        elif 'method' in context:
            return "calls"
        elif 'attribute' in context:
            return "has"
        else:
            return "depends on"
    
    def _render_external_dependencies(self, external_deps: set) -> List[str]:
        """Render external dependencies as notes."""
        lines = []
        
        if external_deps:
            lines.append("")
            lines.append("    %% External Dependencies")
            
            for dep in list(external_deps)[:5]:  # Limit to 5 external deps
                sanitized_dep = self._sanitize_id(dep)
                lines.append(f"    class {sanitized_dep} {{")
                lines.append(f"        <<external>>")
                lines.append("    }")
        
        return lines
    
    def _get_class_diagram_styling(self) -> List[str]:
        """Get styling classes for class diagrams."""
        return [
            "",
            "    %% Styling",
            "    classDef abstract fill:#e1f5fe,stroke:#0277bd,stroke-width:3px,stroke-dasharray: 5 5,color:#000,font-weight:bold",
            "    classDef interface fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px,stroke-dasharray: 10 5,color:#000,font-weight:bold",
            "    classDef external fill:#fff3e0,stroke:#ef6c00,stroke-width:3px,stroke-dasharray: 3 3,color:#000,font-weight:bold"
        ]
    
    def _should_include_node(self, node_name: str, config: DiagramConfig) -> bool:
        """Check if a node should be included in data flow diagram."""
        return self._should_include_class(node_name, config)
    
    def _should_include_node(self, node_name: str, config: DiagramConfig) -> bool:
        """Check if a node should be included in data flow diagram."""
        return self._should_include_class(node_name, config)


class DiagramExporter:
    """Handles export of diagrams to various image formats."""
    
    def __init__(self):
        """Initialize the diagram exporter."""
        self.logger = logging.getLogger(__name__)
        self._check_dependencies()
    
    def _check_dependencies(self) -> None:
        """Check if required external tools are available."""
        self.mermaid_cli_available = shutil.which('mmdc') is not None
        self.puppeteer_available = shutil.which('node') is not None
        
        if not self.mermaid_cli_available:
            self.logger.warning("mermaid-cli (mmdc) not found. SVG/PNG export will be limited.")
        
        self.logger.info(f"Mermaid CLI available: {self.mermaid_cli_available}")
    
    async def export_to_svg(self, mermaid_content: str, title: Optional[str] = None) -> str:
        """Export Mermaid diagram to SVG format.
        
        Args:
            mermaid_content: Mermaid diagram syntax
            title: Optional title for the diagram
            
        Returns:
            SVG content as string
        """
        if self.mermaid_cli_available:
            return await self._export_with_mermaid_cli(mermaid_content, 'svg')
        else:
            return await self._export_with_fallback_svg(mermaid_content, title)
    
    async def export_to_png(self, mermaid_content: str, title: Optional[str] = None) -> bytes:
        """Export Mermaid diagram to PNG format.
        
        Args:
            mermaid_content: Mermaid diagram syntax
            title: Optional title for the diagram
            
        Returns:
            PNG content as bytes
        """
        if self.mermaid_cli_available:
            return await self._export_with_mermaid_cli(mermaid_content, 'png')
        else:
            raise RuntimeError("PNG export requires mermaid-cli (mmdc) to be installed")
    
    async def _export_with_mermaid_cli(self, mermaid_content: str, format: str) -> Any:
        """Export using mermaid-cli tool."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "diagram.mmd"
            output_file = temp_path / f"diagram.{format}"
            
            # Write Mermaid content to file
            input_file.write_text(mermaid_content, encoding='utf-8')
            
            # Prepare mermaid-cli command
            cmd = [
                'mmdc',
                '-i', str(input_file),
                '-o', str(output_file),
                '-t', 'default',  # theme
                '--width', '1200',
                '--height', '800',
                '--backgroundColor', 'white'
            ]
            
            try:
                # Run mermaid-cli
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                    raise RuntimeError(f"Mermaid CLI failed: {error_msg}")
                
                # Read output file
                if format == 'svg':
                    return output_file.read_text(encoding='utf-8')
                else:  # png
                    return output_file.read_bytes()
                    
            except Exception as e:
                self.logger.error(f"Failed to export with mermaid-cli: {e}")
                raise RuntimeError(f"Export failed: {e}")
    
    async def _export_with_fallback_svg(self, mermaid_content: str, title: Optional[str] = None) -> str:
        """Fallback SVG export without external dependencies."""
        # Create a basic SVG wrapper for the Mermaid content
        # This is a simplified fallback that embeds the Mermaid syntax as text
        
        svg_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
    <rect width="100%" height="100%" fill="white"/>
    {f'<text x="400" y="30" text-anchor="middle" font-size="16" font-weight="bold">{title}</text>' if title else ''}
    <foreignObject x="50" y="50" width="700" height="500">
        <div xmlns="http://www.w3.org/1999/xhtml" style="font-family: monospace; font-size: 12px; padding: 10px;">
            <pre style="white-space: pre-wrap; word-wrap: break-word;">
{mermaid_content}
            </pre>
            <p style="margin-top: 20px; font-style: italic; color: #666;">
                Note: This is a fallback SVG. Install mermaid-cli for proper diagram rendering.
            </p>
        </div>
    </foreignObject>
</svg>"""
        
        return svg_template


class DiagramGenerator:
    """Main diagram generator with pluggable format renderers and export capabilities."""
    
    def __init__(self):
        """Initialize the diagram generator."""
        self.logger = logging.getLogger(__name__)
        self.renderers: Dict[DiagramFormat, DiagramRenderer] = {}
        self.exporter = DiagramExporter()
        
        # Register default renderers
        self._register_renderer(MermaidRenderer())
    
    def _register_renderer(self, renderer: DiagramRenderer) -> None:
        """Register a diagram renderer."""
        format_type = renderer.get_supported_format()
        self.renderers[format_type] = renderer
        self.logger.info(f"Registered renderer for format: {format_type.value}")
    
    def get_supported_formats(self) -> List[DiagramFormat]:
        """Get list of supported diagram formats."""
        return list(self.renderers.keys())
    
    def is_export_available(self, format: DiagramFormat) -> bool:
        """Check if export to specific format is available."""
        if format == DiagramFormat.MERMAID:
            return True
        elif format == DiagramFormat.SVG:
            return True  # Fallback always available
        elif format == DiagramFormat.PNG:
            return self.exporter.mermaid_cli_available
        else:
            return False
    
    async def generate_dependency_diagram(self, graph: nx.DiGraph, config: DiagramConfig) -> DiagramOutput:
        """Generate a dependency diagram from a NetworkX graph.
        
        Args:
            graph: NetworkX directed graph representing dependencies
            config: Configuration for diagram generation
            
        Returns:
            DiagramOutput containing the generated diagram
        """
        self.logger.info(f"Generating dependency diagram in {config.format.value} format")
        
        # Generate base content
        if config.format == DiagramFormat.MERMAID or config.format in [DiagramFormat.SVG, DiagramFormat.PNG]:
            # For SVG/PNG, first generate Mermaid then export
            mermaid_renderer = self.renderers[DiagramFormat.MERMAID]
            mermaid_content = await mermaid_renderer.render_dependency_diagram(graph, config)
            
            if config.format == DiagramFormat.MERMAID:
                content = mermaid_content
            elif config.format == DiagramFormat.SVG:
                content = await self.exporter.export_to_svg(mermaid_content, config.title)
            elif config.format == DiagramFormat.PNG:
                content = await self.exporter.export_to_png(mermaid_content, config.title)
            else:
                raise ValueError(f"Unsupported format: {config.format.value}")
        else:
            if config.format not in self.renderers:
                raise ValueError(f"Unsupported format: {config.format.value}")
            
            renderer = self.renderers[config.format]
            content = await renderer.render_dependency_diagram(graph, config)
        
        # Calculate metadata
        metadata = {
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "layout": config.layout,
            "include_external": config.include_external,
            "export_method": "mermaid-cli" if self.exporter.mermaid_cli_available else "fallback"
        }
        
        return DiagramOutput(
            content=content,
            format=config.format,
            diagram_type=DiagramType.DEPENDENCY,
            metadata=metadata,
            title=config.title,
            description=f"Dependency diagram with {metadata['node_count']} nodes and {metadata['edge_count']} edges"
        )
    
    async def generate_class_diagram(self, class_diagram: ClassDiagram, config: DiagramConfig) -> DiagramOutput:
        """Generate a class diagram from ClassDiagram data.
        
        Args:
            class_diagram: ClassDiagram data structure
            config: Configuration for diagram generation
            
        Returns:
            DiagramOutput containing the generated diagram
        """
        self.logger.info(f"Generating class diagram in {config.format.value} format")
        
        # Generate base content
        if config.format == DiagramFormat.MERMAID or config.format in [DiagramFormat.SVG, DiagramFormat.PNG]:
            # For SVG/PNG, first generate Mermaid then export
            mermaid_renderer = self.renderers[DiagramFormat.MERMAID]
            mermaid_content = await mermaid_renderer.render_class_diagram(class_diagram, config)
            
            if config.format == DiagramFormat.MERMAID:
                content = mermaid_content
            elif config.format == DiagramFormat.SVG:
                content = await self.exporter.export_to_svg(mermaid_content, config.title)
            elif config.format == DiagramFormat.PNG:
                content = await self.exporter.export_to_png(mermaid_content, config.title)
            else:
                raise ValueError(f"Unsupported format: {config.format.value}")
        else:
            if config.format not in self.renderers:
                raise ValueError(f"Unsupported format: {config.format.value}")
            
            renderer = self.renderers[config.format]
            content = await renderer.render_class_diagram(class_diagram, config)
        
        # Calculate metadata
        metadata = {
            "class_count": len(class_diagram.classes),
            "relationship_count": len(class_diagram.relationships),
            "package_count": len(class_diagram.packages),
            "external_dependencies": len(class_diagram.external_dependencies),
            "export_method": "mermaid-cli" if self.exporter.mermaid_cli_available else "fallback"
        }
        
        return DiagramOutput(
            content=content,
            format=config.format,
            diagram_type=DiagramType.CLASS,
            metadata=metadata,
            title=config.title,
            description=f"Class diagram with {metadata['class_count']} classes and {metadata['relationship_count']} relationships"
        )
    
    async def generate_data_flow_diagram(self, dfd: DataFlowDiagram, config: DiagramConfig) -> DiagramOutput:
        """Generate a data flow diagram from DataFlowDiagram data.
        
        Args:
            dfd: DataFlowDiagram data structure
            config: Configuration for diagram generation
            
        Returns:
            DiagramOutput containing the generated diagram
        """
        self.logger.info(f"Generating data flow diagram in {config.format.value} format")
        
        # Generate base content
        if config.format == DiagramFormat.MERMAID or config.format in [DiagramFormat.SVG, DiagramFormat.PNG]:
            # For SVG/PNG, first generate Mermaid then export
            mermaid_renderer = self.renderers[DiagramFormat.MERMAID]
            mermaid_content = await mermaid_renderer.render_data_flow_diagram(dfd, config)
            
            if config.format == DiagramFormat.MERMAID:
                content = mermaid_content
            elif config.format == DiagramFormat.SVG:
                content = await self.exporter.export_to_svg(mermaid_content, config.title)
            elif config.format == DiagramFormat.PNG:
                content = await self.exporter.export_to_png(mermaid_content, config.title)
            else:
                raise ValueError(f"Unsupported format: {config.format.value}")
        else:
            if config.format not in self.renderers:
                raise ValueError(f"Unsupported format: {config.format.value}")
            
            renderer = self.renderers[config.format]
            content = await renderer.render_data_flow_diagram(dfd, config)
        
        # Calculate metadata
        metadata = {
            "node_count": len(dfd.nodes),
            "flow_count": len(dfd.flows),
            "process_count": len(dfd.processes),
            "external_entity_count": len(dfd.external_entities),
            "data_store_count": len(dfd.data_stores),
            "export_method": "mermaid-cli" if self.exporter.mermaid_cli_available else "fallback"
        }
        
        return DiagramOutput(
            content=content,
            format=config.format,
            diagram_type=DiagramType.DATA_FLOW,
            metadata=metadata,
            title=config.title,
            description=f"Data flow diagram with {metadata['process_count']} processes and {metadata['flow_count']} flows"
        )
    
    async def batch_export_diagrams(self, diagrams: List[DiagramOutput], 
                                   export_formats: List[DiagramFormat]) -> Dict[str, List[DiagramOutput]]:
        """Export multiple diagrams to multiple formats efficiently.
        
        Args:
            diagrams: List of diagrams to export
            export_formats: List of formats to export to
            
        Returns:
            Dictionary mapping format names to lists of exported diagrams
        """
        self.logger.info(f"Batch exporting {len(diagrams)} diagrams to {len(export_formats)} formats")
        
        results = {}
        
        for format in export_formats:
            results[format.value] = []
            
            for diagram in diagrams:
                try:
                    if diagram.format == format:
                        # Already in target format
                        results[format.value].append(diagram)
                    elif diagram.format == DiagramFormat.MERMAID and format in [DiagramFormat.SVG, DiagramFormat.PNG]:
                        # Export from Mermaid to image format
                        if format == DiagramFormat.SVG:
                            exported_content = await self.exporter.export_to_svg(diagram.content, diagram.title)
                        else:  # PNG
                            exported_content = await self.exporter.export_to_png(diagram.content, diagram.title)
                        
                        exported_diagram = DiagramOutput(
                            content=exported_content,
                            format=format,
                            diagram_type=diagram.diagram_type,
                            metadata={**diagram.metadata, "exported_from": diagram.format.value},
                            title=diagram.title,
                            description=diagram.description
                        )
                        results[format.value].append(exported_diagram)
                    else:
                        self.logger.warning(f"Cannot export from {diagram.format.value} to {format.value}")
                        
                except Exception as e:
                    self.logger.error(f"Failed to export diagram to {format.value}: {e}")
                    continue
        
        return results