"""Tests for k8s_graph.discoverers.registry."""

from k8s_graph.discoverers.base import BaseDiscoverer
from k8s_graph.discoverers.registry import DiscovererRegistry


class MockDiscoverer(BaseDiscoverer):
    """Mock discoverer for testing."""

    def __init__(self, kind=None, test_priority=50):
        super().__init__()
        self._kind = kind
        self._priority = test_priority

    def supports(self, resource):
        if self._kind:
            return resource.get("kind") == self._kind
        return True

    async def discover(self, resource):
        return []

    @property
    def priority(self):
        return self._priority


def test_registry_registration(test_registry):
    """Test registering a discoverer."""
    discoverer = MockDiscoverer()
    test_registry.register(discoverer)

    resource = {"kind": "Pod"}
    discoverers = test_registry.get_discoverers_for_resource(resource)

    assert len(discoverers) == 1
    assert discoverers[0] == discoverer


def test_registry_priority_sorting(test_registry):
    """Test that discoverers are sorted by priority."""
    low_priority = MockDiscoverer(test_priority=10)
    high_priority = MockDiscoverer(test_priority=100)

    test_registry.register(low_priority)
    test_registry.register(high_priority)

    resource = {"kind": "Pod"}
    discoverers = test_registry.get_discoverers_for_resource(resource)

    assert len(discoverers) == 2
    assert discoverers[0] == high_priority
    assert discoverers[1] == low_priority


def test_registry_override(test_registry):
    """Test kind-specific overrides."""
    general = MockDiscoverer(kind="Pod")
    override = MockDiscoverer(kind="Pod", test_priority=100)

    test_registry.register(general)
    test_registry.register(override, resource_kind="Pod")

    resource = {"kind": "Pod"}
    discoverers = test_registry.get_discoverers_for_resource(resource)

    assert len(discoverers) == 1
    assert discoverers[0] == override


def test_registry_get_global():
    """Test global singleton registry."""
    registry1 = DiscovererRegistry.get_global()
    registry2 = DiscovererRegistry.get_global()

    assert registry1 is registry2


def test_registry_list_discoverers(test_registry):
    """Test listing registered discoverers."""
    discoverer1 = MockDiscoverer(test_priority=50)
    discoverer2 = MockDiscoverer(test_priority=100)

    test_registry.register(discoverer1)
    test_registry.register(discoverer2, resource_kind="Pod")

    info = test_registry.list_discoverers()

    assert len(info) == 2
    assert any(d["type"] == "general" for d in info)
    assert any(d["type"] == "override" and d["kind"] == "Pod" for d in info)


def test_registry_clear(test_registry):
    """Test clearing registry."""
    discoverer = MockDiscoverer()
    test_registry.register(discoverer)

    test_registry.clear()

    resource = {"kind": "Pod"}
    discoverers = test_registry.get_discoverers_for_resource(resource)

    assert len(discoverers) == 0
