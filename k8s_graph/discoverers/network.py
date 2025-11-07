import logging
from typing import Any

from k8s_graph.discoverers.base import BaseDiscoverer
from k8s_graph.models import (
    DiscovererCategory,
    RelationshipType,
    ResourceIdentifier,
    ResourceRelationship,
)
from k8s_graph.protocols import K8sClientProtocol

logger = logging.getLogger(__name__)


class NetworkPolicyDiscoverer(BaseDiscoverer):
    """
    Discoverer for NetworkPolicy relationships.

    Handles relationships between NetworkPolicy and:
    - Pods (via podSelector)
    - Ingress sources (via ingress.from)
    - Egress destinations (via egress.to)
    """

    def __init__(self, client: K8sClientProtocol | None = None) -> None:
        super().__init__(client)

    def supports(self, resource: dict[str, Any]) -> bool:
        return resource.get("kind") == "NetworkPolicy"

    @property
    def categories(self) -> DiscovererCategory:
        return DiscovererCategory.NETWORK

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        spec = resource.get("spec", {})

        pod_selector = spec.get("podSelector", {})
        match_labels = pod_selector.get("matchLabels", {})

        if match_labels:
            target = ResourceIdentifier(
                kind="Pod",
                name=f"*[{self._parse_label_selector(match_labels)}]",
                namespace=source.namespace,
            )
            relationships.append(
                ResourceRelationship(
                    source=source,
                    target=target,
                    relationship_type=RelationshipType.NETWORK_POLICY,
                    details=f"Applies to pods with labels: {self._parse_label_selector(match_labels)}",
                )
            )

        ingress_rules = spec.get("ingress") or []
        for ingress_rule in ingress_rules:
            from_rules = ingress_rule.get("from", [])
            for from_rule in from_rules:
                pod_selector = from_rule.get("podSelector", {})
                if pod_selector:
                    match_labels = pod_selector.get("matchLabels", {})
                    if match_labels:
                        target = ResourceIdentifier(
                            kind="Pod",
                            name=f"*[{self._parse_label_selector(match_labels)}]",
                            namespace=source.namespace,
                        )
                        relationships.append(
                            ResourceRelationship(
                                source=source,
                                target=target,
                                relationship_type=RelationshipType.NETWORK_POLICY_INGRESS,
                                details=f"Allows ingress from pods: {self._parse_label_selector(match_labels)}",
                            )
                        )

        egress_rules = spec.get("egress") or []
        for egress_rule in egress_rules:
            to_rules = egress_rule.get("to", [])
            for to_rule in to_rules:
                pod_selector = to_rule.get("podSelector", {})
                if pod_selector:
                    match_labels = pod_selector.get("matchLabels", {})
                    if match_labels:
                        target = ResourceIdentifier(
                            kind="Pod",
                            name=f"*[{self._parse_label_selector(match_labels)}]",
                            namespace=source.namespace,
                        )
                        relationships.append(
                            ResourceRelationship(
                                source=source,
                                target=target,
                                relationship_type=RelationshipType.NETWORK_POLICY_EGRESS,
                                details=f"Allows egress to pods: {self._parse_label_selector(match_labels)}",
                            )
                        )

        return relationships
