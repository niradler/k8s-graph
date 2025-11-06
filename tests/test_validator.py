"""Tests for k8s_graph.validator."""

import networkx as nx

from k8s_graph.validator import check_graph_cycles, get_graph_statistics, validate_graph


def test_validate_empty_graph():
    """Test validation of empty graph."""
    graph = nx.DiGraph()
    result = validate_graph(graph)

    assert result["valid"] is True
    assert result["node_count"] == 0
    assert result["edge_count"] == 0
    assert result["duplicate_count"] == 0


def test_validate_clean_graph():
    """Test validation of clean graph."""
    graph = nx.DiGraph()
    graph.add_node("Pod:default:nginx", kind="Pod", name="nginx", namespace="default")
    graph.add_node("Service:default:web", kind="Service", name="web", namespace="default")
    graph.add_edge(
        "Service:default:web",
        "Pod:default:nginx",
        relationship_type="label_selector",
    )

    result = validate_graph(graph)

    assert result["valid"] is True
    assert result["node_count"] == 2
    assert result["edge_count"] == 1
    assert result["unique_resources"] == 2
    assert result["duplicate_count"] == 0
    assert len(result["issues"]) == 0


def test_validate_duplicate_resources():
    """Test detection of duplicate resources."""
    graph = nx.DiGraph()
    graph.add_node("node1", kind="Pod", name="nginx", namespace="default")
    graph.add_node("node2", kind="Pod", name="nginx", namespace="default")

    result = validate_graph(graph)

    assert result["valid"] is False
    assert result["duplicate_count"] == 1
    assert len(result["issues"]) == 1
    assert result["issues"][0]["type"] == "duplicate_resource"
    assert result["issues"][0]["kind"] == "Pod"


def test_validate_missing_kind():
    """Test detection of missing kind attribute."""
    graph = nx.DiGraph()
    graph.add_node("node1", name="nginx", namespace="default")

    result = validate_graph(graph)

    assert result["valid"] is False
    assert len(result["issues"]) == 1
    assert result["issues"][0]["type"] == "missing_kind"


def test_validate_edge_without_metadata():
    """Test warning for edges without metadata."""
    graph = nx.DiGraph()
    graph.add_node("node1", kind="Pod", name="nginx", namespace="default")
    graph.add_node("node2", kind="Service", name="web", namespace="default")
    graph.add_edge("node1", "node2")

    result = validate_graph(graph)

    assert result["valid"] is True
    assert len(result["warnings"]) >= 1


def test_check_graph_cycles():
    """Test cycle detection."""
    graph = nx.DiGraph()
    graph.add_edge("A", "B")
    graph.add_edge("B", "C")
    graph.add_edge("C", "A")

    result = check_graph_cycles(graph)

    assert result["has_cycles"] is True
    assert result["cycle_count"] > 0


def test_get_graph_statistics():
    """Test graph statistics."""
    graph = nx.DiGraph()
    graph.add_node("Pod:default:nginx", kind="Pod", name="nginx", namespace="default")
    graph.add_node("Service:default:web", kind="Service", name="web", namespace="default")
    graph.add_edge("Service:default:web", "Pod:default:nginx")

    stats = get_graph_statistics(graph)

    assert stats["node_count"] == 2
    assert stats["edge_count"] == 1
    assert stats["kind_count"] == 2
    assert stats["namespace_count"] == 1
    assert "Pod" in stats["resource_kinds"]
    assert "Service" in stats["resource_kinds"]
