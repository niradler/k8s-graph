"""
CRD Registry for automatic CRD discovery and registration.

This module provides a centralized registry for Custom Resource Definitions (CRDs)
that are supported by the handlers. It automatically discovers CRD information from
registered handlers and makes it available to the KubernetesAdapter.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CRDRegistry:
    """
    Registry for Custom Resource Definitions.

    Automatically discovers CRD information from handlers and provides
    it to the KubernetesAdapter for fetching CRD resources.

    Example:
        >>> from k8s_graph import CRDRegistry
        >>> from k8s_graph.discoverers.handlers import get_all_handlers
        >>>
        >>> registry = CRDRegistry.get_global()
        >>> for handler in get_all_handlers():
        ...     registry.register_handler(handler)
        >>>
        >>> # Get CRD info for fetching
        >>> info = registry.get_crd_info("Application")
        >>> # {'group': 'argoproj.io', 'version': 'v1alpha1', 'plural': 'applications'}
    """

    _global_registry: "CRDRegistry | None" = None

    def __init__(self) -> None:
        """Initialize empty CRD registry."""
        self._crd_mapping: dict[str, dict[str, str]] = {}
        self._initialized = False

    @classmethod
    def get_global(cls) -> "CRDRegistry":
        """
        Get the global singleton CRD registry.

        Returns:
            Global CRDRegistry instance
        """
        if cls._global_registry is None:
            cls._global_registry = cls()
        return cls._global_registry

    def register_handler(self, handler: Any) -> None:
        """
        Register a CRD handler and extract its CRD information.

        Args:
            handler: Handler instance (should have get_crd_kinds() and get_crd_info() methods)
        """
        if not hasattr(handler, "get_crd_kinds") or not hasattr(handler, "get_crd_info"):
            return

        try:
            crd_kinds = handler.get_crd_kinds()

            for kind in crd_kinds:
                crd_info = handler.get_crd_info(kind)

                if crd_info and all(k in crd_info for k in ["group", "version", "plural"]):
                    if kind in self._crd_mapping:
                        existing = self._crd_mapping[kind]
                        if existing != crd_info:
                            logger.warning(
                                f"CRD {kind} already registered with different info. "
                                f"Existing: {existing}, New: {crd_info}. Keeping existing."
                            )
                    else:
                        self._crd_mapping[kind] = crd_info
                        logger.debug(
                            f"Registered CRD {kind}: {crd_info['group']}/{crd_info['version']}"
                        )

        except Exception as e:
            logger.warning(f"Error registering CRDs from handler {handler.__class__.__name__}: {e}")

    def get_crd_info(self, kind: str) -> dict[str, str] | None:
        """
        Get CRD information for a specific kind.

        Args:
            kind: CRD kind name (e.g., "Application")

        Returns:
            Dict with 'group', 'version', 'plural' or None if not registered
        """
        return self._crd_mapping.get(kind)

    def list_registered_kinds(self) -> list[str]:
        """
        List all registered CRD kinds.

        Returns:
            List of CRD kind names
        """
        return list(self._crd_mapping.keys())

    def is_crd_registered(self, kind: str) -> bool:
        """
        Check if a CRD kind is registered.

        Args:
            kind: CRD kind name

        Returns:
            True if registered, False otherwise
        """
        return kind in self._crd_mapping

    def clear(self) -> None:
        """Clear all registered CRDs."""
        self._crd_mapping.clear()
        self._initialized = False
        logger.debug("CRD registry cleared")

    def get_all_crd_info(self) -> dict[str, dict[str, str]]:
        """
        Get all registered CRD information.

        Returns:
            Dictionary mapping kind names to CRD info
        """
        return self._crd_mapping.copy()
