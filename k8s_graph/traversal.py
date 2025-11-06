import logging
from collections.abc import Callable, Generator
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


def traverse_bfs(
    graph: nx.DiGraph,
    start: str,
    filter_fn: Callable[[str, dict[str, Any]], bool] | None = None,
) -> Generator[tuple[str, dict[str, Any]], None, None]:
    """
    Traverse graph in breadth-first order starting from a node.

    Args:
        graph: NetworkX directed graph
        start: Starting node ID
        filter_fn: Optional filter function (node_id, attrs) -> bool

    Yields:
        Tuples of (node_id, attributes)

    Example:
        >>> for node_id, attrs in traverse_bfs(graph, "Deployment:default:nginx"):
        ...     print(f"{attrs['kind']}: {attrs['name']}")
    """
    if not graph.has_node(start):
        logger.warning(f"Start node {start} not found in graph")
        return

    visited = set()
    queue = [start]

    while queue:
        node_id = queue.pop(0)

        if node_id in visited:
            continue

        visited.add(node_id)
        attrs = dict(graph.nodes[node_id])

        if filter_fn is None or filter_fn(node_id, attrs):
            yield node_id, attrs

        for successor in graph.successors(node_id):
            if successor not in visited:
                queue.append(successor)


def traverse_dfs(
    graph: nx.DiGraph,
    start: str,
    filter_fn: Callable[[str, dict[str, Any]], bool] | None = None,
) -> Generator[tuple[str, dict[str, Any]], None, None]:
    """
    Traverse graph in depth-first order starting from a node.

    Args:
        graph: NetworkX directed graph
        start: Starting node ID
        filter_fn: Optional filter function (node_id, attrs) -> bool

    Yields:
        Tuples of (node_id, attributes)

    Example:
        >>> for node_id, attrs in traverse_dfs(graph, "Deployment:default:nginx"):
        ...     print(f"{attrs['kind']}: {attrs['name']}")
    """
    if not graph.has_node(start):
        logger.warning(f"Start node {start} not found in graph")
        return

    visited = set()
    stack = [start]

    while stack:
        node_id = stack.pop()

        if node_id in visited:
            continue

        visited.add(node_id)
        attrs = dict(graph.nodes[node_id])

        if filter_fn is None or filter_fn(node_id, attrs):
            yield node_id, attrs

        for successor in reversed(list(graph.successors(node_id))):
            if successor not in visited:
                stack.append(successor)


def get_roots(graph: nx.DiGraph) -> list[str]:
    """
    Get all root nodes (nodes with no predecessors).

    Args:
        graph: NetworkX directed graph

    Returns:
        List of node IDs that have no incoming edges

    Example:
        >>> roots = get_roots(graph)
        >>> print(f"Found {len(roots)} root resources")
    """
    return [node for node in graph.nodes() if graph.in_degree(node) == 0]


def get_leaves(graph: nx.DiGraph) -> list[str]:
    """
    Get all leaf nodes (nodes with no successors).

    Args:
        graph: NetworkX directed graph

    Returns:
        List of node IDs that have no outgoing edges

    Example:
        >>> leaves = get_leaves(graph)
        >>> print(f"Found {len(leaves)} leaf resources")
    """
    return [node for node in graph.nodes() if graph.out_degree(node) == 0]


def topological_order(graph: nx.DiGraph) -> list[str]:
    """
    Get topological ordering of nodes.

    Returns nodes in an order where all dependencies come before dependents.
    Only works on directed acyclic graphs (DAGs).

    Args:
        graph: NetworkX directed graph

    Returns:
        List of node IDs in topological order

    Raises:
        NetworkXError: If graph has cycles

    Example:
        >>> order = topological_order(graph)
        >>> print("Deployment order:", " -> ".join(order))
    """
    try:
        return list(nx.topological_sort(graph))
    except (nx.NetworkXError, nx.NetworkXUnfeasible) as e:
        logger.error(f"Cannot compute topological order: {e}")
        raise


def reverse_topological_order(graph: nx.DiGraph) -> list[str]:
    """
    Get reverse topological ordering of nodes.

    Returns nodes in an order where all dependents come before dependencies.
    Useful for deletion/cleanup ordering.

    Args:
        graph: NetworkX directed graph

    Returns:
        List of node IDs in reverse topological order

    Raises:
        NetworkXError: If graph has cycles

    Example:
        >>> order = reverse_topological_order(graph)
        >>> print("Deletion order:", " -> ".join(order))
    """
    return list(reversed(topological_order(graph)))


def traverse_by_relationship(
    graph: nx.DiGraph, start: str, relationship_type: str
) -> Generator[tuple[str, dict[str, Any]], None, None]:
    """
    Traverse graph following only edges of a specific relationship type.

    Args:
        graph: NetworkX directed graph
        start: Starting node ID
        relationship_type: Type of relationship to follow

    Yields:
        Tuples of (node_id, attributes)

    Example:
        >>> for node_id, attrs in traverse_by_relationship(
        ...     graph, "Deployment:default:nginx", "owner"
        ... ):
        ...     print(f"Owned resource: {attrs['kind']}")
    """
    if not graph.has_node(start):
        logger.warning(f"Start node {start} not found in graph")
        return

    visited = set()
    queue = [start]

    while queue:
        node_id = queue.pop(0)

        if node_id in visited:
            continue

        visited.add(node_id)
        attrs = dict(graph.nodes[node_id])
        yield node_id, attrs

        for successor in graph.successors(node_id):
            edge_data = graph[node_id][successor]
            if edge_data.get("relationship_type") == relationship_type:
                if successor not in visited:
                    queue.append(successor)


def get_dependency_levels(graph: nx.DiGraph) -> dict[str, int]:
    """
    Compute dependency level for each node.

    Level 0 = no dependencies (roots)
    Level N = depends on resources at level N-1

    Args:
        graph: NetworkX directed graph

    Returns:
        Dictionary mapping node IDs to their dependency level

    Example:
        >>> levels = get_dependency_levels(graph)
        >>> for node_id, level in sorted(levels.items(), key=lambda x: x[1]):
        ...     attrs = graph.nodes[node_id]
        ...     print(f"Level {level}: {attrs['kind']}/{attrs['name']}")
    """
    levels = {}

    try:
        for node in nx.topological_sort(graph):
            predecessors = list(graph.predecessors(node))
            if not predecessors:
                levels[node] = 0
            else:
                max_pred_level = max(levels.get(pred, 0) for pred in predecessors)
                levels[node] = max_pred_level + 1
    except (nx.NetworkXError, nx.NetworkXUnfeasible):
        logger.warning("Graph has cycles, computing levels with cycle handling")
        for node in graph.nodes():
            levels[node] = _compute_level_with_cycles(graph, node, visited=set())

    return levels


def _compute_level_with_cycles(graph: nx.DiGraph, node: str, visited: set[str]) -> int:
    """
    Compute level for a node even if graph has cycles.

    Args:
        graph: NetworkX directed graph
        node: Node ID
        visited: Set of visited nodes (to detect cycles)

    Returns:
        Dependency level
    """
    if node in visited:
        return 0

    visited.add(node)
    predecessors = list(graph.predecessors(node))

    if not predecessors:
        return 0

    max_level = 0
    for pred in predecessors:
        pred_level = _compute_level_with_cycles(graph, pred, visited.copy())
        max_level = max(max_level, pred_level + 1)

    return max_level


def get_longest_path(graph: nx.DiGraph) -> list[str]:
    """
    Find the longest path in the graph.

    Useful for understanding maximum dependency depth.

    Args:
        graph: NetworkX directed graph

    Returns:
        List of node IDs representing the longest path

    Example:
        >>> path = get_longest_path(graph)
        >>> print(f"Longest dependency chain has {len(path)} resources")
    """
    try:
        result: list[str] = nx.dag_longest_path(graph)
        return result
    except (nx.NetworkXError, nx.NetworkXUnfeasible):
        logger.warning("Graph has cycles, cannot compute longest path")
        return []


def get_shortest_paths_from_root(graph: nx.DiGraph, root: str) -> dict[str, list[str]]:
    """
    Get shortest paths from a root node to all reachable nodes.

    Args:
        graph: NetworkX directed graph
        root: Root node ID

    Returns:
        Dictionary mapping target node IDs to their shortest path from root

    Example:
        >>> paths = get_shortest_paths_from_root(graph, "Namespace:default")
        >>> for target, path in paths.items():
        ...     print(f"Path to {target}: {' -> '.join(path)}")
    """
    if not graph.has_node(root):
        logger.warning(f"Root node {root} not found in graph")
        return {}

    try:
        result: dict[str, list[str]] = nx.single_source_shortest_path(graph, root)
        return result
    except nx.NetworkXError as e:
        logger.error(f"Error computing shortest paths: {e}")
        return {root: [root]}


def traverse_breadth_first_with_depth(
    graph: nx.DiGraph, start: str, max_depth: int | None = None
) -> Generator[tuple[str, dict[str, Any], int], None, None]:
    """
    Traverse graph in BFS order with depth information.

    Args:
        graph: NetworkX directed graph
        start: Starting node ID
        max_depth: Maximum depth to traverse (None for unlimited)

    Yields:
        Tuples of (node_id, attributes, depth)

    Example:
        >>> for node_id, attrs, depth in traverse_breadth_first_with_depth(graph, "Deployment:default:nginx", max_depth=3):
        ...     print(f"Depth {depth}: {attrs['kind']}/{attrs['name']}")
    """
    if not graph.has_node(start):
        logger.warning(f"Start node {start} not found in graph")
        return

    visited = set()
    queue = [(start, 0)]

    while queue:
        node_id, depth = queue.pop(0)

        if node_id in visited:
            continue

        if max_depth is not None and depth > max_depth:
            continue

        visited.add(node_id)
        attrs = dict(graph.nodes[node_id])
        yield node_id, attrs, depth

        for successor in graph.successors(node_id):
            if successor not in visited:
                queue.append((successor, depth + 1))
