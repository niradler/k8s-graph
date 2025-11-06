"""Basic usage example for k8s-graph."""

import asyncio

from k8s_graph import (
    BuildOptions,
    GraphBuilder,
    KubernetesAdapter,
    ResourceIdentifier,
    validate_graph,
)


async def main():
    """Build and explore a simple K8s resource graph."""
    client = KubernetesAdapter()
    builder = GraphBuilder(client)

    resource_id = ResourceIdentifier(kind="Deployment", name="nginx", namespace="default")

    print("Building graph from Deployment...")
    graph = await builder.build_from_resource(
        resource_id, depth=2, options=BuildOptions(include_rbac=True, max_nodes=100)
    )

    print("\nGraph Statistics:")
    print(f"  Nodes: {graph.number_of_nodes()}")
    print(f"  Edges: {graph.number_of_edges()}")

    print("\nResources:")
    for _node_id, attrs in graph.nodes(data=True):
        kind = attrs.get("kind", "Unknown")
        name = attrs.get("name", "unknown")
        namespace = attrs.get("namespace", "N/A")
        print(f"  {kind}/{name} (namespace: {namespace})")

    print("\nRelationships:")
    for source, target, attrs in graph.edges(data=True):
        rel_type = attrs.get("relationship_type", "unknown")
        print(f"  {source} --[{rel_type}]--> {target}")

    result = validate_graph(graph)
    print(f"\nValidation: {'✓ PASS' if result['valid'] else '✗ FAIL'}")
    if result["issues"]:
        for issue in result["issues"]:
            print(f"  Issue: {issue['message']}")

    api_stats = client.get_api_call_stats()
    print(f"\nKubernetes API Statistics:")
    print(f"  get_resource calls: {api_stats['get_resource']}")
    print(f"  list_resources calls: {api_stats['list_resources']}")
    print(f"  Total API calls: {api_stats['total']}")


if __name__ == "__main__":
    asyncio.run(main())
