import logging
from typing import Any

from k8s_graph.discoverers.base import BaseDiscoverer
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship
from k8s_graph.protocols import K8sClientProtocol

logger = logging.getLogger(__name__)


class RBACDiscoverer(BaseDiscoverer):
    """
    Discoverer for RBAC (Role-Based Access Control) relationships.

    Handles relationships between:
    - ServiceAccount <-> Role
    - ServiceAccount <-> ClusterRole
    - RoleBinding -> ServiceAccount + Role
    - ClusterRoleBinding -> ServiceAccount + ClusterRole
    """

    def __init__(self, client: K8sClientProtocol | None = None) -> None:
        super().__init__(client)

    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind", "")
        return kind in [
            "RoleBinding",
            "ClusterRoleBinding",
            "ServiceAccount",
            "Role",
            "ClusterRole",
        ]

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []
        kind = resource.get("kind")

        if kind == "RoleBinding":
            relationships.extend(self._discover_role_binding_relationships(resource))
        elif kind == "ClusterRoleBinding":
            relationships.extend(self._discover_cluster_role_binding_relationships(resource))

        return relationships

    def _discover_role_binding_relationships(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        role_ref = resource.get("roleRef", {})
        role_kind = role_ref.get("kind")
        role_name = role_ref.get("name")

        if role_kind and role_name:
            target = ResourceIdentifier(
                kind=role_kind,
                name=role_name,
                namespace=source.namespace,
                api_version=role_ref.get("apiGroup"),
            )
            relationships.append(
                ResourceRelationship(
                    source=source,
                    target=target,
                    relationship_type=RelationshipType.ROLE_BINDING,
                    details=f"Binds {role_kind} to subjects",
                )
            )

        subjects = resource.get("subjects", [])
        for subject in subjects:
            subject_kind = subject.get("kind")
            subject_name = subject.get("name")
            subject_namespace = subject.get("namespace", source.namespace)

            if subject_kind == "ServiceAccount" and subject_name:
                target = ResourceIdentifier(
                    kind="ServiceAccount",
                    name=subject_name,
                    namespace=subject_namespace,
                )
                relationships.append(
                    ResourceRelationship(
                        source=source,
                        target=target,
                        relationship_type=RelationshipType.ROLE_BINDING,
                        details="Grants permissions to ServiceAccount",
                    )
                )

        return relationships

    def _discover_cluster_role_binding_relationships(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        role_ref = resource.get("roleRef", {})
        role_kind = role_ref.get("kind")
        role_name = role_ref.get("name")

        if role_kind and role_name:
            target = ResourceIdentifier(
                kind=role_kind,
                name=role_name,
                namespace=None,
                api_version=role_ref.get("apiGroup"),
            )
            relationships.append(
                ResourceRelationship(
                    source=source,
                    target=target,
                    relationship_type=RelationshipType.CLUSTER_ROLE_BINDING,
                    details=f"Binds {role_kind} to subjects cluster-wide",
                )
            )

        subjects = resource.get("subjects", [])
        for subject in subjects:
            subject_kind = subject.get("kind")
            subject_name = subject.get("name")
            subject_namespace = subject.get("namespace")

            if subject_kind == "ServiceAccount" and subject_name:
                target = ResourceIdentifier(
                    kind="ServiceAccount",
                    name=subject_name,
                    namespace=subject_namespace,
                )
                relationships.append(
                    ResourceRelationship(
                        source=source,
                        target=target,
                        relationship_type=RelationshipType.CLUSTER_ROLE_BINDING,
                        details="Grants cluster-wide permissions to ServiceAccount",
                    )
                )

        return relationships
