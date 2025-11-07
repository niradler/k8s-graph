import logging
from pathlib import Path
from typing import Any

import networkx as nx

from k8s_graph.persistence import load_graph, save_graph
from k8s_graph.visualization import draw_hierarchical

logger = logging.getLogger(__name__)

try:
    from pyvis.network import Network  # type: ignore[import-untyped]

    _has_pyvis = True
except ImportError:
    _has_pyvis = False


def aggregate_isolated_nodes(
    graph: nx.DiGraph,
) -> tuple[nx.DiGraph, dict[str, list[tuple[str, dict]]]]:
    """
    Aggregate isolated nodes into summary nodes by kind.

    Reduces visual clutter by grouping disconnected resources of the same kind
    into a single aggregated node showing count and examples.

    Args:
        graph: NetworkX directed graph

    Returns:
        Tuple of (aggregated_graph, isolated_by_kind)
        - aggregated_graph: New graph with isolated nodes replaced by summary nodes
        - isolated_by_kind: Dict mapping kind to list of (node_id, attrs) tuples

    Example:
        >>> agg_graph, isolated = aggregate_isolated_nodes(graph)
        >>> print(f"Aggregated {sum(len(v) for v in isolated.values())} isolated nodes")
    """
    undirected = graph.to_undirected()
    isolated = list(nx.isolates(undirected))

    isolated_by_kind: dict[str, list[tuple[str, dict]]] = {}
    for node_id in isolated:
        attrs = graph.nodes[node_id]
        kind = attrs.get("kind", "Unknown")
        if kind not in isolated_by_kind:
            isolated_by_kind[kind] = []
        isolated_by_kind[kind].append((node_id, attrs))

    new_graph = nx.DiGraph()

    for node_id, attrs in graph.nodes(data=True):
        if node_id not in isolated:
            new_graph.add_node(node_id, **attrs)

    for u, v, data in graph.edges(data=True):
        if u not in isolated and v not in isolated:
            new_graph.add_edge(u, v, **data)

    for kind, nodes in isolated_by_kind.items():
        if len(nodes) > 0:
            aggregate_id = f"⚠️_Hanging_{kind}_{len(nodes)}"
            names = [attrs.get("name", "?")[:30] for _, attrs in nodes[:5]]
            if len(nodes) > 5:
                names_str = ", ".join(names) + f"... (+{len(nodes)-5} more)"
            else:
                names_str = ", ".join(names)

            new_graph.add_node(
                aggregate_id,
                kind=f"⚠️ Hanging {kind}",
                name=f"{len(nodes)} orphaned",
                namespace="(not connected)",
                aggregated=True,
                count=len(nodes),
                examples=names_str,
            )

    return new_graph, isolated_by_kind


def export_png(
    graph: nx.DiGraph,
    filepath: str | Path,
    title: str | None = None,
    aggregate: bool = True,
    dpi: int = 200,
    **kwargs: Any,
) -> bool:
    """
    Export graph to PNG using Graphviz hierarchical layout.

    Args:
        graph: NetworkX directed graph
        filepath: Output file path
        title: Optional title for the visualization
        aggregate: Whether to aggregate isolated nodes (default True)
        dpi: Resolution in dots per inch (default 200)
        **kwargs: Additional arguments passed to draw_hierarchical

    Returns:
        True if export succeeded, False otherwise

    Example:
        >>> export_png(graph, "output.png", title="My Cluster", dpi=300)
        >>> export_png(graph, "output.png", aggregate=False)  # Show all nodes
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    if aggregate:
        graph_to_viz, _ = aggregate_isolated_nodes(graph)
    else:
        graph_to_viz = graph

    try:
        draw_hierarchical(
            graph_to_viz,
            output_file=str(path),
            title=title or "Kubernetes Resource Graph",
            dpi=dpi,
            format="png",
            **kwargs,
        )
        logger.info(f"Exported PNG to {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to export PNG: {e}", exc_info=True)
        return False


def export_html(
    graph: nx.DiGraph,
    filepath: str | Path,
    title: str | None = None,
    aggregate: bool = True,
    height: str = "900px",
    width: str = "100%",
    bgcolor: str = "#222222",
    font_color: str = "white",
    **kwargs: Any,
) -> bool:
    """
    Export graph to interactive HTML using pyvis.

    Creates an interactive visualization with drag-and-drop, zoom,
    and physics simulation.

    Args:
        graph: NetworkX directed graph
        filepath: Output file path
        title: Optional title for the visualization
        aggregate: Whether to aggregate isolated nodes (default True)
        height: Canvas height (default "900px")
        width: Canvas width (default "100%")
        bgcolor: Background color (default "#222222")
        font_color: Font color (default "white")
        **kwargs: Additional arguments for customization

    Returns:
        True if export succeeded, False otherwise

    Raises:
        ImportError: If pyvis is not installed

    Example:
        >>> export_html(graph, "output.html", title="Production Cluster")
        >>> export_html(graph, "output.html", bgcolor="#ffffff", font_color="black")
    """
    if not _has_pyvis:
        logger.error("pyvis is not installed. Install with: pip install pyvis")
        return False

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    if aggregate:
        graph_to_viz, _ = aggregate_isolated_nodes(graph)
    else:
        graph_to_viz = graph

    try:
        net = Network(
            height=height,
            width=width,
            bgcolor=bgcolor,
            font_color=font_color,
            directed=True,
            notebook=False,
        )

        net.set_options(
            """
        {
          "physics": {
            "forceAtlas2Based": {
              "gravitationalConstant": -50,
              "centralGravity": 0.01,
              "springLength": 100,
              "springConstant": 0.08
            },
            "maxVelocity": 50,
            "solver": "forceAtlas2Based",
            "timestep": 0.35,
            "stabilization": {"iterations": 150}
          },
          "nodes": {"font": {"size": 14}},
          "edges": {
            "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}},
            "smooth": {"type": "continuous"}
          }
        }
        """
        )

        kind_colors = {
            "Deployment": "#1f77b4",
            "ReplicaSet": "#ff7f0e",
            "Pod": "#2ca02c",
            "Service": "#d62728",
            "ConfigMap": "#9467bd",
            "Secret": "#8c564b",
            "ServiceAccount": "#e377c2",
            "DaemonSet": "#7f7f7f",
            "StatefulSet": "#bcbd22",
            "Job": "#17becf",
            "CronJob": "#e7ba52",
        }

        for node_id, attrs in graph_to_viz.nodes(data=True):
            kind = attrs.get("kind", "Unknown")
            name = attrs.get("name", "?")
            namespace = attrs.get("namespace", "cluster")

            if attrs.get("aggregated"):
                color = "#ff0000"
                hover_title = f"{kind}\n{attrs.get('examples', '')}"
                size = 30
            else:
                color = kind_colors.get(kind, "#95a5a6")
                hover_title = f"{kind}\n{name}\nNamespace: {namespace}"
                size = 15

            net.add_node(
                node_id,
                label=f"{kind}\n{name[:25]}",
                title=hover_title,
                color=color,
                size=size,
            )

        for u, v, data in graph_to_viz.edges(data=True):
            rel_type = data.get("relationship_type", "")
            details = data.get("details", "")
            net.add_edge(u, v, title=f"{rel_type}\n{details}", color="#666666")

        net.save_graph(str(path))
        logger.info(f"Exported HTML to {path}")
        return True

    except Exception as e:
        logger.error(f"Failed to export HTML: {e}", exc_info=True)
        return False


def export_json(
    graph: nx.DiGraph,
    filepath: str | Path,
) -> bool:
    """
    Export graph to JSON format.

    Convenience wrapper around save_graph() from persistence module.

    Args:
        graph: NetworkX directed graph
        filepath: Output file path

    Returns:
        True if export succeeded, False otherwise

    Example:
        >>> export_json(graph, "output.json")
        >>> loaded = load_json("output.json")
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        save_graph(graph, str(path), format="json")
        logger.info(f"Exported JSON to {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to export JSON: {e}", exc_info=True)
        return False


def load_json(filepath: str | Path) -> nx.DiGraph:
    """
    Load graph from JSON file.

    Convenience wrapper around load_graph() from persistence module.

    Args:
        filepath: Input file path

    Returns:
        Loaded NetworkX directed graph

    Raises:
        FileNotFoundError: If file doesn't exist

    Example:
        >>> export_json(graph, "output.json")
        >>> loaded = load_json("output.json")
        >>> print(f"Loaded {loaded.number_of_nodes()} nodes")
    """
    return load_graph(str(filepath), format="json")


def export_all(
    graph: nx.DiGraph,
    output_dir: str | Path,
    basename: str,
    title: str | None = None,
    aggregate: bool = True,
    formats: list[str] | None = None,
) -> dict[str, bool]:
    """
    Export graph to multiple formats at once.

    Args:
        graph: NetworkX directed graph
        output_dir: Directory for output files
        basename: Base filename (without extension)
        title: Optional title for visualizations
        aggregate: Whether to aggregate isolated nodes (default True)
        formats: List of formats to export ('png', 'html', 'json').
                If None, exports all formats.

    Returns:
        Dictionary mapping format to success status

    Example:
        >>> results = export_all(graph, "output", "cluster", formats=['png', 'json'])
        >>> print(f"PNG: {results['png']}, JSON: {results['json']}")
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if formats is None:
        formats = ["png", "html", "json"]

    results = {}

    if "png" in formats:
        png_file = output_path / f"{basename}.png"
        results["png"] = export_png(graph, png_file, title=title, aggregate=aggregate)

    if "html" in formats:
        html_file = output_path / f"{basename}.html"
        results["html"] = export_html(graph, html_file, title=title, aggregate=aggregate)

    if "json" in formats:
        json_file = output_path / f"{basename}.json"
        results["json"] = export_json(graph, json_file)

    return results
