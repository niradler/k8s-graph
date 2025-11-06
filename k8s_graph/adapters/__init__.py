"""
Kubernetes client adapters.
"""

try:
    from k8s_graph.adapters.kubernetes import KubernetesAdapter

    __all__ = ["KubernetesAdapter"]
except ImportError:
    __all__ = []
