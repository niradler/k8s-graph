import json
import logging
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


def save_graph(graph: nx.DiGraph, filepath: str, format: str = "json") -> None:
    """
    Save a graph to a file in the specified format.

    Args:
        graph: NetworkX directed graph
        filepath: Path to output file
        format: Output format - 'json', 'graphml', 'gml', or 'edgelist'

    Raises:
        ValueError: If format is not supported

    Example:
        >>> save_graph(graph, "cluster.json", format="json")
        >>> save_graph(graph, "cluster.graphml", format="graphml")
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    if format == "json":
        data = nx.node_link_data(graph)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Saved graph to {filepath} (JSON format)")

    elif format == "graphml":
        nx.write_graphml(graph, filepath)
        logger.info(f"Saved graph to {filepath} (GraphML format)")

    elif format == "gml":
        nx.write_gml(graph, filepath)
        logger.info(f"Saved graph to {filepath} (GML format)")

    elif format == "edgelist":
        nx.write_edgelist(graph, filepath, data=True)
        logger.info(f"Saved graph to {filepath} (edge list format)")

    else:
        raise ValueError(
            f"Unsupported format: {format}. " "Supported formats: json, graphml, gml, edgelist"
        )


def load_graph(filepath: str, format: str = "json") -> nx.DiGraph:
    """
    Load a graph from a file in the specified format.

    Args:
        filepath: Path to input file
        format: Input format - 'json', 'graphml', 'gml', or 'edgelist'

    Returns:
        Loaded NetworkX directed graph

    Raises:
        ValueError: If format is not supported
        FileNotFoundError: If file doesn't exist

    Example:
        >>> graph = load_graph("cluster.json", format="json")
        >>> print(f"Loaded {graph.number_of_nodes()} nodes")
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    if format == "json":
        with open(filepath) as f:
            data = json.load(f)
        graph = nx.node_link_graph(data, directed=True)
        logger.info(f"Loaded graph from {filepath} (JSON format)")
        return graph

    elif format == "graphml":
        graph = nx.read_graphml(filepath)
        directed_graph = nx.DiGraph(graph)
        logger.info(f"Loaded graph from {filepath} (GraphML format)")
        return directed_graph

    elif format == "gml":
        graph = nx.read_gml(filepath)
        directed_graph = nx.DiGraph(graph)
        logger.info(f"Loaded graph from {filepath} (GML format)")
        return directed_graph

    elif format == "edgelist":
        graph = nx.read_edgelist(filepath, create_using=nx.DiGraph, data=True)
        logger.info(f"Loaded graph from {filepath} (edge list format)")
        return graph

    else:
        raise ValueError(
            f"Unsupported format: {format}. " "Supported formats: json, graphml, gml, edgelist"
        )


def to_dict(graph: nx.DiGraph) -> dict[str, Any]:
    """
    Convert graph to a dictionary representation.

    Uses NetworkX's node-link format which is suitable for JSON serialization.

    Args:
        graph: NetworkX directed graph

    Returns:
        Dictionary representation of the graph

    Example:
        >>> data = to_dict(graph)
        >>> print(f"Nodes: {len(data['nodes'])}, Links: {len(data['links'])}")
    """
    result: dict[str, Any] = nx.node_link_data(graph)
    return result


def from_dict(data: dict[str, Any]) -> nx.DiGraph:
    """
    Create graph from a dictionary representation.

    Args:
        data: Dictionary in node-link format

    Returns:
        NetworkX directed graph

    Example:
        >>> graph = from_dict(data)
        >>> print(f"Loaded {graph.number_of_nodes()} nodes")
    """
    return nx.node_link_graph(data, directed=True)


def to_edge_list(graph: nx.DiGraph) -> list[tuple[str, str, dict[str, Any]]]:
    """
    Convert graph to an edge list with attributes.

    Args:
        graph: NetworkX directed graph

    Returns:
        List of (source, target, attributes) tuples

    Example:
        >>> edges = to_edge_list(graph)
        >>> for source, target, attrs in edges:
        ...     print(f"{source} -> {target}: {attrs.get('relationship_type')}")
    """
    return [(u, v, dict(data)) for u, v, data in graph.edges(data=True)]


def from_edge_list(
    edges: list[tuple[str, str, dict[str, Any]]],
    node_attrs: dict[str, dict[str, Any]] | None = None,
) -> nx.DiGraph:
    """
    Create graph from an edge list.

    Args:
        edges: List of (source, target, attributes) tuples
        node_attrs: Optional dictionary mapping node IDs to their attributes

    Returns:
        NetworkX directed graph

    Example:
        >>> edges = [("Service:default:web", "Pod:default:nginx", {"relationship_type": "label_selector"})]
        >>> node_attrs = {
        ...     "Service:default:web": {"kind": "Service", "name": "web", "namespace": "default"},
        ...     "Pod:default:nginx": {"kind": "Pod", "name": "nginx", "namespace": "default"}
        ... }
        >>> graph = from_edge_list(edges, node_attrs)
    """
    graph = nx.DiGraph()

    for source, target, attrs in edges:
        graph.add_edge(source, target, **attrs)

    if node_attrs:
        for node_id, attrs in node_attrs.items():
            if graph.has_node(node_id):
                graph.nodes[node_id].update(attrs)

    return graph


def to_adjacency_dict(graph: nx.DiGraph) -> dict[str, list[str]]:
    """
    Convert graph to an adjacency dictionary.

    Args:
        graph: NetworkX directed graph

    Returns:
        Dictionary mapping node IDs to lists of successor node IDs

    Example:
        >>> adj_dict = to_adjacency_dict(graph)
        >>> for node, neighbors in adj_dict.items():
        ...     print(f"{node} -> {neighbors}")
    """
    return {node: list(graph.successors(node)) for node in graph.nodes()}


def from_adjacency_dict(adj_dict: dict[str, list[str]]) -> nx.DiGraph:
    """
    Create graph from an adjacency dictionary.

    Args:
        adj_dict: Dictionary mapping node IDs to lists of neighbor node IDs

    Returns:
        NetworkX directed graph

    Example:
        >>> adj_dict = {"Deployment:default:nginx": ["ReplicaSet:default:nginx-abc"]}
        >>> graph = from_adjacency_dict(adj_dict)
    """
    return nx.DiGraph(adj_dict)


def get_format_from_extension(filepath: str) -> str:
    """
    Infer format from file extension.

    Args:
        filepath: Path to file

    Returns:
        Format string ('json', 'graphml', 'gml', or 'edgelist')

    Raises:
        ValueError: If extension is not recognized

    Example:
        >>> fmt = get_format_from_extension("cluster.graphml")
        >>> print(fmt)  # 'graphml'
    """
    path = Path(filepath)
    ext = path.suffix.lower()

    format_map = {
        ".json": "json",
        ".graphml": "graphml",
        ".xml": "graphml",
        ".gml": "gml",
        ".edgelist": "edgelist",
        ".edges": "edgelist",
    }

    if ext in format_map:
        return format_map[ext]

    raise ValueError(
        f"Cannot infer format from extension: {ext}. "
        "Supported extensions: .json, .graphml, .xml, .gml, .edgelist, .edges"
    )


def save_graph_auto(graph: nx.DiGraph, filepath: str) -> None:
    """
    Save graph with format auto-detected from file extension.

    Args:
        graph: NetworkX directed graph
        filepath: Path to output file (format inferred from extension)

    Example:
        >>> save_graph_auto(graph, "cluster.graphml")  # Uses GraphML format
        >>> save_graph_auto(graph, "data.json")  # Uses JSON format
    """
    format = get_format_from_extension(filepath)
    save_graph(graph, filepath, format=format)


def load_graph_auto(filepath: str) -> nx.DiGraph:
    """
    Load graph with format auto-detected from file extension.

    Args:
        filepath: Path to input file (format inferred from extension)

    Returns:
        Loaded NetworkX directed graph

    Example:
        >>> graph = load_graph_auto("cluster.graphml")
    """
    format = get_format_from_extension(filepath)
    return load_graph(filepath, format=format)
