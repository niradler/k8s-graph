import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class VeleroHandler(BaseCRDHandler):
    def get_crd_kinds(self) -> list[str]:
        return ["Backup", "Restore", "Schedule"]

    def get_crd_info(self, kind: str) -> dict[str, str] | None:
        crd_map = {
            "Backup": {"group": "velero.io", "version": "v1", "plural": "backups"},
            "Restore": {"group": "velero.io", "version": "v1", "plural": "restores"},
            "Schedule": {"group": "velero.io", "version": "v1", "plural": "schedules"},
        }
        return crd_map.get(kind)

    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")

        return kind in self.get_crd_kinds() and "velero.io" in api_version

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []

        try:
            kind = resource.get("kind")
            metadata = resource.get("metadata", {})
            spec = resource.get("spec", {})
            source_id = self._extract_resource_identifier(resource)

            namespace = metadata.get("namespace", "velero")

            if kind == "Backup":
                included_namespaces = spec.get("includedNamespaces", [])

                for ns in included_namespaces:
                    if ns != "*":
                        relationships.append(
                            ResourceRelationship(
                                source=source_id,
                                target=ResourceIdentifier(
                                    kind="Namespace",
                                    name=ns,
                                    namespace=None,
                                ),
                                relationship_type=RelationshipType.VELERO_BACKUP,
                                details=f"Backup includes namespace {ns}",
                            )
                        )

            elif kind == "Schedule" and self.client:
                name = metadata.get("name")
                label_selector = {"velero.io/schedule-name": name}

                backups = await self._find_resources_by_label(
                    kind="Backup",
                    namespace=namespace,
                    label_selector=label_selector,
                )

                for backup in backups:
                    backup_metadata = backup.get("metadata", {})
                    relationships.append(
                        ResourceRelationship(
                            source=source_id,
                            target=ResourceIdentifier(
                                kind="Backup",
                                name=backup_metadata.get("name"),
                                namespace=namespace,
                            ),
                            relationship_type=RelationshipType.OWNED,
                            details="Schedule created Backup",
                        )
                    )

            elif kind == "Restore":
                backup_name = spec.get("backupName")
                if backup_name and self.client:
                    try:
                        backup = await self.client.get_resource(
                            ResourceIdentifier(
                                kind="Backup",
                                name=backup_name,
                                namespace=namespace,
                            )
                        )

                        if backup:
                            relationships.append(
                                ResourceRelationship(
                                    source=source_id,
                                    target=ResourceIdentifier(
                                        kind="Backup",
                                        name=backup_name,
                                        namespace=namespace,
                                    ),
                                    relationship_type=RelationshipType.MANAGED,
                                    details="Restore from Backup",
                                )
                            )
                    except Exception as e:
                        logger.debug(f"Error finding Backup {backup_name}: {e}")

        except Exception as e:
            logger.error(f"Error in VeleroHandler.discover(): {e}", exc_info=True)
            return []

        return relationships
