import logging
from abc import ABC, abstractmethod
from typing import Any

from k8s_graph.models import ResourceIdentifier, ResourceRelationship
from k8s_graph.protocols import K8sClientProtocol

logger = logging.getLogger(__name__)


class BaseDiscoverer(ABC):
    """
    Abstract base class for resource relationship discoverers.

    Provides common functionality for all discoverers and enforces the
    DiscovererProtocol interface.

    Subclasses must implement:
    - supports(): Check if this discoverer handles the resource
    - discover(): Find relationships for the resource

    Example:
        >>> class MyDiscoverer(BaseDiscoverer):
        ...     def __init__(self, client):
        ...         super().__init__(client)
        ...
        ...     def supports(self, resource: Dict[str, Any]) -> bool:
        ...         return resource.get("kind") == "MyCustomResource"
        ...
        ...     async def discover(
        ...         self, resource: Dict[str, Any]
        ...     ) -> List[ResourceRelationship]:
        ...         relationships = []
        ...         # Your discovery logic
        ...         return relationships
        ...
        ...     @property
        ...     def priority(self) -> int:
        ...         return 50  # Built-in priority
    """

    def __init__(self, client: K8sClientProtocol | None = None) -> None:
        """
        Initialize the discoverer.

        Args:
            client: Optional K8s client for making API calls during discovery.
                   Can be None for discoverers that only examine the resource itself.
        """
        self.client = client

    @abstractmethod
    def supports(self, resource: dict[str, Any]) -> bool:
        """
        Check if this discoverer supports the given resource.

        Args:
            resource: Kubernetes resource dictionary

        Returns:
            True if this discoverer can discover relationships for this resource
        """
        pass

    @abstractmethod
    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        """
        Discover relationships for a resource.

        Args:
            resource: Kubernetes resource dictionary

        Returns:
            List of discovered relationships

        Note:
            Implementations should catch exceptions and return empty list on error
            rather than propagating exceptions. Log errors for debugging.
        """
        pass

    @property
    def priority(self) -> int:
        """
        Priority for this discoverer.

        Returns:
            Priority value. Default is 50 for built-in discoverers.
            User-defined handlers should return 100.
        """
        return 50

    def _extract_resource_identifier(self, resource: dict[str, Any]) -> ResourceIdentifier:
        """
        Extract ResourceIdentifier from a resource dictionary.

        Args:
            resource: Kubernetes resource dictionary

        Returns:
            ResourceIdentifier for the resource

        Raises:
            ValueError: If resource is missing required fields
        """
        metadata = resource.get("metadata", {})
        kind = resource.get("kind")
        name = metadata.get("name")

        if not kind:
            raise ValueError("Resource missing 'kind' field")
        if not name:
            raise ValueError("Resource missing 'metadata.name' field")

        return ResourceIdentifier(
            kind=kind,
            name=name,
            namespace=metadata.get("namespace"),
            api_version=resource.get("apiVersion"),
        )

    def _parse_label_selector(self, selector: dict[str, str]) -> str:
        """
        Convert label selector dict to K8s label selector string.

        Args:
            selector: Dictionary of labels (e.g., {"app": "nginx", "env": "prod"})

        Returns:
            Label selector string (e.g., "app=nginx,env=prod")

        Example:
            >>> self._parse_label_selector({"app": "nginx", "tier": "frontend"})
            'app=nginx,tier=frontend'
        """
        return ",".join(f"{k}={v}" for k, v in selector.items())

    def _match_labels(self, selector: dict[str, str], labels: dict[str, str]) -> bool:
        """
        Check if labels match a selector.

        Args:
            selector: Selector dictionary (e.g., {"app": "nginx"})
            labels: Labels dictionary to check

        Returns:
            True if all selector labels match

        Example:
            >>> selector = {"app": "nginx"}
            >>> labels = {"app": "nginx", "env": "prod"}
            >>> self._match_labels(selector, labels)
            True
        """
        for key, value in selector.items():
            if labels.get(key) != value:
                return False
        return True

    async def _safe_discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        """
        Safely discover relationships, catching and logging exceptions.

        This is a wrapper around the discover() method that catches exceptions
        and returns an empty list on error.

        Args:
            resource: Kubernetes resource dictionary

        Returns:
            List of relationships or empty list on error
        """
        try:
            return await self.discover(resource)
        except Exception as e:
            metadata = resource.get("metadata", {})
            kind = resource.get("kind", "Unknown")
            name = metadata.get("name", "unknown")
            namespace = metadata.get("namespace", "unknown")

            logger.error(
                f"Error discovering relationships for {kind}/{name} in {namespace} "
                f"with {self.__class__.__name__}: {e}",
                exc_info=True,
            )
            return []
