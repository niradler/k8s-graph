import logging
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


def draw_cluster(
    graph: nx.DiGraph,
    output_file: str,
    layout: str = "shell",
    title: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Draw the entire cluster graph using specified layout.

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
        _get_node_color(attrs.get("kind", "Unknown")) for _, attrs in graph.nodes(data=True)
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

    logger.info(f"Saved graph visualization to {output_file}")


def draw_namespace(
    graph: nx.DiGraph,
    namespace: str,
    output_file: str,
    layout: str = "shell",
    **kwargs: Any,
) -> None:
    """
    Draw resources from a specific namespace.

    Args:
        graph: NetworkX directed graph
        namespace: Kubernetes namespace to visualize
        output_file: Path to output image file
        layout: Layout algorithm
        **kwargs: Additional arguments passed to layout and drawing functions

    Example:
        >>> draw_namespace(graph, "default", "default_namespace.png")
    """
    namespace_nodes = [
        node_id for node_id, attrs in graph.nodes(data=True) if attrs.get("namespace") == namespace
    ]

    if not namespace_nodes:
        logger.warning(f"No resources found in namespace: {namespace}")
        return

    subgraph = graph.subgraph(namespace_nodes).copy()
    draw_cluster(
        subgraph,
        output_file,
        layout=layout,
        title=f"Namespace: {namespace}",
        **kwargs,
    )


def draw_dependencies(
    graph: nx.DiGraph,
    resource_id: str,
    output_file: str,
    max_depth: int | None = None,
    layout: str = "spring",
    **kwargs: Any,
) -> None:
    """
    Draw dependency tree for a specific resource.

    Args:
        graph: NetworkX directed graph
        resource_id: Node ID of the resource
        output_file: Path to output image file
        max_depth: Maximum depth to traverse
        layout: Layout algorithm
        **kwargs: Additional arguments passed to layout and drawing functions

    Example:
        >>> draw_dependencies(graph, "Deployment:default:nginx", "nginx_deps.png", max_depth=3)
    """
    from k8s_graph.query import find_dependencies

    deps_graph = find_dependencies(graph, resource_id, max_depth=max_depth)

    if deps_graph.number_of_nodes() == 0:
        logger.warning(f"No dependencies found for {resource_id}")
        return

    attrs = graph.nodes.get(resource_id, {})
    title = f"Dependencies: {attrs.get('kind', 'Unknown')}/{attrs.get('name', 'unknown')}"

    draw_cluster(deps_graph, output_file, layout=layout, title=title, **kwargs)


def get_shell_layout(graph: nx.DiGraph) -> list[list[str]]:
    """
    Create shell layout with Kubernetes resource hierarchy.

    Organizes nodes into shells based on resource type:
    - Shell 0 (center): Namespaces
    - Shell 1: Controllers (Deployments, StatefulSets, DaemonSets)
    - Shell 2: ReplicaSets, Jobs
    - Shell 3: Pods
    - Shell 4: ConfigMaps, Secrets, Services
    - Shell 5: Other resources

    Args:
        graph: NetworkX directed graph

    Returns:
        List of shells, where each shell is a list of node IDs

    Example:
        >>> shells = get_shell_layout(graph)
        >>> print(f"Shell layout: {len(shells)} shells")
    """
    shells: list[list[str]] = [[], [], [], [], [], []]

    for node_id, attrs in graph.nodes(data=True):
        kind = attrs.get("kind", "Unknown")

        if kind == "Namespace":
            shells[0].append(node_id)
        elif kind in ("Deployment", "StatefulSet", "DaemonSet", "CronJob"):
            shells[1].append(node_id)
        elif kind in ("ReplicaSet", "Job"):
            shells[2].append(node_id)
        elif kind == "Pod":
            shells[3].append(node_id)
        elif kind in ("ConfigMap", "Secret", "Service", "Ingress", "PersistentVolumeClaim"):
            shells[4].append(node_id)
        else:
            shells[5].append(node_id)

    return [shell for shell in shells if shell]


def draw_with_shell_layout(
    graph: nx.DiGraph,
    output_file: str,
    shells: list[list[str]] | None = None,
    **kwargs: Any,
) -> None:
    """
    Draw graph using shell layout with Kubernetes hierarchy.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        shells: Optional custom shell configuration
        **kwargs: Additional arguments passed to drawing functions

    Example:
        >>> draw_with_shell_layout(graph, "cluster_shell.png")
    """
    if shells is None:
        shells = get_shell_layout(graph)

    draw_cluster(graph, output_file, layout="shell", nlist=shells, **kwargs)


def _get_layout(graph: nx.DiGraph, layout: str, **kwargs: Any) -> dict[str, tuple[float, float]]:
    """
    Get node positions using specified layout algorithm.

    Args:
        graph: NetworkX directed graph
        layout: Layout algorithm name
        **kwargs: Additional arguments for layout function

    Returns:
        Dictionary mapping node IDs to (x, y) positions
    """
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


def _get_node_color(kind: str) -> str:
    """Get color for node based on kind."""
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
        "Deployment": 1000,
        "StatefulSet": 1000,
        "DaemonSet": 1000,
        "Service": 800,
        "Ingress": 800,
        "ReplicaSet": 600,
        "Job": 600,
        "CronJob": 600,
        "Pod": 400,
        "ConfigMap": 300,
        "Secret": 300,
        "PersistentVolumeClaim": 300,
    }
    return size_map.get(kind, 400)


def _format_node_label(node_id: str, attrs: dict[str, Any]) -> str:
    """Format node label for display."""
    kind = attrs.get("kind", "?")
    name = attrs.get("name", "unknown")

    if len(name) > 15:
        name = name[:12] + "..."

    return f"{kind}\n{name}"


def export_to_dot(graph: nx.DiGraph, output_file: str) -> None:
    """
    Export graph to Graphviz DOT format for visualization.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output DOT file

    Example:
        >>> export_to_dot(graph, "cluster.dot")
        >>> # Then: dot -Tpng cluster.dot -o cluster.png
    """
    try:
        import pydot

        pydot_graph = pydot.Dot(graph_type="digraph", rankdir="LR")

        for node_id, attrs in graph.nodes(data=True):
            kind = attrs.get("kind", "Unknown")
            name = attrs.get("name", "unknown")
            label = f"{kind}\\n{name}"

            color = _get_node_color(kind)

            node = pydot.Node(node_id, label=label, shape="box", style="filled", fillcolor=color)
            pydot_graph.add_node(node)

        for source, target, attrs in graph.edges(data=True):
            rel_type = attrs.get("relationship_type", "")
            edge = pydot.Edge(source, target, label=rel_type)
            pydot_graph.add_edge(edge)

        pydot_graph.write(output_file)
        logger.info(f"Exported graph to {output_file}")

    except ImportError:
        logger.error("pydot is not installed. Install with: pip install pydot")
        raise
    except Exception as e:
        logger.error(f"Error exporting to DOT format: {e}")
        raise


def create_legend(output_file: str) -> None:
    """
    Create a legend showing resource kinds and their colors.

    Args:
        output_file: Path to output image file

    Example:
        >>> create_legend("legend.png")
    """
    try:
        import matplotlib.patches as mpatches
        import matplotlib.pyplot as plt
    except ImportError:
        logger.error("matplotlib is required. Install with: pip install matplotlib")
        raise

    kinds = [
        "Namespace",
        "Deployment",
        "StatefulSet",
        "DaemonSet",
        "ReplicaSet",
        "Pod",
        "Service",
        "Ingress",
        "ConfigMap",
        "Secret",
        "Job",
        "CronJob",
    ]

    patches = [mpatches.Patch(color=_get_node_color(kind), label=kind) for kind in kinds]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.legend(handles=patches, loc="center", fontsize=12, frameon=True)
    ax.axis("off")

    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close()

    logger.info(f"Saved legend to {output_file}")
