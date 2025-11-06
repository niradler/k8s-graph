import logging
from typing import Any

logger = logging.getLogger(__name__)


class NodeIdentity:
    """
    Generates stable node IDs for Kubernetes resources.

    Stable node IDs ensure that the same logical resource maintains the same ID
    even when the underlying K8s resource is recreated. This is particularly
    important for:
    - Pods: Named based on owner + pod-template-hash instead of random suffix
    - ReplicaSets: Named based on deployment + pod-template-hash

    Examples:
        >>> identity = NodeIdentity()

        # Regular resource
        >>> deployment = {"kind": "Deployment", "metadata": {"name": "nginx", "namespace": "default"}}
        >>> identity.get_node_id(deployment)
        'Deployment:default:nginx'

        # Pod with template hash
        >>> pod = {
        ...     "kind": "Pod",
        ...     "metadata": {
        ...         "name": "nginx-abc123-xyz",
        ...         "namespace": "default",
        ...         "labels": {"pod-template-hash": "abc123"},
        ...         "ownerReferences": [{"kind": "ReplicaSet", "name": "nginx-abc123"}]
        ...     }
        ... }
        >>> identity.get_node_id(pod)
        'Pod:default:ReplicaSet-nginx-abc123:abc123'
    """

    def get_node_id(self, resource: dict[str, Any]) -> str:
        """
        Generate a stable node ID for a resource.

        Args:
            resource: Kubernetes resource dictionary

        Returns:
            Stable node ID string

        Rules:
            - Stable resources (Deployment, Service, etc.): kind:namespace:name
            - Pods: Pod:namespace:OwnerKind-OwnerName:template-hash
            - ReplicaSets: ReplicaSet:namespace:deployment-name:pod-template-hash
            - Fallback: kind:namespace:name
        """
        kind = resource.get("kind", "Unknown")
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "unknown")
        namespace = metadata.get("namespace") or "cluster"

        if kind == "Pod":
            return self._get_pod_node_id(resource, namespace)
        elif kind == "ReplicaSet":
            return self._get_replicaset_node_id(resource, namespace)

        return f"{kind}:{namespace}:{name}"

    def _get_pod_node_id(self, resource: dict[str, Any], namespace: str) -> str:
        """
        Generate stable node ID for a Pod.

        Tries to use owner + pod-template-hash for stability.
        Falls back to kind:namespace:name if template hash unavailable.
        """
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "unknown")
        labels = metadata.get("labels", {})
        owner_refs = metadata.get("ownerReferences", [])

        pod_template_hash = labels.get("pod-template-hash", "")

        if owner_refs and pod_template_hash:
            owner = owner_refs[0]
            owner_kind = owner.get("kind", "Unknown")
            owner_name = owner.get("name", "unknown")
            return f"Pod:{namespace}:{owner_kind}-{owner_name}:{pod_template_hash}"

        logger.debug(
            f"Pod {namespace}/{name} missing ownerReferences or pod-template-hash, "
            f"using standard ID"
        )
        return f"Pod:{namespace}:{name}"

    def _get_replicaset_node_id(self, resource: dict[str, Any], namespace: str) -> str:
        """
        Generate stable node ID for a ReplicaSet.

        Tries to extract deployment name + pod-template-hash.
        Falls back to kind:namespace:name if pattern not recognized.
        """
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "unknown")
        labels = metadata.get("labels", {})

        pod_template_hash = labels.get("pod-template-hash", "")

        if pod_template_hash and "-" in name:
            deployment_name = name.rsplit("-", 1)[0]
            return f"ReplicaSet:{namespace}:{deployment_name}:{pod_template_hash}"

        logger.debug(
            f"ReplicaSet {namespace}/{name} missing pod-template-hash label, using standard ID"
        )
        return f"ReplicaSet:{namespace}:{name}"

    def extract_node_attributes(self, resource: dict[str, Any]) -> dict[str, Any]:
        """
        Extract node attributes from a resource for graph storage.

        Args:
            resource: Kubernetes resource dictionary

        Returns:
            Dictionary of attributes to store on the graph node
        """
        metadata = resource.get("metadata", {})
        spec = resource.get("spec", {})
        status = resource.get("status", {})

        attrs = {
            "kind": resource.get("kind", "Unknown"),
            "name": metadata.get("name", "unknown"),
            "namespace": metadata.get("namespace"),
            "api_version": resource.get("apiVersion"),
            "uid": metadata.get("uid"),
            "labels": metadata.get("labels", {}),
            "annotations": metadata.get("annotations", {}),
            "creation_timestamp": metadata.get("creationTimestamp"),
        }

        if resource.get("kind") == "Pod":
            attrs["phase"] = status.get("phase")
            attrs["pod_ip"] = status.get("podIP")
            attrs["node_name"] = spec.get("nodeName")
            attrs["restart_count"] = self._get_pod_restart_count(status)

        elif resource.get("kind") == "Service":
            attrs["service_type"] = spec.get("type")
            attrs["cluster_ip"] = spec.get("clusterIP")
            attrs["ports"] = spec.get("ports", [])

        elif resource.get("kind") in ["Deployment", "StatefulSet", "DaemonSet"]:
            attrs["replicas"] = spec.get("replicas")
            attrs["ready_replicas"] = status.get("readyReplicas")
            attrs["available_replicas"] = status.get("availableReplicas")

        return {k: v for k, v in attrs.items() if v is not None}

    def _get_pod_restart_count(self, status: dict[str, Any]) -> int:
        """
        Calculate total restart count for a pod from container statuses.
        """
        total = 0
        container_statuses = status.get("containerStatuses", [])
        for container_status in container_statuses:
            total += container_status.get("restartCount", 0)
        return total

    def get_pod_template_id(self, resource: dict[str, Any]) -> str | None:
        """
        Get the pod template identifier for grouping similar pods.

        This is used for pod sampling - grouping pods that share the same template
        (e.g., all pods of a Deployment) so we can represent them as a single node.

        Args:
            resource: Pod resource dictionary

        Returns:
            Template ID string or None if not applicable
        """
        if resource.get("kind") != "Pod":
            return None

        metadata = resource.get("metadata", {})
        namespace = metadata.get("namespace") or "cluster"
        labels = metadata.get("labels", {})
        owner_refs = metadata.get("ownerReferences", [])

        pod_template_hash = labels.get("pod-template-hash", "")

        if owner_refs and pod_template_hash:
            owner = owner_refs[0]
            owner_kind = owner.get("kind", "Unknown")
            owner_name = owner.get("name", "unknown")
            return f"{namespace}:{owner_kind}:{owner_name}:{pod_template_hash}"

        return None
