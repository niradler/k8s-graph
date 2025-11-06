import logging
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


def validate_graph(graph: nx.DiGraph) -> dict[str, Any]:
    """
    Validate a Kubernetes resource graph for quality and consistency.

    Performs multiple validation checks:
    - Duplicate resources (same kind+namespace+name with different node IDs)
    - Incomplete nodes (missing required attributes like kind or name)
    - Edges without proper metadata

    Args:
        graph: NetworkX directed graph to validate

    Returns:
        Validation report dictionary with:
        - valid (bool): True if no issues found
        - node_count (int): Number of nodes
        - edge_count (int): Number of edges
        - unique_resources (int): Number of unique resources
        - duplicate_count (int): Number of duplicate resource sets
        - issues (list): List of validation issues
        - warnings (list): List of non-critical warnings

    Example:
        >>> from k8s_graph import validate_graph
        >>> import networkx as nx
        >>> graph = nx.DiGraph()
        >>> graph.add_node("Pod:default:nginx", kind="Pod", name="nginx", namespace="default")
        >>> result = validate_graph(graph)
        >>> print(result['valid'])
        True
    """
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    resource_map: dict[tuple, list[str]] = {}

    for node_id, attrs in graph.nodes(data=True):
        kind = attrs.get("kind")
        name = attrs.get("name")
        namespace = attrs.get("namespace") or "cluster"

        if not kind:
            issues.append(
                {
                    "type": "missing_kind",
                    "node_id": node_id,
                    "message": f"Node {node_id} is missing 'kind' attribute",
                }
            )
            continue

        if not name:
            issues.append(
                {
                    "type": "missing_name",
                    "node_id": node_id,
                    "message": f"Node {node_id} is missing 'name' attribute",
                }
            )
            continue

        key = (kind, namespace, name)
        if key not in resource_map:
            resource_map[key] = []
        resource_map[key].append(node_id)

    duplicates = {k: v for k, v in resource_map.items() if len(v) > 1}
    if duplicates:
        for (kind, namespace, name), node_ids in duplicates.items():
            issues.append(
                {
                    "type": "duplicate_resource",
                    "kind": kind,
                    "namespace": namespace,
                    "name": name,
                    "node_ids": node_ids,
                    "count": len(node_ids),
                    "message": f"Found {len(node_ids)} nodes for {kind}/{name} in {namespace}",
                }
            )

    for source, target, edge_attrs in graph.edges(data=True):
        if not edge_attrs:
            warnings.append(
                {
                    "type": "edge_without_metadata",
                    "source": source,
                    "target": target,
                    "message": f"Edge from {source} to {target} has no metadata",
                }
            )
            continue

        if "relationship_type" not in edge_attrs:
            warnings.append(
                {
                    "type": "edge_missing_relationship_type",
                    "source": source,
                    "target": target,
                    "message": f"Edge from {source} to {target} missing 'relationship_type'",
                }
            )

    valid = len(issues) == 0

    return {
        "valid": valid,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "unique_resources": len(resource_map),
        "duplicate_count": len(duplicates),
        "issues": issues,
        "warnings": warnings,
    }


def check_graph_cycles(graph: nx.DiGraph) -> dict[str, Any]:
    """
    Check for cycles in the graph.

    While some cycles are valid in Kubernetes (e.g., Service -> Pod -> Service via endpoints),
    this can help identify unexpected circular dependencies.

    Args:
        graph: NetworkX directed graph

    Returns:
        Dictionary with:
        - has_cycles (bool): Whether cycles were found
        - cycle_count (int): Number of simple cycles found (up to limit)
        - cycles (list): List of cycles (limited to first 10)

    Example:
        >>> result = check_graph_cycles(graph)
        >>> if result['has_cycles']:
        ...     print(f"Found {result['cycle_count']} cycles")
    """
    try:
        cycles = list(nx.simple_cycles(graph))
        has_cycles = len(cycles) > 0

        limited_cycles = cycles[:10]

        return {
            "has_cycles": has_cycles,
            "cycle_count": len(cycles),
            "cycles": limited_cycles,
        }
    except Exception as e:
        logger.error(f"Error checking for cycles: {e}")
        return {"has_cycles": False, "cycle_count": 0, "cycles": [], "error": str(e)}


def get_graph_statistics(graph: nx.DiGraph) -> dict[str, Any]:
    """
    Get detailed statistics about the graph structure.

    Args:
        graph: NetworkX directed graph

    Returns:
        Dictionary with various graph statistics

    Example:
        >>> stats = get_graph_statistics(graph)
        >>> print(f"Average degree: {stats['average_degree']:.2f}")
    """
    stats = {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "density": nx.density(graph) if graph.number_of_nodes() > 0 else 0,
    }

    if graph.number_of_nodes() > 0:
        degrees = [d for _, d in graph.degree()]
        stats["average_degree"] = sum(degrees) / len(degrees)
        stats["max_degree"] = max(degrees)
        stats["min_degree"] = min(degrees)

        in_degrees = [d for _, d in graph.in_degree()]
        out_degrees = [d for _, d in graph.out_degree()]
        stats["average_in_degree"] = sum(in_degrees) / len(in_degrees)
        stats["average_out_degree"] = sum(out_degrees) / len(out_degrees)
        stats["max_in_degree"] = max(in_degrees)
        stats["max_out_degree"] = max(out_degrees)

    kinds: dict[str, int] = {}
    namespaces: dict[str, int] = {}

    for _node_id, attrs in graph.nodes(data=True):
        kind = attrs.get("kind", "Unknown")
        namespace = attrs.get("namespace", "cluster")

        kinds[kind] = kinds.get(kind, 0) + 1
        namespaces[namespace] = namespaces.get(namespace, 0) + 1

    stats["resource_kinds"] = kinds
    stats["namespaces"] = namespaces
    stats["kind_count"] = len(kinds)
    stats["namespace_count"] = len(namespaces)

    return stats


def analyze_connectivity(graph: nx.DiGraph) -> dict[str, Any]:
    """
    Analyze connectivity patterns in the graph.

    Args:
        graph: NetworkX directed graph

    Returns:
        Dictionary with connectivity analysis including:
        - is_weakly_connected: Whether graph is weakly connected
        - is_strongly_connected: Whether graph is strongly connected
        - component_count: Number of weakly connected components
        - largest_component_size: Size of largest component
        - isolated_count: Number of isolated nodes
        - connectivity_ratio: Ratio of nodes in largest component

    Example:
        >>> analysis = analyze_connectivity(graph)
        >>> if not analysis['is_weakly_connected']:
        ...     print(f"Graph has {analysis['component_count']} separate components")
    """
    if graph.number_of_nodes() == 0:
        return {
            "is_weakly_connected": True,
            "is_strongly_connected": True,
            "component_count": 0,
            "largest_component_size": 0,
            "isolated_count": 0,
            "connectivity_ratio": 0.0,
        }

    is_weakly_connected = nx.is_weakly_connected(graph)
    is_strongly_connected = nx.is_strongly_connected(graph)

    components = list(nx.weakly_connected_components(graph))
    component_count = len(components)

    largest_component_size = max(len(c) for c in components) if components else 0

    isolated_nodes = list(nx.isolates(graph))
    isolated_count = len(isolated_nodes)

    connectivity_ratio = (
        largest_component_size / graph.number_of_nodes() if graph.number_of_nodes() > 0 else 0.0
    )

    return {
        "is_weakly_connected": is_weakly_connected,
        "is_strongly_connected": is_strongly_connected,
        "component_count": component_count,
        "largest_component_size": largest_component_size,
        "isolated_count": isolated_count,
        "connectivity_ratio": connectivity_ratio,
        "components": [list(c) for c in components],
    }


def find_isolated_components(graph: nx.DiGraph) -> list[list[str]]:
    """
    Find all weakly connected components in the graph.

    Each component is a group of resources that are connected to each other
    (directly or indirectly), but not connected to resources in other components.

    Args:
        graph: NetworkX directed graph

    Returns:
        List of components, where each component is a list of node IDs

    Example:
        >>> components = find_isolated_components(graph)
        >>> for i, component in enumerate(components):
        ...     print(f"Component {i+1}: {len(component)} resources")
    """
    components = list(nx.weakly_connected_components(graph))
    return [list(c) for c in sorted(components, key=len, reverse=True)]


def identify_critical_resources(
    graph: nx.DiGraph, top_n: int = 10
) -> list[tuple[str, dict[str, Any]]]:
    """
    Identify the most critical resources based on centrality metrics.

    Uses multiple centrality measures:
    - Degree centrality: How many connections a resource has
    - Betweenness centrality: How often a resource is on shortest paths
    - PageRank: Importance based on incoming connections

    Args:
        graph: NetworkX directed graph
        top_n: Number of top resources to return

    Returns:
        List of tuples (node_id, metrics) sorted by combined score

    Example:
        >>> critical = identify_critical_resources(graph, top_n=5)
        >>> for node_id, metrics in critical:
        ...     attrs = graph.nodes[node_id]
        ...     print(f"{attrs['kind']}/{attrs['name']}: score={metrics['combined_score']:.3f}")
    """
    if graph.number_of_nodes() == 0:
        return []

    degree_cent = nx.degree_centrality(graph)

    try:
        betweenness_cent = nx.betweenness_centrality(graph)
    except Exception as e:
        logger.warning(f"Error computing betweenness centrality: {e}")
        betweenness_cent = dict.fromkeys(graph.nodes(), 0.0)

    try:
        pagerank = nx.pagerank(graph)
    except Exception as e:
        logger.warning(f"Error computing PageRank: {e}")
        pagerank = dict.fromkeys(graph.nodes(), 0.0)

    combined_scores = {}
    for node in graph.nodes():
        degree = degree_cent.get(node, 0.0)
        betweenness = betweenness_cent.get(node, 0.0)
        pr = pagerank.get(node, 0.0)

        combined = (degree * 0.3) + (betweenness * 0.4) + (pr * 0.3)
        combined_scores[node] = {
            "degree_centrality": degree,
            "betweenness_centrality": betweenness,
            "pagerank": pr,
            "combined_score": combined,
        }

    sorted_resources = sorted(
        combined_scores.items(), key=lambda x: x[1]["combined_score"], reverse=True
    )

    return sorted_resources[:top_n]


def analyze_dependency_depth(graph: nx.DiGraph) -> dict[str, Any]:
    """
    Analyze the dependency depth of resources in the graph.

    Computes:
    - Maximum depth: Longest dependency chain
    - Average depth: Mean depth across all resources
    - Depth distribution: Count of resources at each depth level

    Args:
        graph: NetworkX directed graph

    Returns:
        Dictionary with depth analysis

    Example:
        >>> depth_analysis = analyze_dependency_depth(graph)
        >>> print(f"Max dependency chain: {depth_analysis['max_depth']} levels")
    """
    if graph.number_of_nodes() == 0:
        return {
            "max_depth": 0,
            "average_depth": 0.0,
            "depth_distribution": {},
            "deepest_resources": [],
        }

    from k8s_graph.traversal import get_dependency_levels

    try:
        levels = get_dependency_levels(graph)

        if not levels:
            return {
                "max_depth": 0,
                "average_depth": 0.0,
                "depth_distribution": {},
                "deepest_resources": [],
            }

        max_depth = max(levels.values())
        average_depth = sum(levels.values()) / len(levels)

        depth_distribution: dict[int, int] = {}
        for _node, depth in levels.items():
            depth_distribution[depth] = depth_distribution.get(depth, 0) + 1

        deepest_resources = [node for node, depth in levels.items() if depth == max_depth]

        return {
            "max_depth": max_depth,
            "average_depth": average_depth,
            "depth_distribution": depth_distribution,
            "deepest_resources": deepest_resources,
        }

    except Exception as e:
        logger.error(f"Error analyzing dependency depth: {e}")
        return {
            "max_depth": 0,
            "average_depth": 0.0,
            "depth_distribution": {},
            "deepest_resources": [],
            "error": str(e),
        }
