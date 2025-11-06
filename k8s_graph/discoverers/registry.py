import logging
from typing import Any, Optional

from k8s_graph.protocols import DiscovererProtocol

logger = logging.getLogger(__name__)


class DiscovererRegistry:
    """
    Registry for relationship discoverers with priority-based selection.

    The registry maintains a collection of discoverers and provides methods to
    register new discoverers and retrieve appropriate discoverers for resources.

    Features:
    - Singleton global registry for convenience
    - Per-instance registries for custom configurations
    - Priority-based sorting (higher priority runs first)
    - Override support (specific kind overrides general discoverers)

    Example:
        # Use global registry
        >>> from k8s_graph import DiscovererRegistry, BaseDiscoverer
        >>> registry = DiscovererRegistry.get_global()

        # Register a custom discoverer
        >>> class MyDiscoverer(BaseDiscoverer):
        ...     def supports(self, resource):
        ...         return resource.get("kind") == "MyResource"
        ...     async def discover(self, resource):
        ...         return []
        ...     @property
        ...     def priority(self):
        ...         return 100
        >>> registry.register(MyDiscoverer(client))

        # Or override a specific kind
        >>> registry.register(MyDiscoverer(client), resource_kind="MyResource")
    """

    _global_registry: Optional["DiscovererRegistry"] = None

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._discoverers: list[DiscovererProtocol] = []
        self._overrides: dict[str, DiscovererProtocol] = {}
        self._initialized = False

    @classmethod
    def get_global(cls) -> "DiscovererRegistry":
        """
        Get the global singleton registry.

        The global registry automatically registers built-in discoverers on first access.

        Returns:
            Global DiscovererRegistry instance
        """
        if cls._global_registry is None:
            cls._global_registry = cls()
            cls._global_registry._register_builtin()
        return cls._global_registry

    def register(self, discoverer: DiscovererProtocol, resource_kind: str | None = None) -> None:
        """
        Register a discoverer.

        Args:
            discoverer: Discoverer instance implementing DiscovererProtocol
            resource_kind: Optional specific kind to handle (e.g., "Application").
                          If provided, this discoverer becomes an override for that kind.

        Example:
            # General discoverer (uses supports() method)
            >>> registry.register(MyDiscoverer(client))

            # Override for specific kind (takes precedence over general discoverers)
            >>> registry.register(MyArgoCDHandler(client), resource_kind="Application")
        """
        if resource_kind:
            logger.debug(
                f"Registering override discoverer for kind {resource_kind}: "
                f"{discoverer.__class__.__name__}"
            )
            self._overrides[resource_kind] = discoverer
        else:
            logger.debug(
                f"Registering general discoverer: {discoverer.__class__.__name__} "
                f"(priority: {discoverer.priority})"
            )
            self._discoverers.append(discoverer)

            self._discoverers.sort(key=lambda d: d.priority, reverse=True)

    def get_discoverers_for_resource(self, resource: dict[str, Any]) -> list[DiscovererProtocol]:
        """
        Get all discoverers that can handle a given resource.

        The method first checks for kind-specific overrides, then returns
        general discoverers that support the resource (sorted by priority).

        Args:
            resource: Kubernetes resource dictionary

        Returns:
            List of discoverers that can handle this resource, sorted by priority

        Example:
            >>> resource = {"kind": "Pod", "metadata": {"name": "nginx"}}
            >>> discoverers = registry.get_discoverers_for_resource(resource)
            >>> for discoverer in discoverers:
            ...     relationships = await discoverer.discover(resource)
        """
        kind = resource.get("kind")

        if kind in self._overrides:
            logger.debug(f"Using override discoverer for kind {kind}")
            return [self._overrides[kind]]

        matching = [d for d in self._discoverers if d.supports(resource)]

        if matching:
            logger.debug(
                f"Found {len(matching)} discoverers for {kind}: "
                f"{[d.__class__.__name__ for d in matching]}"
            )
        else:
            logger.debug(f"No discoverers found for {kind}")

        return matching

    def clear(self) -> None:
        """
        Clear all registered discoverers.

        Useful for testing or resetting the registry.
        """
        self._discoverers.clear()
        self._overrides.clear()
        self._initialized = False
        logger.debug("Registry cleared")

    def _register_builtin(self) -> None:
        """
        Register built-in discoverers.

        This method is called automatically by get_global() on first access.
        """
        if self._initialized:
            return

        logger.debug("Registering built-in discoverers")

        from k8s_graph.discoverers.native import NativeResourceDiscoverer
        from k8s_graph.discoverers.network import NetworkPolicyDiscoverer
        from k8s_graph.discoverers.rbac import RBACDiscoverer

        self.register(NativeResourceDiscoverer())
        self.register(RBACDiscoverer())
        self.register(NetworkPolicyDiscoverer())

        self._initialized = True
        logger.info(
            f"Initialized global registry with {len(self._discoverers)} built-in discoverers"
        )

    def list_discoverers(self) -> list[dict[str, Any]]:
        """
        List all registered discoverers with their information.

        Returns:
            List of dictionaries with discoverer information

        Example:
            >>> for info in registry.list_discoverers():
            ...     print(f"{info['name']}: priority {info['priority']}")
        """
        discoverers_info = []

        for discoverer in self._discoverers:
            discoverers_info.append(
                {
                    "name": discoverer.__class__.__name__,
                    "priority": discoverer.priority,
                    "type": "general",
                }
            )

        for kind, discoverer in self._overrides.items():
            discoverers_info.append(
                {
                    "name": discoverer.__class__.__name__,
                    "priority": discoverer.priority,
                    "type": "override",
                    "kind": kind,
                }
            )

        return discoverers_info
