"""Shared test fixtures for k8s-graph tests."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from k8s_graph.discoverers.registry import DiscovererRegistry
from k8s_graph.models import ResourceIdentifier


class MockK8sClient:
    """Mock K8s client with API statistics tracking for testing."""

    def __init__(self):
        self.resources = {}
        self._api_call_stats = {"get_resource": 0, "list_resources": 0, "total": 0}

    def add_resource(self, resource: dict[str, Any]) -> None:
        """Add a resource to the mock client."""
        kind = resource.get("kind")
        name = resource.get("metadata", {}).get("name")
        namespace = resource.get("metadata", {}).get("namespace")
        key = (kind, namespace, name)
        self.resources[key] = resource

    async def get_resource(self, resource_id: ResourceIdentifier) -> dict[str, Any] | None:
        """Get a resource by ID."""
        self._api_call_stats["get_resource"] += 1
        self._api_call_stats["total"] += 1

        key = (resource_id.kind, resource_id.namespace, resource_id.name)
        return self.resources.get(key)

    async def list_resources(
        self,
        kind: str,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """List resources of a kind."""
        self._api_call_stats["list_resources"] += 1
        self._api_call_stats["total"] += 1

        results = []
        for (res_kind, res_ns, _), resource in self.resources.items():
            if res_kind != kind:
                continue
            if namespace and res_ns != namespace:
                continue
            if label_selector:
                labels = resource.get("metadata", {}).get("labels", {})
                for selector_part in label_selector.split(","):
                    if "=" in selector_part:
                        key, value = selector_part.split("=", 1)
                        if labels.get(key) != value:
                            continue
            results.append(resource)

        return results, {}

    def get_api_call_stats(self) -> dict[str, int]:
        """Get API call statistics."""
        return self._api_call_stats.copy()

    def reset_api_call_stats(self) -> None:
        """Reset API call statistics."""
        self._api_call_stats = {"get_resource": 0, "list_resources": 0, "total": 0}


@pytest.fixture
def sample_pod() -> dict[str, Any]:
    """Sample Pod resource."""
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "nginx-deployment-abc123-xyz",
            "namespace": "default",
            "uid": "pod-123",
            "labels": {
                "app": "nginx",
                "pod-template-hash": "abc123",
            },
            "ownerReferences": [
                {
                    "kind": "ReplicaSet",
                    "name": "nginx-deployment-abc123",
                    "uid": "rs-123",
                }
            ],
        },
        "spec": {
            "containers": [
                {
                    "name": "nginx",
                    "image": "nginx:1.14.2",
                    "env": [
                        {
                            "name": "CONFIG_KEY",
                            "valueFrom": {"configMapKeyRef": {"name": "app-config", "key": "key1"}},
                        }
                    ],
                    "envFrom": [{"configMapRef": {"name": "app-config"}}],
                }
            ],
            "volumes": [
                {"name": "config-volume", "configMap": {"name": "app-config"}},
                {"name": "secret-volume", "secret": {"secretName": "app-secret"}},
            ],
            "serviceAccountName": "default",
        },
        "status": {"phase": "Running", "podIP": "10.0.0.1"},
    }


@pytest.fixture
def sample_deployment() -> dict[str, Any]:
    """Sample Deployment resource."""
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "nginx-deployment",
            "namespace": "default",
            "uid": "deployment-123",
            "labels": {"app": "nginx"},
        },
        "spec": {
            "replicas": 3,
            "selector": {"matchLabels": {"app": "nginx"}},
            "template": {
                "metadata": {"labels": {"app": "nginx"}},
                "spec": {
                    "containers": [{"name": "nginx", "image": "nginx:1.14.2"}],
                    "serviceAccountName": "default",
                },
            },
        },
        "status": {"replicas": 3, "readyReplicas": 3, "availableReplicas": 3},
    }


@pytest.fixture
def sample_service() -> dict[str, Any]:
    """Sample Service resource."""
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": "nginx-service",
            "namespace": "default",
            "uid": "service-123",
        },
        "spec": {
            "type": "ClusterIP",
            "clusterIP": "10.96.0.1",
            "selector": {"app": "nginx"},
            "ports": [{"port": 80, "targetPort": 80, "protocol": "TCP"}],
        },
    }


@pytest.fixture
def sample_replicaset() -> dict[str, Any]:
    """Sample ReplicaSet resource."""
    return {
        "apiVersion": "apps/v1",
        "kind": "ReplicaSet",
        "metadata": {
            "name": "nginx-deployment-abc123",
            "namespace": "default",
            "uid": "rs-123",
            "labels": {
                "app": "nginx",
                "pod-template-hash": "abc123",
            },
            "ownerReferences": [
                {
                    "kind": "Deployment",
                    "name": "nginx-deployment",
                    "uid": "deployment-123",
                }
            ],
        },
        "spec": {
            "replicas": 3,
            "selector": {"matchLabels": {"app": "nginx", "pod-template-hash": "abc123"}},
        },
        "status": {"replicas": 3, "readyReplicas": 3},
    }


@pytest.fixture
def sample_configmap() -> dict[str, Any]:
    """Sample ConfigMap resource."""
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": "app-config",
            "namespace": "default",
            "uid": "cm-123",
        },
        "data": {"key1": "value1", "key2": "value2"},
    }


@pytest.fixture
def sample_secret() -> dict[str, Any]:
    """Sample Secret resource."""
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": "app-secret",
            "namespace": "default",
            "uid": "secret-123",
        },
        "type": "Opaque",
        "data": {"username": "YWRtaW4=", "password": "cGFzc3dvcmQ="},
    }


@pytest.fixture
def sample_ingress() -> dict[str, Any]:
    """Sample Ingress resource."""
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": "nginx-ingress",
            "namespace": "default",
            "uid": "ingress-123",
        },
        "spec": {
            "rules": [
                {
                    "host": "example.com",
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {"name": "nginx-service", "port": {"number": 80}}
                                },
                            }
                        ]
                    },
                }
            ]
        },
    }


@pytest.fixture
def sample_network_policy() -> dict[str, Any]:
    """Sample NetworkPolicy resource."""
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": "nginx-network-policy",
            "namespace": "default",
            "uid": "netpol-123",
        },
        "spec": {
            "podSelector": {"matchLabels": {"app": "nginx"}},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [{"from": [{"podSelector": {"matchLabels": {"app": "frontend"}}}]}],
            "egress": [{"to": [{"podSelector": {"matchLabels": {"app": "backend"}}}]}],
        },
    }


@pytest.fixture
def mock_k8s_client(
    sample_pod,
    sample_deployment,
    sample_service,
    sample_replicaset,
    sample_configmap,
    sample_secret,
) -> AsyncMock:
    """Mock K8s client implementing K8sClientProtocol."""
    client = AsyncMock()

    resources_by_kind = {
        "Pod": [sample_pod],
        "Deployment": [sample_deployment],
        "Service": [sample_service],
        "ReplicaSet": [sample_replicaset],
        "ConfigMap": [sample_configmap],
        "Secret": [sample_secret],
    }

    async def mock_get_resource(resource_id: ResourceIdentifier) -> dict[str, Any] | None:
        for resource in resources_by_kind.get(resource_id.kind, []):
            metadata = resource.get("metadata", {})
            if (
                metadata.get("name") == resource_id.name
                and metadata.get("namespace") == resource_id.namespace
            ):
                return resource
        return None

    async def mock_list_resources(
        kind: str, namespace: str | None = None, label_selector: str | None = None
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        resources = resources_by_kind.get(kind, [])
        if namespace:
            resources = [
                r for r in resources if r.get("metadata", {}).get("namespace") == namespace
            ]
        return resources, {"resource_version": "12345"}

    client.get_resource.side_effect = mock_get_resource
    client.list_resources.side_effect = mock_list_resources

    return client


@pytest.fixture
def test_registry() -> DiscovererRegistry:
    """Fresh discoverer registry for testing."""
    registry = DiscovererRegistry()
    return registry
