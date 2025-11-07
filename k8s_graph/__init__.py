"""
k8s-graph: Protocol-based Python library for building NetworkX graphs from Kubernetes resources.

This library provides flexible, extensible tools for discovering and visualizing
relationships between Kubernetes resources using NetworkX graphs.

Key Features:
- Protocol-based design for easy integration
- Extensible discoverer registry system
- Stable node identity for pods and replicasets
- Built-in support for native K8s resources
- Comprehensive relationship discovery

Example:
    >>> from k8s_graph import GraphBuilder, KubernetesAdapter, ResourceIdentifier, BuildOptions
    >>> client = KubernetesAdapter()
    >>> builder = GraphBuilder(client)
    >>> graph = await builder.build_from_resource(
    ...     ResourceIdentifier(kind="Deployment", name="nginx", namespace="default"),
    ...     depth=2,
    ...     options=BuildOptions()
    ... )
"""

__version__ = "0.1.0"

from k8s_graph.builder import GraphBuilder
from k8s_graph.discoverers.base import BaseDiscoverer
from k8s_graph.discoverers.native import NativeResourceDiscoverer
from k8s_graph.discoverers.network import NetworkPolicyDiscoverer
from k8s_graph.discoverers.rbac import RBACDiscoverer
from k8s_graph.discoverers.registry import DiscovererRegistry
from k8s_graph.discoverers.unified import UnifiedDiscoverer
from k8s_graph.export import (
    aggregate_isolated_nodes,
    export_all,
    export_html,
    export_json,
    export_png,
    load_json,
)
from k8s_graph.formatter import export_to_dot, format_graph_output
from k8s_graph.models import (
    BuildOptions,
    DiscovererCategory,
    DiscoveryOptions,
    RelationshipType,
    ResourceIdentifier,
    ResourceRelationship,
)
from k8s_graph.node_identity import NodeIdentity
from k8s_graph.operations import (
    compose_namespace_graphs,
    diff_graphs,
    extract_namespace,
    filter_by_kind,
    filter_by_relationship,
    merge_graphs,
    split_by_namespace,
    union_graphs,
)
from k8s_graph.persistence import (
    from_dict,
    load_graph,
    load_graph_auto,
    save_graph,
    save_graph_auto,
    to_dict,
)
from k8s_graph.protocols import DiscovererProtocol, K8sClientProtocol
from k8s_graph.query import (
    extract_subgraph,
    filter_nodes,
    find_all_paths,
    find_by_kind,
    find_by_label,
    find_by_namespace,
    find_dependencies,
    find_dependents,
    find_path,
    get_edge_data,
    get_neighbors,
    get_node_data,
    get_resource_cluster,
)
from k8s_graph.traversal import (
    get_dependency_levels,
    get_leaves,
    get_longest_path,
    get_roots,
    reverse_topological_order,
    topological_order,
    traverse_bfs,
    traverse_by_relationship,
    traverse_dfs,
)
from k8s_graph.validator import (
    analyze_connectivity,
    analyze_dependency_depth,
    check_graph_cycles,
    find_isolated_components,
    get_graph_statistics,
    identify_critical_resources,
    validate_graph,
)
from k8s_graph.visualization import (
    create_legend,
    draw_circular,
    draw_cluster,
    draw_dependencies,
    draw_hierarchical,
    draw_namespace,
    draw_radial,
    draw_with_shell_layout,
    get_shell_layout,
)

try:
    from k8s_graph.adapters.kubernetes import KubernetesAdapter

    _has_kubernetes = True
except ImportError:
    _has_kubernetes = False

__all__ = [
    "__version__",
    "BuildOptions",
    "DiscovererCategory",
    "DiscoveryOptions",
    "RelationshipType",
    "ResourceIdentifier",
    "ResourceRelationship",
    "K8sClientProtocol",
    "DiscovererProtocol",
    "GraphBuilder",
    "NodeIdentity",
    "DiscovererRegistry",
    "UnifiedDiscoverer",
    "BaseDiscoverer",
    "NativeResourceDiscoverer",
    "RBACDiscoverer",
    "NetworkPolicyDiscoverer",
    "validate_graph",
    "check_graph_cycles",
    "get_graph_statistics",
    "analyze_connectivity",
    "analyze_dependency_depth",
    "find_isolated_components",
    "identify_critical_resources",
    "format_graph_output",
    "export_to_dot",
    "find_dependencies",
    "find_dependents",
    "find_path",
    "find_all_paths",
    "get_neighbors",
    "find_by_kind",
    "find_by_namespace",
    "find_by_label",
    "extract_subgraph",
    "get_resource_cluster",
    "get_edge_data",
    "get_node_data",
    "filter_nodes",
    "save_graph",
    "load_graph",
    "save_graph_auto",
    "load_graph_auto",
    "to_dict",
    "from_dict",
    "traverse_bfs",
    "traverse_dfs",
    "traverse_by_relationship",
    "get_roots",
    "get_leaves",
    "topological_order",
    "reverse_topological_order",
    "get_dependency_levels",
    "get_longest_path",
    "merge_graphs",
    "compose_namespace_graphs",
    "extract_namespace",
    "diff_graphs",
    "union_graphs",
    "filter_by_kind",
    "filter_by_relationship",
    "split_by_namespace",
    "draw_cluster",
    "draw_namespace",
    "draw_dependencies",
    "draw_with_shell_layout",
    "draw_hierarchical",
    "draw_radial",
    "draw_circular",
    "get_shell_layout",
    "create_legend",
    "export_png",
    "export_html",
    "export_json",
    "export_all",
    "load_json",
    "aggregate_isolated_nodes",
]

if _has_kubernetes:
    __all__.append("KubernetesAdapter")
