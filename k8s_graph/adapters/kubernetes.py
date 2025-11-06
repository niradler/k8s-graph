import logging
from typing import Any

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from k8s_graph.models import ResourceIdentifier

logger = logging.getLogger(__name__)


class KubernetesAdapter:
    """
    Default Kubernetes client adapter using kubernetes-python library.

    Implements K8sClientProtocol and provides access to native Kubernetes resources.
    Supports both in-cluster and out-of-cluster (kubeconfig) configurations.

    Example:
        >>> from k8s_graph import KubernetesAdapter, GraphBuilder
        >>> client = KubernetesAdapter()
        >>> builder = GraphBuilder(client)

        # Or with specific context
        >>> client = KubernetesAdapter(context="production")
    """

    def __init__(self, context: str | None = None):
        """
        Initialize the Kubernetes adapter.

        Args:
            context: Optional kubeconfig context name. If None, uses default context.
        """
        self.context = context
        self._api_call_stats = {"get_resource": 0, "list_resources": 0, "total": 0}
        self._load_config()
        self._build_api_mapping()

    def _load_config(self) -> None:
        """Load Kubernetes configuration from kubeconfig or in-cluster."""
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes configuration")
        except config.ConfigException:
            try:
                if self.context:
                    config.load_kube_config(context=self.context)
                    logger.info(f"Loaded kubeconfig with context: {self.context}")
                else:
                    config.load_kube_config()
                    logger.info("Loaded kubeconfig with default context")
            except Exception as e:
                logger.error(f"Failed to load Kubernetes configuration: {e}")
                raise

        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.batch_v1 = client.BatchV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        self.rbac_v1 = client.RbacAuthorizationV1Api()
        self.storage_v1 = client.StorageV1Api()
        self.autoscaling_v2 = client.AutoscalingV2Api()
        self.policy_v1 = client.PolicyV1Api()

    def _build_api_mapping(self) -> None:
        """Build mapping from resource kinds to API methods."""
        self._api_mapping = {
            "Pod": {
                "api": self.core_v1,
                "api_version": "v1",
                "read_namespaced": "read_namespaced_pod",
                "list_namespaced": "list_namespaced_pod",
                "list_all": "list_pod_for_all_namespaces",
            },
            "Service": {
                "api": self.core_v1,
                "api_version": "v1",
                "read_namespaced": "read_namespaced_service",
                "list_namespaced": "list_namespaced_service",
                "list_all": "list_service_for_all_namespaces",
            },
            "ConfigMap": {
                "api": self.core_v1,
                "api_version": "v1",
                "read_namespaced": "read_namespaced_config_map",
                "list_namespaced": "list_namespaced_config_map",
                "list_all": "list_config_map_for_all_namespaces",
            },
            "Secret": {
                "api": self.core_v1,
                "api_version": "v1",
                "read_namespaced": "read_namespaced_secret",
                "list_namespaced": "list_namespaced_secret",
                "list_all": "list_secret_for_all_namespaces",
            },
            "Namespace": {
                "api": self.core_v1,
                "api_version": "v1",
                "read": "read_namespace",
                "list": "list_namespace",
            },
            "Node": {
                "api": self.core_v1,
                "api_version": "v1",
                "read": "read_node",
                "list": "list_node",
            },
            "PersistentVolume": {
                "api": self.core_v1,
                "api_version": "v1",
                "read": "read_persistent_volume",
                "list": "list_persistent_volume",
            },
            "PersistentVolumeClaim": {
                "api": self.core_v1,
                "api_version": "v1",
                "read_namespaced": "read_namespaced_persistent_volume_claim",
                "list_namespaced": "list_namespaced_persistent_volume_claim",
                "list_all": "list_persistent_volume_claim_for_all_namespaces",
            },
            "ServiceAccount": {
                "api": self.core_v1,
                "api_version": "v1",
                "read_namespaced": "read_namespaced_service_account",
                "list_namespaced": "list_namespaced_service_account",
                "list_all": "list_service_account_for_all_namespaces",
            },
            "Deployment": {
                "api": self.apps_v1,
                "api_version": "apps/v1",
                "read_namespaced": "read_namespaced_deployment",
                "list_namespaced": "list_namespaced_deployment",
                "list_all": "list_deployment_for_all_namespaces",
            },
            "ReplicaSet": {
                "api": self.apps_v1,
                "api_version": "apps/v1",
                "read_namespaced": "read_namespaced_replica_set",
                "list_namespaced": "list_namespaced_replica_set",
                "list_all": "list_replica_set_for_all_namespaces",
            },
            "StatefulSet": {
                "api": self.apps_v1,
                "api_version": "apps/v1",
                "read_namespaced": "read_namespaced_stateful_set",
                "list_namespaced": "list_namespaced_stateful_set",
                "list_all": "list_stateful_set_for_all_namespaces",
            },
            "DaemonSet": {
                "api": self.apps_v1,
                "api_version": "apps/v1",
                "read_namespaced": "read_namespaced_daemon_set",
                "list_namespaced": "list_namespaced_daemon_set",
                "list_all": "list_daemon_set_for_all_namespaces",
            },
            "Job": {
                "api": self.batch_v1,
                "api_version": "batch/v1",
                "read_namespaced": "read_namespaced_job",
                "list_namespaced": "list_namespaced_job",
                "list_all": "list_job_for_all_namespaces",
            },
            "CronJob": {
                "api": self.batch_v1,
                "api_version": "batch/v1",
                "read_namespaced": "read_namespaced_cron_job",
                "list_namespaced": "list_namespaced_cron_job",
                "list_all": "list_cron_job_for_all_namespaces",
            },
            "Ingress": {
                "api": self.networking_v1,
                "api_version": "networking.k8s.io/v1",
                "read_namespaced": "read_namespaced_ingress",
                "list_namespaced": "list_namespaced_ingress",
                "list_all": "list_ingress_for_all_namespaces",
            },
            "NetworkPolicy": {
                "api": self.networking_v1,
                "api_version": "networking.k8s.io/v1",
                "read_namespaced": "read_namespaced_network_policy",
                "list_namespaced": "list_namespaced_network_policy",
                "list_all": "list_network_policy_for_all_namespaces",
            },
            "Role": {
                "api": self.rbac_v1,
                "api_version": "rbac.authorization.k8s.io/v1",
                "read_namespaced": "read_namespaced_role",
                "list_namespaced": "list_namespaced_role",
                "list_all": "list_role_for_all_namespaces",
            },
            "RoleBinding": {
                "api": self.rbac_v1,
                "api_version": "rbac.authorization.k8s.io/v1",
                "read_namespaced": "read_namespaced_role_binding",
                "list_namespaced": "list_namespaced_role_binding",
                "list_all": "list_role_binding_for_all_namespaces",
            },
            "ClusterRole": {
                "api": self.rbac_v1,
                "api_version": "rbac.authorization.k8s.io/v1",
                "read": "read_cluster_role",
                "list": "list_cluster_role",
            },
            "ClusterRoleBinding": {
                "api": self.rbac_v1,
                "api_version": "rbac.authorization.k8s.io/v1",
                "read": "read_cluster_role_binding",
                "list": "list_cluster_role_binding",
            },
            "StorageClass": {
                "api": self.storage_v1,
                "api_version": "storage.k8s.io/v1",
                "read": "read_storage_class",
                "list": "list_storage_class",
            },
            "HorizontalPodAutoscaler": {
                "api": self.autoscaling_v2,
                "api_version": "autoscaling/v2",
                "read_namespaced": "read_namespaced_horizontal_pod_autoscaler",
                "list_namespaced": "list_namespaced_horizontal_pod_autoscaler",
                "list_all": "list_horizontal_pod_autoscaler_for_all_namespaces",
            },
            "PodDisruptionBudget": {
                "api": self.policy_v1,
                "api_version": "policy/v1",
                "read_namespaced": "read_namespaced_pod_disruption_budget",
                "list_namespaced": "list_namespaced_pod_disruption_budget",
                "list_all": "list_pod_disruption_budget_for_all_namespaces",
            },
            "ResourceQuota": {
                "api": self.core_v1,
                "api_version": "v1",
                "read_namespaced": "read_namespaced_resource_quota",
                "list_namespaced": "list_namespaced_resource_quota",
                "list_all": "list_resource_quota_for_all_namespaces",
            },
            "LimitRange": {
                "api": self.core_v1,
                "api_version": "v1",
                "read_namespaced": "read_namespaced_limit_range",
                "list_namespaced": "list_namespaced_limit_range",
                "list_all": "list_limit_range_for_all_namespaces",
            },
            "Endpoints": {
                "api": self.core_v1,
                "api_version": "v1",
                "read_namespaced": "read_namespaced_endpoints",
                "list_namespaced": "list_namespaced_endpoints",
                "list_all": "list_endpoints_for_all_namespaces",
            },
        }

    async def get_resource(self, resource_id: ResourceIdentifier) -> dict[str, Any] | None:
        """
        Get a single resource by identifier.

        Args:
            resource_id: Resource identifier

        Returns:
            Resource dict or None if not found
        """
        self._api_call_stats["get_resource"] += 1
        self._api_call_stats["total"] += 1

        api_info = self._api_mapping.get(resource_id.kind)
        if not api_info:
            logger.warning(f"Unknown resource kind: {resource_id.kind}")
            return None

        try:
            api = api_info["api"]

            if resource_id.namespace:
                method_name = api_info.get("read_namespaced")
                if not method_name:
                    logger.warning(f"No namespaced read method for {resource_id.kind}")
                    return None

                method = getattr(api, method_name)
                result = method(name=resource_id.name, namespace=resource_id.namespace)
            else:
                method_name = api_info.get("read")
                if not method_name:
                    logger.warning(f"No read method for {resource_id.kind}")
                    return None

                method = getattr(api, method_name)
                result = method(name=resource_id.name)

            resource = self._to_dict(result)
            resource["kind"] = resource_id.kind
            if not resource.get("apiVersion") and api_info.get("api_version"):
                resource["apiVersion"] = api_info["api_version"]
            return resource

        except ApiException as e:
            if e.status == 404:
                logger.debug(f"Resource not found: {resource_id.kind}/{resource_id.name}")
                return None
            elif e.status == 403:
                logger.warning(f"Permission denied accessing {resource_id.kind}/{resource_id.name}")
                return None
            else:
                logger.error(f"API error getting {resource_id}: {e}")
                raise

    async def list_resources(
        self,
        kind: str,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        List resources of a specific kind.

        Args:
            kind: Resource kind
            namespace: Optional namespace filter
            label_selector: Optional label selector

        Returns:
            Tuple of (resources list, metadata dict)
        """
        self._api_call_stats["list_resources"] += 1
        self._api_call_stats["total"] += 1

        api_info = self._api_mapping.get(kind)
        if not api_info:
            logger.warning(f"Unknown resource kind: {kind}")
            return [], {}

        try:
            api = api_info["api"]

            if namespace:
                method_name = api_info.get("list_namespaced")
                if not method_name:
                    logger.warning(f"No namespaced list method for {kind}")
                    return [], {}

                method = getattr(api, method_name)
                result = method(namespace=namespace, label_selector=label_selector)
            else:
                method_name = api_info.get("list_all") or api_info.get("list")
                if not method_name:
                    logger.warning(f"No list method for {kind}")
                    return [], {}

                method = getattr(api, method_name)
                result = method(label_selector=label_selector)

            resources = [self._to_dict(item) for item in result.items]

            for resource in resources:
                resource["kind"] = kind
                if not resource.get("apiVersion") and api_info.get("api_version"):
                    resource["apiVersion"] = api_info["api_version"]

            metadata = {
                "resource_version": result.metadata.resource_version,
                "continue": getattr(result.metadata, "_continue", None),
            }

            logger.debug(
                f"Listed {len(resources)} {kind} resources in namespace={namespace or 'all'}"
            )

            return resources, metadata

        except ApiException as e:
            if e.status == 403:
                logger.warning(f"Permission denied listing {kind}")
                return [], {}
            else:
                logger.error(f"API error listing {kind}: {e}")
                raise

    def _snake_to_camel(self, snake_str: str) -> str:
        """Convert snake_case to camelCase."""
        components = snake_str.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    def _convert_keys_to_camel(self, obj: Any) -> Any:
        """Recursively convert all dict keys from snake_case to camelCase, excluding None values."""
        if isinstance(obj, dict):
            return {
                self._snake_to_camel(k): self._convert_keys_to_camel(v)
                for k, v in obj.items()
                if v is not None
            }
        elif isinstance(obj, list):
            return [self._convert_keys_to_camel(item) for item in obj]
        else:
            return obj

    def _to_dict(self, obj: Any) -> dict[str, Any]:
        """
        Convert Kubernetes API object to dictionary with camelCase keys.

        Args:
            obj: Kubernetes API object

        Returns:
            Dictionary representation with camelCase keys
        """
        if hasattr(obj, "to_dict"):
            snake_dict = obj.to_dict()
            return self._convert_keys_to_camel(snake_dict)  # type: ignore[no-any-return]
        return obj  # type: ignore[no-any-return]

    def get_api_call_stats(self) -> dict[str, int]:
        """
        Get statistics about Kubernetes API calls made.

        Returns:
            Dictionary with call counts: get_resource, list_resources, total

        Example:
            >>> client = KubernetesAdapter()
            >>> # ... build graph ...
            >>> stats = client.get_api_call_stats()
            >>> print(f"Total API calls: {stats['total']}")
        """
        return self._api_call_stats.copy()

    def reset_api_call_stats(self) -> None:
        """Reset API call statistics to zero."""
        self._api_call_stats = {"get_resource": 0, "list_resources": 0, "total": 0}
