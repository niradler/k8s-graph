import logging
from typing import Any

import networkx as nx

from k8s_graph.discoverers.registry import DiscovererRegistry
from k8s_graph.discoverers.unified import UnifiedDiscoverer
from k8s_graph.models import BuildOptions, DiscoveryOptions, ResourceIdentifier
from k8s_graph.node_identity import NodeIdentity
from k8s_graph.protocols import K8sClientProtocol

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Builds NetworkX graphs from Kubernetes resources.

    The GraphBuilder orchestrates the entire graph building process:
    - Fetching resources from the K8s API
    - Discovering relationships via registered discoverers
    - Building the NetworkX graph with proper node IDs
    - Handling duplicates and pod template sampling
    - Tracking permissions and statistics

    Key features:
    - Stateless design (no internal caching)
    - Bidirectional expansion from starting resources
    - Configurable depth and options
    - Graceful permission handling
    - Max nodes limit enforcement

    Example:
        >>> from k8s_graph import GraphBuilder, KubernetesAdapter, ResourceIdentifier, BuildOptions
        >>> client = KubernetesAdapter()
        >>> builder = GraphBuilder(client)
        >>> graph = await builder.build_from_resource(
        ...     ResourceIdentifier(kind="Deployment", name="nginx", namespace="default"),
        ...     depth=2,
        ...     options=BuildOptions()
        ... )
    """

    def __init__(
        self,
        client: K8sClientProtocol,
        registry: DiscovererRegistry | None = None,
    ):
        """
        Initialize the graph builder.

        Args:
            client: K8s client implementation
            registry: Optional discoverer registry (uses global if None)
        """
        self.client = client
        self.registry = registry or DiscovererRegistry.get_global()
        self.unified_discoverer = UnifiedDiscoverer(client, self.registry)
        self.node_identity = NodeIdentity()

        self._permission_errors: list[str] = []
        self._pod_templates: dict[str, dict[str, Any]] = {}

    async def build_from_resource(
        self,
        resource_id: ResourceIdentifier,
        depth: int,
        options: BuildOptions,
    ) -> nx.DiGraph:
        """
        Build graph starting from a specific resource.

        Expands bidirectionally (following both incoming and outgoing edges)
        for the specified depth.

        Args:
            resource_id: Starting resource identifier
            depth: How many levels to expand (0 = just the resource itself)
            options: Build configuration options

        Returns:
            NetworkX directed graph

        Example:
            >>> graph = await builder.build_from_resource(
            ...     ResourceIdentifier(kind="Service", name="web", namespace="default"),
            ...     depth=2,
            ...     options=BuildOptions(include_rbac=True, max_nodes=100)
            ... )
        """
        graph = nx.DiGraph()
        visited: set[str] = set()

        self._permission_errors = []
        self._pod_templates = {}
        self.unified_discoverer.reset_stats()

        resource = await self.client.get_resource(resource_id)
        if not resource:
            logger.warning(f"Starting resource not found: {resource_id}")
            return graph

        await self._expand_from_node(graph, resource, depth, visited, options)

        logger.info(
            f"Built graph with {graph.number_of_nodes()} nodes "
            f"and {graph.number_of_edges()} edges"
        )

        return graph

    async def build_namespace_graph(
        self,
        namespace: str,
        depth: int,
        options: BuildOptions,
    ) -> nx.DiGraph:
        """
        Build complete graph for a namespace.

        Lists all major resource types in the namespace and builds a graph
        including all resources and their relationships.

        Args:
            namespace: Kubernetes namespace
            depth: Expansion depth per resource
            options: Build configuration options

        Returns:
            NetworkX directed graph with all namespace resources

        Example:
            >>> graph = await builder.build_namespace_graph(
            ...     namespace="production",
            ...     depth=2,
            ...     options=BuildOptions(max_nodes=1000)
            ... )
        """
        graph = nx.DiGraph()
        visited: set[str] = set()

        self._permission_errors = []
        self._pod_templates = {}
        self.unified_discoverer.reset_stats()

        resource_kinds = [
            "Pod",
            "Service",
            "Deployment",
            "StatefulSet",
            "DaemonSet",
            "ReplicaSet",
            "Job",
            "CronJob",
            "ConfigMap",
            "Secret",
            "PersistentVolumeClaim",
            "ServiceAccount",
            "HorizontalPodAutoscaler",
            "PodDisruptionBudget",
            "ResourceQuota",
            "LimitRange",
            "Endpoints",
        ]

        if options.include_rbac:
            resource_kinds.extend(["Role", "RoleBinding"])

        if options.include_network:
            resource_kinds.extend(["NetworkPolicy", "Ingress"])

        for kind in resource_kinds:
            if graph.number_of_nodes() >= options.max_nodes:
                logger.warning(f"Reached max_nodes limit of {options.max_nodes}")
                break

            resources, _ = await self.client.list_resources(kind=kind, namespace=namespace)

            for resource in resources:
                if graph.number_of_nodes() >= options.max_nodes:
                    break

                await self._expand_from_node(graph, resource, depth, visited, options)

        logger.info(
            f"Built namespace graph for '{namespace}' with {graph.number_of_nodes()} nodes "
            f"and {graph.number_of_edges()} edges"
        )

        return graph

    async def _expand_from_node(
        self,
        graph: nx.DiGraph,
        resource: dict[str, Any],
        depth: int,
        visited: set[str],
        options: BuildOptions,
    ) -> None:
        """
        Recursively expand graph from a resource node.

        Args:
            graph: Graph to expand
            resource: Current resource
            depth: Remaining expansion depth
            visited: Set of visited node IDs
            options: Build options
        """
        node_id = self.node_identity.get_node_id(resource)

        if graph.number_of_nodes() >= options.max_nodes:
            logger.debug(f"Reached max_nodes limit of {options.max_nodes}")
            return

        if self._should_sample_pod(resource, node_id):
            return

        if not graph.has_node(node_id):
            attrs = self.node_identity.extract_node_attributes(resource)
            graph.add_node(node_id, **attrs)

            logger.debug(
                f"Added node: {attrs.get('kind')}/{attrs.get('name')} "
                f"(namespace: {attrs.get('namespace')})"
            )

        already_visited = node_id in visited
        visited.add(node_id)

        if depth > 0 and not already_visited:
            discovery_options = DiscoveryOptions(
                include_rbac=options.include_rbac,
                include_network=options.include_network,
                include_crds=options.include_crds,
            )

            relationships = await self.unified_discoverer.discover_all_relationships(
                resource, discovery_options
            )

            for rel in relationships:
                target_node_id = self._get_node_id_from_identifier(rel.target)

                if not graph.has_node(target_node_id):
                    graph.add_node(
                        target_node_id,
                        kind=rel.target.kind,
                        name=rel.target.name,
                        namespace=rel.target.namespace,
                    )

                if not graph.has_edge(node_id, target_node_id):
                    graph.add_edge(
                        node_id,
                        target_node_id,
                        relationship_type=rel.relationship_type.value,
                        details=rel.details,
                    )
                    logger.debug(
                        f"Added edge: {node_id} --[{rel.relationship_type.value}]--> {target_node_id}"
                    )

                if target_node_id not in visited and graph.number_of_nodes() < options.max_nodes:
                    target_resource = await self.client.get_resource(rel.target)
                    if target_resource:
                        await self._expand_from_node(
                            graph, target_resource, depth - 1, visited, options
                        )

                source_node_id = self._get_node_id_from_identifier(rel.source)
                if source_node_id != node_id and not graph.has_node(source_node_id):
                    graph.add_node(
                        source_node_id,
                        kind=rel.source.kind,
                        name=rel.source.name,
                        namespace=rel.source.namespace,
                    )

                if (
                    source_node_id != node_id
                    and source_node_id not in visited
                    and graph.number_of_nodes() < options.max_nodes
                ):
                    source_resource = await self.client.get_resource(rel.source)
                    if source_resource:
                        await self._expand_from_node(
                            graph, source_resource, depth - 1, visited, options
                        )

    def _should_sample_pod(self, resource: dict[str, Any], node_id: str) -> bool:
        """
        Check if pod should be sampled (skipped due to template deduplication).

        For pods with the same template (e.g., replicas of a Deployment),
        only include one representative pod in the graph.

        Args:
            resource: Resource dictionary
            node_id: Generated node ID

        Returns:
            True if pod should be skipped
        """
        if resource.get("kind") != "Pod":
            return False

        template_id = self.node_identity.get_pod_template_id(resource)
        if not template_id:
            return False

        if template_id in self._pod_templates:
            logger.debug(
                f"Sampling pod {resource.get('metadata', {}).get('name', 'unknown')} "
                f"(template: {template_id})"
            )
            return True

        self._pod_templates[template_id] = {
            "node_id": node_id,
            "name": resource.get("metadata", {}).get("name"),
            "namespace": resource.get("metadata", {}).get("namespace"),
        }
        return False

    def _get_node_id_from_identifier(self, resource_id: ResourceIdentifier) -> str:
        """
        Generate node ID from ResourceIdentifier.

        For wildcard selectors (e.g., Pod:*[app=nginx]), returns the selector string.
        For regular resources, returns kind:namespace:name format.

        Args:
            resource_id: Resource identifier

        Returns:
            Node ID string
        """
        namespace = resource_id.namespace or "cluster"
        return f"{resource_id.kind}:{namespace}:{resource_id.name}"

    def get_permission_errors(self) -> list[str]:
        """
        Get list of resources that couldn't be accessed due to permissions.

        Returns:
            List of resource descriptions that had permission errors
        """
        return self._permission_errors.copy()

    def get_discovery_stats(self) -> dict[str, Any]:
        """
        Get statistics about relationship discovery.

        Returns:
            Dictionary with discovery statistics
        """
        return self.unified_discoverer.get_discovery_stats()

    def get_pod_sampling_info(self) -> dict[str, Any]:
        """
        Get information about pod template sampling.

        Returns:
            Dictionary with pod sampling information including:
            - sampled_count: Number of pod templates
            - total_count: Estimated total pods represented
            - templates: List of template information
        """
        total_count = len(self._pod_templates) * 3
        return {
            "sampled_count": len(self._pod_templates),
            "total_count": total_count,
            "templates": list(self._pod_templates.values()),
        }
