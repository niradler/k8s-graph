"""Tests for k8s_graph.formatter."""

import json

import networkx as nx

from k8s_graph.formatter import format_graph_output


def test_format_json():
    """Test JSON format output."""
    graph = nx.DiGraph()
    graph.add_node("Pod:default:nginx", kind="Pod", name="nginx", namespace="default")
    graph.add_node("Service:default:web", kind="Service", name="web", namespace="default")
    graph.add_edge(
        "Service:default:web",
        "Pod:default:nginx",
        relationship_type="label_selector",
        details="Selects pods",
    )

    output = format_graph_output(graph, format_type="json", include_metadata=True)

    data = json.loads(output)
    assert "nodes" in data
    assert "edges" in data
    assert "metadata" in data
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    assert data["metadata"]["node_count"] == 2
    assert data["metadata"]["edge_count"] == 1


def test_format_json_without_metadata():
    """Test JSON format without metadata."""
    graph = nx.DiGraph()
    graph.add_node("Pod:default:nginx", kind="Pod", name="nginx")

    output = format_graph_output(graph, format_type="json", include_metadata=False)

    data = json.loads(output)
    assert "nodes" in data
    assert "edges" in data
    assert "metadata" not in data


def test_format_json_with_pod_sampling():
    """Test JSON format with pod sampling info."""
    graph = nx.DiGraph()
    graph.add_node("Pod:default:nginx", kind="Pod", name="nginx")

    pod_sampling_info = {"sampled_count": 3, "total_count": 9}

    output = format_graph_output(
        graph,
        format_type="json",
        include_metadata=True,
        pod_sampling_info=pod_sampling_info,
    )

    data = json.loads(output)
    assert "metadata" in data
    assert "pod_sampling" in data["metadata"]
    assert data["metadata"]["pod_sampling"]["sampled_count"] == 3


def test_format_llm_friendly():
    """Test LLM-friendly format."""
    graph = nx.DiGraph()
    graph.add_node(
        "Pod:default:nginx", kind="Pod", name="nginx", namespace="default", phase="Running"
    )
    graph.add_node(
        "Service:default:web",
        kind="Service",
        name="web",
        namespace="default",
        service_type="ClusterIP",
    )
    graph.add_edge("Service:default:web", "Pod:default:nginx", relationship_type="label_selector")

    output = format_graph_output(graph, format_type="llm", include_metadata=True)

    assert "Kubernetes Resource Graph" in output
    assert "Total Resources: 2" in output
    assert "Total Relationships: 1" in output
    assert "Pod: nginx" in output
    assert "Service: web" in output
    assert "label_selector" in output


def test_format_llm_with_pod_sampling():
    """Test LLM format with pod sampling info."""
    graph = nx.DiGraph()
    graph.add_node("Pod:default:nginx", kind="Pod", name="nginx")

    pod_sampling_info = {"sampled_count": 2, "total_count": 6}

    output = format_graph_output(
        graph, format_type="llm", include_metadata=True, pod_sampling_info=pod_sampling_info
    )

    assert "Pod sampling active" in output
    assert "2 representative pods" in output
    assert "6 total" in output


def test_format_minimal():
    """Test minimal format output."""
    graph = nx.DiGraph()
    graph.add_node(
        "Pod:default:nginx", kind="Pod", name="nginx", namespace="default", phase="Running"
    )
    graph.add_node("Service:default:web", kind="Service", name="web", namespace="default")
    graph.add_edge("Service:default:web", "Pod:default:nginx", relationship_type="label_selector")

    output = format_graph_output(graph, format_type="minimal")

    data = json.loads(output)
    assert "nodes" in data
    assert len(data["nodes"]) == 2
    pod_node = next(n for n in data["nodes"] if n["kind"] == "Pod")
    assert "kind" in pod_node
    assert "name" in pod_node
    assert "namespace" in pod_node
    assert "phase" not in pod_node


def test_format_unknown_type():
    """Test unknown format type raises error."""
    import pytest

    graph = nx.DiGraph()

    with pytest.raises(ValueError, match="Unknown format type"):
        format_graph_output(graph, format_type="unknown")
