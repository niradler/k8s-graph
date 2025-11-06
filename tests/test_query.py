import networkx as nx
import pytest

from k8s_graph.query import (
    extract_subgraph,
    filter_nodes,
    find_all_paths,
    find_by_kind,
    find_by_label,
    find_by_namespace,
    find_dependencies,
    find_dependents,
    find_path,
    get_edge_data,
    get_neighbors,
    get_node_data,
    get_resource_cluster,
)


@pytest.fixture
def sample_graph():
    """Create a sample Kubernetes-like graph for testing."""
    graph = nx.DiGraph()

    graph.add_node(
        "Namespace:default",
        kind="Namespace",
        name="default",
        namespace=None,
    )

    graph.add_node(
        "Deployment:default:nginx",
        kind="Deployment",
        name="nginx",
        namespace="default",
        labels={"app": "nginx"},
    )

    graph.add_node(
        "ReplicaSet:default:nginx-abc",
        kind="ReplicaSet",
        name="nginx-abc",
        namespace="default",
        labels={"app": "nginx"},
    )

    graph.add_node(
        "Pod:default:nginx-abc-xyz",
        kind="Pod",
        name="nginx-abc-xyz",
        namespace="default",
        phase="Running",
        labels={"app": "nginx"},
    )

    graph.add_node(
        "Service:default:nginx",
        kind="Service",
        name="nginx",
        namespace="default",
        labels={"app": "nginx"},
    )

    graph.add_node(
        "ConfigMap:default:nginx-config",
        kind="ConfigMap",
        name="nginx-config",
        namespace="default",
    )

    graph.add_edge(
        "Deployment:default:nginx",
        "ReplicaSet:default:nginx-abc",
        relationship_type="owner",
    )

    graph.add_edge(
        "ReplicaSet:default:nginx-abc",
        "Pod:default:nginx-abc-xyz",
        relationship_type="owner",
    )

    graph.add_edge(
        "Service:default:nginx",
        "Pod:default:nginx-abc-xyz",
        relationship_type="label_selector",
    )

    graph.add_edge(
        "Pod:default:nginx-abc-xyz",
        "ConfigMap:default:nginx-config",
        relationship_type="volume",
    )

    return graph


def test_find_dependencies(sample_graph):
    """Test finding dependencies of a resource."""
    deps = find_dependencies(sample_graph, "Deployment:default:nginx")
    assert deps.number_of_nodes() == 4
    assert deps.has_node("Deployment:default:nginx")
    assert deps.has_node("ReplicaSet:default:nginx-abc")
    assert deps.has_node("Pod:default:nginx-abc-xyz")
    assert deps.has_node("ConfigMap:default:nginx-config")


def test_find_dependencies_with_max_depth(sample_graph):
    """Test finding dependencies with depth limit."""
    deps = find_dependencies(sample_graph, "Deployment:default:nginx", max_depth=1)
    assert deps.number_of_nodes() == 2
    assert deps.has_node("Deployment:default:nginx")
    assert deps.has_node("ReplicaSet:default:nginx-abc")


def test_find_dependents(sample_graph):
    """Test finding dependents of a resource."""
    dependents = find_dependents(sample_graph, "ConfigMap:default:nginx-config")
    assert dependents.number_of_nodes() >= 1
    assert dependents.has_node("Pod:default:nginx-abc-xyz")


def test_find_path(sample_graph):
    """Test finding shortest path between resources."""
    path = find_path(sample_graph, "Deployment:default:nginx", "ConfigMap:default:nginx-config")
    assert path is not None
    assert len(path) == 4
    assert path[0] == "Deployment:default:nginx"
    assert path[-1] == "ConfigMap:default:nginx-config"


def test_find_path_no_path():
    """Test finding path when none exists."""
    graph = nx.DiGraph()
    graph.add_node("Node1", kind="Pod", name="pod1", namespace="default")
    graph.add_node("Node2", kind="Pod", name="pod2", namespace="default")

    path = find_path(graph, "Node1", "Node2")
    assert path is None


def test_find_all_paths(sample_graph):
    """Test finding all paths between resources."""
    paths = find_all_paths(
        sample_graph, "Deployment:default:nginx", "ConfigMap:default:nginx-config"
    )
    assert len(paths) >= 1
    for path in paths:
        assert path[0] == "Deployment:default:nginx"
        assert path[-1] == "ConfigMap:default:nginx-config"


def test_get_neighbors(sample_graph):
    """Test getting N-hop neighborhood."""
    neighborhood = get_neighbors(sample_graph, "ReplicaSet:default:nginx-abc", hops=1)
    assert neighborhood.has_node("ReplicaSet:default:nginx-abc")
    assert neighborhood.has_node("Pod:default:nginx-abc-xyz")


def test_find_by_kind(sample_graph):
    """Test finding resources by kind."""
    pods = find_by_kind(sample_graph, "Pod")
    assert len(pods) == 1
    assert "Pod:default:nginx-abc-xyz" in pods

    deployments = find_by_kind(sample_graph, "Deployment")
    assert len(deployments) == 1


def test_find_by_namespace(sample_graph):
    """Test finding resources by namespace."""
    default_resources = find_by_namespace(sample_graph, "default")
    assert len(default_resources) == 5


def test_find_by_label(sample_graph):
    """Test finding resources by label."""
    nginx_resources = find_by_label(sample_graph, "app", "nginx")
    assert len(nginx_resources) == 4

    any_app = find_by_label(sample_graph, "app")
    assert len(any_app) == 4


def test_extract_subgraph(sample_graph):
    """Test extracting subgraph."""
    pods = find_by_kind(sample_graph, "Pod")
    services = find_by_kind(sample_graph, "Service")
    nodes = pods + services

    subgraph = extract_subgraph(sample_graph, nodes)
    assert subgraph.number_of_nodes() == 2
    assert subgraph.has_node("Pod:default:nginx-abc-xyz")
    assert subgraph.has_node("Service:default:nginx")


def test_get_resource_cluster(sample_graph):
    """Test getting connected component."""
    cluster = get_resource_cluster(sample_graph, "Deployment:default:nginx")
    assert cluster.number_of_nodes() == 5


def test_get_edge_data(sample_graph):
    """Test getting edge attributes."""
    edge_data = get_edge_data(
        sample_graph, "Deployment:default:nginx", "ReplicaSet:default:nginx-abc"
    )
    assert edge_data["relationship_type"] == "owner"


def test_get_node_data(sample_graph):
    """Test getting node attributes."""
    node_data = get_node_data(sample_graph, "Pod:default:nginx-abc-xyz")
    assert node_data["kind"] == "Pod"
    assert node_data["phase"] == "Running"


def test_filter_nodes(sample_graph):
    """Test filtering nodes with custom predicate."""
    running_pods = filter_nodes(
        sample_graph,
        lambda nid, attrs: attrs.get("kind") == "Pod" and attrs.get("phase") == "Running",
    )
    assert len(running_pods) == 1
    assert "Pod:default:nginx-abc-xyz" in running_pods


def test_find_dependencies_nonexistent_node(sample_graph):
    """Test finding dependencies of non-existent node."""
    deps = find_dependencies(sample_graph, "NonExistent:default:missing")
    assert deps.number_of_nodes() == 0


def test_find_path_nonexistent_nodes():
    """Test finding path with non-existent nodes."""
    graph = nx.DiGraph()
    graph.add_node("Node1", kind="Pod", name="pod1", namespace="default")

    path = find_path(graph, "Node1", "NonExistent")
    assert path is None

    path = find_path(graph, "NonExistent", "Node1")
    assert path is None
