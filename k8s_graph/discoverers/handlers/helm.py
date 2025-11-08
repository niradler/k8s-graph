import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class HelmHandler(BaseCRDHandler):
    def supports(self, resource: dict[str, Any]) -> bool:
        labels = resource.get("metadata", {}).get("annotations", {})
        return labels.get("meta.helm.sh/release-name") is not None or \
               resource.get("metadata", {}).get("labels", {}).get("app.kubernetes.io/managed-by") == "Helm"

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []
        
        try:
            metadata = resource.get("metadata", {})
            annotations = metadata.get("annotations", {})
            labels = metadata.get("labels", {})
            namespace = metadata.get("namespace")
            
            release_name = annotations.get("meta.helm.sh/release-name") or labels.get("app.kubernetes.io/instance")
            if not release_name:
                return []
            
            source_id = self._extract_resource_identifier(resource)
            
            release_secret_name = f"sh.helm.release.v1.{release_name}"
            
            if self.client and namespace:
                try:
                    secrets, _ = await self.client.list_resources(
                        kind="Secret",
                        namespace=namespace,
                    )
                    
                    for secret in secrets:
                        secret_metadata = secret.get("metadata", {})
                        secret_name = secret_metadata.get("name", "")
                        secret_labels = secret_metadata.get("labels", {})
                        
                        if (secret_name.startswith(release_secret_name) or
                            (secret_labels.get("owner") == "helm" and 
                             secret_labels.get("name") == release_name)):
                            relationships.append(
                                ResourceRelationship(
                                    source=source_id,
                                    target=ResourceIdentifier(
                                        kind="Secret",
                                        name=secret_metadata.get("name"),
                                        namespace=namespace,
                                    ),
                                    relationship_type=RelationshipType.HELM_MANAGED,
                                    details=f"Helm release metadata for {release_name}",
                                )
                            )
                            break
                except Exception as e:
                    logger.debug(f"Error finding Helm release Secret: {e}")
            
            if self.client and namespace and release_name:
                for kind in ["Deployment", "StatefulSet", "DaemonSet", "Service", "ConfigMap", "Ingress"]:
                    try:
                        resources, _ = await self.client.list_resources(
                            kind=kind,
                            namespace=namespace,
                        )
                        
                        for res in resources:
                            res_metadata = res.get("metadata", {})
                            res_annotations = res_metadata.get("annotations", {})
                            res_labels = res_metadata.get("labels", {})
                            
                            res_release = res_annotations.get("meta.helm.sh/release-name") or res_labels.get("app.kubernetes.io/instance")
                            
                            if res_release == release_name and res_metadata.get("name") != metadata.get("name"):
                                relationships.append(
                                    ResourceRelationship(
                                        source=source_id,
                                        target=ResourceIdentifier(
                                            kind=kind,
                                            name=res_metadata.get("name"),
                                            namespace=namespace,
                                        ),
                                        relationship_type=RelationshipType.HELM_MANAGED,
                                        details=f"Managed by Helm release {release_name}",
                                    )
                                )
                    except Exception as e:
                        logger.debug(f"Error finding Helm-managed {kind} resources: {e}")
        
        except Exception as e:
            logger.error(f"Error in HelmHandler.discover(): {e}", exc_info=True)
            return []
        
        return relationships

