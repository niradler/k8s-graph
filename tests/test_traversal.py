import networkx as nx
import pytest

from k8s_graph.traversal import (
    get_dependency_levels,
    get_leaves,
    get_longest_path,
    get_roots,
    get_shortest_paths_from_root,
    reverse_topological_order,
    topological_order,
    traverse_bfs,
    traverse_by_relationship,
    traverse_dfs,
)


@pytest.fixture
def dag_graph():
    """Create a DAG for topological sort testing."""
    graph = nx.DiGraph()

    graph.add_node("A", kind="Namespace", name="A", namespace=None)
    graph.add_node("B", kind="Deployment", name="B", namespace="default")
    graph.add_node("C", kind="ReplicaSet", name="C", namespace="default")
    graph.add_node("D", kind="Pod", name="D", namespace="default")
    graph.add_node("E", kind="ConfigMap", name="E", namespace="default")

    graph.add_edge("A", "B", relationship_type="namespace")
    graph.add_edge("B", "C", relationship_type="owner")
    graph.add_edge("C", "D", relationship_type="owner")
    graph.add_edge("B", "E", relationship_type="volume")

    return graph


def test_traverse_bfs(dag_graph):
    """Test breadth-first traversal."""
    visited = list(traverse_bfs(dag_graph, "A"))

    node_ids = [nid for nid, _ in visited]
    assert node_ids[0] == "A"
    assert "B" in node_ids
    assert len(visited) == 5


def test_traverse_bfs_with_filter(dag_graph):
    """Test BFS with filter function."""
    visited = list(
        traverse_bfs(dag_graph, "A", filter_fn=lambda nid, attrs: attrs.get("kind") != "Pod")
    )

    node_ids = [nid for nid, _ in visited]
    assert "D" not in node_ids
    assert len(visited) == 4


def test_traverse_dfs(dag_graph):
    """Test depth-first traversal."""
    visited = list(traverse_dfs(dag_graph, "A"))

    node_ids = [nid for nid, _ in visited]
    assert node_ids[0] == "A"
    assert len(visited) == 5


def test_get_roots(dag_graph):
    """Test finding root nodes."""
    roots = get_roots(dag_graph)
    assert len(roots) == 1
    assert "A" in roots


def test_get_leaves(dag_graph):
    """Test finding leaf nodes."""
    leaves = get_leaves(dag_graph)
    assert len(leaves) == 2
    assert "D" in leaves
    assert "E" in leaves


def test_topological_order(dag_graph):
    """Test topological ordering."""
    order = topological_order(dag_graph)
    assert len(order) == 5

    a_idx = order.index("A")
    b_idx = order.index("B")
    c_idx = order.index("C")
    d_idx = order.index("D")

    assert a_idx < b_idx
    assert b_idx < c_idx
    assert c_idx < d_idx


def test_reverse_topological_order(dag_graph):
    """Test reverse topological ordering."""
    order = reverse_topological_order(dag_graph)
    assert len(order) == 5

    a_idx = order.index("A")
    d_idx = order.index("D")

    assert d_idx < a_idx


def test_topological_order_with_cycle():
    """Test topological sort on graph with cycle."""
    graph = nx.DiGraph()
    graph.add_edge("A", "B")
    graph.add_edge("B", "C")
    graph.add_edge("C", "A")

    with pytest.raises((nx.NetworkXError, nx.NetworkXUnfeasible)):
        topological_order(graph)


def test_traverse_by_relationship(dag_graph):
    """Test traversal by relationship type."""
    visited = list(traverse_by_relationship(dag_graph, "B", "owner"))

    node_ids = [nid for nid, _ in visited]
    assert "B" in node_ids
    assert "C" in node_ids
    assert "D" in node_ids
    assert "E" not in node_ids


def test_get_dependency_levels(dag_graph):
    """Test computing dependency levels."""
    levels = get_dependency_levels(dag_graph)

    assert levels["A"] == 0
    assert levels["B"] == 1
    assert levels["C"] == 2
    assert levels["D"] == 3
    assert levels["E"] == 2


def test_get_dependency_levels_with_cycle():
    """Test dependency levels with cycles."""
    graph = nx.DiGraph()
    graph.add_node("A", kind="Pod", name="A", namespace="default")
    graph.add_node("B", kind="Pod", name="B", namespace="default")
    graph.add_node("C", kind="Pod", name="C", namespace="default")

    graph.add_edge("A", "B")
    graph.add_edge("B", "C")
    graph.add_edge("C", "A")

    levels = get_dependency_levels(graph)
    assert len(levels) == 3


def test_get_longest_path(dag_graph):
    """Test finding longest path."""
    path = get_longest_path(dag_graph)
    assert len(path) >= 4


def test_get_longest_path_with_cycle():
    """Test longest path on graph with cycle."""
    graph = nx.DiGraph()
    graph.add_edge("A", "B")
    graph.add_edge("B", "A")

    path = get_longest_path(graph)
    assert path == []


def test_get_shortest_paths_from_root(dag_graph):
    """Test shortest paths from root."""
    paths = get_shortest_paths_from_root(dag_graph, "A")

    assert "A" in paths
    assert "B" in paths
    assert "D" in paths
    assert len(paths["D"]) == 4
    assert paths["D"][0] == "A"
    assert paths["D"][-1] == "D"


def test_traverse_bfs_nonexistent_node(dag_graph):
    """Test BFS with non-existent start node."""
    visited = list(traverse_bfs(dag_graph, "NonExistent"))
    assert len(visited) == 0


def test_get_shortest_paths_nonexistent_root(dag_graph):
    """Test shortest paths with non-existent root."""
    paths = get_shortest_paths_from_root(dag_graph, "NonExistent")
    assert len(paths) == 0
