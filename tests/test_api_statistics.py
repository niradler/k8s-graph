import pytest

from k8s_graph import BuildOptions, GraphBuilder
from k8s_graph.adapters import KubernetesAdapter
from k8s_graph.models import ResourceIdentifier
from tests.conftest import MockK8sClient


@pytest.mark.asyncio
async def test_api_call_statistics():
    """Test API call statistics tracking."""
    client = MockK8sClient()
    builder = GraphBuilder(client)

    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "nginx",
            "namespace": "default",
            "uid": "deployment-123",
            "labels": {"app": "nginx"},
        },
        "spec": {
            "replicas": 2,
            "selector": {"matchLabels": {"app": "nginx"}},
            "template": {
                "metadata": {"labels": {"app": "nginx", "pod-template-hash": "abc123"}},
                "spec": {"containers": [{"name": "nginx", "image": "nginx:latest"}]},
            },
        },
    }

    replicaset = {
        "apiVersion": "apps/v1",
        "kind": "ReplicaSet",
        "metadata": {
            "name": "nginx-abc123",
            "namespace": "default",
            "uid": "rs-123",
            "labels": {"app": "nginx", "pod-template-hash": "abc123"},
            "ownerReferences": [{"kind": "Deployment", "name": "nginx", "uid": "deployment-123"}],
        },
        "spec": {
            "replicas": 2,
            "selector": {"matchLabels": {"app": "nginx", "pod-template-hash": "abc123"}},
        },
    }

    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "nginx-abc123-xyz",
            "namespace": "default",
            "uid": "pod-123",
            "labels": {"app": "nginx", "pod-template-hash": "abc123"},
            "ownerReferences": [{"kind": "ReplicaSet", "name": "nginx-abc123", "uid": "rs-123"}],
        },
        "spec": {"containers": [{"name": "nginx", "image": "nginx:latest"}]},
    }

    client.add_resource(deployment)
    client.add_resource(replicaset)
    client.add_resource(pod)

    if hasattr(client, "reset_api_call_stats"):
        client.reset_api_call_stats()

    resource_id = ResourceIdentifier(kind="Deployment", name="nginx", namespace="default")
    await builder.build_from_resource(
        resource_id, depth=2, options=BuildOptions(include_rbac=False, max_nodes=100)
    )

    if hasattr(client, "get_api_call_stats"):
        stats = client.get_api_call_stats()

        assert "get_resource" in stats
        assert "list_resources" in stats
        assert "total" in stats

        assert stats["get_resource"] > 0
        assert stats["total"] > 0
        assert stats["total"] == stats["get_resource"] + stats["list_resources"]

        print(f"\nAPI Call Statistics:")
        print(f"  get_resource: {stats['get_resource']}")
        print(f"  list_resources: {stats['list_resources']}")
        print(f"  total: {stats['total']}")


@pytest.mark.asyncio
async def test_api_stats_reset():
    """Test resetting API call statistics."""
    client = MockK8sClient()

    if not hasattr(client, "get_api_call_stats"):
        pytest.skip("Client doesn't support API statistics")

    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "test", "namespace": "default", "uid": "test-123"},
        "spec": {"replicas": 1},
    }

    client.add_resource(deployment)

    resource_id = ResourceIdentifier(kind="Deployment", name="test", namespace="default")
    await client.get_resource(resource_id)

    stats_before = client.get_api_call_stats()
    assert stats_before["total"] > 0

    client.reset_api_call_stats()

    stats_after = client.get_api_call_stats()
    assert stats_after["get_resource"] == 0
    assert stats_after["list_resources"] == 0
    assert stats_after["total"] == 0


def test_kubernetes_adapter_api_stats():
    """Test that KubernetesAdapter has API statistics methods."""
    try:
        from kubernetes import client as k8s_client

        k8s_client.CoreV1Api()
    except Exception:
        pytest.skip("Kubernetes client not configured")

    adapter = KubernetesAdapter()

    assert hasattr(adapter, "get_api_call_stats")
    assert hasattr(adapter, "reset_api_call_stats")

    stats = adapter.get_api_call_stats()
    assert isinstance(stats, dict)
    assert "get_resource" in stats
    assert "list_resources" in stats
    assert "total" in stats
    assert all(isinstance(v, int) for v in stats.values())
