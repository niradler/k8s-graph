"""
Example demonstrating export functionality for graphs.

This example shows how to:
- Export graphs to PNG (visualized with Graphviz)
- Export graphs to HTML (interactive with pyvis)
- Export graphs to JSON (for persistence and reloading)
- Use export_all for multiple formats at once
"""

import asyncio
from pathlib import Path

from k8s_graph import (
    BuildOptions,
    GraphBuilder,
    KubernetesAdapter,
    ResourceIdentifier,
    export_all,
    export_html,
    export_json,
    export_png,
    load_json,
)


async def main():
    output_dir = Path("examples/output")
    output_dir.mkdir(exist_ok=True)

    client = KubernetesAdapter()
    builder = GraphBuilder(client)

    print("🔨 Building graph from deployment...")
    graph = await builder.build_from_resource(
        resource_id=ResourceIdentifier(kind="Deployment", name="nginx", namespace="default"),
        depth=2,
        options=BuildOptions(max_nodes=50),
    )

    print(f"✅ Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    print("\n📤 Exporting to PNG...")
    png_success = export_png(
        graph, output_dir / "nginx_deployment.png", title="Nginx Deployment Graph"
    )
    if png_success:
        print(f"   ✅ PNG saved: {output_dir / 'nginx_deployment.png'}")

    print("\n📤 Exporting to HTML...")
    html_success = export_html(
        graph,
        output_dir / "nginx_deployment.html",
        title="Nginx Deployment Graph (Interactive)",
    )
    if html_success:
        print(f"   ✅ HTML saved: {output_dir / 'nginx_deployment.html'}")

    print("\n📤 Exporting to JSON...")
    json_success = export_json(graph, output_dir / "nginx_deployment.json")
    if json_success:
        print(f"   ✅ JSON saved: {output_dir / 'nginx_deployment.json'}")

    print("\n📤 Exporting to all formats at once...")
    results = export_all(
        graph, output_dir, "nginx_all", title="Nginx Deployment", formats=["png", "html", "json"]
    )
    print(f"   Results: {results}")

    print("\n📥 Loading graph back from JSON...")
    loaded_graph = load_json(output_dir / "nginx_deployment.json")
    print(f"   ✅ Loaded: {loaded_graph.number_of_nodes()} nodes")

    print("\n📤 Exporting without aggregation...")
    export_png(
        graph,
        output_dir / "nginx_no_agg.png",
        title="No Aggregation",
        aggregate=False,
    )
    print("   ✅ Saved without aggregation")

    print(f"\n🎉 Done! View the interactive HTML:\n   open {output_dir / 'nginx_deployment.html'}")


if __name__ == "__main__":
    asyncio.run(main())
