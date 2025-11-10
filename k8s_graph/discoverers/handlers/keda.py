import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class KEDAHandler(BaseCRDHandler):
    def get_crd_kinds(self) -> list[str]:
        return ["ScaledObject", "ScaledJob"]

    def get_crd_info(self, kind: str) -> dict[str, str] | None:
        crd_map = {
            "ScaledObject": {"group": "keda.sh", "version": "v1alpha1", "plural": "scaledobjects"},
            "ScaledJob": {"group": "keda.sh", "version": "v1alpha1", "plural": "scaledjobs"},
        }
        return crd_map.get(kind)

    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")

        return kind in self.get_crd_kinds() and "keda.sh" in api_version

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []

        try:
            metadata = resource.get("metadata", {})
            spec = resource.get("spec", {})
            source_id = self._extract_resource_identifier(resource)

            namespace = metadata.get("namespace")

            scale_target_ref = spec.get("scaleTargetRef", {})
            target_kind = scale_target_ref.get("kind")
            target_name = scale_target_ref.get("name")

            if target_kind and target_name and self.client:
                try:
                    target = await self.client.get_resource(
                        ResourceIdentifier(
                            kind=target_kind,
                            name=target_name,
                            namespace=namespace,
                        )
                    )

                    if target:
                        relationships.append(
                            ResourceRelationship(
                                source=source_id,
                                target=ResourceIdentifier(
                                    kind=target_kind,
                                    name=target_name,
                                    namespace=namespace,
                                ),
                                relationship_type=RelationshipType.KEDA_SCALE,
                                details=f"KEDA scales {target_kind}",
                            )
                        )
                except Exception as e:
                    logger.debug(f"Error finding scale target {target_kind}/{target_name}: {e}")

            triggers = spec.get("triggers", [])
            for trigger in triggers:
                metadata_trigger = trigger.get("metadata", {})

                if "configMapName" in metadata_trigger:
                    cm_name = metadata_trigger["configMapName"]
                    relationships.append(
                        ResourceRelationship(
                            source=source_id,
                            target=ResourceIdentifier(
                                kind="ConfigMap",
                                name=cm_name,
                                namespace=namespace,
                            ),
                            relationship_type=RelationshipType.MANAGED,
                            details="KEDA trigger config",
                        )
                    )

                if "secretName" in metadata_trigger:
                    secret_name = metadata_trigger["secretName"]
                    relationships.append(
                        ResourceRelationship(
                            source=source_id,
                            target=ResourceIdentifier(
                                kind="Secret",
                                name=secret_name,
                                namespace=namespace,
                            ),
                            relationship_type=RelationshipType.MANAGED,
                            details="KEDA trigger credentials",
                        )
                    )

        except Exception as e:
            logger.error(f"Error in KEDAHandler.discover(): {e}", exc_info=True)
            return []

        return relationships
