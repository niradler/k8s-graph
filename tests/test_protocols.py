"""Tests for k8s_graph.protocols."""

from k8s_graph.discoverers.native import NativeResourceDiscoverer
from k8s_graph.protocols import DiscovererProtocol, K8sClientProtocol


def test_k8s_client_protocol_check(mock_k8s_client):
    """Test that mock client implements K8sClientProtocol."""
    assert isinstance(mock_k8s_client, K8sClientProtocol)


def test_discoverer_protocol_check():
    """Test that discoverers implement DiscovererProtocol."""
    discoverer = NativeResourceDiscoverer()
    assert isinstance(discoverer, DiscovererProtocol)
    assert hasattr(discoverer, "supports")
    assert hasattr(discoverer, "discover")
    assert hasattr(discoverer, "priority")
