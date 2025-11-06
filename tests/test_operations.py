import networkx as nx
import pytest

from k8s_graph.operations import (
    compose_namespace_graphs,
    diff_graphs,
    extract_namespace,
    filter_by_kind,
    filter_by_relationship,
    get_largest_component,
    merge_graphs,
    remove_isolated_nodes,
    split_by_namespace,
    union_graphs,
)


@pytest.fixture
def graph1():
    """Create first sample graph."""
    graph = nx.DiGraph()

    graph.add_node("Pod:default:nginx-1", kind="Pod", name="nginx-1", namespace="default")
    graph.add_node("Service:default:web", kind="Service", name="web", namespace="default")

    graph.add_edge("Service:default:web", "Pod:default:nginx-1", relationship_type="label_selector")

    return graph


@pytest.fixture
def graph2():
    """Create second sample graph."""
    graph = nx.DiGraph()

    graph.add_node("Pod:default:nginx-2", kind="Pod", name="nginx-2", namespace="default")
    graph.add_node("ConfigMap:default:config", kind="ConfigMap", name="config", namespace="default")

    graph.add_edge("Pod:default:nginx-2", "ConfigMap:default:config", relationship_type="volume")

    return graph


def test_merge_graphs(graph1, graph2):
    """Test merging multiple graphs."""
    merged = merge_graphs([graph1, graph2])

    assert merged.number_of_nodes() == 4
    assert merged.number_of_edges() == 2
    assert merged.has_node("Pod:default:nginx-1")
    assert merged.has_node("Pod:default:nginx-2")
    assert merged.has_node("Service:default:web")
    assert merged.has_node("ConfigMap:default:config")


def test_merge_empty_graphs():
    """Test merging empty graph list."""
    merged = merge_graphs([])
    assert merged.number_of_nodes() == 0


def test_union_graphs(graph1, graph2):
    """Test union of two graphs."""
    union = union_graphs(graph1, graph2)

    assert union.number_of_nodes() == 4
    assert union.number_of_edges() == 2


def test_compose_namespace_graphs():
    """Test composing namespace graphs with hierarchy."""
    default_graph = nx.DiGraph()
    default_graph.add_node("Pod:default:nginx", kind="Pod", name="nginx", namespace="default")

    kube_system_graph = nx.DiGraph()
    kube_system_graph.add_node(
        "Pod:kube-system:coredns",
        kind="Pod",
        name="coredns",
        namespace="kube-system",
    )

    ns_graphs = {"default": default_graph, "kube-system": kube_system_graph}
    composed = compose_namespace_graphs(ns_graphs)

    assert composed.has_node("Namespace:default")
    assert composed.has_node("Namespace:kube-system")
    assert composed.has_node("Pod:default:nginx")
    assert composed.has_node("Pod:kube-system:coredns")
    assert composed.has_edge("Pod:default:nginx", "Namespace:default")


def test_extract_namespace(graph1):
    """Test extracting namespace subgraph."""
    subgraph = extract_namespace(graph1, "default")

    assert subgraph.number_of_nodes() == 2
    assert subgraph.has_node("Pod:default:nginx-1")
    assert subgraph.has_node("Service:default:web")


def test_extract_nonexistent_namespace(graph1):
    """Test extracting non-existent namespace."""
    subgraph = extract_namespace(graph1, "nonexistent")
    assert subgraph.number_of_nodes() == 0


def test_diff_graphs(graph1, graph2):
    """Test graph diff."""
    diff = diff_graphs(graph1, graph2)

    assert len(diff["added_nodes"]) == 2
    assert len(diff["removed_nodes"]) == 2
    assert "Pod:default:nginx-2" in diff["added_nodes"]
    assert "Pod:default:nginx-1" in diff["removed_nodes"]


def test_diff_identical_graphs(graph1):
    """Test diff of identical graphs."""
    diff = diff_graphs(graph1, graph1)

    assert len(diff["added_nodes"]) == 0
    assert len(diff["removed_nodes"]) == 0
    assert len(diff["modified_nodes"]) == 0


def test_filter_by_kind(graph1):
    """Test filtering by resource kind."""
    pods = filter_by_kind(graph1, ["Pod"])

    assert pods.number_of_nodes() == 1
    assert pods.has_node("Pod:default:nginx-1")
    assert not pods.has_node("Service:default:web")


def test_filter_by_relationship(graph1):
    """Test filtering by relationship type."""
    filtered = filter_by_relationship(graph1, ["label_selector"])

    assert filtered.number_of_nodes() == 2
    assert filtered.number_of_edges() == 1


def test_remove_isolated_nodes():
    """Test removing isolated nodes."""
    graph = nx.DiGraph()
    graph.add_node("Connected1", kind="Pod", name="c1", namespace="default")
    graph.add_node("Connected2", kind="Pod", name="c2", namespace="default")
    graph.add_node("Isolated", kind="Pod", name="iso", namespace="default")

    graph.add_edge("Connected1", "Connected2")

    filtered = remove_isolated_nodes(graph)

    assert filtered.number_of_nodes() == 2
    assert not filtered.has_node("Isolated")


def test_get_largest_component():
    """Test getting largest connected component."""
    graph = nx.DiGraph()

    graph.add_node("A1", kind="Pod", name="a1", namespace="default")
    graph.add_node("A2", kind="Pod", name="a2", namespace="default")
    graph.add_node("A3", kind="Pod", name="a3", namespace="default")
    graph.add_edge("A1", "A2")
    graph.add_edge("A2", "A3")

    graph.add_node("B1", kind="Pod", name="b1", namespace="default")
    graph.add_node("B2", kind="Pod", name="b2", namespace="default")
    graph.add_edge("B1", "B2")

    largest = get_largest_component(graph)

    assert largest.number_of_nodes() == 3
    assert largest.has_node("A1")


def test_split_by_namespace():
    """Test splitting graph by namespace."""
    graph = nx.DiGraph()
    graph.add_node("Pod:default:nginx", kind="Pod", name="nginx", namespace="default")
    graph.add_node("Pod:kube-system:coredns", kind="Pod", name="coredns", namespace="kube-system")

    ns_graphs = split_by_namespace(graph)

    assert len(ns_graphs) == 2
    assert "default" in ns_graphs
    assert "kube-system" in ns_graphs
    assert ns_graphs["default"].number_of_nodes() == 1
    assert ns_graphs["kube-system"].number_of_nodes() == 1
