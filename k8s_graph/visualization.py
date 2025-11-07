"""
Unified visualization module with multiple backends.

Supports:
- Matplotlib (draw_cluster, draw_namespace, draw_dependencies)
- Graphviz (draw_hierarchical, draw_radial, draw_circular)
- PyVis interactive HTML (via export module)
"""

import logging
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

RESOURCE_COLORS = {
    "Pod": "#90EE90",
    "Service": "#87CEEB",
    "Deployment": "#FFB6C1",
    "StatefulSet": "#FFB6C1",
    "DaemonSet": "#FFB6C1",
    "ReplicaSet": "#DDA0DD",
    "Job": "#F0E68C",
    "CronJob": "#F0E68C",
    "ConfigMap": "#FFFACD",
    "Secret": "#FFE4B5",
    "PersistentVolumeClaim": "#FFA07A",
    "PersistentVolume": "#FA8072",
    "StorageClass": "#FF8C69",
    "ServiceAccount": "#E0BBE4",
    "Role": "#87CEEB",
    "RoleBinding": "#B0C4DE",
    "ClusterRole": "#6495ED",
    "ClusterRoleBinding": "#4682B4",
    "NetworkPolicy": "#87CEFA",
    "Ingress": "#ADD8E6",
    "Endpoints": "#B0E0E6",
    "Namespace": "#F5DEB3",
    "HorizontalPodAutoscaler": "#F0E68C",
}


def draw_hierarchical(
    graph: nx.DiGraph,
    output_file: str,
    title: str | None = None,
    dpi: int = 300,
    format: str = "png",
    **kwargs: Any,
) -> None:
    """
    Draw graph using Graphviz with hierarchical (dot) layout.

    Best for Kubernetes resource hierarchies (Deployment -> ReplicaSet -> Pod).

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        title: Optional title for the graph
        dpi: Resolution in dots per inch
        format: Output format (png, svg, pdf, etc.)
        **kwargs: Additional graphviz attributes

    Example:
        >>> draw_hierarchical(graph, "cluster.png", title="My Cluster")
        >>> draw_hierarchical(graph, "cluster.svg", format="svg", dpi=600)
    """
    _draw_with_graphviz(
        graph, output_file, layout="dot", title=title, dpi=dpi, format=format, **kwargs
    )


def draw_radial(
    graph: nx.DiGraph,
    output_file: str,
    title: str | None = None,
    dpi: int = 300,
    format: str = "png",
    **kwargs: Any,
) -> None:
    """
    Draw graph using Graphviz with radial (twopi) layout.

    Good for showing relationships radiating from a central resource.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        title: Optional title for the graph
        dpi: Resolution in dots per inch
        format: Output format
        **kwargs: Additional graphviz attributes
    """
    _draw_with_graphviz(
        graph, output_file, layout="twopi", title=title, dpi=dpi, format=format, **kwargs
    )


def draw_circular(
    graph: nx.DiGraph,
    output_file: str,
    title: str | None = None,
    dpi: int = 300,
    format: str = "png",
    **kwargs: Any,
) -> None:
    """
    Draw graph using Graphviz with circular (circo) layout.

    Places nodes in a circular arrangement.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        title: Optional title for the graph
        dpi: Resolution in dots per inch
        format: Output format
        **kwargs: Additional graphviz attributes
    """
    _draw_with_graphviz(
        graph, output_file, layout="circo", title=title, dpi=dpi, format=format, **kwargs
    )


def _draw_with_graphviz(
    graph: nx.DiGraph,
    output_file: str,
    layout: str = "dot",
    title: str | None = None,
    dpi: int = 300,
    format: str = "png",
    **kwargs: Any,
) -> None:
    """
    Internal function to draw graph using Graphviz.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        layout: Graphviz layout engine (dot, neato, fdp, sfdp, circo, twopi)
        title: Optional title
        dpi: Resolution
        format: Output format
        **kwargs: Additional graphviz attributes
    """
    try:
        import pygraphviz as pgv
    except ImportError:
        logger.error(
            "pygraphviz not installed. Install with: pip install pygraphviz\n"
            "Note: Requires graphviz system package. On macOS: brew install graphviz"
        )
        raise

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    agraph = pgv.AGraph(directed=True, strict=False)

    node_count = graph.number_of_nodes()
    if node_count > 100:
        default_dpi = 600
        default_ranksep = "2.5"
        default_nodesep = "1.5"
        default_sep = "2.0"
    elif node_count > 50:
        default_dpi = 450
        default_ranksep = "2.0"
        default_nodesep = "1.2"
        default_sep = "1.5"
    else:
        default_dpi = 300
        default_ranksep = "1.5"
        default_nodesep = "0.8"
        default_sep = "1.0"

    agraph.graph_attr.update(
        {
            "rankdir": kwargs.get("rankdir", "TB"),
            "ranksep": kwargs.get("ranksep", default_ranksep),
            "nodesep": kwargs.get("nodesep", default_nodesep),
            "sep": kwargs.get("sep", default_sep),
            "splines": kwargs.get("splines", "ortho"),
            "overlap": kwargs.get("overlap", "false"),
            "dpi": str(kwargs.get("dpi", dpi or default_dpi)),
            "bgcolor": kwargs.get("bgcolor", "white"),
            "fontname": kwargs.get("fontname", "Arial"),
            "fontsize": kwargs.get("fontsize", "14"),
        }
    )

    if title:
        agraph.graph_attr["label"] = title
        agraph.graph_attr["labelloc"] = "t"
        agraph.graph_attr["labeljust"] = "c"

    agraph.node_attr.update(
        {
            "shape": "box",
            "style": "rounded,filled",
            "fontname": "Arial",
            "fontsize": "10",
            "margin": "0.2,0.1",
        }
    )

    agraph.edge_attr.update(
        {
            "color": "#666666",
            "arrowsize": "0.7",
            "penwidth": "1.5",
            "fontname": "Arial",
            "fontsize": "8",
        }
    )

    for node_id, attrs in graph.nodes(data=True):
        kind = attrs.get("kind", "Unknown")
        name = attrs.get("name", "?")
        namespace = attrs.get("namespace")

        color = RESOURCE_COLORS.get(kind, "#FFFFFF")

        label_parts = [f"<B>{kind}</B>", name]
        if namespace and namespace != "cluster":
            label_parts.append(f"<I>ns:{namespace}</I>")

        label = "<" + "<BR/>".join(label_parts) + ">"

        agraph.add_node(
            node_id,
            label=label,
            fillcolor=color,
            color="#333333",
        )

    for source, target, edge_attrs in graph.edges(data=True):
        rel_type = edge_attrs.get("relationship_type", "")
        details = edge_attrs.get("details", "")

        edge_label = rel_type or details
        if len(edge_label) > 20:
            edge_label = edge_label[:17] + "..."

        agraph.add_edge(
            source,
            target,
            label=edge_label if edge_label else "",
        )

    agraph.layout(prog=layout)
    agraph.draw(output_file, format=format)

    logger.info(f"Saved {layout} layout visualization to {output_file}")


def draw_cluster(
    graph: nx.DiGraph,
    output_file: str,
    layout: str = "shell",
    title: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Draw the entire cluster graph using matplotlib.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        layout: Layout algorithm - 'shell', 'circular', 'spectral', 'spring', 'kamada_kawai'
        title: Optional title for the graph
        **kwargs: Additional arguments passed to layout and drawing functions

    Example:
        >>> draw_cluster(graph, "cluster.png", layout="shell")
        >>> draw_cluster(graph, "cluster.png", layout="spring", k=0.5)
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.error(
            "matplotlib is required for visualization. Install with: pip install matplotlib"
        )
        raise

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=kwargs.pop("figsize", (16, 12)))

    pos = _get_layout(graph, layout, **kwargs)

    node_colors = [
        _get_node_color_mpl(attrs.get("kind", "Unknown")) for _, attrs in graph.nodes(data=True)
    ]
    node_sizes = [
        _get_node_size(attrs.get("kind", "Unknown")) for _, attrs in graph.nodes(data=True)
    ]

    nx.draw_networkx_nodes(
        graph,
        pos,
        node_color=node_colors,
        node_size=node_sizes,
        alpha=0.9,
        ax=ax,
    )

    nx.draw_networkx_labels(
        graph,
        pos,
        labels={node: _format_node_label(node, attrs) for node, attrs in graph.nodes(data=True)},
        font_size=kwargs.get("font_size", 6),
        font_weight="bold",
        ax=ax,
    )

    nx.draw_networkx_edges(
        graph,
        pos,
        edge_color="gray",
        alpha=0.5,
        arrows=True,
        arrowsize=10,
        ax=ax,
    )

    if title:
        ax.set_title(title, fontsize=16, fontweight="bold")

    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    logger.info(f"Saved matplotlib visualization to {output_file}")


def draw_namespace(
    graph: nx.DiGraph,
    namespace: str,
    output_file: str,
    layout: str = "shell",
    **kwargs: Any,
) -> None:
    """
    Draw resources from a specific namespace using matplotlib.

    Args:
        graph: NetworkX directed graph
        namespace: Namespace to visualize
        output_file: Path to output image file
        layout: Layout algorithm
        **kwargs: Additional arguments
    """
    subgraph_nodes = [
        node_id for node_id, attrs in graph.nodes(data=True) if attrs.get("namespace") == namespace
    ]

    subgraph = graph.subgraph(subgraph_nodes).copy()

    draw_cluster(subgraph, output_file, layout=layout, title=f"Namespace: {namespace}", **kwargs)


def draw_dependencies(
    graph: nx.DiGraph,
    resource_id: str,
    output_file: str,
    max_depth: int = 3,
    layout: str = "spring",
    **kwargs: Any,
) -> None:
    """
    Draw dependency graph for a specific resource using matplotlib.

    Args:
        graph: NetworkX directed graph
        resource_id: Node ID of the resource
        output_file: Path to output image file
        max_depth: Maximum depth to explore
        layout: Layout algorithm
        **kwargs: Additional arguments
    """
    if resource_id not in graph:
        logger.warning(f"Resource {resource_id} not found in graph")
        return

    nodes_to_include = {resource_id}

    for _ in range(max_depth):
        new_nodes = set()
        for node in nodes_to_include:
            new_nodes.update(graph.successors(node))
            new_nodes.update(graph.predecessors(node))
        nodes_to_include.update(new_nodes)

    subgraph = graph.subgraph(nodes_to_include).copy()

    resource_name = graph.nodes[resource_id].get("name", resource_id)
    draw_cluster(
        subgraph,
        output_file,
        layout=layout,
        title=f"Dependencies: {resource_name}",
        **kwargs,
    )


def draw_with_shell_layout(
    graph: nx.DiGraph,
    output_file: str,
    shells: list[list[str]] | None = None,
    **kwargs: Any,
) -> None:
    """
    Draw graph using shell layout with Kubernetes hierarchy using matplotlib.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        shells: Optional custom shell configuration
        **kwargs: Additional arguments passed to drawing functions
    """
    if shells is None:
        shells = get_shell_layout(graph)

    draw_cluster(graph, output_file, layout="shell", nlist=shells, **kwargs)


def get_shell_layout(graph: nx.DiGraph) -> list[list[str]]:
    """
    Organize nodes into shells based on Kubernetes resource hierarchy.

    Returns:
        List of node ID lists, one per shell:
        - Shell 0: Namespaces
        - Shell 1: Controllers (Deployment, StatefulSet, DaemonSet)
        - Shell 2: ReplicaSets, Jobs, CronJobs
        - Shell 3: Pods
        - Shell 4: ConfigMaps, Secrets, Services, etc.
        - Shell 5: Other resources
    """
    shells: list[list[str]] = [[] for _ in range(6)]

    for node_id, attrs in graph.nodes(data=True):
        kind = attrs.get("kind", "Unknown")

        if kind == "Namespace":
            shells[0].append(node_id)
        elif kind in ("Deployment", "StatefulSet", "DaemonSet"):
            shells[1].append(node_id)
        elif kind in ("ReplicaSet", "Job", "CronJob"):
            shells[2].append(node_id)
        elif kind == "Pod":
            shells[3].append(node_id)
        elif kind in ("ConfigMap", "Secret", "Service", "Ingress", "PersistentVolumeClaim"):
            shells[4].append(node_id)
        else:
            shells[5].append(node_id)

    return [shell for shell in shells if shell]


def create_legend(output_file: str) -> None:
    """
    Create a legend image showing resource colors using matplotlib.

    Args:
        output_file: Path to output image file
    """
    try:
        import matplotlib.patches as mpatches
        import matplotlib.pyplot as plt
    except ImportError:
        logger.error("matplotlib is required. Install with: pip install matplotlib")
        raise

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 10))
    ax.axis("off")

    legend_items = []
    for kind, color in sorted(RESOURCE_COLORS.items()):
        patch = mpatches.Patch(color=color, label=kind)
        legend_items.append(patch)

    ax.legend(
        handles=legend_items,
        loc="center",
        fontsize=10,
        frameon=True,
        title="Resource Types",
        title_fontsize=12,
    )

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    logger.info(f"Saved legend to {output_file}")


def _get_layout(graph: nx.DiGraph, layout: str, **kwargs: Any) -> dict[str, tuple[float, float]]:
    """Get node positions using specified layout algorithm."""
    if layout == "shell":
        nlist = kwargs.pop("nlist", None)
        if nlist is None:
            nlist = get_shell_layout(graph)
        result: dict[str, tuple[float, float]] = nx.shell_layout(graph, nlist=nlist, **kwargs)
        return result

    elif layout == "circular":
        result = nx.circular_layout(graph, **kwargs)
        return result

    elif layout == "spectral":
        result = nx.spectral_layout(graph, **kwargs)
        return result

    elif layout == "spring":
        result = nx.spring_layout(
            graph, k=kwargs.pop("k", 0.5), iterations=kwargs.pop("iterations", 50), **kwargs
        )
        return result

    elif layout == "kamada_kawai":
        result = nx.kamada_kawai_layout(graph, **kwargs)
        return result

    else:
        logger.warning(f"Unknown layout: {layout}, using spring layout")
        result = nx.spring_layout(graph, **kwargs)
        return result


def _get_node_color_mpl(kind: str) -> str:
    """Get matplotlib color for node based on kind."""
    color_map = {
        "Namespace": "#E8F4F8",
        "Pod": "#6495ED",
        "Deployment": "#90EE90",
        "StatefulSet": "#90EE90",
        "DaemonSet": "#90EE90",
        "ReplicaSet": "#98FB98",
        "Service": "#FFD700",
        "ConfigMap": "#D3D3D3",
        "Secret": "#FFB6C1",
        "Job": "#87CEEB",
        "CronJob": "#87CEEB",
        "Ingress": "#FFA500",
        "NetworkPolicy": "#F08080",
        "ServiceAccount": "#E6E6FA",
        "Role": "#E6E6FA",
        "RoleBinding": "#E6E6FA",
        "PersistentVolumeClaim": "#DEB887",
        "HorizontalPodAutoscaler": "#F0E68C",
    }
    return color_map.get(kind, "#FFFFFF")


def _get_node_size(kind: str) -> int:
    """Get node size based on kind importance."""
    size_map = {
        "Namespace": 1500,
        "Deployment": 1200,
        "StatefulSet": 1200,
        "DaemonSet": 1200,
        "Service": 1000,
        "Pod": 800,
        "ReplicaSet": 600,
        "ConfigMap": 400,
        "Secret": 400,
    }
    return size_map.get(kind, 500)


def _format_node_label(node_id: str, attrs: dict[str, Any]) -> str:
    """Format node label for display."""
    name = str(attrs.get("name", "?"))
    if len(name) > 20:
        name = name[:17] + "..."
    return name
