"""Graphviz-based graph visualization with beautiful layouts."""

import logging
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

# Color scheme for different resource types
RESOURCE_COLORS = {
    "Pod": "#90EE90",  # Light green
    "Service": "#87CEEB",  # Sky blue
    "Deployment": "#FFB6C1",  # Light pink
    "StatefulSet": "#FFB6C1",  # Light pink
    "DaemonSet": "#FFB6C1",  # Light pink
    "ReplicaSet": "#DDA0DD",  # Plum
    "Job": "#F0E68C",  # Khaki
    "CronJob": "#F0E68C",  # Khaki
    "ConfigMap": "#FFFACD",  # Lemon chiffon
    "Secret": "#FFE4B5",  # Moccasin
    "PersistentVolumeClaim": "#FFA07A",  # Light salmon
    "PersistentVolume": "#FA8072",  # Salmon (darker than PVC)
    "StorageClass": "#FF8C69",  # Dark salmon
    "ServiceAccount": "#E0BBE4",  # Light purple
    "Role": "#87CEEB",  # Sky blue (different from RoleBinding)
    "RoleBinding": "#B0C4DE",  # Light steel blue (different from Role)
    "ClusterRole": "#6495ED",  # Cornflower blue (different from Role)
    "ClusterRoleBinding": "#4682B4",  # Steel blue (different from ClusterRole)
    "NetworkPolicy": "#87CEFA",  # Light sky blue
    "Ingress": "#ADD8E6",  # Light blue
    "Endpoints": "#B0E0E6",  # Powder blue
    "Namespace": "#F5DEB3",  # Wheat
}


def draw_with_graphviz(
    graph: nx.DiGraph,
    output_file: str,
    layout: str = "dot",
    title: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Draw graph using Graphviz with professional layout.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        layout: Graphviz layout engine:
            - 'dot': Hierarchical (best for K8s resources)
            - 'neato': Spring model
            - 'fdp': Force-directed
            - 'sfdp': Scalable force-directed (for large graphs)
            - 'circo': Circular
            - 'twopi': Radial
        title: Optional title for the graph
        **kwargs: Additional graphviz attributes

    Example:
        >>> draw_with_graphviz(graph, "cluster.png", layout="dot")
        >>> draw_with_graphviz(graph, "cluster.png", layout="fdp", ranksep="2")
    """
    try:
        import pygraphviz as pgv
    except ImportError:
        logger.error(
            "pygraphviz not installed. Install with: pip install pygraphviz\n"
            "Note: Requires graphviz system package. On macOS: brew install graphviz"
        )
        raise

    # Create pygraphviz graph
    agraph = pgv.AGraph(directed=True, strict=False)

    # Scale parameters based on graph size
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

    # Set graph attributes for better layout
    agraph.graph_attr.update(
        {
            "rankdir": kwargs.get("rankdir", "TB"),  # Top to bottom
            "ranksep": kwargs.get("ranksep", default_ranksep),  # Space between ranks
            "nodesep": kwargs.get("nodesep", default_nodesep),  # Space between nodes
            "sep": kwargs.get(
                "sep", default_sep
            ),  # Minimum separation (for neato, fdp, sfdp, twopi)
            "overlap": kwargs.get("overlap", "false"),  # Prevent node overlap
            "splines": kwargs.get("splines", "ortho"),  # Orthogonal edges
            "concentrate": "true",  # Merge parallel edges
            "dpi": str(kwargs.get("dpi", default_dpi)),  # High resolution
            "bgcolor": "white",
            "fontname": "Arial",
            "fontsize": "16",
            "size": "100,100!",  # Large canvas
            "resolution": str(kwargs.get("dpi", default_dpi)),
        }
    )

    if title:
        agraph.graph_attr["label"] = title
        agraph.graph_attr["labelloc"] = "t"
        agraph.graph_attr["fontsize"] = "18"

    # Set default node attributes - scale by graph size
    node_count = graph.number_of_nodes()
    if node_count > 100:
        node_fontsize = "14"
        node_margin = "0.3,0.15"
        node_width = "2.5"
        node_height = "0.8"
    elif node_count > 50:
        node_fontsize = "12"
        node_margin = "0.25,0.12"
        node_width = "2.0"
        node_height = "0.6"
    else:
        node_fontsize = "10"
        node_margin = "0.2,0.1"
        node_width = "1.5"
        node_height = "0.5"

    # Set default node attributes
    agraph.node_attr.update(
        {
            "shape": "box",
            "style": "filled,rounded",
            "fontname": "Arial",
            "fontsize": node_fontsize,
            "margin": node_margin,
            "height": node_height,
            "width": node_width,
        }
    )

    # Set default edge attributes - scale by graph size
    node_count = graph.number_of_nodes()
    if node_count > 100:
        edge_fontsize = "12"
        arrowsize = "1.0"
        penwidth = "2.0"
    elif node_count > 50:
        edge_fontsize = "10"
        arrowsize = "0.85"
        penwidth = "1.5"
    else:
        edge_fontsize = "8"
        arrowsize = "0.7"
        penwidth = "1.0"

    # Set default edge attributes
    agraph.edge_attr.update(
        {
            "fontname": "Arial",
            "fontsize": edge_fontsize,
            "color": "#666666",
            "arrowsize": arrowsize,
            "penwidth": penwidth,
        }
    )

    # Add nodes with styling
    for node_id, attrs in graph.nodes(data=True):
        kind = attrs.get("kind", "Unknown")
        name = attrs.get("name", "unknown")
        namespace = attrs.get("namespace", "")

        # Create label with status for Pods
        if kind == "Pod":
            status = attrs.get("status", "Unknown")
            # Shorten common statuses
            status_short = (
                status.replace("Running", "▶ Running")
                .replace("Pending", "⏸ Pending")
                .replace("Failed", "✗ Failed")
                .replace("Succeeded", "✓ Succeeded")
            )
            label = f"{kind}\n{name}\n{status_short}"
            if namespace and namespace != "cluster":
                label = f"{kind}\n{name}\n{status_short}\n({namespace})"
        else:
            label = f"{kind}\n{name}"
            if namespace and namespace != "cluster":
                label = f"{kind}\n{name}\n({namespace})"

        # Get color for this resource type
        color = RESOURCE_COLORS.get(kind, "#D3D3D3")  # Light gray default

        # Add node
        agraph.add_node(
            node_id,
            label=label,
            fillcolor=color,
            color="#333333",  # Border color
        )

    # Add edges with labels
    for source, target, attrs in graph.edges(data=True):
        rel_type = attrs.get("relationship_type", "")
        details = attrs.get("details", "")

        # Create edge label
        edge_label = rel_type
        if details and len(details) < 30:
            edge_label = f"{rel_type}\n{details}"

        agraph.add_edge(
            source,
            target,
            label=edge_label if kwargs.get("show_edge_labels", False) else "",
        )

    # Generate layout
    agraph.layout(prog=layout)

    # Save to file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine format from file extension
    format = output_path.suffix.lstrip(".")
    if not format:
        format = "png"

    agraph.draw(str(output_path), format=format)
    logger.info(f"Generated Graphviz visualization: {output_file}")


def draw_hierarchical(
    graph: nx.DiGraph,
    output_file: str,
    title: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Draw graph with hierarchical layout (dot engine).

    Best for showing Kubernetes resource hierarchies:
    Deployment -> ReplicaSet -> Pod

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        title: Optional title
        **kwargs: Additional arguments
    """
    draw_with_graphviz(
        graph,
        output_file,
        layout="dot",
        title=title or "Kubernetes Resources - Hierarchical View",
        rankdir="TB",  # Top to bottom
        ranksep="1.5",
        nodesep="1.0",
        splines="ortho",
        **kwargs,
    )


def draw_radial(
    graph: nx.DiGraph,
    output_file: str,
    title: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Draw graph with radial layout (twopi engine).

    Good for showing relationships radiating from a central resource.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        title: Optional title
        **kwargs: Additional arguments
    """
    draw_with_graphviz(
        graph,
        output_file,
        layout="twopi",
        title=title or "Kubernetes Resources - Radial View",
        ranksep="2.0",
        **kwargs,
    )


def draw_force_directed(
    graph: nx.DiGraph,
    output_file: str,
    title: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Draw graph with force-directed layout (fdp engine).

    Good for showing natural clustering of resources.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        title: Optional title
        **kwargs: Additional arguments
    """
    # Use sfdp for large graphs, fdp for small
    layout_engine = "sfdp" if graph.number_of_nodes() > 50 else "fdp"

    draw_with_graphviz(
        graph,
        output_file,
        layout=layout_engine,
        title=title or "Kubernetes Resources - Force-Directed View",
        splines="true",  # Curved edges for force-directed
        **kwargs,
    )


def draw_circular(
    graph: nx.DiGraph,
    output_file: str,
    title: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Draw graph with circular layout (circo engine).

    Good for showing connectivity patterns.

    Args:
        graph: NetworkX directed graph
        output_file: Path to output image file
        title: Optional title
        **kwargs: Additional arguments
    """
    draw_with_graphviz(
        graph,
        output_file,
        layout="circo",
        title=title or "Kubernetes Resources - Circular View",
        **kwargs,
    )
