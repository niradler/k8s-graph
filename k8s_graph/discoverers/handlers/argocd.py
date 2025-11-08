import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class ArgoCDHandler(BaseCRDHandler):
    def supports(self, resource: dict[str, Any]) -> bool:
        return (
            resource.get("kind") == "Application" and
            resource.get("apiVersion", "").startswith("argoproj.io/")
        )

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []
        
        try:
            metadata = resource.get("metadata", {})
            spec = resource.get("spec", {})
            source_id = self._extract_resource_identifier(resource)
            
            app_name = metadata.get("name")
            argocd_namespace = metadata.get("namespace", "argocd")
            dest_namespace = spec.get("destination", {}).get("namespace")
            
            if self.client and dest_namespace and app_name:
                label_selector = {"argocd.argoproj.io/instance": app_name}
                
                for kind in ["Deployment", "StatefulSet", "DaemonSet", "Service", "ConfigMap", "Secret", "Ingress"]:
                    try:
                        resources = await self._find_resources_by_label(
                            kind=kind,
                            namespace=dest_namespace,
                            label_selector=label_selector,
                        )
                        
                        for res in resources:
                            res_metadata = res.get("metadata", {})
                            relationships.append(
                                ResourceRelationship(
                                    source=source_id,
                                    target=ResourceIdentifier(
                                        kind=kind,
                                        name=res_metadata.get("name"),
                                        namespace=dest_namespace,
                                    ),
                                    relationship_type=RelationshipType.ARGOCD_MANAGED,
                                    details=f"Managed by ArgoCD Application {app_name}",
                                )
                            )
                    except Exception as e:
                        logger.debug(f"Error finding ArgoCD-managed {kind} resources: {e}")
            
            project = spec.get("project")
            if project and project != "default" and self.client:
                try:
                    project_resource = await self.client.get_resource(
                        ResourceIdentifier(
                            kind="AppProject",
                            name=project,
                            namespace=argocd_namespace,
                            api_version="argoproj.io/v1alpha1",
                        )
                    )
                    
                    if project_resource:
                        relationships.append(
                            ResourceRelationship(
                                source=source_id,
                                target=ResourceIdentifier(
                                    kind="AppProject",
                                    name=project,
                                    namespace=argocd_namespace,
                                ),
                                relationship_type=RelationshipType.OWNED,
                                details=f"Application belongs to project {project}",
                            )
                        )
                except Exception as e:
                    logger.debug(f"Error finding AppProject: {e}")
            
            source = spec.get("source", {})
            if isinstance(source, dict):
                repo_url = source.get("repoURL", "")
                if repo_url.startswith("git@") or "git" in repo_url:
                    try:
                        secrets, _ = await self.client.list_resources(
                            kind="Secret",
                            namespace=argocd_namespace,
                        )
                        
                        for secret in secrets:
                            secret_metadata = secret.get("metadata", {})
                            secret_labels = secret_metadata.get("labels", {})
                            
                            if secret_labels.get("argocd.argoproj.io/secret-type") == "repository":
                                relationships.append(
                                    ResourceRelationship(
                                        source=source_id,
                                        target=ResourceIdentifier(
                                            kind="Secret",
                                            name=secret_metadata.get("name"),
                                            namespace=argocd_namespace,
                                        ),
                                        relationship_type=RelationshipType.MANAGED,
                                        details="Repository credentials",
                                    )
                                )
                                break
                    except Exception as e:
                        logger.debug(f"Error finding repository Secret: {e}")
        
        except Exception as e:
            logger.error(f"Error in ArgoCDHandler.discover(): {e}", exc_info=True)
            return []
        
        return relationships

