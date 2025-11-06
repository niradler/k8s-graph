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

### Performance

On a typical cluster namespace:
- **88% graph connectivity** (only 12% orphaned resources)
- **Multiple relationship types** discovered per resource
- **Handles 400+ edges** efficiently
- **Graceful error handling** for permission errors

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

