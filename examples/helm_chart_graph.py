import asyncio

from k8s_graph import BuildOptions, GraphBuilder, ResourceIdentifier
from k8s_graph.adapters import KubernetesAdapter
from k8s_graph.export import export_to_json


async def main():
    client = KubernetesAdapter()
    builder = GraphBuilder(client)

    helm_deployment = ResourceIdentifier(
        kind="Deployment",
        name="myapp",
        namespace="default",
    )

    print(f"Building graph from Helm-managed Deployment: {helm_deployment.name}")
    print("Note: This will discover all resources managed by the same Helm release")

    graph = await builder.build_from_resource(
        helm_deployment,
        depth=2,
        options=BuildOptions(
            include_rbac=True,
            include_network=True,
            include_crds=True,
            max_nodes=500,
        ),
    )

    print(f"Graph built: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    helm_managed = []
    for node, attrs in graph.nodes(data=True):
        annotations = attrs.get("annotations", {})
        labels = attrs.get("labels", {})

        if (
            annotations.get("meta.helm.sh/release-name")
            or labels.get("app.kubernetes.io/managed-by") == "Helm"
        ):
            helm_managed.append(node)

    print(f"Helm-managed resources found: {len(helm_managed)}")
    for resource in helm_managed[:10]:
        print(f"  - {resource}")

    export_to_json(graph, "helm_chart_graph.json")
    print("Exported to helm_chart_graph.json")


if __name__ == "__main__":
    asyncio.run(main())
