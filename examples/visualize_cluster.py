"""
Demonstrate visualization capabilities with various layouts.
Shows shell, circular, spring, spectral layouts and dependency graphs.
"""

import asyncio
from pathlib import Path

from k8s_graph import (
    BuildOptions,
    GraphBuilder,
    KubernetesAdapter,
    create_legend,
    draw_cluster,
    draw_dependencies,
    draw_namespace,
    draw_with_shell_layout,
    find_by_kind,
    get_shell_layout,
)


async def demonstrate_visualization():
    """Demonstrate visualization capabilities with various layouts."""
    print("=== K8s Graph Visualization Demo ===\n")

    client = KubernetesAdapter()
    builder = GraphBuilder(client)

    namespace = "default"
    print(f"Building graph for namespace: {namespace}")

    graph = await builder.build_namespace_graph(
        namespace=namespace, depth=2, options=BuildOptions(max_nodes=200)
    )

    print(f"Graph built: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges\n")

    # Ensure output directory exists
    output_dir = Path("test-output")
    output_dir.mkdir(exist_ok=True)

    print("Creating visualizations:\n")

    print("1. Shell layout (hierarchical K8s structure)...")
    draw_with_shell_layout(graph, "test-output/viz_shell_layout.png", figsize=(20, 16))
    print("   ✓ Saved to test-output/viz_shell_layout.png")

    print("\n2. Circular layout...")
    draw_cluster(graph, "test-output/viz_circular_layout.png", layout="circular", figsize=(16, 16))
    print("   ✓ Saved to test-output/viz_circular_layout.png")

    print("\n3. Spring layout (force-directed)...")
    draw_cluster(
        graph,
        "test-output/viz_spring_layout.png",
        layout="spring",
        k=0.5,
        figsize=(20, 16),
    )
    print("   ✓ Saved to test-output/viz_spring_layout.png")

    print("\n4. Spectral layout...")
    draw_cluster(graph, "test-output/viz_spectral_layout.png", layout="spectral", figsize=(16, 16))
    print("   ✓ Saved to test-output/viz_spectral_layout.png")

    print("\n5. Namespace-specific visualization...")
    draw_namespace(graph, namespace, "test-output/viz_namespace.png", layout="spring")
    print("   ✓ Saved to test-output/viz_namespace.png")

    deployments = find_by_kind(graph, "Deployment")
    if deployments:
        deployment_id = deployments[0]
        deployment_name = graph.nodes[deployment_id].get("name")
        print(f"\n6. Dependencies visualization for '{deployment_name}'...")
        draw_dependencies(
            graph,
            deployment_id,
            "test-output/viz_dependencies.png",
            max_depth=3,
            layout="spring",
        )
        print("   ✓ Saved to test-output/viz_dependencies.png")

    print("\n7. Creating color legend...")
    create_legend("test-output/viz_legend.png")
    print("   ✓ Saved to test-output/viz_legend.png")

    print("\n=== Shell Layout Details ===")
    shells = get_shell_layout(graph)
    print(f"Graph organized into {len(shells)} shells:")
    shell_names = [
        "Namespaces",
        "Controllers",
        "ReplicaSets/Jobs",
        "Pods",
        "Config/Services",
        "Other",
    ]
    for i, shell in enumerate(shells):
        if i < len(shell_names):
            print(f"  Shell {i} ({shell_names[i]}): {len(shell)} resources")

    print("\n=== Visualization Demo Complete ===")
    print("\nGenerated files in test-output/:")
    print("  - viz_shell_layout.png (hierarchical)")
    print("  - viz_circular_layout.png")
    print("  - viz_spring_layout.png (force-directed)")
    print("  - viz_spectral_layout.png")
    print("  - viz_namespace.png")
    print("  - viz_dependencies.png")
    print("  - viz_legend.png")


if __name__ == "__main__":
    asyncio.run(demonstrate_visualization())
