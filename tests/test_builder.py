"""Tests for k8s_graph.builder."""

import pytest

from k8s_graph.builder import GraphBuilder
from k8s_graph.models import BuildOptions, ResourceIdentifier


@pytest.mark.asyncio
async def test_builder_initialization(mock_k8s_client):
    """Test GraphBuilder initialization."""
    builder = GraphBuilder(mock_k8s_client)

    assert builder.client == mock_k8s_client
    assert builder.registry is not None
    assert builder.unified_discoverer is not None
    assert builder.node_identity is not None


@pytest.mark.asyncio
async def test_build_from_resource(mock_k8s_client, sample_deployment):
    """Test building graph from a resource."""
    builder = GraphBuilder(mock_k8s_client)

    resource_id = ResourceIdentifier(
        kind="Deployment", name="nginx-deployment", namespace="default"
    )

    graph = await builder.build_from_resource(
        resource_id, depth=1, options=BuildOptions(max_nodes=100)
    )

    assert graph.number_of_nodes() > 0
    assert graph.number_of_edges() >= 0


@pytest.mark.asyncio
async def test_build_from_missing_resource(mock_k8s_client):
    """Test building from non-existent resource."""
    builder = GraphBuilder(mock_k8s_client)

    resource_id = ResourceIdentifier(kind="Pod", name="nonexistent", namespace="default")

    graph = await builder.build_from_resource(resource_id, depth=1, options=BuildOptions())

    assert graph.number_of_nodes() == 0


@pytest.mark.asyncio
async def test_build_namespace_graph(mock_k8s_client):
    """Test building complete namespace graph."""
    builder = GraphBuilder(mock_k8s_client)

    graph = await builder.build_namespace_graph(
        namespace="default", depth=1, options=BuildOptions(max_nodes=100)
    )

    assert graph.number_of_nodes() > 0


@pytest.mark.asyncio
async def test_max_nodes_limit(mock_k8s_client):
    """Test that max_nodes limit is enforced."""
    builder = GraphBuilder(mock_k8s_client)

    graph = await builder.build_namespace_graph(
        namespace="default", depth=2, options=BuildOptions(max_nodes=10)
    )

    assert graph.number_of_nodes() <= 10
    assert graph.number_of_nodes() > 0


@pytest.mark.asyncio
async def test_pod_sampling(mock_k8s_client, sample_pod):
    """Test pod template sampling."""
    builder = GraphBuilder(mock_k8s_client)

    resource_id = ResourceIdentifier(
        kind="Pod", name="nginx-deployment-abc123-xyz", namespace="default"
    )

    await builder.build_from_resource(resource_id, depth=1, options=BuildOptions())

    sampling_info = builder.get_pod_sampling_info()
    assert "sampled_count" in sampling_info
    assert "total_count" in sampling_info


@pytest.mark.asyncio
async def test_get_discovery_stats(mock_k8s_client, sample_deployment):
    """Test getting discovery statistics."""
    builder = GraphBuilder(mock_k8s_client)

    resource_id = ResourceIdentifier(
        kind="Deployment", name="nginx-deployment", namespace="default"
    )

    await builder.build_from_resource(resource_id, depth=1, options=BuildOptions())

    stats = builder.get_discovery_stats()
    assert "discoveries" in stats
    assert "errors" in stats
    assert "total_relationships" in stats
