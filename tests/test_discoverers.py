"""Tests for discoverers."""

import pytest

from k8s_graph.discoverers.native import NativeResourceDiscoverer
from k8s_graph.discoverers.network import NetworkPolicyDiscoverer
from k8s_graph.discoverers.rbac import RBACDiscoverer
from k8s_graph.models import RelationshipType


@pytest.mark.asyncio
async def test_native_discoverer_supports():
    """Test that native discoverer supports all resources."""
    discoverer = NativeResourceDiscoverer()

    assert discoverer.supports({"kind": "Pod"}) is True
    assert discoverer.supports({"kind": "Service"}) is True
    assert discoverer.supports({"kind": "CustomResource"}) is True


@pytest.mark.asyncio
async def test_native_discover_owner_references(sample_pod):
    """Test discovering owner references (parent → child direction)."""
    discoverer = NativeResourceDiscoverer()
    relationships = await discoverer.discover(sample_pod)

    # After fix: edges go from parent to child (ReplicaSet → Pod)
    owner_rels = [r for r in relationships if r.relationship_type == RelationshipType.OWNED]
    assert len(owner_rels) == 1
    assert owner_rels[0].source.kind == "ReplicaSet"  # Parent is source
    assert owner_rels[0].source.name == "nginx-deployment-abc123"
    assert owner_rels[0].target.kind == "Pod"  # Child is target


@pytest.mark.asyncio
async def test_native_discover_service_selector(sample_service):
    """Test discovering service label selector."""
    discoverer = NativeResourceDiscoverer()
    relationships = await discoverer.discover(sample_service)

    selector_rels = [
        r for r in relationships if r.relationship_type == RelationshipType.LABEL_SELECTOR
    ]
    assert len(selector_rels) == 1
    assert selector_rels[0].target.kind == "Pod"


@pytest.mark.asyncio
async def test_native_discover_pod_volumes(sample_pod):
    """Test discovering pod volume mounts."""
    discoverer = NativeResourceDiscoverer()
    relationships = await discoverer.discover(sample_pod)

    volume_rels = [r for r in relationships if r.relationship_type == RelationshipType.VOLUME]
    assert len(volume_rels) == 2

    config_rels = [r for r in volume_rels if r.target.kind == "ConfigMap"]
    secret_rels = [r for r in volume_rels if r.target.kind == "Secret"]

    assert len(config_rels) == 1
    assert len(secret_rels) == 1


@pytest.mark.asyncio
async def test_native_discover_pod_env(sample_pod):
    """Test discovering pod environment references."""
    discoverer = NativeResourceDiscoverer()
    relationships = await discoverer.discover(sample_pod)

    env_rels = [
        r
        for r in relationships
        if r.relationship_type in (RelationshipType.ENV_FROM, RelationshipType.ENV_VAR)
    ]
    assert len(env_rels) >= 1


@pytest.mark.asyncio
async def test_native_discover_ingress(sample_ingress):
    """Test discovering ingress backends."""
    discoverer = NativeResourceDiscoverer()
    relationships = await discoverer.discover(sample_ingress)

    backend_rels = [
        r for r in relationships if r.relationship_type == RelationshipType.INGRESS_BACKEND
    ]
    assert len(backend_rels) == 1
    assert backend_rels[0].target.kind == "Service"
    assert backend_rels[0].target.name == "nginx-service"


@pytest.mark.asyncio
async def test_rbac_discoverer_supports():
    """Test that RBAC discoverer supports RBAC resources."""
    discoverer = RBACDiscoverer()

    assert discoverer.supports({"kind": "RoleBinding"}) is True
    assert discoverer.supports({"kind": "ClusterRoleBinding"}) is True
    assert discoverer.supports({"kind": "Pod"}) is False


@pytest.mark.asyncio
async def test_rbac_discover_role_binding():
    """Test discovering RoleBinding relationships."""
    discoverer = RBACDiscoverer()

    role_binding = {
        "kind": "RoleBinding",
        "metadata": {"name": "test-binding", "namespace": "default"},
        "roleRef": {"kind": "Role", "name": "test-role"},
        "subjects": [{"kind": "ServiceAccount", "name": "test-sa", "namespace": "default"}],
    }

    relationships = await discoverer.discover(role_binding)

    assert len(relationships) == 2

    role_rels = [r for r in relationships if r.target.kind == "Role"]
    sa_rels = [r for r in relationships if r.target.kind == "ServiceAccount"]

    assert len(role_rels) == 1
    assert len(sa_rels) == 1


@pytest.mark.asyncio
async def test_network_discoverer_supports():
    """Test that network discoverer supports NetworkPolicy."""
    discoverer = NetworkPolicyDiscoverer()

    assert discoverer.supports({"kind": "NetworkPolicy"}) is True
    assert discoverer.supports({"kind": "Pod"}) is False


@pytest.mark.asyncio
async def test_network_discover_policy(sample_network_policy):
    """Test discovering NetworkPolicy relationships."""
    discoverer = NetworkPolicyDiscoverer()
    relationships = await discoverer.discover(sample_network_policy)

    policy_rels = [
        r for r in relationships if r.relationship_type == RelationshipType.NETWORK_POLICY
    ]
    ingress_rels = [
        r for r in relationships if r.relationship_type == RelationshipType.NETWORK_POLICY_INGRESS
    ]
    egress_rels = [
        r for r in relationships if r.relationship_type == RelationshipType.NETWORK_POLICY_EGRESS
    ]

    assert len(policy_rels) >= 1
    assert len(ingress_rels) >= 1
    assert len(egress_rels) >= 1
