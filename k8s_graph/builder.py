import logging
from typing import Any

import networkx as nx

from k8s_graph.discoverers.registry import DiscovererRegistry
from k8s_graph.discoverers.unified import UnifiedDiscoverer
from k8s_graph.models import BuildOptions, DiscoveryOptions, RelationshipType, ResourceIdentifier
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
        self._resource_cache: dict[tuple[str, str | None], list[dict[str, Any]]] = {}

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
        # Generate node ID
        if not options.sample_pods and resource.get("kind") == "Pod":
            metadata = resource.get("metadata", {})
            namespace = metadata.get("namespace") or "cluster"
            node_id = f"Pod:{namespace}:{metadata.get('name')}"
        else:
            node_id = self.node_identity.get_node_id(resource)

        if graph.number_of_nodes() >= options.max_nodes:
            logger.debug(f"Reached max_nodes limit of {options.max_nodes}")
            return

        if options.sample_pods and self._should_sample_pod(resource, node_id):
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

            # Collect resources to fetch and create edges
            # Note: We only add edges here, not nodes - nodes will be added when we fetch the actual resources
            # This prevents duplicate nodes with different IDs
            resources_to_fetch: list[ResourceIdentifier] = []
            pending_edges: list[
                tuple[ResourceIdentifier, ResourceIdentifier, RelationshipType, str | None]
            ] = []

            current_kind = resource.get("kind")
            current_name = resource.get("metadata", {}).get("name")

            for rel in relationships:
                # Handle label selector relationships (Service -> Pod via labels)
                if rel.target.name.startswith("*[") and rel.target.name.endswith("]"):
                    # This is a label selector - resolve to actual pods
                    label_selector_str = rel.target.name[2:-1]  # Extract "app=redis"
                    try:
                        pods, _ = await self.client.list_resources(
                            kind="Pod",
                            namespace=rel.target.namespace,
                            label_selector=label_selector_str,
                        )

                        # Create edges to each matching pod
                        for pod in pods:
                            pod_metadata = pod.get("metadata", {})
                            pod_name = pod_metadata.get("name")
                            if pod_name:
                                pod_id = ResourceIdentifier(
                                    kind="Pod", name=pod_name, namespace=rel.target.namespace
                                )
                                pending_edges.append(
                                    (rel.source, pod_id, rel.relationship_type, rel.details)
                                )
                                if graph.number_of_nodes() < options.max_nodes:
                                    resources_to_fetch.append(pod_id)
                    except Exception as e:
                        logger.debug(f"Failed to resolve label selector {label_selector_str}: {e}")
                else:
                    # Regular relationship - store edge info to add later
                    pending_edges.append(
                        (rel.source, rel.target, rel.relationship_type, rel.details)
                    )

                    # Collect resources to fetch
                    if graph.number_of_nodes() < options.max_nodes:
                        resources_to_fetch.append(rel.target)
                        if rel.source.kind != current_kind or rel.source.name != current_name:
                            resources_to_fetch.append(rel.source)

            # Batch fetch resources by kind/namespace
            fetched_resources = await self._batch_fetch_resources(resources_to_fetch)

            # Add fetched resources as nodes (with proper stable IDs)
            resource_id_map: dict[tuple[str, str | None, str], str] = {}
            for res_id, resource_data in fetched_resources.items():
                if resource_data:
                    if not options.sample_pods and resource_data.get("kind") == "Pod":
                        metadata = resource_data.get("metadata", {})
                        namespace = metadata.get("namespace") or "cluster"
                        stable_node_id = f"Pod:{namespace}:{metadata.get('name')}"
                    else:
                        stable_node_id = self.node_identity.get_node_id(resource_data)
                    
                    resource_id_map[res_id] = stable_node_id

                    if not graph.has_node(stable_node_id):
                        attrs = self.node_identity.extract_node_attributes(resource_data)
                        graph.add_node(stable_node_id, **attrs)

            # Add edges using stable node IDs - only for nodes that exist in the graph
            for source_id, target_id, rel_type, details in pending_edges:
                source_key = self._make_resource_key(source_id)
                target_key = self._make_resource_key(target_id)

                # Get stable node IDs from fetched resources
                # If source is the current node, use its node_id
                if source_id.kind == current_kind and source_id.name == current_name:
                    source_node_id = node_id
                else:
                    source_node_id = resource_id_map.get(source_key)  # type: ignore[assignment]

                target_node_id = resource_id_map.get(target_key)

                # CRITICAL FIX: If we don't have the node ID from resource_id_map,
                # try to find it by looking through all graph nodes
                # This handles cases where NodeIdentity generates different IDs
                if not source_node_id and source_id.kind and source_id.name:
                    for gnode_id, gattrs in graph.nodes(data=True):
                        if (
                            gattrs.get("kind") == source_id.kind
                            and gattrs.get("name") == source_id.name
                            and gattrs.get("namespace") == source_id.namespace
                        ):
                            source_node_id = gnode_id
                            break

                if not target_node_id and target_id.kind and target_id.name:
                    for gnode_id, gattrs in graph.nodes(data=True):
                        if (
                            gattrs.get("kind") == target_id.kind
                            and gattrs.get("name") == target_id.name
                            and gattrs.get("namespace") == target_id.namespace
                        ):
                            target_node_id = gnode_id
                            break

                # Only add edge if both nodes exist (have been fetched and added)
                if source_node_id and target_node_id:
                    if graph.has_node(source_node_id) and graph.has_node(target_node_id):
                        if not graph.has_edge(source_node_id, target_node_id):
                            graph.add_edge(
                                source_node_id,
                                target_node_id,
                                relationship_type=rel_type.value,
                                details=details,
                            )
                            logger.debug(
                                f"Added edge: {source_node_id} --[{rel_type.value}]--> {target_node_id}"
                            )

            # Expand from fetched resources
            for res_key, resource_data in fetched_resources.items():
                if resource_data:
                    stable_node_id = resource_id_map.get(res_key)  # type: ignore[assignment]
                    if (
                        stable_node_id
                        and stable_node_id not in visited
                        and graph.number_of_nodes() < options.max_nodes
                    ):
                        await self._expand_from_node(
                            graph, resource_data, depth - 1, visited, options
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

    def _make_resource_key(self, resource_id: ResourceIdentifier) -> tuple[str, str | None, str]:
        """Make a cache key from resource identifier."""
        return (resource_id.kind, resource_id.namespace, resource_id.name)

    async def _batch_fetch_resources(
        self, resource_ids: list[ResourceIdentifier]
    ) -> dict[tuple[str, str | None, str], dict[str, Any]]:
        """
        Batch fetch resources using list_resources instead of individual get_resource calls.

        Groups resources by (kind, namespace) and fetches them in batches.

        Args:
            resource_ids: List of resource identifiers to fetch

        Returns:
            Dictionary mapping (kind, namespace, name) to resource dict
        """
        if not resource_ids:
            return {}

        # Group by (kind, namespace)
        groups: dict[tuple[str, str | None], set[str]] = {}
        for res_id in resource_ids:
            key = (res_id.kind, res_id.namespace)
            if key not in groups:
                groups[key] = set()
            groups[key].add(res_id.name)

        fetched: dict[tuple[str, str | None, str], dict[str, Any]] = {}

        # Fetch each group using list_resources (with caching to avoid duplicate calls)
        for (kind, namespace), names in groups.items():
            cache_key = (kind, namespace)

            # Check if we already fetched this kind/namespace
            if cache_key not in self._resource_cache:
                try:
                    resources, _ = await self.client.list_resources(kind, namespace)
                    self._resource_cache[cache_key] = resources
                    logger.debug(
                        f"Cached {len(resources)} {kind} resources in namespace {namespace}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to list {kind} in namespace {namespace}: {e}")
                    self._resource_cache[cache_key] = []

            # Get from cache
            resources = self._resource_cache[cache_key]

            # Filter to only the names we need
            for resource in resources:
                res_metadata = resource.get("metadata", {})
                res_name = res_metadata.get("name")

                if res_name in names:
                    fetch_key = (kind, namespace, res_name)
                    fetched[fetch_key] = resource

            # Check if any names were not found and fall back to get_resource
            found_names = {
                res.get("metadata", {}).get("name")
                for res in resources
                if res.get("metadata", {}).get("name") in names
            }
            missing_names = names - found_names

            if missing_names:

                # Fall back to individual get_resource for missing names
                for name in missing_names:
                    try:
                        res_id = ResourceIdentifier(kind=kind, name=name, namespace=namespace)
                        resource = await self.client.get_resource(res_id)  # type: ignore[assignment]
                        if resource:
                            fetch_key = (kind, namespace, name)
                            fetched[fetch_key] = resource
                    except Exception as inner_e:
                        logger.debug(f"Failed to get {kind}/{name}: {inner_e}")

        return fetched

    def get_pod_sampling_info(self) -> dict[str, Any]:
        """
        Get information about pod template sampling.

        Only relevant when BuildOptions.sample_pods=True. Returns statistics
        about how many unique pod templates were found vs estimated total pods.

        Returns:
            Dictionary with pod sampling information including:
            - sampled_count: Number of unique pod templates found
            - total_count: Estimated total pods represented (templates * avg replicas)
            - templates: List of template information (pod names shown)

        Note:
            Returns zeros if sample_pods=False (no sampling performed).
        """
        if not self._pod_templates:
            return {
                "sampled_count": 0,
                "total_count": 0,
                "templates": [],
            }

        total_count = len(self._pod_templates) * 3
        return {
            "sampled_count": len(self._pod_templates),
            "total_count": total_count,
            "templates": list(self._pod_templates.values()),
        }
