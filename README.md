# k8s-graph

> Protocol-based Python library for building NetworkX graphs from Kubernetes resources

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-139%20passing-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-70%25-green.svg)](htmlcov/)
[![Type Checked](https://img.shields.io/badge/type--checked-mypy-blue.svg)](k8s_graph/)

## Overview

**k8s-graph** is a flexible, extensible Python library that builds NetworkX graphs from Kubernetes cluster resources. It provides intelligent relationship discovery, stable node identity, and a powerful plugin system for custom resource types.

### Key Features

- **Protocol-Based Design**: Easy to integrate with any K8s client (add caching, proxying, mocking)
- **Strong Defaults**: Works out-of-the-box with kubernetes-python
- **Extensible Architecture**: Runtime plugin system for custom CRD handlers
- **Stable Node Identity**: Consistent node IDs even when pods recreate
- **Stateless Library**: No built-in caching - you control the strategy
- **Type-Safe**: Comprehensive type hints and Pydantic models
- **Production Ready**: Async/await throughout, graceful error handling

## Visualizations

### Complete Namespace Graph

Full namespace visualization showing all resources and their relationships:

![Complete Namespace](docs/images/showcase_full_namespace.png)

### Deployment with Dependencies

Focused view of a single deployment with its dependencies (ReplicaSet, Pods, ConfigMaps, Secrets):

![Deployment Dependencies](docs/images/showcase_deployment_with_dependencies.png)

### Service Mesh Connections

Service-to-service connections and network topology:

![Service Connections](docs/images/showcase_service_connections.png)

## Installation

```bash
# Using uv (recommended)
uv pip install k8s-graph

# Using pip
pip install k8s-graph
```

## Quick Start

```python
import asyncio
from k8s_graph import GraphBuilder, KubernetesAdapter, ResourceIdentifier, BuildOptions

async def main():
    # Create K8s client adapter
    client = KubernetesAdapter()
    
    # Create graph builder
    builder = GraphBuilder(client)
    
    # Build graph from a Deployment
    graph = await builder.build_from_resource(
        resource_id=ResourceIdentifier(
            kind="Deployment",
            name="nginx",
            namespace="default"
        ),
        depth=2,
        options=BuildOptions()
    )
    
    # Explore the graph
    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")
    
    # Query relationships
    for node_id, attrs in graph.nodes(data=True):
        print(f"{attrs['kind']}: {attrs['name']}")

asyncio.run(main())
```

## Core Concepts

### Protocol-Based Design

k8s-graph uses protocols to define extension points, making it easy to customize:

```python
from k8s_graph import K8sClientProtocol

class CachedK8sClient:
    """Custom client with caching"""
    
    async def get_resource(self, resource_id):
        # Your caching logic
        pass
    
    async def list_resources(self, kind, namespace=None, label_selector=None):
        # Your caching logic
        pass

# Use your custom client
builder = GraphBuilder(CachedK8sClient())
```

### Extensible Discovery

Register custom handlers for CRDs or override built-in behavior:

```python
from k8s_graph import BaseDiscoverer, DiscovererRegistry

class MyCustomHandler(BaseDiscoverer):
    def supports(self, resource):
        return resource.get("kind") == "MyCustomResource"
    
    async def discover(self, resource):
        # Your relationship discovery logic
        return relationships

# Register globally
DiscovererRegistry.get_global().register(MyCustomHandler(client))
```

### Stable Node Identity

Pods and ReplicaSets get stable IDs based on their template hash, not their name:

```python
# Pod names change: nginx-abc123-xyz -> nginx-abc123-def
# Node ID stays same: Pod:default:Deployment-nginx:abc123

# Graph remains consistent across pod recreations
```

## Architecture

```
k8s-graph/
├── k8s_graph/
│   ├── models.py           # Pydantic models (ResourceIdentifier, etc.)
│   ├── protocols.py        # K8sClientProtocol, DiscovererProtocol
│   ├── builder.py          # GraphBuilder (main orchestration)
│   ├── node_identity.py    # Stable node ID generation
│   ├── validator.py        # Graph validation
│   ├── formatter.py        # Output formatting
│   ├── discoverers/
│   │   ├── base.py         # BaseDiscoverer
│   │   ├── registry.py     # DiscovererRegistry
│   │   ├── unified.py      # UnifiedDiscoverer
│   │   ├── native.py       # Core K8s resources
│   │   ├── rbac.py         # RBAC relationships
│   │   └── network.py      # NetworkPolicy relationships
│   └── adapters/
│       └── kubernetes.py   # Default K8s adapter
```

## Examples

See the [examples/](examples/) directory for:

- **basic_usage.py** - Simple graph building and exploration
- **namespace_graph.py** - Building complete namespace graphs
- **cached_client.py** - Custom client with TTL-based caching
- **custom_client.py** - Custom client with rate limiting
- **query_graph.py** - Query API demonstrations (dependencies, paths, filtering)
- **visualize_cluster.py** - Graph visualization with multiple layouts

## Supported Resources

### Native Kubernetes Resources

**Workloads:**
- Pod, Deployment, StatefulSet, DaemonSet, ReplicaSet, Job, CronJob

**Networking:**
- Service, Ingress, NetworkPolicy, Endpoints

**Storage:**
- PersistentVolumeClaim, ConfigMap, Secret

**RBAC:**
- ServiceAccount, Role, RoleBinding, ClusterRole, ClusterRoleBinding

**Policy & Scaling:**
- HorizontalPodAutoscaler, PodDisruptionBudget, ResourceQuota, LimitRange

**Infrastructure:**
- Namespace

### Relationship Discovery

k8s-graph automatically discovers relationships:

- **namespace**: Resource → Namespace
- **owner**: Deployment → ReplicaSet → Pod
- **label_selector**: Service → Pods (via label matching)
- **volume**: Pod → ConfigMap/Secret/PVC (volume mounts)
- **env_var**: Pod → ConfigMap/Secret (environment variables)
- **env_from**: Pod → ConfigMap/Secret (envFrom)
- **service_account**: Workload → ServiceAccount
- **role_binding**: RoleBinding → Role/ServiceAccount
- **network_policy**: NetworkPolicy → Pods
- **ingress_backend**: Ingress → Service
- **pvc**: Pod → PersistentVolumeClaim

## Use Cases

### Troubleshooting & Investigation

**Find why a pod is failing:**
```python
# Build graph from deployment
graph = await builder.build_from_resource(
    ResourceIdentifier(kind="Deployment", name="my-app", namespace="production"),
    depth=3,
    options=BuildOptions()
)

# Find all secrets and configmaps
for node_id, attrs in graph.nodes(data=True):
    if attrs['kind'] in ['Secret', 'ConfigMap']:
        print(f"{attrs['kind']}: {attrs['name']}")
```

**Trace service dependencies:**
```python
# Build from service
graph = await builder.build_from_resource(
    ResourceIdentifier(kind="Service", name="api-gateway", namespace="default"),
    depth=2,
    options=BuildOptions()
)

# Find all connected pods
pods = [attrs for _, attrs in graph.nodes(data=True) if attrs['kind'] == 'Pod']
print(f"Service connects to {len(pods)} pods")
```

**Audit secret usage across namespace:**
```python
# Build complete namespace
graph = await builder.build_namespace_graph("production", depth=5, options=BuildOptions())

# Find all resources using secrets
import networkx as nx
secret_users = {}
for node_id, attrs in graph.nodes(data=True):
    if attrs['kind'] == 'Secret':
        secret_name = attrs['name']
        # Find predecessors (resources using this secret)
        users = list(graph.predecessors(node_id))
        secret_users[secret_name] = len(users)

for secret, count in sorted(secret_users.items(), key=lambda x: x[1], reverse=True):
    print(f"{secret}: used by {count} resources")
```

## Advanced NetworkX Operations

Since k8s-graph returns standard NetworkX graphs, you can leverage all NetworkX capabilities:

### Path Analysis

**Find dependency path between resources:**
```python
import networkx as nx

# Find path from deployment to secret
try:
    path = nx.shortest_path(
        graph,
        source="Deployment:production:api-gateway",
        target="Secret:production:db-credentials"
    )
    print("Dependency chain:", " → ".join([graph.nodes[n]['kind'] for n in path]))
except nx.NetworkXNoPath:
    print("No direct dependency path found")
```

### Subgraph Extraction

**Extract workloads only:**
```python
# Filter to workload resources
workload_kinds = ['Deployment', 'StatefulSet', 'DaemonSet', 'Job']
workload_nodes = [
    n for n, attrs in graph.nodes(data=True) 
    if attrs.get('kind') in workload_kinds
]
workload_graph = graph.subgraph(workload_nodes)
```

**Extract configuration layer:**
```python
# Get all ConfigMaps, Secrets, and what uses them
config_kinds = ['ConfigMap', 'Secret']
config_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get('kind') in config_kinds]

# Include resources that use them
extended_nodes = set(config_nodes)
for node in config_nodes:
    extended_nodes.update(graph.predecessors(node))

config_graph = graph.subgraph(extended_nodes)
```

### Graph Analysis

**Find most connected resources (hubs):**
```python
# Calculate degree centrality
centrality = nx.degree_centrality(graph)
top_resources = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:10]

for node_id, score in top_resources:
    attrs = graph.nodes[node_id]
    print(f"{attrs['kind']}/{attrs['name']}: {score:.3f}")
```

**Detect isolated resources:**
```python
# Find resources with no connections
undirected = graph.to_undirected()
isolated = list(nx.isolates(undirected))

print(f"Found {len(isolated)} isolated resources:")
for node_id in isolated:
    attrs = graph.nodes[node_id]
    print(f"  {attrs['kind']}/{attrs['name']}")
```

**Analyze connectivity:**
```python
# Check graph connectivity
undirected = graph.to_undirected()
components = list(nx.connected_components(undirected))

print(f"Graph has {len(components)} connected components")
print(f"Largest component: {len(max(components, key=len))} nodes")
```

### Export & Visualization

**Export to different formats:**
```python
from k8s_graph import export_json, export_png, export_html

# JSON for programmatic use
export_json(graph, "cluster.json")

# PNG for documentation
export_png(graph, "cluster.png", title="Production Cluster", aggregate=True)

# Interactive HTML
export_html(graph, "cluster.html", title="Production Cluster", aggregate=True)
```

**Custom NetworkX exports:**
```python
import networkx as nx

# GraphML for Gephi/Cytoscape
nx.write_graphml(graph, "cluster.graphml")

# GML format
nx.write_gml(graph, "cluster.gml")

# Edge list
nx.write_edgelist(graph, "cluster.edgelist")
```

## Development

```bash
# Setup
git clone https://github.com/k8s-graph/k8s-graph
cd k8s-graph
uv venv
source .venv/bin/activate
make install-dev

# Run tests
make test

# Run checks
make check

# Build package
make build
```

See [agents.md](agents.md) for detailed development guide.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Documentation

- **Architecture Guide**: [agents.md](agents.md) - Comprehensive guide for developers
- **Examples**: [examples/](examples/) - Working code examples
- **Tests**: [tests/](tests/) - Full test suite showcasing capabilities

