# k8s-graph: Agent Guide for Code Generation

## Project Overview

**k8s-graph** is a flexible, protocol-based Python library for building NetworkX graphs from Kubernetes resources. It provides intelligent relationship discovery, stable node identity, and an extensible plugin system for custom resource types.

### Core Value Proposition
- **Protocol-Based Design**: Easy to integrate with any K8s client (proxy, caching, custom logic)
- **Strong Defaults**: Works out-of-the-box with kubernetes-python
- **Extensible Plugin System**: Runtime registration of custom CRD handlers
- **Stable Node Identity**: Handles pod recreation with consistent node IDs
- **No Built-in Caching**: Stateless library - users control caching strategy
- **Production Ready**: Comprehensive tests, type hints, validation

## Architecture

```
k8s-graph/
├── k8s_graph/
│   ├── __init__.py                    # Public API exports
│   ├── protocols.py                   # K8sClientProtocol, DiscovererProtocol
│   ├── models.py                      # Pydantic models (ResourceIdentifier, RelationshipType, etc.)
│   ├── builder.py                     # GraphBuilder (main orchestration)
│   ├── node_identity.py               # Stable node ID generation
│   ├── validator.py                   # Graph validation (duplicate detection, etc.)
│   ├── formatter.py                   # Output formatting (LLM-friendly, JSON, etc.)
│   ├── discoverers/
│   │   ├── __init__.py                # Public exports
│   │   ├── base.py                    # BaseDiscoverer protocol
│   │   ├── registry.py                # DiscovererRegistry for runtime plugins
│   │   ├── unified.py                 # UnifiedDiscoverer orchestrator
│   │   ├── native.py                  # Core K8s resource discoverer
│   │   ├── rbac.py                    # RBAC relationship discoverer
│   │   ├── network.py                 # NetworkPolicy discoverer
│   │   └── handlers/                  # CRD handlers (plugin system)
│   │       ├── __init__.py
│   │       ├── base.py                # BaseCRDHandler
│   │       ├── argocd.py              # ArgoCD handler
│   │       ├── argo_workflows.py      # Argo Workflows handler
│   │       ├── helm.py                # Helm handler
│   │       ├── airflow.py             # Apache Airflow handler
│   │       └── ...                    # 13+ handlers
│   └── adapters/
│       ├── __init__.py
│       └── kubernetes.py              # Default kubernetes-python adapter
├── tests/                             # Comprehensive test suite
├── examples/                          # Usage examples
├── pyproject.toml
├── Makefile
├── README.md
└── LICENSE
```

## Key Modules

### 1. `protocols.py` - Protocol Definitions
**Purpose**: Define interfaces for extension points  
**Key Protocols**:

#### K8sClientProtocol
Defines interface for Kubernetes API interactions. Users implement this to:
- Add caching layer
- Use proxy to reduce cluster load
- Mock for testing
- Add rate limiting, retries, etc.

```python
from typing import Protocol, Optional, Dict, Any, List, Tuple

class K8sClientProtocol(Protocol):
    """Protocol for Kubernetes client implementations."""
    
    async def get_resource(
        self,
        resource_id: ResourceIdentifier
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single resource by identifier.
        
        Returns:
            Resource dict or None if not found
        """
        ...
    
    async def list_resources(
        self,
        kind: str,
        namespace: Optional[str] = None,
        label_selector: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        List resources of a kind.
        
        Returns:
            (list of resources, metadata dict)
        """
        ...
```

**Pattern**: Users can implement any client that matches this protocol

```python
class ProxiedK8sClient:
    """Example: K8s client with proxy caching."""
    
    def __init__(self, proxy_url: str):
        self.proxy_url = proxy_url
        self.cache = {}
    
    async def get_resource(
        self, resource_id: ResourceIdentifier
    ) -> Optional[Dict[str, Any]]:
        # Check local cache
        cache_key = f"{resource_id.kind}:{resource_id.namespace}:{resource_id.name}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Fetch from proxy instead of K8s API directly
        async with aiohttp.ClientSession() as session:
            url = f"{self.proxy_url}/api/v1/resources/{resource_id.kind}/{resource_id.name}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    resource = await resp.json()
                    self.cache[cache_key] = resource
                    return resource
                return None
    
    async def list_resources(
        self, kind: str, namespace: Optional[str] = None, 
        label_selector: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        # Proxy implementation
        ...

# Use with k8s-graph
builder = GraphBuilder(client=ProxiedK8sClient("https://k8s-proxy.example.com"))
```

#### DiscovererProtocol
Defines interface for relationship discoverers (CRD handlers).

```python
class DiscovererProtocol(Protocol):
    """Protocol for relationship discoverers."""
    
    async def discover(
        self, resource: Dict[str, Any]
    ) -> List[ResourceRelationship]:
        """
        Discover relationships for a resource.
        
        Returns:
            List of discovered relationships
        """
        ...
    
    def supports(self, resource: Dict[str, Any]) -> bool:
        """
        Check if this discoverer supports the resource.
        
        Returns:
            True if discoverer can handle this resource type
        """
        ...
    
    @property
    def priority(self) -> int:
        """
        Priority for this discoverer (higher = runs first).
        User handlers default to priority 100.
        Built-in handlers have priority 50.
        """
        ...
```

### 2. `models.py` - Core Data Models
**Purpose**: Type-safe data structures using Pydantic  
**Key Models**:

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class ResourceIdentifier(BaseModel):
    """Unique identifier for a K8s resource."""
    kind: str
    name: str
    namespace: Optional[str] = None
    api_version: Optional[str] = None
    
    class Config:
        frozen = True  # Immutable

class RelationshipType(str, Enum):
    """Types of relationships between resources."""
    OWNER = "owner"                    # Parent resource
    OWNED = "owned"                    # Child resource
    LABEL_SELECTOR = "label_selector"  # Service -> Pods
    VOLUME = "volume"                  # Pod -> ConfigMap/Secret
    ENV_FROM = "env_from"              # Pod -> ConfigMap/Secret
    SERVICE_ACCOUNT = "service_account"
    NETWORK_POLICY = "network_policy"
    INGRESS_BACKEND = "ingress_backend"
    # ... more types

class ResourceRelationship(BaseModel):
    """A relationship between two resources."""
    source: ResourceIdentifier
    target: ResourceIdentifier
    relationship_type: RelationshipType
    details: Optional[str] = None

class BuildOptions(BaseModel):
    """Options for building a graph."""
    include_rbac: bool = True
    include_network: bool = True
    include_crds: bool = True
    max_nodes: int = 500
    cluster_id: Optional[str] = None

class DiscoveryOptions(BaseModel):
    """Options for relationship discovery."""
    include_rbac: bool = True
    include_network: bool = True
    include_crds: bool = True
```

### 3. `builder.py` - Graph Builder
**Purpose**: Main orchestration for building NetworkX graphs  
**Key Class**: `GraphBuilder`

**Pattern**:
```python
class GraphBuilder:
    """Builds NetworkX graphs from K8s resources."""
    
    def __init__(
        self,
        client: K8sClientProtocol,
        registry: Optional[DiscovererRegistry] = None
    ):
        """
        Initialize builder.
        
        Args:
            client: K8s client implementation (any protocol match)
            registry: Optional discoverer registry (uses global if None)
        """
        self.client = client
        self.registry = registry or DiscovererRegistry.get_global()
        self.unified_discoverer = UnifiedDiscoverer(client, self.registry)
        self.node_identity = NodeIdentity()
    
    async def build_from_resource(
        self,
        resource_id: ResourceIdentifier,
        depth: int,
        options: BuildOptions
    ) -> nx.DiGraph:
        """
        Build graph starting from a specific resource.
        Expands bidirectionally for 'depth' hops.
        
        Args:
            resource_id: Starting resource
            depth: How many levels to expand
            options: Build configuration
        
        Returns:
            NetworkX directed graph
        """
        graph = nx.DiGraph()
        visited = set()
        
        await self._expand_from_node(
            graph, resource_id, depth, visited, options
        )
        
        return graph
    
    async def build_namespace_graph(
        self,
        namespace: str,
        depth: int,
        options: BuildOptions
    ) -> nx.DiGraph:
        """
        Build complete graph for a namespace.
        
        Args:
            namespace: K8s namespace
            depth: Expansion depth per resource
            options: Build configuration
        
        Returns:
            NetworkX directed graph with all namespace resources
        """
        ...
```

**Key Features**:
- **No caching**: Stateless, calls client directly
- **Duplicate merging**: Detects same resource with different node IDs
- **Stable node IDs**: Uses `NodeIdentity` for consistent IDs
- **Permission handling**: Gracefully handles 403 errors
- **Validation**: Built-in graph validation for quality

### 4. `node_identity.py` - Stable Node Identity
**Purpose**: Generate consistent node IDs even when pods/replicasets recreate  
**Key Class**: `NodeIdentity`

**Algorithm**:
```python
class NodeIdentity:
    """Generates stable node IDs for K8s resources."""
    
    def get_node_id(self, resource: Dict[str, Any]) -> str:
        """
        Generate stable node ID.
        
        Rules:
        - Stable resources (Deployment, Service): kind:namespace:name
        - Pods: Pod:namespace:OwnerKind-OwnerName:template-hash
        - ReplicaSets: ReplicaSet:namespace:deployment-name:pod-template-hash
        
        Returns:
            Stable node ID string
        """
        kind = resource.get("kind")
        metadata = resource.get("metadata", {})
        name = metadata.get("name")
        namespace = metadata.get("namespace") or "cluster"
        
        if kind == "Pod":
            # Extract owner and template hash
            owner_refs = metadata.get("ownerReferences", [])
            labels = metadata.get("labels", {})
            pod_template_hash = labels.get("pod-template-hash", "")
            
            if owner_refs and pod_template_hash:
                owner = owner_refs[0]
                return f"Pod:{namespace}:{owner['kind']}-{owner['name']}:{pod_template_hash}"
        
        elif kind == "ReplicaSet":
            # Extract deployment name and template hash
            labels = metadata.get("labels", {})
            pod_template_hash = labels.get("pod-template-hash", "")
            
            # Parse deployment name from RS name
            if "-" in name and pod_template_hash:
                deployment_name = name.rsplit("-", 1)[0]
                return f"ReplicaSet:{namespace}:{deployment_name}:{pod_template_hash}"
        
        # Default: kind:namespace:name
        return f"{kind}:{namespace}:{name}"
```

**Why This Matters**:
- Pod name changes on recreation: `nginx-abc123-xyz` → `nginx-abc123-def`
- Template hash stays same: `abc123`
- Node ID stays same: `Pod:default:Deployment-nginx:abc123`
- Graph remains consistent across pod recreations

### 5. `discoverers/registry.py` - Plugin Registry
**Purpose**: Runtime registration and management of CRD handlers  
**Key Class**: `DiscovererRegistry`

**Pattern**:
```python
class DiscovererRegistry:
    """Registry for relationship discoverers."""
    
    _global_registry = None
    
    def __init__(self):
        self._discoverers: List[DiscovererProtocol] = []
        self._overrides: Dict[str, DiscovererProtocol] = {}
    
    @classmethod
    def get_global(cls) -> "DiscovererRegistry":
        """Get global singleton registry."""
        if cls._global_registry is None:
            cls._global_registry = cls()
            cls._global_registry._register_builtin()
        return cls._global_registry
    
    def register(
        self,
        discoverer: DiscovererProtocol,
        resource_kind: Optional[str] = None
    ):
        """
        Register a discoverer.
        
        Args:
            discoverer: Discoverer instance
            resource_kind: Optional specific kind to handle
        """
        if resource_kind:
            # Override for specific kind
            self._overrides[resource_kind] = discoverer
        else:
            # General discoverer (uses supports() check)
            self._discoverers.append(discoverer)
        
        # Sort by priority
        self._discoverers.sort(key=lambda d: d.priority, reverse=True)
    
    def get_discoverers_for_resource(
        self, resource: Dict[str, Any]
    ) -> List[DiscovererProtocol]:
        """
        Get discoverers that can handle this resource.
        Checks overrides first, then general discoverers.
        """
        kind = resource.get("kind")
        
        # Check override
        if kind in self._overrides:
            return [self._overrides[kind]]
        
        # Check general discoverers
        return [d for d in self._discoverers if d.supports(resource)]
    
    def _register_builtin(self):
        """Register built-in discoverers."""
        from .native import NativeResourceDiscoverer
        from .rbac import RBACDiscoverer
        from .network import NetworkPolicyDiscoverer
        from .handlers import get_all_handlers
        
        self.register(NativeResourceDiscoverer())
        self.register(RBACDiscoverer())
        self.register(NetworkPolicyDiscoverer())
        
        for handler in get_all_handlers():
            self.register(handler)
```

**Usage - Register Custom Handler**:
```python
from k8s_graph import DiscovererRegistry, BaseDiscoverer

class MyArgoCDHandler(BaseDiscoverer):
    """Custom ArgoCD handler with different logic."""
    
    def supports(self, resource: Dict[str, Any]) -> bool:
        return resource.get("kind") == "Application" and \
               resource.get("apiVersion", "").startswith("argoproj.io")
    
    async def discover(
        self, resource: Dict[str, Any]
    ) -> List[ResourceRelationship]:
        # Custom ArgoCD relationship logic
        relationships = []
        
        spec = resource.get("spec", {})
        # Your custom logic here
        
        return relationships
    
    @property
    def priority(self) -> int:
        return 100  # Higher than built-in (50)

# Register globally
DiscovererRegistry.get_global().register(
    MyArgoCDHandler(), 
    resource_kind="Application"  # Override built-in
)

# Or use per-builder registry
custom_registry = DiscovererRegistry()
custom_registry.register(MyArgoCDHandler())
builder = GraphBuilder(client, registry=custom_registry)
```

### 6. `discoverers/handlers/` - CRD Handlers
**Purpose**: Discover relationships for custom resources  
**Base Class**: `BaseCRDHandler`

**Pattern**:
```python
from k8s_graph.discoverers.base import BaseDiscoverer

class ArgoCDHandler(BaseDiscoverer):
    """Discover relationships for ArgoCD Applications."""
    
    def supports(self, resource: Dict[str, Any]) -> bool:
        """Check if this is an ArgoCD Application."""
        return (
            resource.get("kind") == "Application" and
            resource.get("apiVersion", "").startswith("argoproj.io")
        )
    
    async def discover(
        self, resource: Dict[str, Any]
    ) -> List[ResourceRelationship]:
        """Discover ArgoCD-specific relationships."""
        relationships = []
        
        metadata = resource.get("metadata", {})
        namespace = metadata.get("namespace")
        resource_id = ResourceIdentifier(
            kind="Application",
            name=metadata.get("name"),
            namespace=namespace
        )
        
        spec = resource.get("spec", {})
        
        # Find managed resources
        # ArgoCD creates resources based on manifests
        # We can query by labels
        label_selector = f"argocd.argoproj.io/instance={metadata.get('name')}"
        
        # This uses the K8s client passed to UnifiedDiscoverer
        managed_resources = await self.client.list_resources(
            kind="Deployment",  # Example
            namespace=spec.get("destination", {}).get("namespace"),
            label_selector=label_selector
        )
        
        for res in managed_resources:
            res_metadata = res.get("metadata", {})
            relationships.append(
                ResourceRelationship(
                    source=resource_id,
                    target=ResourceIdentifier(
                        kind=res.get("kind"),
                        name=res_metadata.get("name"),
                        namespace=res_metadata.get("namespace")
                    ),
                    relationship_type=RelationshipType.MANAGED,
                    details="Managed by ArgoCD Application"
                )
            )
        
        return relationships
    
    @property
    def priority(self) -> int:
        return 50  # Built-in priority
```

**Built-in Handlers** (13+):
- `ArgoCD` - Application resources
- `ArgoWorkflows` - Workflow, CronWorkflow
- `Helm` - Release resources
- `Airflow` - AirflowCluster, DagRun
- `Knative` - Service, Route, Configuration
- `FluxCD` - HelmRelease, Kustomization
- `Istio` - VirtualService, DestinationRule
- `cert-manager` - Certificate, Issuer
- `Tekton` - Pipeline, PipelineRun
- `Spark` - SparkApplication
- `KEDA` - ScaledObject
- `Velero` - Backup, Restore
- `PrometheusOperator` - ServiceMonitor, PrometheusRule

### 7. `adapters/kubernetes.py` - Default K8s Adapter
**Purpose**: Default implementation using kubernetes-python  
**Key Class**: `KubernetesAdapter`

**Pattern**:
```python
from kubernetes import client, config
from kubernetes.client.rest import ApiException

class KubernetesAdapter:
    """Default K8s client using kubernetes-python library."""
    
    def __init__(self, context: Optional[str] = None):
        """
        Initialize with kubernetes-python.
        
        Args:
            context: Optional K8s context name
        """
        self.context = context
        self._load_config()
        self._build_api_mapping()
    
    def _load_config(self):
        """Load K8s config from kubeconfig or in-cluster."""
        try:
            config.load_incluster_config()
        except config.ConfigException:
            if self.context:
                config.load_kube_config(context=self.context)
            else:
                config.load_kube_config()
        
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.batch_v1 = client.BatchV1Api()
        self.networking_v1 = client.NetworkingV1Api()
    
    async def get_resource(
        self, resource_id: ResourceIdentifier
    ) -> Optional[Dict[str, Any]]:
        """Get resource from K8s API."""
        api_info = self._api_mapping.get(resource_id.kind)
        if not api_info:
            return None
        
        try:
            api = api_info["api"]
            method_name = api_info["read_namespaced"]
            method = getattr(api, method_name)
            
            result = method(
                name=resource_id.name,
                namespace=resource_id.namespace
            )
            
            # Convert to dict
            return self._to_dict(result)
        
        except ApiException as e:
            if e.status == 404:
                return None
            raise
    
    async def list_resources(
        self,
        kind: str,
        namespace: Optional[str] = None,
        label_selector: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """List resources from K8s API."""
        api_info = self._api_mapping.get(kind)
        if not api_info:
            return [], {}
        
        api = api_info["api"]
        
        if namespace:
            method_name = api_info["list_namespaced"]
            method = getattr(api, method_name)
            result = method(
                namespace=namespace,
                label_selector=label_selector
            )
        else:
            method_name = api_info["list_all"]
            method = getattr(api, method_name)
            result = method(label_selector=label_selector)
        
        resources = [self._to_dict(item) for item in result.items]
        
        # Add kind/apiVersion (K8s API doesn't populate on list items)
        for resource in resources:
            if "kind" not in resource:
                resource["kind"] = kind
            if "apiVersion" not in resource and api_info.get("api_version"):
                resource["apiVersion"] = api_info["api_version"]
        
        metadata = {
            "resource_version": result.metadata.resource_version,
            "continue": result.metadata._continue
        }
        
        return resources, metadata
```

**Usage**:
```python
from k8s_graph import GraphBuilder
from k8s_graph.adapters import KubernetesAdapter

# Default adapter
client = KubernetesAdapter()
builder = GraphBuilder(client)

# With specific context
client = KubernetesAdapter(context="production")
builder = GraphBuilder(client)
```

### 8. `validator.py` - Graph Validation
**Purpose**: Validate graph quality and detect issues  
**Key Function**: `validate_graph()`

```python
def validate_graph(graph: nx.DiGraph) -> Dict[str, Any]:
    """
    Validate graph for duplicates and consistency.
    
    Checks:
    - Duplicate resources (same kind+namespace+name)
    - Incomplete nodes (missing kind/name)
    - Edges without metadata
    
    Returns:
        Validation report dict
    """
    issues = []
    warnings = []
    
    # Check for duplicate resources
    resource_map = {}  # (kind, ns, name) -> [node_ids]
    
    for node_id, attrs in graph.nodes(data=True):
        kind = attrs.get("kind")
        name = attrs.get("name")
        namespace = attrs.get("namespace") or "cluster"
        
        if kind and name:
            key = (kind, namespace, name)
            if key not in resource_map:
                resource_map[key] = []
            resource_map[key].append(node_id)
    
    # Report duplicates
    duplicates = {k: v for k, v in resource_map.items() if len(v) > 1}
    if duplicates:
        for (kind, namespace, name), node_ids in duplicates.items():
            issues.append({
                "type": "duplicate_resource",
                "kind": kind,
                "namespace": namespace,
                "name": name,
                "node_ids": node_ids,
                "message": f"Found {len(node_ids)} nodes for same resource"
            })
    
    return {
        "valid": len(issues) == 0,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "unique_resources": len(resource_map),
        "duplicate_count": len(duplicates),
        "issues": issues,
        "warnings": warnings
    }
```

## Code Generation Guidelines

### 1. Async/Await Pattern
**Always** use async/await for I/O operations:

```python
# ✅ Correct
async def discover(self, resource: Dict[str, Any]) -> List[ResourceRelationship]:
    resources = await self.client.list_resources("Pod", namespace)
    return relationships

# ❌ Wrong
def discover(self, resource: Dict[str, Any]) -> List[ResourceRelationship]:
    resources = self.client.list_resources("Pod", namespace)  # Missing await
```

### 2. Type Hints
**Always** use comprehensive type hints:

```python
from typing import Optional, List, Dict, Any, Tuple

async def get_resource(
    self,
    resource_id: ResourceIdentifier
) -> Optional[Dict[str, Any]]:
    pass
```

### 3. Protocol Implementations
Check protocol compliance using `isinstance()` or type checkers:

```python
from typing import runtime_checkable

@runtime_checkable
class K8sClientProtocol(Protocol):
    ...

# Usage
def validate_client(client):
    if not isinstance(client, K8sClientProtocol):
        raise TypeError("Client must implement K8sClientProtocol")
```

### 4. Error Handling
Library should be resilient:

```python
# In discoverers
try:
    resources = await self.client.list_resources(...)
    # Process
except Exception as e:
    logger.warning(f"Error discovering relationships: {e}")
    return []  # Return empty, don't crash

# In builder
try:
    resource = await self.client.get_resource(resource_id)
except ApiException as e:
    if e.status == 403:
        # Permission denied - log and continue
        logger.warning(f"Permission denied: {resource_id}")
        return
    raise  # Re-raise other errors
```

### 5. Logging
Use structured logging:

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Detailed debug info")
logger.info("Important state changes")
logger.warning("Unexpected but handled")
logger.error("Error with context", exc_info=True)
```

### 6. Testing
**Every feature needs tests**:

```python
# tests/test_registry.py
import pytest
from k8s_graph import DiscovererRegistry, BaseDiscoverer

class MockDiscoverer(BaseDiscoverer):
    def supports(self, resource):
        return resource.get("kind") == "MockResource"
    
    async def discover(self, resource):
        return []
    
    @property
    def priority(self):
        return 50

def test_registry_registration():
    registry = DiscovererRegistry()
    discoverer = MockDiscoverer()
    
    registry.register(discoverer)
    
    resource = {"kind": "MockResource"}
    discoverers = registry.get_discoverers_for_resource(resource)
    
    assert len(discoverers) == 1
    assert discoverers[0] == discoverer

def test_registry_override():
    registry = DiscovererRegistry()
    
    builtin = MockDiscoverer()
    custom = MockDiscoverer()
    
    registry.register(builtin)
    registry.register(custom, resource_kind="MockResource")
    
    resource = {"kind": "MockResource"}
    discoverers = registry.get_discoverers_for_resource(resource)
    
    # Should return override, not builtin
    assert discoverers[0] == custom
```

### 7. Pydantic Models
Use Pydantic for validation:

```python
from pydantic import BaseModel, Field, validator

class ResourceIdentifier(BaseModel):
    kind: str
    name: str
    namespace: Optional[str] = None
    
    @validator("kind")
    def validate_kind(cls, v):
        if not v or not v[0].isupper():
            raise ValueError("Kind must start with uppercase")
        return v
    
    class Config:
        frozen = True  # Immutable
        extra = "forbid"  # No extra fields
```

## Common Patterns

### Pattern 1: Custom K8s Client with Caching

```python
from k8s_graph import GraphBuilder, KubernetesAdapter
from typing import Optional, Dict, Any
import asyncio

class CachedK8sClient:
    """K8s client with TTL cache."""
    
    def __init__(self, upstream: KubernetesAdapter, ttl: int = 30):
        self.upstream = upstream
        self.cache = {}
        self.ttl = ttl
    
    async def get_resource(
        self, resource_id: ResourceIdentifier
    ) -> Optional[Dict[str, Any]]:
        cache_key = f"{resource_id.kind}:{resource_id.namespace}:{resource_id.name}"
        
        # Check cache
        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if asyncio.get_event_loop().time() - timestamp < self.ttl:
                return data
        
        # Fetch from upstream
        resource = await self.upstream.get_resource(resource_id)
        
        # Cache result
        if resource:
            self.cache[cache_key] = (resource, asyncio.get_event_loop().time())
        
        return resource
    
    async def list_resources(self, kind, namespace=None, label_selector=None):
        # Similar caching logic
        return await self.upstream.list_resources(kind, namespace, label_selector)

# Usage
upstream = KubernetesAdapter(context="production")
cached_client = CachedK8sClient(upstream, ttl=60)
builder = GraphBuilder(cached_client)
```

### Pattern 2: Custom CRD Handler

```python
from k8s_graph import BaseDiscoverer, ResourceRelationship, RelationshipType
from k8s_graph import DiscovererRegistry

class CustomWorkflowHandler(BaseDiscoverer):
    """Handler for custom workflow CRD."""
    
    def __init__(self, client):
        self.client = client
    
    def supports(self, resource: Dict[str, Any]) -> bool:
        return (
            resource.get("kind") == "CustomWorkflow" and
            resource.get("apiVersion") == "workflows.example.com/v1"
        )
    
    async def discover(
        self, resource: Dict[str, Any]
    ) -> List[ResourceRelationship]:
        relationships = []
        
        metadata = resource.get("metadata", {})
        spec = resource.get("spec", {})
        
        source_id = ResourceIdentifier(
            kind="CustomWorkflow",
            name=metadata.get("name"),
            namespace=metadata.get("namespace")
        )
        
        # Find pods created by this workflow
        label_selector = f"workflow={metadata.get('name')}"
        pods, _ = await self.client.list_resources(
            kind="Pod",
            namespace=metadata.get("namespace"),
            label_selector=label_selector
        )
        
        for pod in pods:
            pod_metadata = pod.get("metadata", {})
            relationships.append(
                ResourceRelationship(
                    source=source_id,
                    target=ResourceIdentifier(
                        kind="Pod",
                        name=pod_metadata.get("name"),
                        namespace=pod_metadata.get("namespace")
                    ),
                    relationship_type=RelationshipType.OWNED,
                    details="Created by workflow"
                )
            )
        
        return relationships
    
    @property
    def priority(self) -> int:
        return 100  # User handler priority

# Register globally
from k8s_graph import KubernetesAdapter

client = KubernetesAdapter()
handler = CustomWorkflowHandler(client)
DiscovererRegistry.get_global().register(handler)

# Or per-builder
builder = GraphBuilder(client)
# Handler already registered globally
```

### Pattern 3: Proxied K8s Client

```python
import aiohttp
from k8s_graph import GraphBuilder

class K8sProxyClient:
    """K8s client that uses HTTP proxy to reduce cluster load."""
    
    def __init__(self, proxy_url: str, api_token: str):
        self.proxy_url = proxy_url
        self.api_token = api_token
    
    async def get_resource(
        self, resource_id: ResourceIdentifier
    ) -> Optional[Dict[str, Any]]:
        url = f"{self.proxy_url}/api/resources"
        params = {
            "kind": resource_id.kind,
            "name": resource_id.name,
            "namespace": resource_id.namespace
        }
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.api_token}"}
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    return None
                else:
                    resp.raise_for_status()
    
    async def list_resources(
        self, kind, namespace=None, label_selector=None
    ):
        url = f"{self.proxy_url}/api/resources/list"
        params = {"kind": kind}
        if namespace:
            params["namespace"] = namespace
        if label_selector:
            params["labelSelector"] = label_selector
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.api_token}"}
            async with session.get(url, params=params, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["items"], data["metadata"]

# Usage
proxy_client = K8sProxyClient(
    proxy_url="https://k8s-proxy.company.com",
    api_token="secret-token"
)
builder = GraphBuilder(proxy_client)

graph = await builder.build_from_resource(
    ResourceIdentifier(kind="Deployment", name="nginx", namespace="default"),
    depth=2,
    options=BuildOptions()
)
```

### Pattern 4: Building Complete Cluster Visualizer

```python
from k8s_graph import GraphBuilder, KubernetesAdapter, BuildOptions
from k8s_graph import ResourceIdentifier
import asyncio

async def build_cluster_graph():
    """Build graph of entire cluster."""
    
    client = KubernetesAdapter()
    builder = GraphBuilder(client)
    
    # Get all namespaces
    namespaces, _ = await client.list_resources(kind="Namespace")
    
    all_graphs = []
    
    for ns in namespaces:
        ns_name = ns["metadata"]["name"]
        print(f"Building graph for namespace: {ns_name}")
        
        graph = await builder.build_namespace_graph(
            namespace=ns_name,
            depth=2,
            options=BuildOptions(
                include_rbac=True,
                include_network=True,
                include_crds=True,
                max_nodes=1000
            )
        )
        
        all_graphs.append((ns_name, graph))
    
    # Merge graphs or process separately
    for ns_name, graph in all_graphs:
        print(f"{ns_name}: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    
    return all_graphs

if __name__ == "__main__":
    graphs = asyncio.run(build_cluster_graph())
```

## Performance Considerations

### 1. No Built-in Caching
- Library is stateless
- Users implement caching in their K8s client
- Simpler design, more flexible

### 2. Parallel Operations
Use `asyncio.gather()` for parallel API calls:

```python
# In discoverer
pods_task = self.client.list_resources("Pod", namespace)
services_task = self.client.list_resources("Service", namespace)

pods, services = await asyncio.gather(pods_task, services_task)
```

### 3. Depth Control
Control graph size with depth parameter:

```python
# Shallow graph (fast)
graph = await builder.build_from_resource(
    resource_id, depth=1, options=BuildOptions()
)

# Deep graph (slower, more complete)
graph = await builder.build_from_resource(
    resource_id, depth=3, options=BuildOptions()
)
```

### 4. Max Nodes Limit
Prevent runaway graph building:

```python
options = BuildOptions(
    max_nodes=500,  # Stop after 500 nodes
    include_crds=True
)
```

## Common Pitfalls

### ❌ Don't: Mix sync and async
```python
# Wrong
def sync_function():
    result = await async_operation()  # SyntaxError
```

### ❌ Don't: Forget to await
```python
# Wrong
async def my_function():
    result = async_operation()  # Returns coroutine, not result
    return result
```

### ❌ Don't: Modify protocol signatures
```python
# Wrong - breaks protocol
class MyClient:
    async def get_resource(self, resource_id, extra_param):  # Extra param
        ...
```

### ❌ Don't: Raise in discoverers
```python
# Wrong
async def discover(self, resource):
    data = await self.client.get_resource(...)
    if not data:
        raise ValueError("Not found")  # Should return [] instead
```

### ❌ Don't: Ignore None checks
```python
# Wrong
metadata = resource["metadata"]  # KeyError if missing

# Right
metadata = resource.get("metadata", {})
```

## Testing Best Practices

1. **Use mocks for K8s client**:
```python
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_builder():
    mock_client = AsyncMock()
    mock_client.get_resource.return_value = {"kind": "Pod", ...}
    
    builder = GraphBuilder(mock_client)
    graph = await builder.build_from_resource(...)
    
    assert graph.number_of_nodes() > 0
```

2. **Test protocol compliance**:
```python
def test_client_implements_protocol():
    from k8s_graph.protocols import K8sClientProtocol
    from k8s_graph.adapters import KubernetesAdapter
    
    client = KubernetesAdapter()
    assert isinstance(client, K8sClientProtocol)
```

3. **Test discoverer registration**:
```python
def test_custom_handler_priority():
    registry = DiscovererRegistry()
    
    handler1 = MockHandler(priority=50)
    handler2 = MockHandler(priority=100)
    
    registry.register(handler1)
    registry.register(handler2)
    
    # Handler2 should come first (higher priority)
    resource = {"kind": "Test"}
    discoverers = registry.get_discoverers_for_resource(resource)
    assert discoverers[0] == handler2
```

## Migration Guide from k8s-explorer-mcp

### What Changed

1. **No caching in library**: Move caching to your K8s client
2. **Protocol-based**: Implement `K8sClientProtocol` instead of using `K8sClient` directly
3. **Registry system**: Use `DiscovererRegistry` for custom handlers
4. **No MCP server**: Pure library, no FastMCP dependency

### Migration Steps

**Before (k8s-explorer-mcp)**:
```python
from k8s_mcp import K8sClient
from k8s_mcp.graph import GraphBuilder

client = K8sClient(cache=K8sCache())
builder = GraphBuilder(client, cache=GraphCache())
```

**After (k8s-graph)**:
```python
from k8s_graph import KubernetesAdapter, GraphBuilder

client = KubernetesAdapter()
builder = GraphBuilder(client)  # No cache param
```

**Custom CRD Handler Before**:
```python
# Was part of crd_handlers.py
@dataclass
class MyHandler(CRDHandler):
    ...
```

**Custom CRD Handler After**:
```python
from k8s_graph import BaseDiscoverer, DiscovererRegistry

class MyHandler(BaseDiscoverer):
    ...

DiscovererRegistry.get_global().register(MyHandler())
```

## Quick Reference

### Key Classes
- `GraphBuilder`: Main orchestration for building graphs
- `NodeIdentity`: Generates stable node IDs
- `DiscovererRegistry`: Runtime plugin system
- `KubernetesAdapter`: Default K8s client implementation
- `ResourceIdentifier`: Unique resource ID
- `ResourceRelationship`: Edge between resources

### Key Protocols
- `K8sClientProtocol`: Interface for K8s clients
- `DiscovererProtocol`: Interface for relationship discoverers

### Key Patterns
- **Custom client**: Implement `K8sClientProtocol`
- **Custom handler**: Extend `BaseDiscoverer`, register with registry
- **Validation**: Use `validate_graph()` for quality checks
- **Testing**: Mock K8s client with `AsyncMock`

## Summary

This library emphasizes:
- **Protocol-based design** for flexibility
- **Strong defaults** with kubernetes-python
- **Extensibility** via registry system
- **No built-in caching** (user responsibility)
- **Comprehensive testing**
- **Type safety** with Pydantic
- **Async/await** throughout

**Goal**: Make K8s graph building flexible, extensible, and easy to integrate into any project! 🚀

