import asyncio

from k8s_graph import BuildOptions, GraphBuilder, ResourceIdentifier
from k8s_graph.adapters import KubernetesAdapter
from k8s_graph.export import export_to_json


async def main():
    client = KubernetesAdapter()
    builder = GraphBuilder(client)

    workflow = ResourceIdentifier(
        kind="Workflow",
        name="my-workflow",
        namespace="default",
    )

    print(f"Building graph from Argo Workflow: {workflow.name}")

    graph = await builder.build_from_resource(
        workflow,
        depth=2,
        options=BuildOptions(
            include_rbac=True,
            include_network=False,
            include_crds=True,
            max_nodes=500,
        ),
    )

    print(f"Graph built: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    workflow_nodes = [n for n in graph.nodes() if "Workflow" in n]
    print(f"Workflow nodes: {len(workflow_nodes)}")

    spawned_pods = []
    for node in workflow_nodes:
        for successor in graph.successors(node):
            edge_data = graph[node][successor]
            if edge_data.get("relationship_type") == "argo_workflow_spawned":
                spawned_pods.append(successor)

    print(f"Pods spawned by workflow: {len(spawned_pods)}")
    for pod in spawned_pods[:10]:
        print(f"  - {pod}")

    configmaps = [n for n in graph.nodes() if "ConfigMap" in n]
    secrets = [n for n in graph.nodes() if "Secret" in n]

    print(f"ConfigMaps used: {len(configmaps)}")
    print(f"Secrets used: {len(secrets)}")

    export_to_json(graph, "workflow_graph.json")
    print("Exported to workflow_graph.json")


if __name__ == "__main__":
    asyncio.run(main())
