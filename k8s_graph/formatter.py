import json
import logging
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


def format_graph_output(
    graph: nx.DiGraph,
    format_type: str = "json",
    include_metadata: bool = True,
    pod_sampling_info: dict[str, Any] | None = None,
) -> str:
    """
    Format graph for output in various formats.

    Args:
        graph: NetworkX directed graph
        format_type: Output format - 'json', 'llm', or 'minimal'
        include_metadata: Whether to include graph metadata
        pod_sampling_info: Optional pod sampling information

    Returns:
        Formatted string output

    Supported formats:
        - 'json': Full JSON representation with all node/edge data
        - 'llm': LLM-friendly format with natural language descriptions
        - 'minimal': Minimal JSON with just kind/name/relationships

    Example:
        >>> output = format_graph_output(graph, format_type='json')
        >>> print(output)
    """
    if format_type == "json":
        return _format_json(graph, include_metadata, pod_sampling_info)
    elif format_type == "llm":
        return _format_llm_friendly(graph, include_metadata, pod_sampling_info)
    elif format_type == "minimal":
        return _format_minimal(graph, include_metadata)
    else:
        raise ValueError(f"Unknown format type: {format_type}")


def _format_json(
    graph: nx.DiGraph, include_metadata: bool, pod_sampling_info: dict[str, Any] | None
) -> str:
    """
    Format graph as complete JSON.

    Note: For persistence, use k8s_graph.persistence.save_graph() instead.
    This is kept for backward compatibility and LLM-friendly output.
    """
    nodes = []
    for node_id, attrs in graph.nodes(data=True):
        node_data = {"id": node_id, **attrs}
        nodes.append(node_data)

    edges = []
    for source, target, attrs in graph.edges(data=True):
        edge_data = {"source": source, "target": target, **attrs}
        edges.append(edge_data)

    output: dict[str, Any] = {"nodes": nodes, "edges": edges}

    if include_metadata:
        metadata = {
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
        }

        if pod_sampling_info:
            metadata["pod_sampling"] = pod_sampling_info

        output["metadata"] = metadata

    return json.dumps(output, indent=2, default=str)


def _format_llm_friendly(
    graph: nx.DiGraph, include_metadata: bool, pod_sampling_info: dict[str, Any] | None
) -> str:
    """Format graph in LLM-friendly natural language."""
    lines: list[str] = []

    if include_metadata:
        lines.append("# Kubernetes Resource Graph\n")
        lines.append(f"Total Resources: {graph.number_of_nodes()}")
        lines.append(f"Total Relationships: {graph.number_of_edges()}\n")

        if pod_sampling_info:
            sampled = pod_sampling_info.get("sampled_count", 0)
            total = pod_sampling_info.get("total_count", 0)
            if sampled > 0:
                lines.append(
                    f"Note: Pod sampling active - showing {sampled} representative pods "
                    f"out of {total} total\n"
                )

    kinds: dict[str, int] = {}
    for _, attrs in graph.nodes(data=True):
        kind = attrs.get("kind", "Unknown")
        kinds[kind] = kinds.get(kind, 0) + 1

    lines.append("## Resources by Kind")
    for kind, count in sorted(kinds.items()):
        lines.append(f"- {kind}: {count}")
    lines.append("")

    lines.append("## Resources\n")
    for node_id, attrs in sorted(graph.nodes(data=True)):
        kind = attrs.get("kind", "Unknown")
        name = attrs.get("name", "unknown")
        namespace = attrs.get("namespace", "cluster")

        lines.append(f"### {kind}: {name} (namespace: {namespace})")

        phase = attrs.get("phase")
        if phase:
            lines.append(f"  Status: {phase}")

        service_type = attrs.get("service_type")
        if service_type:
            lines.append(f"  Type: {service_type}")

        replicas = attrs.get("replicas")
        if replicas is not None:
            ready = attrs.get("ready_replicas", 0)
            lines.append(f"  Replicas: {ready}/{replicas}")

        out_edges = list(graph.out_edges(node_id, data=True))
        if out_edges:
            lines.append("  Relationships:")
            for _, target, edge_attrs in out_edges:
                target_attrs = graph.nodes[target]
                target_kind = target_attrs.get("kind", "Unknown")
                target_name = target_attrs.get("name", "unknown")
                rel_type = edge_attrs.get("relationship_type", "unknown")
                lines.append(f"    - {rel_type} -> {target_kind}/{target_name}")

        lines.append("")

    return "\n".join(lines)


def _format_minimal(graph: nx.DiGraph, include_metadata: bool) -> str:
    """Format graph as minimal JSON with just essential fields."""
    nodes = []
    for node_id, attrs in graph.nodes(data=True):
        node_data = {
            "id": node_id,
            "kind": attrs.get("kind"),
            "name": attrs.get("name"),
            "namespace": attrs.get("namespace"),
        }
        nodes.append(node_data)

    edges = []
    for source, target, attrs in graph.edges(data=True):
        edge_data = {
            "source": source,
            "target": target,
            "type": attrs.get("relationship_type"),
        }
        edges.append(edge_data)

    output: dict[str, Any] = {"nodes": nodes, "edges": edges}

    if include_metadata:
        output["metadata"] = {
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
        }

    return json.dumps(output, indent=2, default=str)


def export_to_dot(graph: nx.DiGraph, output_file: str) -> None:
    """
    Export graph to Graphviz DOT format.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output DOT file

    Example:
        >>> export_to_dot(graph, "cluster.dot")
        >>> # Then: dot -Tpng cluster.dot -o cluster.png
    """
    try:
        nx.drawing.nx_pydot.write_dot(graph, output_file)
    except ImportError:
        logger.error("pydot is required for DOT export. Install with: pip install pydot")
        raise
