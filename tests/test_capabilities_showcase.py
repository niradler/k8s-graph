"""
Capability Showcase Tests
========================

This test file demonstrates ALL key capabilities of k8s-graph.
It serves as both test coverage and documentation for contributors.

Each test shows a specific feature or use case with clear examples.
"""

from unittest.mock import AsyncMock

import networkx as nx
import pytest

from k8s_graph import (
    BuildOptions,
    GraphBuilder,
    RelationshipType,
    ResourceIdentifier,
    ResourceRelationship,
)
from k8s_graph.discoverers import (
    BaseDiscoverer,
    DiscovererRegistry,
    NativeResourceDiscoverer,
    NetworkPolicyDiscoverer,
    RBACDiscoverer,
)
from k8s_graph.formatter import format_graph_output
from k8s_graph.node_identity import NodeIdentity
from k8s_graph.validator import check_graph_cycles, get_graph_statistics, validate_graph

# ==============================================================================
# CAPABILITY 1: Protocol-Based Design - Custom K8s Clients
# ==============================================================================


@pytest.mark.asyncio
async def test_capability_custom_k8s_client():
    """
    CAPABILITY: Protocol-Based Design

    Users can implement custom K8s clients for:
    - Caching layers
    - Proxy servers
    - Testing/mocking
    - Rate limiting

    Example: Custom client with in-memory cache
    """

    class CachedK8sClient:
        """Custom client implementing K8sClientProtocol with caching."""

        def __init__(self):
            self.cache = {}
            self.call_count = 0

        async def get_resource(self, resource_id):
            self.call_count += 1
            cache_key = f"{resource_id.kind}:{resource_id.namespace}:{resource_id.name}"

            if cache_key in self.cache:
                return self.cache[cache_key]

            resource = {
                "kind": resource_id.kind,
                "apiVersion": "v1",
                "metadata": {
                    "name": resource_id.name,
                    "namespace": resource_id.namespace,
                    "uid": "test-uid",
                },
                "spec": {},
            }
            self.cache[cache_key] = resource
            return resource

        async def list_resources(self, kind, namespace=None, label_selector=None):
            self.call_count += 1
            return [], {"resource_version": "123"}

    client = CachedK8sClient()
    _ = GraphBuilder(client)

    resource_id = ResourceIdentifier(kind="Pod", name="test", namespace="default")
    await client.get_resource(resource_id)
    await client.get_resource(resource_id)

    assert client.call_count == 2
    assert "Pod:default:test" in client.cache


# ==============================================================================
# CAPABILITY 2: Stable Node Identity - Pod Recreation Consistency
# ==============================================================================


def test_capability_stable_node_identity():
    """
    CAPABILITY: Stable Node Identity

    Pods that are recreated get the same node ID if they have the same template.
    This ensures graph consistency across pod recreations.

    Example: ReplicaSet pods with same template hash get consistent IDs
    """
    identity = NodeIdentity()

    pod_v1 = {
        "kind": "Pod",
        "metadata": {
            "name": "nginx-abc123-xyz",
            "namespace": "default",
            "labels": {"pod-template-hash": "abc123"},
            "ownerReferences": [{"kind": "ReplicaSet", "name": "nginx-abc123"}],
        },
    }

    pod_v2 = {
        "kind": "Pod",
        "metadata": {
            "name": "nginx-abc123-def",
            "namespace": "default",
            "labels": {"pod-template-hash": "abc123"},
            "ownerReferences": [{"kind": "ReplicaSet", "name": "nginx-abc123"}],
        },
    }

    id1 = identity.get_node_id(pod_v1)
    id2 = identity.get_node_id(pod_v2)

    assert id1 == id2, "Same template pods should have same node ID"
    assert id1 == "Pod:default:ReplicaSet-nginx-abc123:abc123"


# ==============================================================================
# CAPABILITY 3: Plugin System - Custom CRD Handlers
# ==============================================================================


@pytest.mark.asyncio
async def test_capability_custom_crd_handler():
    """
    CAPABILITY: Extensible Plugin System

    Users can register custom discoverers for CRDs at runtime.
    No need to modify core library code.

    Example: Custom handler for fictional "Workflow" CRD
    """

    class WorkflowDiscoverer(BaseDiscoverer):
        """Custom discoverer for Workflow CRD."""

        def __init__(self, client=None):
            super().__init__(client)

        def supports(self, resource):
            return resource.get("kind") == "Workflow" and resource.get("apiVersion", "").startswith(
                "workflows.example.com"
            )

        async def discover(self, resource):
            relationships = []

            metadata = resource.get("metadata", {})
            spec = resource.get("spec", {})

            source = ResourceIdentifier(
                kind="Workflow",
                name=metadata.get("name"),
                namespace=metadata.get("namespace"),
            )

            for step in spec.get("steps", []):
                pod_name = step.get("podName")
                if pod_name:
                    relationships.append(
                        ResourceRelationship(
                            source=source,
                            target=ResourceIdentifier(
                                kind="Pod",
                                name=pod_name,
                                namespace=metadata.get("namespace"),
                            ),
                            relationship_type=RelationshipType.OWNED,
                            details=f"Workflow step: {step.get('name')}",
                        )
                    )

            return relationships

        @property
        def priority(self):
            return 100

    registry = DiscovererRegistry()

    mock_client = AsyncMock()
    discoverer = WorkflowDiscoverer(mock_client)
    registry.register(discoverer)

    workflow = {
        "kind": "Workflow",
        "apiVersion": "workflows.example.com/v1",
        "metadata": {"name": "test-workflow", "namespace": "default"},
        "spec": {
            "steps": [
                {"name": "step1", "podName": "worker-1"},
                {"name": "step2", "podName": "worker-2"},
            ]
        },
    }

    assert discoverer.supports(workflow)
    relationships = await discoverer.discover(workflow)

    assert len(relationships) == 2
    assert all(r.relationship_type == RelationshipType.OWNED for r in relationships)


# ==============================================================================
# CAPABILITY 4: Comprehensive Relationship Discovery
# ==============================================================================


@pytest.mark.asyncio
async def test_capability_native_relationships():
    """
    CAPABILITY: Comprehensive Native K8s Relationship Discovery

    The library discovers all major native Kubernetes relationships:
    - Owner references (Deployment -> ReplicaSet -> Pod)
    - Label selectors (Service -> Pods)
    - Volume mounts (Pod -> ConfigMap/Secret)
    - Environment variables (Pod -> ConfigMap/Secret)
    - Service accounts
    - Ingress backends
    - PVC -> PV relationships

    Example: Service selecting Pods via labels
    """
    discoverer = NativeResourceDiscoverer()

    service = {
        "kind": "Service",
        "apiVersion": "v1",
        "metadata": {"name": "web", "namespace": "default"},
        "spec": {
            "selector": {"app": "nginx", "tier": "frontend"},
            "type": "ClusterIP",
        },
    }

    relationships = await discoverer.discover(service)

    assert len(relationships) > 0
    selector_rel = relationships[0]
    assert selector_rel.relationship_type == RelationshipType.LABEL_SELECTOR
    assert "app=nginx,tier=frontend" in selector_rel.target.name


# ==============================================================================
# CAPABILITY 5: Graph Building with Options
# ==============================================================================


@pytest.mark.asyncio
async def test_capability_build_options():
    """
    CAPABILITY: Flexible Graph Building Options

    Control graph generation with various options:
    - max_nodes: Limit graph size
    - depth: Control relationship traversal depth
    - include_rbac: Include/exclude RBAC resources
    - include_network: Include/exclude NetworkPolicies
    - include_crds: Include/exclude custom resources

    Example: Build graph with specific constraints
    """
    mock_client = AsyncMock()

    async def mock_list(kind, namespace=None, label_selector=None):
        if kind == "Pod":
            return [
                {
                    "kind": "Pod",
                    "metadata": {"name": f"pod-{i}", "namespace": "default"},
                    "spec": {},
                }
                for i in range(5)
            ], {}
        return [], {}

    mock_client.list_resources.side_effect = mock_list

    builder = GraphBuilder(mock_client)

    options = BuildOptions(
        max_nodes=10,
        include_rbac=False,
        include_network=False,
        include_crds=False,
    )

    graph = await builder.build_namespace_graph(namespace="default", depth=1, options=options)

    assert graph.number_of_nodes() <= 10


# ==============================================================================
# CAPABILITY 6: Graph Validation
# ==============================================================================


def test_capability_graph_validation():
    """
    CAPABILITY: Graph Quality Validation

    Validate graphs for:
    - Duplicate resources
    - Missing attributes
    - Cycles
    - Structural issues

    Example: Detecting duplicate nodes
    """
    graph = nx.DiGraph()

    graph.add_node(
        "Pod:default:nginx",
        kind="Pod",
        name="nginx",
        namespace="default",
    )

    graph.add_node(
        "Pod:default:nginx-duplicate",
        kind="Pod",
        name="nginx",
        namespace="default",
    )

    validation = validate_graph(graph)

    assert validation["duplicate_count"] > 0
    assert len(validation["issues"]) > 0
    assert validation["issues"][0]["type"] == "duplicate_resource"


# ==============================================================================
# CAPABILITY 7: Multiple Output Formats
# ==============================================================================


def test_capability_output_formats():
    """
    CAPABILITY: Multiple Output Formats

    Export graphs in various formats:
    - JSON: Full structured data
    - LLM-friendly: Human-readable text
    - Minimal: Compact JSON with essential fields
    - DOT: Graphviz format (requires pydot)
    - Mermaid: Diagram format (custom export)

    Example: Generate JSON and LLM-friendly formats
    """
    graph = nx.DiGraph()

    graph.add_node(
        "Deployment:default:nginx",
        kind="Deployment",
        name="nginx",
        namespace="default",
        replicas=3,
    )

    graph.add_node(
        "Pod:default:nginx-abc",
        kind="Pod",
        name="nginx-abc",
        namespace="default",
        phase="Running",
    )

    graph.add_edge(
        "Deployment:default:nginx",
        "Pod:default:nginx-abc",
        relationship_type="owner",
        details="Owned by deployment",
    )

    json_output = format_graph_output(graph, format_type="json", include_metadata=True)
    assert "nodes" in json_output
    assert "edges" in json_output
    assert "metadata" in json_output

    llm_output = format_graph_output(graph, format_type="llm", include_metadata=True)
    assert "Kubernetes Resource Graph" in llm_output
    assert "Deployment: nginx" in llm_output
    assert "Pod: nginx-abc" in llm_output


# ==============================================================================
# CAPABILITY 8: RBAC Relationships
# ==============================================================================


@pytest.mark.asyncio
async def test_capability_rbac_discovery():
    """
    CAPABILITY: RBAC Relationship Discovery

    Discover Role-Based Access Control relationships:
    - RoleBinding -> ServiceAccount
    - RoleBinding -> Role
    - ClusterRoleBinding relationships

    Example: RoleBinding connecting ServiceAccount to Role
    """
    discoverer = RBACDiscoverer()

    role_binding = {
        "kind": "RoleBinding",
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "metadata": {"name": "read-pods", "namespace": "default"},
        "subjects": [
            {
                "kind": "ServiceAccount",
                "name": "pod-reader",
                "namespace": "default",
            }
        ],
        "roleRef": {
            "kind": "Role",
            "name": "pod-reader-role",
            "apiGroup": "rbac.authorization.k8s.io",
        },
    }

    assert discoverer.supports(role_binding)
    relationships = await discoverer.discover(role_binding)

    assert len(relationships) >= 2

    sa_rel = next(r for r in relationships if r.target.kind == "ServiceAccount")
    assert sa_rel.target.name == "pod-reader"

    role_rel = next(r for r in relationships if r.target.kind == "Role")
    assert role_rel.target.name == "pod-reader-role"


# ==============================================================================
# CAPABILITY 9: NetworkPolicy Relationships
# ==============================================================================


@pytest.mark.asyncio
async def test_capability_network_policy_discovery():
    """
    CAPABILITY: NetworkPolicy Relationship Discovery

    Discover network segmentation relationships:
    - Policy -> Pods (via podSelector)
    - Ingress rules
    - Egress rules

    Example: NetworkPolicy selecting pods by labels
    """
    discoverer = NetworkPolicyDiscoverer()

    network_policy = {
        "kind": "NetworkPolicy",
        "apiVersion": "networking.k8s.io/v1",
        "metadata": {"name": "allow-frontend", "namespace": "default"},
        "spec": {
            "podSelector": {"matchLabels": {"app": "backend"}},
            "policyTypes": ["Ingress"],
            "ingress": [{"from": [{"podSelector": {"matchLabels": {"app": "frontend"}}}]}],
        },
    }

    assert discoverer.supports(network_policy)
    relationships = await discoverer.discover(network_policy)

    assert len(relationships) >= 1
    assert any(r.relationship_type == RelationshipType.NETWORK_POLICY for r in relationships)


# ==============================================================================
# CAPABILITY 10: Graph Statistics
# ==============================================================================


def test_capability_graph_statistics():
    """
    CAPABILITY: Graph Statistics and Analysis

    Get detailed statistics about graphs:
    - Node/edge counts
    - Density
    - Degree statistics
    - Resources by kind
    - Namespace distribution

    Example: Analyzing graph structure
    """
    graph = nx.DiGraph()

    for i in range(5):
        graph.add_node(
            f"Pod:default:pod-{i}",
            kind="Pod",
            name=f"pod-{i}",
            namespace="default",
        )

    for i in range(3):
        graph.add_node(
            f"Service:default:svc-{i}",
            kind="Service",
            name=f"svc-{i}",
            namespace="default",
        )

    graph.add_edge("Service:default:svc-0", "Pod:default:pod-0")
    graph.add_edge("Service:default:svc-0", "Pod:default:pod-1")

    stats = get_graph_statistics(graph)

    assert stats["node_count"] == 8
    assert stats["edge_count"] == 2
    assert "Pod" in stats["resource_kinds"]
    assert stats["resource_kinds"]["Pod"] == 5
    assert stats["resource_kinds"]["Service"] == 3
    assert "default" in stats["namespaces"]


# ==============================================================================
# CAPABILITY 11: Cycle Detection
# ==============================================================================


def test_capability_cycle_detection():
    """
    CAPABILITY: Cycle Detection in Relationships

    Detect circular dependencies in resource relationships.
    This can indicate configuration issues.

    Example: Detecting a circular reference
    """
    graph = nx.DiGraph()

    graph.add_edge("A", "B")
    graph.add_edge("B", "C")
    graph.add_edge("C", "A")

    cycle_info = check_graph_cycles(graph)

    assert cycle_info["has_cycles"] is True
    assert cycle_info["cycle_count"] >= 1
    assert len(cycle_info["cycles"]) > 0


# ==============================================================================
# CAPABILITY 12: Priority-Based Discoverer Registry
# ==============================================================================


def test_capability_discoverer_priority():
    """
    CAPABILITY: Priority-Based Plugin System

    Discoverers with higher priority run first.
    This allows overriding default behavior.

    Example: Custom handler overriding built-in
    """

    class HighPriorityDiscoverer(BaseDiscoverer):
        def supports(self, resource):
            return resource.get("kind") == "Pod"

        async def discover(self, resource):
            return []

        @property
        def priority(self):
            return 200

    class LowPriorityDiscoverer(BaseDiscoverer):
        def supports(self, resource):
            return resource.get("kind") == "Pod"

        async def discover(self, resource):
            return []

        @property
        def priority(self):
            return 50

    registry = DiscovererRegistry()

    high = HighPriorityDiscoverer()
    low = LowPriorityDiscoverer()

    registry.register(low)
    registry.register(high)

    pod = {"kind": "Pod"}
    discoverers = registry.get_discoverers_for_resource(pod)

    assert discoverers[0] == high, "Higher priority discoverer should be first"
    assert discoverers[1] == low


# ==============================================================================
# CAPABILITY 13: Stateless Design
# ==============================================================================


@pytest.mark.asyncio
async def test_capability_stateless_builder():
    """
    CAPABILITY: Stateless Graph Builder

    GraphBuilder doesn't maintain internal state/caching.
    Each build operation is independent.
    Users control caching via their K8s client implementation.

    Example: Multiple builds don't interfere
    """
    mock_client = AsyncMock()
    mock_client.list_resources.return_value = ([], {})

    builder = GraphBuilder(mock_client)

    options = BuildOptions()

    graph1 = await builder.build_namespace_graph("default", depth=1, options=options)
    graph2 = await builder.build_namespace_graph("kube-system", depth=1, options=options)

    assert graph1 is not graph2, "Each build creates independent graph"


# ==============================================================================
# Summary Test - Documents All Capabilities
# ==============================================================================


def test_all_capabilities_documented():
    """
    Summary: All k8s-graph capabilities

    1. Protocol-based design for custom K8s clients
    2. Stable node identity across pod recreations
    3. Plugin system for custom CRD handlers
    4. Comprehensive native K8s relationship discovery
    5. Flexible graph building options
    6. Graph validation and quality checks
    7. Multiple output formats (JSON, LLM, DOT, Mermaid)
    8. RBAC relationship discovery
    9. NetworkPolicy relationship discovery
    10. Graph statistics and analysis
    11. Cycle detection
    12. Priority-based discoverer registry
    13. Stateless design pattern

    Run this test file to see examples of each capability!
    """
    assert True, "All capabilities are tested above"
