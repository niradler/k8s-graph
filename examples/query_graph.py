import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from k8s_graph import (
    BuildOptions,
    GraphBuilder,
    KubernetesAdapter,
    extract_subgraph,
    find_all_paths,
    find_by_kind,
    find_by_namespace,
    find_dependencies,
    find_dependents,
    find_path,
    get_neighbors,
    load_graph,
    save_graph,
)


async def demonstrate_query_api():
    """
    Demonstrate the query API with a real Kubernetes cluster.
    """
    print("=== K8s Graph Query API Demo ===\n")

    client = KubernetesAdapter()
    builder = GraphBuilder(client)

    namespace = "default"
    print(f"Building graph for namespace: {namespace}")

    graph = await builder.build_namespace_graph(
        namespace=namespace, depth=2, options=BuildOptions(max_nodes=200)
    )

    print(f"Graph built: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges\n")

    save_graph(graph, "test-output/query_demo_graph.json")
    print("Saved graph to test-output/query_demo_graph.json\n")

    print("=== Query Examples ===\n")

    print("1. Find all Deployments:")
    deployments = find_by_kind(graph, "Deployment")
    for dep in deployments[:3]:
        attrs = graph.nodes[dep]
        print(f"   - {attrs.get('name')}")
    if len(deployments) > 3:
        print(f"   ... and {len(deployments) - 3} more")
    print()

    print("2. Find resources in default namespace:")
    default_resources = find_by_namespace(graph, "default")
    print(f"   Found {len(default_resources)} resources\n")

    if deployments:
        deployment_id = deployments[0]
        deployment_name = graph.nodes[deployment_id].get("name")
        print(f"3. Find dependencies of Deployment '{deployment_name}':")
        deps = find_dependencies(graph, deployment_id, max_depth=2)
        print(f"   Dependencies: {deps.number_of_nodes()} resources")
        for node in list(deps.nodes())[:5]:
            attrs = deps.nodes[node]
            print(f"   - {attrs.get('kind')}/{attrs.get('name')}")
        print()

    services = find_by_kind(graph, "Service")
    if services:
        service_id = services[0]
        service_name = graph.nodes[service_id].get("name")
        print(f"4. Find what depends on Service '{service_name}':")
        dependents = find_dependents(graph, service_id)
        print(f"   Dependents: {dependents.number_of_nodes()} resources")
        for node in list(dependents.nodes())[:5]:
            attrs = dependents.nodes[node]
            print(f"   - {attrs.get('kind')}/{attrs.get('name')}")
        print()

    if deployments and services:
        print("5. Find path from Deployment to Service:")
        path = find_path(graph, deployments[0], services[0])
        if path:
            print(f"   Path found with {len(path)} hops:")
            for node_id in path:
                attrs = graph.nodes[node_id]
                print(f"   -> {attrs.get('kind')}/{attrs.get('name')}")
        else:
            print("   No path found")
        print()

        print("6. Find all paths (up to length 5):")
        all_paths = find_all_paths(graph, deployments[0], services[0], cutoff=5)
        print(f"   Found {len(all_paths)} path(s)")
        for i, path in enumerate(all_paths[:3], 1):
            print(f"   Path {i}: {len(path)} hops")
        print()

    if deployments:
        print("7. Get 2-hop neighborhood:")
        neighborhood = get_neighbors(graph, deployments[0], hops=2)
        print(
            f"   Neighborhood: {neighborhood.number_of_nodes()} nodes, {neighborhood.number_of_edges()} edges\n"
        )

    pods = find_by_kind(graph, "Pod")
    if pods:
        print("8. Extract subgraph of all Pods:")
        pod_graph = extract_subgraph(graph, pods[:10])
        print(
            f"   Pod subgraph: {pod_graph.number_of_nodes()} nodes, {pod_graph.number_of_edges()} edges\n"
        )

    print("\n=== Persistence Examples ===\n")

    print("Saving graph in multiple formats:")
    save_graph(graph, "test-output/query_demo.json", format="json")
    print("  ✓ Saved as JSON")

    save_graph(graph, "test-output/query_demo.graphml", format="graphml")
    print("  ✓ Saved as GraphML")

    save_graph(graph, "test-output/query_demo.gml", format="gml")
    print("  ✓ Saved as GML")

    print("\nLoading graph from JSON:")
    loaded_graph = load_graph("test-output/query_demo.json")
    print(
        f"  Loaded: {loaded_graph.number_of_nodes()} nodes, {loaded_graph.number_of_edges()} edges"
    )

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(demonstrate_query_api())
