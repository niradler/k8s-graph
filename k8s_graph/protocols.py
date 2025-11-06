from typing import Any, Protocol, runtime_checkable

from k8s_graph.models import ResourceIdentifier, ResourceRelationship


@runtime_checkable
class K8sClientProtocol(Protocol):
    """
    Protocol for Kubernetes client implementations.

    This protocol defines the interface for accessing Kubernetes resources.
    Users can implement this protocol to add caching, proxying, rate limiting,
    or any other custom behavior.

    Example:
        class CachedK8sClient:
            def __init__(self, upstream_client):
                self.upstream = upstream_client
                self.cache = {}

            async def get_resource(
                self, resource_id: ResourceIdentifier
            ) -> Optional[Dict[str, Any]]:
                cache_key = f"{resource_id.kind}:{resource_id.namespace}:{resource_id.name}"
                if cache_key in self.cache:
                    return self.cache[cache_key]

                resource = await self.upstream.get_resource(resource_id)
                if resource:
                    self.cache[cache_key] = resource
                return resource

            async def list_resources(
                self, kind: str, namespace: Optional[str] = None,
                label_selector: Optional[str] = None
            ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
                return await self.upstream.list_resources(kind, namespace, label_selector)
    """

    async def get_resource(self, resource_id: ResourceIdentifier) -> dict[str, Any] | None:
        """
        Get a single resource by identifier.

        Args:
            resource_id: Identifier for the resource to retrieve

        Returns:
            Resource as a dictionary if found, None otherwise

        Raises:
            Exception: For errors other than "not found" (404)
        """
        ...

    async def list_resources(
        self,
        kind: str,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        List resources of a specific kind.

        Args:
            kind: Resource kind to list (e.g., 'Pod', 'Service')
            namespace: Optional namespace filter. If None, lists across all namespaces
            label_selector: Optional label selector (e.g., 'app=nginx,env=prod')

        Returns:
            Tuple of (resources list, metadata dict)
            - resources: List of resource dictionaries
            - metadata: Dict with pagination info (resourceVersion, continue token, etc.)

        Raises:
            Exception: For API errors
        """
        ...


@runtime_checkable
class DiscovererProtocol(Protocol):
    """
    Protocol for relationship discoverers.

    Discoverers are responsible for finding relationships between Kubernetes resources.
    They can be registered with the DiscovererRegistry to extend k8s-graph with
    support for custom resources or override built-in behavior.

    Example:
        class MyCustomDiscoverer:
            def __init__(self, client: K8sClientProtocol):
                self.client = client

            def supports(self, resource: Dict[str, Any]) -> bool:
                return (
                    resource.get("kind") == "MyCustomResource" and
                    "mycompany.io" in resource.get("apiVersion", "")
                )

            async def discover(
                self, resource: Dict[str, Any]
            ) -> List[ResourceRelationship]:
                relationships = []
                # Your discovery logic here
                return relationships

            @property
            def priority(self) -> int:
                return 100  # User handlers default to 100

        # Register with global registry
        from k8s_graph import DiscovererRegistry
        registry = DiscovererRegistry.get_global()
        registry.register(MyCustomDiscoverer(client))
    """

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        """
        Discover relationships for a resource.

        Args:
            resource: Kubernetes resource as a dictionary (with kind, metadata, spec, etc.)

        Returns:
            List of discovered relationships

        Note:
            Discoverers should not raise exceptions. If an error occurs during discovery,
            log the error and return an empty list. This ensures that one failing discoverer
            doesn't break the entire discovery process.
        """
        ...

    def supports(self, resource: dict[str, Any]) -> bool:
        """
        Check if this discoverer supports the given resource.

        Args:
            resource: Kubernetes resource as a dictionary

        Returns:
            True if this discoverer can discover relationships for this resource type

        Note:
            This method should be fast as it's called for every resource.
            Typically checks resource.get("kind") and optionally resource.get("apiVersion").
        """
        ...

    @property
    def priority(self) -> int:
        """
        Priority for this discoverer (higher values run first).

        Returns:
            Priority value. Convention:
            - User-defined handlers: 100 (highest priority, can override built-ins)
            - Built-in handlers: 50 (standard priority)
            - Fallback handlers: 10 (lowest priority)
        """
        ...
