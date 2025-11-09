import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class KnativeHandler(BaseCRDHandler):
    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")
        
        return (
            kind in ["Service", "Route", "Configuration", "Revision"] and
            ("knative.dev" in api_version or "serving.knative.dev" in api_version)
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
            
            owner_refs = metadata.get("ownerReferences", [])
            for owner_ref in owner_refs:
                if owner_ref.get("kind") in ["Service", "Configuration"]:
                    relationships.append(
                        ResourceRelationship(
                            source=ResourceIdentifier(
                                kind=owner_ref.get("kind"),
                                name=owner_ref.get("name"),
                                namespace=namespace,
                            ),
                            target=source_id,
                            relationship_type=RelationshipType.OWNED,
                            details=f"{owner_ref.get('kind')} owns {kind}",
                        )
                    )
            
            if kind == "Revision" and self.client and namespace:
                label_selector = {
                    "serving.knative.dev/revision": name,
                }
                
                deployments = await self._find_resources_by_label(
                    kind="Deployment",
                    namespace=namespace,
                    label_selector=label_selector,
                )
                
                for deployment in deployments:
                    deployment_metadata = deployment.get("metadata", {})
                    relationships.append(
                        ResourceRelationship(
                            source=source_id,
                            target=ResourceIdentifier(
                                kind="Deployment",
                                name=deployment_metadata.get("name"),
                                namespace=namespace,
                            ),
                            relationship_type=RelationshipType.KNATIVE_SERVES,
                            details="Knative Revision serves traffic via Deployment",
                        )
                    )
            
            elif kind == "Route":
                traffic = spec.get("traffic", [])
                for traffic_target in traffic:
                    revision_name = traffic_target.get("revisionName")
                    if revision_name and self.client:
                        try:
                            revision = await self.client.get_resource(
                                ResourceIdentifier(
                                    kind="Revision",
                                    name=revision_name,
                                    namespace=namespace,
                                )
                            )
                            
                            if revision:
                                relationships.append(
                                    ResourceRelationship(
                                        source=source_id,
                                        target=ResourceIdentifier(
                                            kind="Revision",
                                            name=revision_name,
                                            namespace=namespace,
                                        ),
                                        relationship_type=RelationshipType.KNATIVE_SERVES,
                                        details=f"Route traffic to Revision (weight: {traffic_target.get('percent', 100)}%)",
                                    )
                                )
                        except Exception as e:
                            logger.debug(f"Error finding Revision {revision_name}: {e}")
        
        except Exception as e:
            logger.error(f"Error in KnativeHandler.discover(): {e}", exc_info=True)
            return []
        
        return relationships

