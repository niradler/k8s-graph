"""Example: Build complete namespace graph."""

import asyncio

from k8s_graph import BuildOptions, GraphBuilder, KubernetesAdapter, format_graph_output


async def main():
    """Build and export complete namespace graph."""
    namespace = "default"

    client = KubernetesAdapter()
    builder = GraphBuilder(client)

    print(f"Building complete graph for namespace '{namespace}'...")
    print("This may take a moment...\n")

    graph = await builder.build_namespace_graph(
        namespace=namespace,
        depth=2,
        options=BuildOptions(
            include_rbac=True,
            include_network=True,
            include_crds=False,
            max_nodes=500,
        ),
    )

    print("Graph Statistics:")
    print(f"  Total Nodes: {graph.number_of_nodes()}")
    print(f"  Total Edges: {graph.number_of_edges()}")

    kinds = {}
    for _, attrs in graph.nodes(data=True):
        kind = attrs.get("kind", "Unknown")
        kinds[kind] = kinds.get(kind, 0) + 1

    print("\nResources by Kind:")
    for kind, count in sorted(kinds.items(), key=lambda x: x[1], reverse=True):
        print(f"  {kind}: {count}")

    sampling_info = builder.get_pod_sampling_info()
    if sampling_info["sampled_count"] > 0:
        print("\nPod Sampling:")
        print(f"  Templates: {sampling_info['sampled_count']}")
        print(f"  Estimated total pods: {sampling_info['total_count']}")

    discovery_stats = builder.get_discovery_stats()
    print("\nDiscovery Statistics:")
    print(f"  Discoveries: {discovery_stats['discoveries']}")
    print(f"  Errors: {discovery_stats['errors']}")
    print(f"  Total relationships: {discovery_stats['total_relationships']}")

    print("\nExporting graph...")

    json_output = format_graph_output(
        graph, format_type="json", include_metadata=True, pod_sampling_info=sampling_info
    )
    with open(f"{namespace}_graph.json", "w") as f:
        f.write(json_output)
    print(f"  Saved JSON: {namespace}_graph.json")

    llm_output = format_graph_output(
        graph, format_type="llm", include_metadata=True, pod_sampling_info=sampling_info
    )
    with open(f"{namespace}_graph.txt", "w") as f:
        f.write(llm_output)
    print(f"  Saved LLM-friendly: {namespace}_graph.txt")

    api_stats = client.get_api_call_stats()
    print("\nKubernetes API Statistics:")
    print(f"  get_resource calls: {api_stats['get_resource']}")
    print(f"  list_resources calls: {api_stats['list_resources']}")
    print(f"  Total API calls: {api_stats['total']}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
