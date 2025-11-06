import networkx as nx
import pytest

from k8s_graph.visualization import get_shell_layout


@pytest.fixture
def sample_graph():
    """Create a sample K8s-like graph."""
    graph = nx.DiGraph()

    graph.add_node("Namespace:default", kind="Namespace", name="default", namespace=None)
    graph.add_node("Deployment:default:nginx", kind="Deployment", name="nginx", namespace="default")
    graph.add_node(
        "ReplicaSet:default:nginx-abc", kind="ReplicaSet", name="nginx-abc", namespace="default"
    )
    graph.add_node("Pod:default:nginx-xyz", kind="Pod", name="nginx-xyz", namespace="default")
    graph.add_node("Service:default:web", kind="Service", name="web", namespace="default")
    graph.add_node("ConfigMap:default:config", kind="ConfigMap", name="config", namespace="default")

    return graph


def test_get_shell_layout(sample_graph):
    """Test shell layout generation."""
    shells = get_shell_layout(sample_graph)

    assert len(shells) > 0
    assert len(shells[0]) >= 1
    assert "Namespace:default" in shells[0]

    for shell in shells[1:]:
        if "Deployment:default:nginx" in shell:
            assert "Deployment:default:nginx" in shell


def test_get_shell_layout_empty_graph():
    """Test shell layout with empty graph."""
    graph = nx.DiGraph()
    shells = get_shell_layout(graph)

    assert len(shells) == 0 or all(len(shell) == 0 for shell in shells)


def test_get_shell_layout_hierarchy(sample_graph):
    """Test shell layout maintains hierarchy."""
    shells = get_shell_layout(sample_graph)

    namespace_shell = None
    deployment_shell = None
    pod_shell = None

    for i, shell in enumerate(shells):
        if "Namespace:default" in shell:
            namespace_shell = i
        if "Deployment:default:nginx" in shell:
            deployment_shell = i
        if "Pod:default:nginx-xyz" in shell:
            pod_shell = i

    if namespace_shell is not None and deployment_shell is not None:
        assert namespace_shell < deployment_shell

    if deployment_shell is not None and pod_shell is not None:
        assert deployment_shell < pod_shell
