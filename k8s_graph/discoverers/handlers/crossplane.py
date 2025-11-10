import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class CrossplaneHandler(BaseCRDHandler):
    def get_crd_kinds(self) -> list[str]:
        return ["Composition", "CompositeResourceDefinition"]

    def get_crd_info(self, kind: str) -> dict[str, str] | None:
        crd_map = {
            "Composition": {
                "group": "apiextensions.crossplane.io",
                "version": "v1",
                "plural": "compositions",
            },
            "CompositeResourceDefinition": {
                "group": "apiextensions.crossplane.io",
                "version": "v1",
                "plural": "compositeresourcedefinitions",
            },
        }
        return crd_map.get(kind)

    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")
        annotations = resource.get("metadata", {}).get("annotations", {})

        return (
            (kind in self.get_crd_kinds() and "crossplane.io" in api_version)
            or "crossplane.io/claim-name" in annotations
            or "crossplane.io/claim-namespace" in annotations
        )

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []

        try:
            kind = resource.get("kind")
            metadata = resource.get("metadata", {})
            annotations = metadata.get("annotations", {})
            source_id = self._extract_resource_identifier(resource)

            namespace = metadata.get("namespace")

            claim_name = annotations.get("crossplane.io/claim-name")
            claim_namespace = annotations.get("crossplane.io/claim-namespace")

            if claim_name and claim_namespace and self.client:
                try:
                    resources, _ = await self.client.list_resources(
                        kind=kind,
                        namespace=claim_namespace,
                    )

                    for res in resources:
                        res_metadata = res.get("metadata", {})
                        if res_metadata.get("name") == claim_name:
                            relationships.append(
                                ResourceRelationship(
                                    source=ResourceIdentifier(
                                        kind=kind,
                                        name=claim_name,
                                        namespace=claim_namespace,
                                    ),
                                    target=source_id,
                                    relationship_type=RelationshipType.CROSSPLANE_PROVISION,
                                    details="Crossplane claim provisions resource",
                                )
                            )
                            break
                except Exception as e:
                    logger.debug(f"Error finding Crossplane claim: {e}")

            if kind == "Composition" and self.client:
                try:
                    all_resources_kinds = [
                        "Deployment",
                        "Service",
                        "ConfigMap",
                        "Secret",
                        "StatefulSet",
                    ]

                    for res_kind in all_resources_kinds:
                        resources, _ = await self.client.list_resources(
                            kind=res_kind,
                            namespace=namespace,
                        )

                        for res in resources:
                            res_annotations = res.get("metadata", {}).get("annotations", {})
                            res_labels = res.get("metadata", {}).get("labels", {})

                            if res_annotations.get(
                                "crossplane.io/composition-resource-name"
                            ) or res_labels.get("crossplane.io/composite"):
                                relationships.append(
                                    ResourceRelationship(
                                        source=source_id,
                                        target=ResourceIdentifier(
                                            kind=res_kind,
                                            name=res.get("metadata", {}).get("name"),
                                            namespace=namespace,
                                        ),
                                        relationship_type=RelationshipType.CROSSPLANE_PROVISION,
                                        details="Composition provisions resource",
                                    )
                                )
                except Exception as e:
                    logger.debug(f"Error finding Crossplane managed resources: {e}")

        except Exception as e:
            logger.error(f"Error in CrossplaneHandler.discover(): {e}", exc_info=True)
            return []

        return relationships
