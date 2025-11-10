import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class SparkHandler(BaseCRDHandler):
    def get_crd_kinds(self) -> list[str]:
        return ["SparkApplication", "ScheduledSparkApplication"]

    def get_crd_info(self, kind: str) -> dict[str, str] | None:
        crd_map = {
            "SparkApplication": {
                "group": "sparkoperator.k8s.io",
                "version": "v1beta2",
                "plural": "sparkapplications",
            },
            "ScheduledSparkApplication": {
                "group": "sparkoperator.k8s.io",
                "version": "v1beta2",
                "plural": "scheduledsparkapplications",
            },
        }
        return crd_map.get(kind)

    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")

        return kind == "SparkApplication" and "sparkoperator.k8s.io" in api_version

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []

        try:
            metadata = resource.get("metadata", {})
            spec = resource.get("spec", {})
            source_id = self._extract_resource_identifier(resource)

            namespace = metadata.get("namespace")
            name = metadata.get("name")

            if not self.client or not namespace:
                return []

            driver_label_selector = {
                "spark-role": "driver",
                "sparkoperator.k8s.io/app-name": name,
            }
            driver_pods = await self._find_resources_by_label(
                kind="Pod",
                namespace=namespace,
                label_selector=driver_label_selector,
            )

            for pod in driver_pods:
                pod_metadata = pod.get("metadata", {})
                relationships.append(
                    ResourceRelationship(
                        source=source_id,
                        target=ResourceIdentifier(
                            kind="Pod",
                            name=pod_metadata.get("name"),
                            namespace=namespace,
                        ),
                        relationship_type=RelationshipType.SPARK_DRIVER,
                        details="Spark driver pod",
                    )
                )

            executor_label_selector = {
                "spark-role": "executor",
                "sparkoperator.k8s.io/app-name": name,
            }
            executor_pods = await self._find_resources_by_label(
                kind="Pod",
                namespace=namespace,
                label_selector=executor_label_selector,
            )

            for pod in executor_pods:
                pod_metadata = pod.get("metadata", {})
                relationships.append(
                    ResourceRelationship(
                        source=source_id,
                        target=ResourceIdentifier(
                            kind="Pod",
                            name=pod_metadata.get("name"),
                            namespace=namespace,
                        ),
                        relationship_type=RelationshipType.SPARK_EXECUTOR,
                        details="Spark executor pod",
                    )
                )

            volumes = spec.get("volumes", [])
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
                                details="Spark volume mount",
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
                                details="Spark volume mount",
                            )
                        )

        except Exception as e:
            logger.error(f"Error in SparkHandler.discover(): {e}", exc_info=True)
            return []

        return relationships
