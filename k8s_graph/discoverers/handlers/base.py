import logging
from typing import Any

from k8s_graph.discoverers.base import BaseDiscoverer
from k8s_graph.models import DiscovererCategory, ResourceIdentifier

logger = logging.getLogger(__name__)


class BaseCRDHandler(BaseDiscoverer):
    @property
    def categories(self) -> DiscovererCategory:
        return DiscovererCategory.CRD

    def get_crd_kinds(self) -> list[str]:
        """
        Return list of CRD kinds this handler supports.
        Used by the system to automatically register CRD types.

        Override this in subclasses to declare which CRD kinds are supported.

        Returns:
            List of CRD kind names (e.g., ["Application", "AppProject"])
        """
        return []

    def get_crd_info(self, kind: str) -> dict[str, str] | None:
        """
        Return CRD API group/version/plural for a specific kind.
        Used by KubernetesAdapter to fetch CRD resources.

        Args:
            kind: CRD kind name

        Returns:
            Dict with 'group', 'version', 'plural' or None if not supported
        """
        return None

    def _parse_label_selector(self, label_selector: dict[str, str]) -> str:
        """
        Convert label selector dict to Kubernetes label selector string.

        Args:
            label_selector: Dictionary of label key-value pairs

        Returns:
            Comma-separated string like "app=nginx,env=prod"
        """
        return ",".join(f"{k}={v}" for k, v in label_selector.items())

    async def _find_resources_by_label(
        self,
        kind: str,
        namespace: str | None,
        label_selector: dict[str, str],
    ) -> list[dict[str, Any]]:
        if not self.client:
            return []

        try:
            label_str = self._parse_label_selector(label_selector)
            resources, _ = await self.client.list_resources(
                kind=kind,
                namespace=namespace,
                label_selector=label_str,
            )
            return resources
        except Exception as e:
            logger.warning(f"Error finding {kind} resources by label {label_selector}: {e}")
            return []

    async def _find_resources_by_annotation(
        self,
        kind: str,
        namespace: str | None,
        annotation_key: str,
        annotation_value: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.client:
            return []

        try:
            resources, _ = await self.client.list_resources(
                kind=kind,
                namespace=namespace,
            )

            matching = []
            for resource in resources:
                annotations = resource.get("metadata", {}).get("annotations", {})
                if annotation_key in annotations:
                    if annotation_value is None or annotations[annotation_key] == annotation_value:
                        matching.append(resource)

            return matching
        except Exception as e:
            logger.warning(f"Error finding {kind} resources by annotation {annotation_key}: {e}")
            return []

    def _extract_resource_references(
        self,
        spec: dict[str, Any],
        namespace: str | None,
    ) -> list[ResourceIdentifier]:
        references = []

        if "serviceAccountName" in spec:
            references.append(
                ResourceIdentifier(
                    kind="ServiceAccount",
                    name=spec["serviceAccountName"],
                    namespace=namespace,
                )
            )

        volumes = spec.get("volumes", [])
        for volume in volumes:
            if "configMap" in volume:
                cm_name = volume["configMap"].get("name")
                if cm_name:
                    references.append(
                        ResourceIdentifier(
                            kind="ConfigMap",
                            name=cm_name,
                            namespace=namespace,
                        )
                    )

            if "secret" in volume:
                secret_name = volume["secret"].get("secretName")
                if secret_name:
                    references.append(
                        ResourceIdentifier(
                            kind="Secret",
                            name=secret_name,
                            namespace=namespace,
                        )
                    )

            if "persistentVolumeClaim" in volume:
                pvc_name = volume["persistentVolumeClaim"].get("claimName")
                if pvc_name:
                    references.append(
                        ResourceIdentifier(
                            kind="PersistentVolumeClaim",
                            name=pvc_name,
                            namespace=namespace,
                        )
                    )

        return references

    def _extract_env_references(
        self,
        containers: list[dict[str, Any]],
        namespace: str | None,
    ) -> list[ResourceIdentifier]:
        references = []

        for container in containers:
            env_from = container.get("envFrom", [])
            for env_source in env_from:
                if "configMapRef" in env_source:
                    cm_name = env_source["configMapRef"].get("name")
                    if cm_name:
                        references.append(
                            ResourceIdentifier(
                                kind="ConfigMap",
                                name=cm_name,
                                namespace=namespace,
                            )
                        )

                if "secretRef" in env_source:
                    secret_name = env_source["secretRef"].get("name")
                    if secret_name:
                        references.append(
                            ResourceIdentifier(
                                kind="Secret",
                                name=secret_name,
                                namespace=namespace,
                            )
                        )

            env_vars = container.get("env", [])
            for env_var in env_vars:
                value_from = env_var.get("valueFrom", {})

                if "configMapKeyRef" in value_from:
                    cm_name = value_from["configMapKeyRef"].get("name")
                    if cm_name:
                        references.append(
                            ResourceIdentifier(
                                kind="ConfigMap",
                                name=cm_name,
                                namespace=namespace,
                            )
                        )

                if "secretKeyRef" in value_from:
                    secret_name = value_from["secretKeyRef"].get("name")
                    if secret_name:
                        references.append(
                            ResourceIdentifier(
                                kind="Secret",
                                name=secret_name,
                                namespace=namespace,
                            )
                        )

        return references
