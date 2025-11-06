"""Example: Custom K8s client with rate limiting."""

import asyncio
from typing import Any

from k8s_graph import BuildOptions, GraphBuilder, KubernetesAdapter, ResourceIdentifier


class RateLimitedK8sClient:
    """K8s client with rate limiting."""

    def __init__(self, upstream: KubernetesAdapter, requests_per_second: float = 10.0):
        """
        Initialize rate-limited client.

        Args:
            upstream: Upstream K8s client
            requests_per_second: Maximum requests per second
        """
        self.upstream = upstream
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self.request_count = 0

    async def _rate_limit(self) -> None:
        """Enforce rate limit."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_interval:
            await asyncio.sleep(self.min_interval - time_since_last)

        self.last_request_time = asyncio.get_event_loop().time()
        self.request_count += 1

    async def get_resource(self, resource_id: ResourceIdentifier) -> dict[str, Any] | None:
        """Get resource with rate limiting."""
        await self._rate_limit()
        return await self.upstream.get_resource(resource_id)

    async def list_resources(
        self,
        kind: str,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """List resources with rate limiting."""
        await self._rate_limit()
        return await self.upstream.list_resources(kind, namespace, label_selector)

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiting statistics."""
        return {
            "total_requests": self.request_count,
            "rate_limit": f"{1.0/self.min_interval:.1f} req/s",
        }


async def main():
    """Demonstrate custom client with rate limiting."""
    upstream = KubernetesAdapter()
    rate_limited_client = RateLimitedK8sClient(upstream, requests_per_second=5.0)

    builder = GraphBuilder(rate_limited_client)

    resource_id = ResourceIdentifier(kind="Service", name="kubernetes", namespace="default")

    print("Building graph with rate-limited client...")
    print("Rate limit: 5 requests/second\n")

    graph = await builder.build_from_resource(
        resource_id, depth=1, options=BuildOptions(max_nodes=50)
    )

    print("Graph Statistics:")
    print(f"  Nodes: {graph.number_of_nodes()}")
    print(f"  Edges: {graph.number_of_edges()}")

    stats = rate_limited_client.get_stats()
    print("\nRate Limiting Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
