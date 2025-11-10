import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class PrometheusHandler(BaseCRDHandler):
    def get_crd_kinds(self) -> list[str]:
        return ["ServiceMonitor", "PodMonitor", "PrometheusRule"]

    def get_crd_info(self, kind: str) -> dict[str, str] | None:
        crd_map = {
            "ServiceMonitor": {
                "group": "monitoring.coreos.com",
                "version": "v1",
                "plural": "servicemonitors",
            },
            "PodMonitor": {
                "group": "monitoring.coreos.com",
                "version": "v1",
                "plural": "podmonitors",
            },
            "PrometheusRule": {
                "group": "monitoring.coreos.com",
                "version": "v1",
                "plural": "prometheusrules",
            },
        }
        return crd_map.get(kind)

    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")

        return kind in self.get_crd_kinds() and "monitoring.coreos.com" in api_version

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []

        try:
            kind = resource.get("kind")
            metadata = resource.get("metadata", {})
            spec = resource.get("spec", {})
            source_id = self._extract_resource_identifier(resource)

            namespace = metadata.get("namespace")

            if kind == "ServiceMonitor" and self.client and namespace:
                selector = spec.get("selector", {})
                match_labels = selector.get("matchLabels", {})

                if match_labels:
                    services = await self._find_resources_by_label(
                        kind="Service",
                        namespace=namespace,
                        label_selector=match_labels,
                    )

                    for service in services:
                        service_metadata = service.get("metadata", {})
                        relationships.append(
                            ResourceRelationship(
                                source=source_id,
                                target=ResourceIdentifier(
                                    kind="Service",
                                    name=service_metadata.get("name"),
                                    namespace=namespace,
                                ),
                                relationship_type=RelationshipType.PROMETHEUS_MONITOR,
                                details="ServiceMonitor monitors Service",
                            )
                        )

            elif kind == "PodMonitor" and self.client and namespace:
                selector = spec.get("selector", {})
                match_labels = selector.get("matchLabels", {})

                if match_labels:
                    pods = await self._find_resources_by_label(
                        kind="Pod",
                        namespace=namespace,
                        label_selector=match_labels,
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
                                relationship_type=RelationshipType.PROMETHEUS_MONITOR,
                                details="PodMonitor monitors Pod",
                            )
                        )

            elif kind == "Prometheus" and self.client:
                service_monitor_selector = spec.get("serviceMonitorSelector", {})
                match_labels = service_monitor_selector.get("matchLabels", {})

                if match_labels:
                    service_monitors = await self._find_resources_by_label(
                        kind="ServiceMonitor",
                        namespace=namespace,
                        label_selector=match_labels,
                    )

                    for sm in service_monitors:
                        sm_metadata = sm.get("metadata", {})
                        relationships.append(
                            ResourceRelationship(
                                source=source_id,
                                target=ResourceIdentifier(
                                    kind="ServiceMonitor",
                                    name=sm_metadata.get("name"),
                                    namespace=sm_metadata.get("namespace"),
                                ),
                                relationship_type=RelationshipType.PROMETHEUS_MONITOR,
                                details="Prometheus scrapes ServiceMonitor",
                            )
                        )

        except Exception as e:
            logger.error(f"Error in PrometheusHandler.discover(): {e}", exc_info=True)
            return []

        return relationships
