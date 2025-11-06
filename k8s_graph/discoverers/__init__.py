"""
Discoverers for Kubernetes resource relationships.
"""

from k8s_graph.discoverers.base import BaseDiscoverer
from k8s_graph.discoverers.native import NativeResourceDiscoverer
from k8s_graph.discoverers.network import NetworkPolicyDiscoverer
from k8s_graph.discoverers.rbac import RBACDiscoverer
from k8s_graph.discoverers.registry import DiscovererRegistry
from k8s_graph.discoverers.unified import UnifiedDiscoverer

__all__ = [
    "BaseDiscoverer",
    "DiscovererRegistry",
    "UnifiedDiscoverer",
    "NativeResourceDiscoverer",
    "RBACDiscoverer",
    "NetworkPolicyDiscoverer",
]
