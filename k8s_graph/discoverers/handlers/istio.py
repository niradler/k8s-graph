import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class IstioHandler(BaseCRDHandler):
    def get_crd_kinds(self) -> list[str]:
        return ["VirtualService", "DestinationRule", "Gateway"]

    def get_crd_info(self, kind: str) -> dict[str, str] | None:
        crd_map = {
            "VirtualService": {
                "group": "networking.istio.io",
                "version": "v1beta1",
                "plural": "virtualservices",
            },
            "DestinationRule": {
                "group": "networking.istio.io",
                "version": "v1beta1",
                "plural": "destinationrules",
            },
            "Gateway": {"group": "networking.istio.io", "version": "v1beta1", "plural": "gateways"},
        }
        return crd_map.get(kind)

    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")

        return kind in self.get_crd_kinds() and "istio.io" in api_version

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []

        try:
            kind = resource.get("kind")
            metadata = resource.get("metadata", {})
            spec = resource.get("spec", {})
            source_id = self._extract_resource_identifier(resource)

            namespace = metadata.get("namespace")

            if kind == "VirtualService" and self.client:
                http_routes = spec.get("http", [])
                for route in http_routes:
                    for destination in route.get("route", []):
                        dest_info = destination.get("destination", {})
                        host = dest_info.get("host", "")

                        if host and "." not in host:
                            try:
                                service = await self.client.get_resource(
                                    ResourceIdentifier(
                                        kind="Service",
                                        name=host,
                                        namespace=namespace,
                                    )
                                )

                                if service:
                                    relationships.append(
                                        ResourceRelationship(
                                            source=source_id,
                                            target=ResourceIdentifier(
                                                kind="Service",
                                                name=host,
                                                namespace=namespace,
                                            ),
                                            relationship_type=RelationshipType.ISTIO_ROUTE,
                                            details="VirtualService routes to Service",
                                        )
                                    )
                            except Exception as e:
                                logger.debug(f"Error finding Service {host}: {e}")
                        elif host and "." in host:
                            service_name = host.split(".")[0]
                            service_namespace = (
                                host.split(".")[1] if len(host.split(".")) > 1 else namespace
                            )

                            try:
                                service = await self.client.get_resource(
                                    ResourceIdentifier(
                                        kind="Service",
                                        name=service_name,
                                        namespace=service_namespace,
                                    )
                                )

                                if service:
                                    relationships.append(
                                        ResourceRelationship(
                                            source=source_id,
                                            target=ResourceIdentifier(
                                                kind="Service",
                                                name=service_name,
                                                namespace=service_namespace,
                                            ),
                                            relationship_type=RelationshipType.ISTIO_ROUTE,
                                            details="VirtualService routes to Service",
                                        )
                                    )
                            except Exception as e:
                                logger.debug(f"Error finding Service {service_name}: {e}")

            elif kind == "DestinationRule" and self.client:
                host = spec.get("host", "")

                if host and "." not in host:
                    try:
                        service = await self.client.get_resource(
                            ResourceIdentifier(
                                kind="Service",
                                name=host,
                                namespace=namespace,
                            )
                        )

                        if service:
                            relationships.append(
                                ResourceRelationship(
                                    source=source_id,
                                    target=ResourceIdentifier(
                                        kind="Service",
                                        name=host,
                                        namespace=namespace,
                                    ),
                                    relationship_type=RelationshipType.ISTIO_ROUTE,
                                    details="DestinationRule applies to Service",
                                )
                            )
                    except Exception as e:
                        logger.debug(f"Error finding Service {host}: {e}")

            elif kind == "Gateway" and self.client:
                try:
                    services, _ = await self.client.list_resources(
                        kind="Service",
                        namespace="istio-system",
                    )

                    for service in services:
                        service_metadata = service.get("metadata", {})
                        service_labels = service_metadata.get("labels", {})

                        if service_labels.get("istio") == "ingressgateway":
                            relationships.append(
                                ResourceRelationship(
                                    source=source_id,
                                    target=ResourceIdentifier(
                                        kind="Service",
                                        name=service_metadata.get("name"),
                                        namespace="istio-system",
                                    ),
                                    relationship_type=RelationshipType.INGRESS_BACKEND,
                                    details="Gateway uses Istio ingress",
                                )
                            )
                            break
                except Exception as e:
                    logger.debug(f"Error finding Istio ingress Service: {e}")

        except Exception as e:
            logger.error(f"Error in IstioHandler.discover(): {e}", exc_info=True)
            return []

        return relationships
