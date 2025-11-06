import logging
from collections.abc import Callable
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


def find_dependencies(
    graph: nx.DiGraph, resource_id: str, max_depth: int | None = None
) -> nx.DiGraph:
    """
    Find all resources that the given resource depends on.

    Args:
        graph: NetworkX directed graph
        resource_id: Node ID of the resource to find dependencies for
        max_depth: Maximum depth to traverse (None for unlimited)

    Returns:
        Subgraph containing the resource and all its dependencies

    Example:
        >>> deps = find_dependencies(graph, "Deployment:default:nginx", max_depth=2)
        >>> print(f"Found {deps.number_of_nodes()} dependencies")
    """
    if not graph.has_node(resource_id):
        logger.warning(f"Node {resource_id} not found in graph")
        return nx.DiGraph()

    if max_depth is None:
        descendants = nx.descendants(graph, resource_id)
    else:
        descendants = set()
        current_level = {resource_id}
        for _ in range(max_depth):
            next_level = set()
            for node in current_level:
                next_level.update(graph.successors(node))
            descendants.update(next_level)
            current_level = next_level
            if not current_level:
                break

    nodes = {resource_id} | descendants
    return graph.subgraph(nodes).copy()


def find_dependents(
    graph: nx.DiGraph, resource_id: str, max_depth: int | None = None
) -> nx.DiGraph:
    """
    Find all resources that depend on the given resource.

    Args:
        graph: NetworkX directed graph
        resource_id: Node ID of the resource to find dependents for
        max_depth: Maximum depth to traverse (None for unlimited)

    Returns:
        Subgraph containing the resource and all its dependents

    Example:
        >>> dependents = find_dependents(graph, "ConfigMap:default:app-config")
        >>> print(f"Found {dependents.number_of_nodes()} resources depending on this ConfigMap")
    """
    if not graph.has_node(resource_id):
        logger.warning(f"Node {resource_id} not found in graph")
        return nx.DiGraph()

    if max_depth is None:
        ancestors = nx.ancestors(graph, resource_id)
    else:
        ancestors = set()
        current_level = {resource_id}
        for _ in range(max_depth):
            next_level = set()
            for node in current_level:
                next_level.update(graph.predecessors(node))
            ancestors.update(next_level)
            current_level = next_level
            if not current_level:
                break

    nodes = {resource_id} | ancestors
    return graph.subgraph(nodes).copy()


def find_path(graph: nx.DiGraph, source: str, target: str) -> list[str] | None:
    """
    Find the shortest path between two resources.

    Args:
        graph: NetworkX directed graph
        source: Source node ID
        target: Target node ID

    Returns:
        List of node IDs representing the path, or None if no path exists

    Example:
        >>> path = find_path(graph, "Deployment:default:nginx", "Pod:default:nginx-abc")
        >>> if path:
        ...     print(" -> ".join(path))
    """
    if not graph.has_node(source):
        logger.warning(f"Source node {source} not found in graph")
        return None

    if not graph.has_node(target):
        logger.warning(f"Target node {target} not found in graph")
        return None

    try:
        result: list[str] = nx.shortest_path(graph, source, target)
        return result
    except nx.NetworkXNoPath:
        logger.debug(f"No path found between {source} and {target}")
        return None


def find_all_paths(
    graph: nx.DiGraph, source: str, target: str, cutoff: int | None = None
) -> list[list[str]]:
    """
    Find all simple paths between two resources.

    Args:
        graph: NetworkX directed graph
        source: Source node ID
        target: Target node ID
        cutoff: Maximum path length (None for unlimited)

    Returns:
        List of paths, where each path is a list of node IDs

    Example:
        >>> paths = find_all_paths(graph, "Service:default:web", "Pod:default:nginx-abc")
        >>> print(f"Found {len(paths)} paths")
    """
    if not graph.has_node(source):
        logger.warning(f"Source node {source} not found in graph")
        return []

    if not graph.has_node(target):
        logger.warning(f"Target node {target} not found in graph")
        return []

    try:
        return list(nx.all_simple_paths(graph, source, target, cutoff=cutoff))
    except nx.NetworkXNoPath:
        logger.debug(f"No paths found between {source} and {target}")
        return []


def get_neighbors(graph: nx.DiGraph, resource_id: str, hops: int = 1) -> nx.DiGraph:
    """
    Get N-hop neighborhood of a resource.

    Args:
        graph: NetworkX directed graph
        resource_id: Node ID of the resource
        hops: Number of hops to include (1 = direct neighbors)

    Returns:
        Subgraph containing the resource and its N-hop neighborhood

    Example:
        >>> neighborhood = get_neighbors(graph, "Deployment:default:nginx", hops=2)
        >>> print(f"2-hop neighborhood has {neighborhood.number_of_nodes()} nodes")
    """
    if not graph.has_node(resource_id):
        logger.warning(f"Node {resource_id} not found in graph")
        return nx.DiGraph()

    return nx.ego_graph(graph, resource_id, radius=hops).copy()


def find_by_kind(graph: nx.DiGraph, kind: str) -> list[str]:
    """
    Find all resources of a specific kind.

    Args:
        graph: NetworkX directed graph
        kind: Kubernetes resource kind (e.g., "Pod", "Deployment")

    Returns:
        List of node IDs matching the kind

    Example:
        >>> pods = find_by_kind(graph, "Pod")
        >>> print(f"Found {len(pods)} pods")
    """
    return [node_id for node_id, attrs in graph.nodes(data=True) if attrs.get("kind") == kind]


def find_by_namespace(graph: nx.DiGraph, namespace: str) -> list[str]:
    """
    Find all resources in a specific namespace.

    Args:
        graph: NetworkX directed graph
        namespace: Kubernetes namespace

    Returns:
        List of node IDs in the namespace

    Example:
        >>> default_resources = find_by_namespace(graph, "default")
        >>> print(f"Found {len(default_resources)} resources in default namespace")
    """
    return [
        node_id for node_id, attrs in graph.nodes(data=True) if attrs.get("namespace") == namespace
    ]


def find_by_label(graph: nx.DiGraph, label_key: str, label_value: str | None = None) -> list[str]:
    """
    Find resources with a specific label.

    Args:
        graph: NetworkX directed graph
        label_key: Label key to search for
        label_value: Optional label value to match (None matches any value)

    Returns:
        List of node IDs with matching labels

    Example:
        >>> app_nginx = find_by_label(graph, "app", "nginx")
        >>> print(f"Found {len(app_nginx)} resources with app=nginx")
    """
    results = []
    for node_id, attrs in graph.nodes(data=True):
        labels = attrs.get("labels", {})
        if label_key in labels:
            if label_value is None or labels[label_key] == label_value:
                results.append(node_id)
    return results


def extract_subgraph(graph: nx.DiGraph, node_ids: list[str]) -> nx.DiGraph:
    """
    Extract a subgraph containing only the specified nodes.

    Args:
        graph: NetworkX directed graph
        node_ids: List of node IDs to include

    Returns:
        Subgraph containing only the specified nodes and their edges

    Example:
        >>> pods = find_by_kind(graph, "Pod")
        >>> pod_subgraph = extract_subgraph(graph, pods)
    """
    valid_nodes = [node_id for node_id in node_ids if graph.has_node(node_id)]

    if len(valid_nodes) < len(node_ids):
        missing = set(node_ids) - set(valid_nodes)
        logger.warning(f"Nodes not found in graph: {missing}")

    return graph.subgraph(valid_nodes).copy()


def get_resource_cluster(graph: nx.DiGraph, resource_id: str) -> nx.DiGraph:
    """
    Get the weakly connected component containing the resource.

    This finds all resources that are connected to the given resource
    (directly or indirectly), regardless of edge direction.

    Args:
        graph: NetworkX directed graph
        resource_id: Node ID of the resource

    Returns:
        Subgraph containing the entire connected component

    Example:
        >>> cluster = get_resource_cluster(graph, "Deployment:default:nginx")
        >>> print(f"This deployment is part of a cluster with {cluster.number_of_nodes()} resources")
    """
    if not graph.has_node(resource_id):
        logger.warning(f"Node {resource_id} not found in graph")
        return nx.DiGraph()

    for component in nx.weakly_connected_components(graph):
        if resource_id in component:
            return graph.subgraph(component).copy()

    return nx.DiGraph()


def get_edge_data(graph: nx.DiGraph, source: str, target: str) -> dict[str, Any]:
    """
    Get edge attributes between two resources.

    Args:
        graph: NetworkX directed graph
        source: Source node ID
        target: Target node ID

    Returns:
        Dictionary of edge attributes, or empty dict if edge doesn't exist

    Example:
        >>> edge_data = get_edge_data(graph, "Service:default:web", "Pod:default:nginx-abc")
        >>> print(f"Relationship type: {edge_data.get('relationship_type')}")
    """
    if not graph.has_edge(source, target):
        logger.warning(f"Edge {source} -> {target} not found in graph")
        return {}

    return dict(graph[source][target])


def get_node_data(graph: nx.DiGraph, node_id: str) -> dict[str, Any]:
    """
    Get node attributes for a resource.

    Args:
        graph: NetworkX directed graph
        node_id: Node ID of the resource

    Returns:
        Dictionary of node attributes, or empty dict if node doesn't exist

    Example:
        >>> node_data = get_node_data(graph, "Pod:default:nginx-abc")
        >>> print(f"Phase: {node_data.get('phase')}")
    """
    if not graph.has_node(node_id):
        logger.warning(f"Node {node_id} not found in graph")
        return {}

    return dict(graph.nodes[node_id])


def filter_nodes(graph: nx.DiGraph, filter_fn: Callable[[str, dict[str, Any]], bool]) -> list[str]:
    """
    Filter nodes based on a custom predicate function.

    Args:
        graph: NetworkX directed graph
        filter_fn: Function that takes (node_id, attributes) and returns bool

    Returns:
        List of node IDs that match the filter

    Example:
        >>> running_pods = filter_nodes(
        ...     graph,
        ...     lambda nid, attrs: attrs.get('kind') == 'Pod' and attrs.get('phase') == 'Running'
        ... )
    """
    return [node_id for node_id, attrs in graph.nodes(data=True) if filter_fn(node_id, attrs)]
