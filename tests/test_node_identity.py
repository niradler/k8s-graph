"""Tests for k8s_graph.node_identity."""

from k8s_graph.node_identity import NodeIdentity


def test_node_identity_standard_resource(sample_deployment):
    """Test node ID for standard resources."""
    identity = NodeIdentity()
    node_id = identity.get_node_id(sample_deployment)
    assert node_id == "Deployment:default:nginx-deployment"


def test_node_identity_pod_with_template_hash(sample_pod):
    """Test stable node ID for pod with template hash."""
    identity = NodeIdentity()
    node_id = identity.get_node_id(sample_pod)
    assert node_id == "Pod:default:ReplicaSet-nginx-deployment-abc123:abc123"


def test_node_identity_replicaset_with_template_hash(sample_replicaset):
    """Test stable node ID for ReplicaSet."""
    identity = NodeIdentity()
    node_id = identity.get_node_id(sample_replicaset)
    assert node_id == "ReplicaSet:default:nginx-deployment:abc123"


def test_node_identity_cluster_scoped():
    """Test node ID for cluster-scoped resources."""
    identity = NodeIdentity()
    node = {"kind": "Node", "metadata": {"name": "node-1"}}
    node_id = identity.get_node_id(node)
    assert node_id == "Node:cluster:node-1"


def test_extract_node_attributes(sample_pod):
    """Test extracting node attributes."""
    identity = NodeIdentity()
    attrs = identity.extract_node_attributes(sample_pod)

    assert attrs["kind"] == "Pod"
    assert attrs["name"] == "nginx-deployment-abc123-xyz"
    assert attrs["namespace"] == "default"
    assert attrs["phase"] == "Running"
    assert attrs["pod_ip"] == "10.0.0.1"
    assert "labels" in attrs


def test_get_pod_template_id(sample_pod):
    """Test getting pod template ID."""
    identity = NodeIdentity()
    template_id = identity.get_pod_template_id(sample_pod)
    assert template_id == "default:ReplicaSet:nginx-deployment-abc123:abc123"


def test_get_pod_template_id_non_pod(sample_deployment):
    """Test that non-pods return None for template ID."""
    identity = NodeIdentity()
    template_id = identity.get_pod_template_id(sample_deployment)
    assert template_id is None
