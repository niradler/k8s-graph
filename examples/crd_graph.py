import asyncio

from k8s_graph import GraphBuilder, BuildOptions, ResourceIdentifier
from k8s_graph.adapters import KubernetesAdapter
from k8s_graph.export import export_to_json


async def main():
    client = KubernetesAdapter()
    builder = GraphBuilder(client)
    
    argocd_app = ResourceIdentifier(
        kind="Application",
        name="myapp",
        namespace="argocd",
    )
    
    print(f"Building graph from ArgoCD Application: {argocd_app.name}")
    
    graph = await builder.build_from_resource(
        argocd_app,
        depth=3,
        options=BuildOptions(
            include_rbac=True,
            include_network=True,
            include_crds=True,
            max_nodes=500,
        ),
    )
    
    print(f"Graph built: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    
    argocd_nodes = [n for n in graph.nodes() if "Application" in n]
    print(f"ArgoCD Application nodes: {len(argocd_nodes)}")
    
    managed_resources = []
    for node in argocd_nodes:
        for successor in graph.successors(node):
            edge_data = graph[node][successor]
            if edge_data.get("relationship_type") == "argocd_managed":
                managed_resources.append(successor)
    
    print(f"Managed resources found: {len(managed_resources)}")
    for resource in managed_resources[:10]:
        print(f"  - {resource}")
    
    export_to_json(graph, "argocd_app_graph.json")
    print("Exported to argocd_app_graph.json")


if __name__ == "__main__":
    asyncio.run(main())

