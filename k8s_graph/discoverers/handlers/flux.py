import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class FluxCDHandler(BaseCRDHandler):
    def get_crd_kinds(self) -> list[str]:
        return ["HelmRelease", "Kustomization"]

    def get_crd_info(self, kind: str) -> dict[str, str] | None:
        crd_map = {
            "HelmRelease": {
                "group": "helm.toolkit.fluxcd.io",
                "version": "v2beta1",
                "plural": "helmreleases",
            },
            "Kustomization": {
                "group": "kustomize.toolkit.fluxcd.io",
                "version": "v1",
                "plural": "kustomizations",
            },
        }
        return crd_map.get(kind)

    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")

        return (
            kind in ["HelmRelease", "Kustomization", "GitRepository", "HelmRepository"]
            and "fluxcd.io" in api_version
        )

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []

        try:
            kind = resource.get("kind")
            metadata = resource.get("metadata", {})
            spec = resource.get("spec", {})
            source_id = self._extract_resource_identifier(resource)

            namespace = metadata.get("namespace")
            name = metadata.get("name")

            if kind in ["HelmRelease", "Kustomization"] and self.client and namespace:
                label_selector = {
                    "kustomize.toolkit.fluxcd.io/name": name,
                }

                for res_kind in [
                    "Deployment",
                    "StatefulSet",
                    "DaemonSet",
                    "Service",
                    "ConfigMap",
                    "Secret",
                ]:
                    try:
                        resources = await self._find_resources_by_label(
                            kind=res_kind,
                            namespace=namespace,
                            label_selector=label_selector,
                        )

                        for res in resources:
                            res_metadata = res.get("metadata", {})
                            relationships.append(
                                ResourceRelationship(
                                    source=source_id,
                                    target=ResourceIdentifier(
                                        kind=res_kind,
                                        name=res_metadata.get("name"),
                                        namespace=namespace,
                                    ),
                                    relationship_type=RelationshipType.FLUX_MANAGED,
                                    details=f"Managed by Flux {kind} {name}",
                                )
                            )
                    except Exception as e:
                        logger.debug(f"Error finding Flux-managed {res_kind}: {e}")

            if kind == "HelmRelease":
                chart = spec.get("chart", {})
                source_ref = chart.get("spec", {}).get("sourceRef", {})

                if source_ref:
                    source_kind = source_ref.get("kind", "HelmRepository")
                    source_name = source_ref.get("name")
                    source_namespace = source_ref.get("namespace", namespace)

                    if source_name and self.client:
                        try:
                            source_resource = await self.client.get_resource(
                                ResourceIdentifier(
                                    kind=source_kind,
                                    name=source_name,
                                    namespace=source_namespace,
                                )
                            )

                            if source_resource:
                                relationships.append(
                                    ResourceRelationship(
                                        source=source_id,
                                        target=ResourceIdentifier(
                                            kind=source_kind,
                                            name=source_name,
                                            namespace=source_namespace,
                                        ),
                                        relationship_type=RelationshipType.MANAGED,
                                        details="Helm chart source",
                                    )
                                )
                        except Exception as e:
                            logger.debug(f"Error finding Flux source: {e}")

            elif kind == "Kustomization":
                source_ref = spec.get("sourceRef", {})

                if source_ref:
                    source_kind = source_ref.get("kind", "GitRepository")
                    source_name = source_ref.get("name")
                    source_namespace = source_ref.get("namespace", namespace)

                    if source_name and self.client:
                        try:
                            source_resource = await self.client.get_resource(
                                ResourceIdentifier(
                                    kind=source_kind,
                                    name=source_name,
                                    namespace=source_namespace,
                                )
                            )

                            if source_resource:
                                relationships.append(
                                    ResourceRelationship(
                                        source=source_id,
                                        target=ResourceIdentifier(
                                            kind=source_kind,
                                            name=source_name,
                                            namespace=source_namespace,
                                        ),
                                        relationship_type=RelationshipType.MANAGED,
                                        details="Git repository source",
                                    )
                                )
                        except Exception as e:
                            logger.debug(f"Error finding Flux source: {e}")

        except Exception as e:
            logger.error(f"Error in FluxCDHandler.discover(): {e}", exc_info=True)
            return []

        return relationships
