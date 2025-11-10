import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship

logger = logging.getLogger(__name__)


class CertManagerHandler(BaseCRDHandler):
    def get_crd_kinds(self) -> list[str]:
        return ["Certificate", "Issuer", "ClusterIssuer", "CertificateRequest"]

    def get_crd_info(self, kind: str) -> dict[str, str] | None:
        crd_map = {
            "Certificate": {"group": "cert-manager.io", "version": "v1", "plural": "certificates"},
            "Issuer": {"group": "cert-manager.io", "version": "v1", "plural": "issuers"},
            "ClusterIssuer": {
                "group": "cert-manager.io",
                "version": "v1",
                "plural": "clusterissuers",
            },
            "CertificateRequest": {
                "group": "cert-manager.io",
                "version": "v1",
                "plural": "certificaterequests",
            },
        }
        return crd_map.get(kind)

    def supports(self, resource: dict[str, Any]) -> bool:
        kind = resource.get("kind")
        api_version = resource.get("apiVersion", "")

        return kind in self.get_crd_kinds() and "cert-manager.io" in api_version

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []

        try:
            kind = resource.get("kind")
            metadata = resource.get("metadata", {})
            spec = resource.get("spec", {})
            source_id = self._extract_resource_identifier(resource)

            namespace = metadata.get("namespace")

            if kind == "Certificate":
                secret_name = spec.get("secretName")
                if secret_name and self.client:
                    try:
                        secret = await self.client.get_resource(
                            ResourceIdentifier(
                                kind="Secret",
                                name=secret_name,
                                namespace=namespace,
                            )
                        )

                        if secret:
                            relationships.append(
                                ResourceRelationship(
                                    source=source_id,
                                    target=ResourceIdentifier(
                                        kind="Secret",
                                        name=secret_name,
                                        namespace=namespace,
                                    ),
                                    relationship_type=RelationshipType.CERT_ISSUED,
                                    details="Certificate stored in Secret",
                                )
                            )
                    except Exception as e:
                        logger.debug(f"Error finding Secret {secret_name}: {e}")

                issuer_ref = spec.get("issuerRef", {})
                if issuer_ref and self.client:
                    issuer_kind = issuer_ref.get("kind", "Issuer")
                    issuer_name = issuer_ref.get("name")
                    issuer_namespace = namespace if issuer_kind == "Issuer" else None

                    if issuer_name:
                        try:
                            issuer = await self.client.get_resource(
                                ResourceIdentifier(
                                    kind=issuer_kind,
                                    name=issuer_name,
                                    namespace=issuer_namespace,
                                )
                            )

                            if issuer:
                                relationships.append(
                                    ResourceRelationship(
                                        source=source_id,
                                        target=ResourceIdentifier(
                                            kind=issuer_kind,
                                            name=issuer_name,
                                            namespace=issuer_namespace,
                                        ),
                                        relationship_type=RelationshipType.MANAGED,
                                        details="Certificate issued by",
                                    )
                                )
                        except Exception as e:
                            logger.debug(f"Error finding {issuer_kind} {issuer_name}: {e}")

                if self.client and namespace and secret_name:
                    try:
                        ingresses, _ = await self.client.list_resources(
                            kind="Ingress",
                            namespace=namespace,
                        )

                        for ingress in ingresses:
                            ingress_metadata = ingress.get("metadata", {})
                            ingress_spec = ingress.get("spec", {})
                            tls_configs = ingress_spec.get("tls", [])

                            for tls_config in tls_configs:
                                if tls_config.get("secretName") == secret_name:
                                    relationships.append(
                                        ResourceRelationship(
                                            source=ResourceIdentifier(
                                                kind="Ingress",
                                                name=ingress_metadata.get("name"),
                                                namespace=namespace,
                                            ),
                                            target=source_id,
                                            relationship_type=RelationshipType.INGRESS_BACKEND,
                                            details="Ingress uses Certificate",
                                        )
                                    )
                                    break
                    except Exception as e:
                        logger.debug(f"Error finding Ingresses using Certificate: {e}")

        except Exception as e:
            logger.error(f"Error in CertManagerHandler.discover(): {e}", exc_info=True)
            return []

        return relationships
