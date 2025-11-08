import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class ArgoWorkflowsHandler(BaseCRDHandler):
    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")
        
        return (
            kind in ["Workflow", "CronWorkflow", "WorkflowTemplate"] and
            api_version.startswith("argoproj.io/")
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
            
            if kind == "Workflow" and self.client and namespace and name:
                label_selector = {"workflows.argoproj.io/workflow": name}
                pods = await self._find_resources_by_label(
                    kind="Pod",
                    namespace=namespace,
                    label_selector=label_selector,
                )
                
                for pod in pods:
                    pod_metadata = pod.get("metadata", {})
                    relationships.append(
                        ResourceRelationship(
                            source=source_id,
                            target=ResourceIdentifier(
                                kind="Pod",
                                name=pod_metadata.get("name"),
                                namespace=namespace,
                            ),
                            relationship_type=RelationshipType.ARGO_WORKFLOW_SPAWNED,
                            details="Workflow spawned pod",
                        )
                    )
            
            elif kind == "CronWorkflow" and self.client and namespace:
                label_selector = {"workflows.argoproj.io/cron-workflow": name}
                workflows = await self._find_resources_by_label(
                    kind="Workflow",
                    namespace=namespace,
                    label_selector=label_selector,
                )
                
                for workflow in workflows:
                    workflow_metadata = workflow.get("metadata", {})
                    relationships.append(
                        ResourceRelationship(
                            source=source_id,
                            target=ResourceIdentifier(
                                kind="Workflow",
                                name=workflow_metadata.get("name"),
                                namespace=namespace,
                            ),
                            relationship_type=RelationshipType.OWNED,
                            details="CronWorkflow created this Workflow",
                        )
                    )
            
            workflow_spec = spec.get("workflowSpec", spec)
            
            templates = workflow_spec.get("templates", [])
            for template in templates:
                volumes = template.get("volumes", [])
                for volume in volumes:
                    if "configMap" in volume:
                        cm_name = volume["configMap"].get("name")
                        if cm_name:
                            relationships.append(
                                ResourceRelationship(
                                    source=source_id,
                                    target=ResourceIdentifier(
                                        kind="ConfigMap",
                                        name=cm_name,
                                        namespace=namespace,
                                    ),
                                    relationship_type=RelationshipType.VOLUME,
                                    details="Volume mounted from ConfigMap",
                                )
                            )
                    
                    if "secret" in volume:
                        secret_name = volume["secret"].get("secretName")
                        if secret_name:
                            relationships.append(
                                ResourceRelationship(
                                    source=source_id,
                                    target=ResourceIdentifier(
                                        kind="Secret",
                                        name=secret_name,
                                        namespace=namespace,
                                    ),
                                    relationship_type=RelationshipType.VOLUME,
                                    details="Volume mounted from Secret",
                                )
                            )
            
            service_account = workflow_spec.get("serviceAccountName")
            if service_account:
                relationships.append(
                    ResourceRelationship(
                        source=source_id,
                        target=ResourceIdentifier(
                            kind="ServiceAccount",
                            name=service_account,
                            namespace=namespace,
                        ),
                        relationship_type=RelationshipType.SERVICE_ACCOUNT,
                        details="Workflow uses ServiceAccount",
                    )
                )
        
        except Exception as e:
            logger.error(f"Error in ArgoWorkflowsHandler.discover(): {e}", exc_info=True)
            return []
        
        return relationships

