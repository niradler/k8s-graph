"""Example showing how to add caching to the K8s client."""

import asyncio
import time
from typing import Any

from k8s_graph import BuildOptions, GraphBuilder, KubernetesAdapter, ResourceIdentifier


class CachedK8sClient:
    """K8s client wrapper with TTL-based caching."""

    def __init__(self, upstream: KubernetesAdapter, ttl: int = 60):
        """
        Initialize cached client.

        Args:
            upstream: Upstream K8s client
            ttl: Time-to-live for cache entries in seconds
        """
        self.upstream = upstream
        self.ttl = ttl
        self.cache: dict[str, tuple[Any, float]] = {}
        self.hits = 0
        self.misses = 0

    async def get_resource(self, resource_id: ResourceIdentifier) -> dict[str, Any] | None:
        """Get resource with caching."""
        cache_key = f"get:{resource_id.kind}:{resource_id.namespace}:{resource_id.name}"

        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.ttl:
                self.hits += 1
                return data

        self.misses += 1
        resource = await self.upstream.get_resource(resource_id)

        if resource:
            self.cache[cache_key] = (resource, time.time())

        return resource

    async def list_resources(
        self,
        kind: str,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """List resources with caching."""
        cache_key = f"list:{kind}:{namespace}:{label_selector}"

        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.ttl:
                self.hits += 1
                return data

        self.misses += 1
        result = await self.upstream.list_resources(kind, namespace, label_selector)

        self.cache[cache_key] = (result, time.time())

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            "hits": self.hits,
            "misses": self.misses,
            "total": total,
            "hit_rate": f"{hit_rate:.1f}%",
            "cache_size": len(self.cache),
        }


async def main():
    """Demonstrate caching benefits."""
    upstream = KubernetesAdapter()
    cached_client = CachedK8sClient(upstream, ttl=60)

    builder = GraphBuilder(cached_client)

    resource_id = ResourceIdentifier(kind="Deployment", name="nginx", namespace="default")

    print("Building graph (first time - cache cold)...")
    start = time.time()
    graph1 = await builder.build_from_resource(resource_id, depth=2, options=BuildOptions())
    duration1 = time.time() - start

    print(f"  Took {duration1:.2f}s")
    print(f"  Nodes: {graph1.number_of_nodes()}, Edges: {graph1.number_of_edges()}")

    print("\nBuilding same graph again (cache warm)...")
    start = time.time()
    graph2 = await builder.build_from_resource(resource_id, depth=2, options=BuildOptions())
    duration2 = time.time() - start

    print(f"  Took {duration2:.2f}s")
    print(f"  Nodes: {graph2.number_of_nodes()}, Edges: {graph2.number_of_edges()}")

    speedup = duration1 / duration2 if duration2 > 0 else 0
    print(f"\nSpeedup: {speedup:.1f}x faster")

    stats = cached_client.get_stats()
    print("\nCache Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
