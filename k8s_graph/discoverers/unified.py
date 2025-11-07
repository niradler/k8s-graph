import asyncio
import logging
from typing import Any

from k8s_graph.discoverers.registry import DiscovererRegistry
from k8s_graph.models import DiscovererCategory, DiscoveryOptions, ResourceRelationship
from k8s_graph.protocols import K8sClientProtocol

logger = logging.getLogger(__name__)


class UnifiedDiscoverer:
    """
    Orchestrates all registered discoverers to find resource relationships.

    The UnifiedDiscoverer queries the registry for appropriate discoverers
    and coordinates their execution, collecting all discovered relationships.

    Features:
    - Parallel discovery execution (using asyncio.gather)
    - Graceful error handling (one failing discoverer doesn't break others)
    - Filtering based on DiscoveryOptions
    - Statistics collection

    Example:
        >>> from k8s_graph import UnifiedDiscoverer, DiscovererRegistry
        >>> registry = DiscovererRegistry.get_global()
        >>> unified = UnifiedDiscoverer(client, registry)
        >>> relationships = await unified.discover_all_relationships(resource)
    """

    def __init__(
        self, client: K8sClientProtocol, registry: DiscovererRegistry | None = None
    ) -> None:
        """
        Initialize the unified discoverer.

        Args:
            client: K8s client for API access
            registry: Optional discoverer registry (uses global if None)
        """
        self.client = client
        self.registry = registry or DiscovererRegistry.get_global()
        self._discovery_stats: dict[str, Any] = {
            "discoveries": 0,
            "errors": 0,
            "total_relationships": 0,
        }

    async def discover_all_relationships(
        self,
        resource: dict[str, Any],
        options: DiscoveryOptions | None = None,
    ) -> list[ResourceRelationship]:
        """
        Discover all relationships for a resource using registered discoverers.

        Args:
            resource: Kubernetes resource dictionary
            options: Optional discovery options to filter discoverers

        Returns:
            List of all discovered relationships

        Example:
            >>> resource = {"kind": "Pod", "metadata": {"name": "nginx"}}
            >>> options = DiscoveryOptions(include_rbac=True, include_network=True)
            >>> relationships = await unified.discover_all_relationships(resource, options)
        """
        if options is None:
            options = DiscoveryOptions()

        discoverers = self.registry.get_discoverers_for_resource(resource)

        if not discoverers:
            return []

        filtered_discoverers = self._filter_discoverers(discoverers, resource, options)

        if not filtered_discoverers:
            logger.debug(f"No discoverers matched filters for {resource.get('kind')}")
            return []

        tasks = []
        for discoverer in filtered_discoverers:
            tasks.append(self._safe_discover(discoverer, resource))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_relationships: list[ResourceRelationship] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Discoverer {filtered_discoverers[i].__class__.__name__} "
                    f"failed with exception: {result}"
                )
                self._discovery_stats["errors"] += 1
            elif isinstance(result, list):
                all_relationships.extend(result)
                self._discovery_stats["discoveries"] += 1

        self._discovery_stats["total_relationships"] += len(all_relationships)

        return all_relationships

    def _filter_discoverers(
        self,
        discoverers: list[Any],
        resource: dict[str, Any],
        options: DiscoveryOptions,
    ) -> list[Any]:
        """
        Filter discoverers based on discovery options using category flags.

        Args:
            discoverers: List of discoverers
            resource: Resource being discovered
            options: Discovery options

        Returns:
            Filtered list of discoverers
        """
        filtered = []

        for discoverer in discoverers:
            categories = discoverer.categories

            if (categories & DiscovererCategory.RBAC) and not options.include_rbac:
                logger.debug(f"Skipping {discoverer.__class__.__name__} (RBAC category disabled)")
                continue

            if (categories & DiscovererCategory.NETWORK) and not options.include_network:
                logger.debug(
                    f"Skipping {discoverer.__class__.__name__} (Network category disabled)"
                )
                continue

            if (categories & DiscovererCategory.CRD) and not options.include_crds:
                logger.debug(f"Skipping {discoverer.__class__.__name__} (CRD category disabled)")
                continue

            filtered.append(discoverer)

        return filtered

    async def _safe_discover(
        self, discoverer: Any, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        """
        Safely execute a discoverer, catching and logging exceptions.

        Injects the client into the discoverer if it doesn't have one,
        enabling discoverers to query for child resources.

        Args:
            discoverer: Discoverer instance
            resource: Resource to discover relationships for

        Returns:
            List of relationships or empty list on error
        """
        try:
            # Inject client if discoverer doesn't have one
            # This allows registry discoverers to access the K8s API
            if hasattr(discoverer, "client") and discoverer.client is None:
                discoverer.client = self.client
                logger.debug(f"Injected client into {discoverer.__class__.__name__}")

            relationships = await discoverer.discover(resource)
            logger.debug(
                f"{discoverer.__class__.__name__} found {len(relationships)} relationships "
                f"for {resource.get('kind')}/{resource.get('metadata', {}).get('name', 'unknown')}"
            )
            return relationships  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Error in {discoverer.__class__.__name__}.discover(): {e}", exc_info=True)
            return []

    def get_discovery_stats(self) -> dict[str, Any]:
        """
        Get statistics about discovery operations.

        Returns:
            Dictionary with discovery statistics

        Example:
            >>> stats = unified.get_discovery_stats()
            >>> print(f"Total discoveries: {stats['discoveries']}")
            >>> print(f"Total relationships found: {stats['total_relationships']}")
        """
        return self._discovery_stats.copy()

    def reset_stats(self) -> None:
        """
        Reset discovery statistics.

        Useful when starting a new graph build operation.
        """
        self._discovery_stats = {
            "discoveries": 0,
            "errors": 0,
            "total_relationships": 0,
        }
