"""
Integration tests with realistic Kubernetes API data structures.
These tests use data structures that match actual kubernetes-python responses,
including None values and edge cases that the simple mocks don't catch.
"""

from unittest.mock import AsyncMock

import pytest

from k8s_graph import BuildOptions, GraphBuilder
from k8s_graph.discoverers.native import NativeResourceDiscoverer


@pytest.fixture
def realistic_pod_with_null_volumes():
    """Pod with None values in volume fields - common in real K8s API responses."""
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "test-pod",
            "namespace": "default",
            "uid": "test-uid",
            "labels": {"app": "test"},
        },
        "spec": {
            "containers": [
                {
                    "name": "main",
                    "image": "nginx",
                    "env": None,
                }
            ],
            "volumes": [
                {
                    "name": "empty-vol",
                    "emptyDir": {},
                },
                {
                    "name": "secret-vol",
                    "secret": None,
                },
                {
                    "name": "cm-vol",
                    "configMap": None,
                },
            ],
            "serviceAccountName": "default",
        },
        "status": {"phase": "Running"},
    }


@pytest.fixture
def realistic_network_policy_with_nulls():
    """NetworkPolicy with None ingress/egress - common in real responses."""
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": "test-policy",
            "namespace": "default",
        },
        "spec": {
            "podSelector": {"matchLabels": {"app": "test"}},
            "policyTypes": ["Ingress"],
            "ingress": None,
            "egress": [],
        },
    }


@pytest.fixture
def kubernetes_api_list_response():
    """Simulates a real kubernetes-python list response."""

    class MockItem:
        def to_dict(self):
            return {
                "metadata": {"name": "test-item", "namespace": "default"},
                "spec": {},
                "status": {},
            }

    class MockMetadata:
        resource_version = "12345"
        _continue = None

    class MockListResponse:
        items = [MockItem(), MockItem()]
        metadata = MockMetadata()

    return MockListResponse()


@pytest.mark.asyncio
async def test_native_discoverer_handles_null_volumes(realistic_pod_with_null_volumes):
    """Test that discoverer handles None values in volume definitions."""
    discoverer = NativeResourceDiscoverer()

    try:
        relationships = await discoverer.discover(realistic_pod_with_null_volumes)
        assert isinstance(relationships, list)
    except AttributeError as e:
        pytest.fail(f"Discoverer should handle None volume fields: {e}")
    except TypeError as e:
        pytest.fail(f"Discoverer should handle None iterable fields: {e}")


@pytest.mark.asyncio
async def test_native_discoverer_handles_null_env(realistic_pod_with_null_volumes):
    """Test that discoverer handles None values in container env."""

    discoverer = NativeResourceDiscoverer()

    try:
        relationships = await discoverer.discover(realistic_pod_with_null_volumes)
        assert isinstance(relationships, list)
    except TypeError as e:
        pytest.fail(f"Discoverer should handle None env field: {e}")


@pytest.mark.asyncio
async def test_network_policy_discoverer_handles_null_rules(realistic_network_policy_with_nulls):
    """Test that NetworkPolicyDiscoverer handles None ingress/egress rules."""
    from k8s_graph.discoverers.network import NetworkPolicyDiscoverer

    discoverer = NetworkPolicyDiscoverer()

    try:
        relationships = await discoverer.discover(realistic_network_policy_with_nulls)
        assert isinstance(relationships, list)
    except TypeError as e:
        pytest.fail(f"NetworkPolicyDiscoverer should handle None ingress/egress: {e}")


@pytest.mark.asyncio
async def test_graph_builder_extracts_attributes_correctly():
    """Test that graph builder correctly extracts and stores node attributes."""
    mock_client = AsyncMock()

    pod_with_kind = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "test-pod",
            "namespace": "default",
            "uid": "test-uid",
        },
        "spec": {},
        "status": {"phase": "Running"},
    }

    async def mock_list(*args, **kwargs):
        return [pod_with_kind], {"resource_version": "123"}

    mock_client.list_resources.side_effect = mock_list
    mock_client.get_resource.return_value = pod_with_kind

    builder = GraphBuilder(mock_client)
    graph = await builder.build_namespace_graph(
        namespace="default", depth=1, options=BuildOptions()
    )

    assert graph.number_of_nodes() > 0

    for node_id, attrs in graph.nodes(data=True):
        assert attrs.get("kind") is not None, f"Node {node_id} missing 'kind' attribute"
        assert attrs.get("kind") != "Unknown", f"Node {node_id} has 'Unknown' kind"
        assert attrs.get("name") is not None, f"Node {node_id} missing 'name' attribute"


@pytest.mark.asyncio
async def test_discoverer_with_missing_spec_fields():
    """Test discoverers handle resources with missing spec fields."""
    minimal_pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "minimal", "namespace": "default"},
        "spec": {},
        "status": {},
    }

    discoverer = NativeResourceDiscoverer()

    try:
        relationships = await discoverer.discover(minimal_pod)
        assert isinstance(relationships, list)
    except KeyError as e:
        pytest.fail(f"Discoverer should handle missing spec fields: {e}")
    except AttributeError as e:
        pytest.fail(f"Discoverer should handle missing attributes: {e}")


@pytest.mark.asyncio
async def test_discoverer_with_empty_lists():
    """Test discoverers handle resources with empty lists."""
    pod_with_empties = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "empty", "namespace": "default"},
        "spec": {
            "containers": [],
            "volumes": [],
            "initContainers": [],
        },
        "status": {},
    }

    discoverer = NativeResourceDiscoverer()

    try:
        relationships = await discoverer.discover(pod_with_empties)
        assert isinstance(relationships, list)
        assert len(relationships) == 0
    except (IndexError, KeyError) as e:
        pytest.fail(f"Discoverer should handle empty lists gracefully: {e}")


def test_realistic_data_structures():
    """Test that our test fixtures match real Kubernetes API structures."""

    from kubernetes import client

    api_pod = client.V1Pod(
        metadata=client.V1ObjectMeta(name="test", namespace="default"),
        spec=client.V1PodSpec(
            containers=[
                client.V1Container(
                    name="main",
                    image="nginx",
                    env=None,
                    volume_mounts=None,
                )
            ]
        ),
    )

    pod_dict = api_pod.to_dict()

    assert (
        pod_dict.get("kind") is None or pod_dict.get("kind") == "Pod"
    ), "kubernetes-python to_dict() includes 'kind' but it may be None"
    assert (
        pod_dict["spec"]["containers"][0]["env"] is None
    ), "Real API can have None for optional fields"
