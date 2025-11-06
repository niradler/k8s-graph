import logging
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


def merge_graphs(graphs: list[nx.DiGraph]) -> nx.DiGraph:
    """
    Merge multiple graphs into one.

    Nodes and edges from all graphs are combined. If the same node appears
    in multiple graphs, attributes are merged (later graphs take precedence).

    Args:
        graphs: List of NetworkX directed graphs to merge

    Returns:
        Merged NetworkX directed graph

    Example:
        >>> namespace_graphs = [build_namespace_graph(ns) for ns in namespaces]
        >>> cluster_graph = merge_graphs(namespace_graphs)
    """
    if not graphs:
        return nx.DiGraph()

    merged = nx.DiGraph()

    for graph in graphs:
        for node, attrs in graph.nodes(data=True):
            if merged.has_node(node):
                merged.nodes[node].update(attrs)
            else:
                merged.add_node(node, **attrs)

        for source, target, attrs in graph.edges(data=True):
            if merged.has_edge(source, target):
                merged[source][target].update(attrs)
            else:
                merged.add_edge(source, target, **attrs)

    logger.info(
        f"Merged {len(graphs)} graphs into graph with "
        f"{merged.number_of_nodes()} nodes and {merged.number_of_edges()} edges"
    )

    return merged


def compose_namespace_graphs(graphs: dict[str, nx.DiGraph]) -> nx.DiGraph:
    """
    Compose graphs from multiple namespaces with namespace nodes.

    Creates a unified graph where each namespace is represented as a node,
    and resources are connected to their namespace.

    Args:
        graphs: Dictionary mapping namespace names to their graphs

    Returns:
        Composed graph with namespace hierarchy

    Example:
        >>> ns_graphs = {
        ...     "default": default_graph,
        ...     "kube-system": kube_system_graph
        ... }
        >>> cluster_graph = compose_namespace_graphs(ns_graphs)
    """
    composed = nx.DiGraph()

    for namespace, graph in graphs.items():
        ns_node_id = f"Namespace:{namespace}"
        composed.add_node(
            ns_node_id,
            kind="Namespace",
            name=namespace,
            namespace=None,
        )

        for node, attrs in graph.nodes(data=True):
            composed.add_node(node, **attrs)

            if attrs.get("namespace") == namespace:
                composed.add_edge(
                    node,
                    ns_node_id,
                    relationship_type="namespace",
                    details=f"Resource in namespace '{namespace}'",
                )

        for source, target, attrs in graph.edges(data=True):
            composed.add_edge(source, target, **attrs)

    logger.info(
        f"Composed {len(graphs)} namespace graphs into graph with "
        f"{composed.number_of_nodes()} nodes and {composed.number_of_edges()} edges"
    )

    return composed


def extract_namespace(graph: nx.DiGraph, namespace: str) -> nx.DiGraph:
    """
    Extract subgraph containing only resources from a specific namespace.

    Args:
        graph: NetworkX directed graph
        namespace: Namespace to extract

    Returns:
        Subgraph containing only resources from the namespace

    Example:
        >>> default_graph = extract_namespace(cluster_graph, "default")
    """
    namespace_nodes = [
        node for node, attrs in graph.nodes(data=True) if attrs.get("namespace") == namespace
    ]

    if not namespace_nodes:
        logger.warning(f"No resources found in namespace: {namespace}")
        return nx.DiGraph()

    subgraph = graph.subgraph(namespace_nodes).copy()

    logger.info(
        f"Extracted namespace '{namespace}' with "
        f"{subgraph.number_of_nodes()} nodes and {subgraph.number_of_edges()} edges"
    )

    return subgraph


def diff_graphs(graph1: nx.DiGraph, graph2: nx.DiGraph) -> dict[str, Any]:
    """
    Compare two graphs and identify differences.

    Args:
        graph1: First graph (baseline)
        graph2: Second graph (comparison)

    Returns:
        Dictionary with:
        - added_nodes: Nodes in graph2 but not in graph1
        - removed_nodes: Nodes in graph1 but not in graph2
        - added_edges: Edges in graph2 but not in graph1
        - removed_edges: Edges in graph1 but not in graph2
        - modified_nodes: Nodes with changed attributes
        - added_subgraph: Graph of added nodes/edges
        - removed_subgraph: Graph of removed nodes/edges

    Example:
        >>> before = load_graph("before.json")
        >>> after = load_graph("after.json")
        >>> diff = diff_graphs(before, after)
        >>> print(f"Added {len(diff['added_nodes'])} resources")
    """
    nodes1 = set(graph1.nodes())
    nodes2 = set(graph2.nodes())

    added_nodes = list(nodes2 - nodes1)
    removed_nodes = list(nodes1 - nodes2)

    edges1 = set(graph1.edges())
    edges2 = set(graph2.edges())

    added_edges = list(edges2 - edges1)
    removed_edges = list(edges1 - edges2)

    modified_nodes = []
    common_nodes = nodes1 & nodes2
    for node in common_nodes:
        attrs1 = dict(graph1.nodes[node])
        attrs2 = dict(graph2.nodes[node])
        if attrs1 != attrs2:
            modified_nodes.append(
                {
                    "node_id": node,
                    "before": attrs1,
                    "after": attrs2,
                }
            )

    added_subgraph = nx.DiGraph()
    for node in added_nodes:
        added_subgraph.add_node(node, **graph2.nodes[node])
    for source, target in added_edges:
        if graph2.has_edge(source, target):
            added_subgraph.add_edge(source, target, **graph2[source][target])

    removed_subgraph = nx.DiGraph()
    for node in removed_nodes:
        removed_subgraph.add_node(node, **graph1.nodes[node])
    for source, target in removed_edges:
        if graph1.has_edge(source, target):
            removed_subgraph.add_edge(source, target, **graph1[source][target])

    logger.info(
        f"Graph diff: +{len(added_nodes)} nodes, -{len(removed_nodes)} nodes, "
        f"+{len(added_edges)} edges, -{len(removed_edges)} edges, "
        f"~{len(modified_nodes)} modified"
    )

    return {
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
        "modified_nodes": modified_nodes,
        "added_subgraph": added_subgraph,
        "removed_subgraph": removed_subgraph,
    }


def union_graphs(graph1: nx.DiGraph, graph2: nx.DiGraph) -> nx.DiGraph:
    """
    Create union of two graphs.

    Uses NetworkX compose which combines all nodes and edges.
    When nodes/edges exist in both graphs, attributes from graph2 take precedence.

    Args:
        graph1: First graph
        graph2: Second graph

    Returns:
        Union graph containing all nodes and edges

    Example:
        >>> prod_graph = load_graph("prod.json")
        >>> staging_graph = load_graph("staging.json")
        >>> combined = union_graphs(prod_graph, staging_graph)
    """
    union = nx.compose(graph1, graph2)

    logger.info(
        f"Union of graphs: {union.number_of_nodes()} nodes, {union.number_of_edges()} edges"
    )

    return union


def filter_by_kind(graph: nx.DiGraph, kinds: list[str]) -> nx.DiGraph:
    """
    Filter graph to include only specific resource kinds.

    Args:
        graph: NetworkX directed graph
        kinds: List of resource kinds to include

    Returns:
        Filtered subgraph

    Example:
        >>> workload_graph = filter_by_kind(graph, ["Deployment", "StatefulSet", "DaemonSet"])
    """
    filtered_nodes = [node for node, attrs in graph.nodes(data=True) if attrs.get("kind") in kinds]

    if not filtered_nodes:
        logger.warning(f"No nodes found with kinds: {kinds}")
        return nx.DiGraph()

    subgraph = graph.subgraph(filtered_nodes).copy()

    logger.info(
        f"Filtered graph by kinds {kinds}: "
        f"{subgraph.number_of_nodes()} nodes, {subgraph.number_of_edges()} edges"
    )

    return subgraph


def filter_by_relationship(graph: nx.DiGraph, relationship_types: list[str]) -> nx.DiGraph:
    """
    Filter graph to include only specific relationship types.

    Args:
        graph: NetworkX directed graph
        relationship_types: List of relationship types to include

    Returns:
        Graph with filtered edges (all nodes retained)

    Example:
        >>> ownership_graph = filter_by_relationship(graph, ["owner", "owned"])
    """
    filtered = graph.copy()

    edges_to_remove = [
        (source, target)
        for source, target, attrs in filtered.edges(data=True)
        if attrs.get("relationship_type") not in relationship_types
    ]

    filtered.remove_edges_from(edges_to_remove)

    logger.info(
        f"Filtered graph by relationships {relationship_types}: "
        f"kept {filtered.number_of_edges()}/{graph.number_of_edges()} edges"
    )

    return filtered


def remove_isolated_nodes(graph: nx.DiGraph) -> nx.DiGraph:
    """
    Remove nodes with no connections.

    Args:
        graph: NetworkX directed graph

    Returns:
        Graph with isolated nodes removed

    Example:
        >>> connected_graph = remove_isolated_nodes(graph)
    """
    isolated = list(nx.isolates(graph))

    if not isolated:
        logger.info("No isolated nodes found")
        return graph.copy()

    filtered = graph.copy()
    filtered.remove_nodes_from(isolated)

    logger.info(f"Removed {len(isolated)} isolated nodes")

    return filtered


def extract_connected_component(graph: nx.DiGraph, node_id: str) -> nx.DiGraph:
    """
    Extract the connected component containing a specific node.

    Args:
        graph: NetworkX directed graph
        node_id: Node ID to find component for

    Returns:
        Subgraph containing the connected component

    Example:
        >>> component = extract_connected_component(graph, "Deployment:default:nginx")
    """
    if not graph.has_node(node_id):
        logger.warning(f"Node {node_id} not found in graph")
        return nx.DiGraph()

    for component in nx.weakly_connected_components(graph):
        if node_id in component:
            subgraph = graph.subgraph(component).copy()
            logger.info(
                f"Extracted connected component with "
                f"{subgraph.number_of_nodes()} nodes and {subgraph.number_of_edges()} edges"
            )
            return subgraph

    return nx.DiGraph()


def get_largest_component(graph: nx.DiGraph) -> nx.DiGraph:
    """
    Get the largest weakly connected component.

    Args:
        graph: NetworkX directed graph

    Returns:
        Subgraph containing the largest component

    Example:
        >>> main_component = get_largest_component(graph)
    """
    if graph.number_of_nodes() == 0:
        return nx.DiGraph()

    largest = max(nx.weakly_connected_components(graph), key=len)
    subgraph = graph.subgraph(largest).copy()

    logger.info(
        f"Largest component has "
        f"{subgraph.number_of_nodes()} nodes and {subgraph.number_of_edges()} edges"
    )

    return subgraph


def split_by_namespace(graph: nx.DiGraph) -> dict[str, nx.DiGraph]:
    """
    Split graph into separate graphs per namespace.

    Args:
        graph: NetworkX directed graph

    Returns:
        Dictionary mapping namespace names to their subgraphs

    Example:
        >>> ns_graphs = split_by_namespace(cluster_graph)
        >>> for ns, g in ns_graphs.items():
        ...     print(f"{ns}: {g.number_of_nodes()} resources")
    """
    namespaces: dict[str, list[str]] = {}

    for node, attrs in graph.nodes(data=True):
        namespace = attrs.get("namespace", "cluster")
        if namespace not in namespaces:
            namespaces[namespace] = []
        namespaces[namespace].append(node)

    result = {}
    for namespace, nodes in namespaces.items():
        subgraph = graph.subgraph(nodes).copy()
        result[namespace] = subgraph

    logger.info(f"Split graph into {len(result)} namespace subgraphs")

    return result


def invert_graph(graph: nx.DiGraph) -> nx.DiGraph:
    """
    Invert the direction of all edges in the graph.

    Useful for switching between dependency and dependent views.

    Args:
        graph: NetworkX directed graph

    Returns:
        Graph with all edges reversed

    Example:
        >>> inverted = invert_graph(graph)
    """
    return graph.reverse(copy=True)
