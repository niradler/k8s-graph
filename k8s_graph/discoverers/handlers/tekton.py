import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class TektonHandler(BaseCRDHandler):
    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")
        
        return (
            kind in ["Pipeline", "PipelineRun", "Task", "TaskRun"] and
            "tekton.dev" in api_version
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
            
            if kind == "PipelineRun":
                pipeline_ref = spec.get("pipelineRef", {})
                pipeline_name = pipeline_ref.get("name")
                
                if pipeline_name and self.client:
                    try:
                        pipeline = await self.client.get_resource(
                            ResourceIdentifier(
                                kind="Pipeline",
                                name=pipeline_name,
                                namespace=namespace,
                            )
                        )
                        
                        if pipeline:
                            relationships.append(
                                ResourceRelationship(
                                    source=source_id,
                                    target=ResourceIdentifier(
                                        kind="Pipeline",
                                        name=pipeline_name,
                                        namespace=namespace,
                                    ),
                                    relationship_type=RelationshipType.MANAGED,
                                    details="PipelineRun executes Pipeline",
                                )
                            )
                    except Exception as e:
                        logger.debug(f"Error finding Pipeline {pipeline_name}: {e}")
                
                if self.client and namespace:
                    label_selector = {"tekton.dev/pipelineRun": name}
                    task_runs = await self._find_resources_by_label(
                        kind="TaskRun",
                        namespace=namespace,
                        label_selector=label_selector,
                    )
                    
                    for task_run in task_runs:
                        task_run_metadata = task_run.get("metadata", {})
                        relationships.append(
                            ResourceRelationship(
                                source=source_id,
                                target=ResourceIdentifier(
                                    kind="TaskRun",
                                    name=task_run_metadata.get("name"),
                                    namespace=namespace,
                                ),
                                relationship_type=RelationshipType.TEKTON_RUN,
                                details="PipelineRun created TaskRun",
                            )
                        )
            
            elif kind == "TaskRun":
                task_ref = spec.get("taskRef", {})
                task_name = task_ref.get("name")
                
                if task_name and self.client:
                    try:
                        task = await self.client.get_resource(
                            ResourceIdentifier(
                                kind="Task",
                                name=task_name,
                                namespace=namespace,
                            )
                        )
                        
                        if task:
                            relationships.append(
                                ResourceRelationship(
                                    source=source_id,
                                    target=ResourceIdentifier(
                                        kind="Task",
                                        name=task_name,
                                        namespace=namespace,
                                    ),
                                    relationship_type=RelationshipType.MANAGED,
                                    details="TaskRun executes Task",
                                )
                            )
                    except Exception as e:
                        logger.debug(f"Error finding Task {task_name}: {e}")
                
                if self.client and namespace:
                    label_selector = {"tekton.dev/taskRun": name}
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
                                relationship_type=RelationshipType.TEKTON_RUN,
                                details="TaskRun created Pod",
                            )
                        )
                
                workspaces = spec.get("workspaces", [])
                for workspace in workspaces:
                    pvc = workspace.get("persistentVolumeClaim", {})
                    pvc_name = pvc.get("claimName")
                    
                    if pvc_name:
                        relationships.append(
                            ResourceRelationship(
                                source=source_id,
                                target=ResourceIdentifier(
                                    kind="PersistentVolumeClaim",
                                    name=pvc_name,
                                    namespace=namespace,
                                ),
                                relationship_type=RelationshipType.PVC,
                                details="TaskRun uses workspace PVC",
                            )
                        )
        
        except Exception as e:
            logger.error(f"Error in TektonHandler.discover(): {e}", exc_info=True)
            return []
        
        return relationships

