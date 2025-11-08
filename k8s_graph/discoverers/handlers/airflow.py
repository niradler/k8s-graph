import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class AirflowHandler(BaseCRDHandler):
    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")
        
        return (
            kind in ["AirflowCluster", "AirflowBase", "Airflow"] and
            "airflow" in api_version.lower()
        )

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []
        
        try:
            metadata = resource.get("metadata", {})
            source_id = self._extract_resource_identifier(resource)
            
            namespace = metadata.get("namespace")
            name = metadata.get("name")
            
            if not self.client or not namespace:
                return []
            
            airflow_labels = {
                "airflow.apache.org/cluster": name,
            }
            
            for kind in ["StatefulSet", "Deployment"]:
                try:
                    resources = await self._find_resources_by_label(
                        kind=kind,
                        namespace=namespace,
                        label_selector=airflow_labels,
                    )
                    
                    for res in resources:
                        res_metadata = res.get("metadata", {})
                        relationships.append(
                            ResourceRelationship(
                                source=source_id,
                                target=ResourceIdentifier(
                                    kind=kind,
                                    name=res_metadata.get("name"),
                                    namespace=namespace,
                                ),
                                relationship_type=RelationshipType.OWNED,
                                details="Airflow cluster component",
                            )
                        )
                except Exception as e:
                    logger.debug(f"Error finding Airflow {kind}: {e}")
            
            pod_labels = {
                "airflow.apache.org/component": "worker",
            }
            pods = await self._find_resources_by_label(
                kind="Pod",
                namespace=namespace,
                label_selector=pod_labels,
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
                        relationship_type=RelationshipType.AIRFLOW_TASK,
                        details="Airflow worker pod",
                    )
                )
            
            try:
                pvcs, _ = await self.client.list_resources(
                    kind="PersistentVolumeClaim",
                    namespace=namespace,
                )
                
                for pvc in pvcs:
                    pvc_metadata = pvc.get("metadata", {})
                    pvc_name = pvc_metadata.get("name", "")
                    pvc_labels = pvc_metadata.get("labels", {})
                    
                    if (pvc_labels.get("airflow.apache.org/cluster") == name or
                        "airflow" in pvc_name.lower()):
                        relationships.append(
                            ResourceRelationship(
                                source=source_id,
                                target=ResourceIdentifier(
                                    kind="PersistentVolumeClaim",
                                    name=pvc_metadata.get("name"),
                                    namespace=namespace,
                                ),
                                relationship_type=RelationshipType.PVC,
                                details="Airflow logs storage",
                            )
                        )
            except Exception as e:
                logger.debug(f"Error finding Airflow PVCs: {e}")
        
        except Exception as e:
            logger.error(f"Error in AirflowHandler.discover(): {e}", exc_info=True)
            return []
        
        return relationships

