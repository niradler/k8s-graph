import logging
from typing import Any

from k8s_graph.discoverers.base import BaseDiscoverer
from k8s_graph.models import RelationshipType, ResourceIdentifier, ResourceRelationship
from k8s_graph.protocols import K8sClientProtocol

logger = logging.getLogger(__name__)


class NativeResourceDiscoverer(BaseDiscoverer):
    """
    Discoverer for native Kubernetes resource relationships.

    Handles standard relationships including:
    - Owner references (ReplicaSet -> Deployment)
    - Owned resources (Deployment -> ReplicaSets -> Pods)
    - Label selectors (Service -> Pods)
    - Volume mounts (Pod -> ConfigMap/Secret/PVC)
    - Environment variables (Pod -> ConfigMap/Secret)
    - Service accounts (Pod -> ServiceAccount)
    - Service endpoints (Service -> Pods)
    - Ingress backends (Ingress -> Service)
    - PV/PVC relationships
    """

    def __init__(self, client: K8sClientProtocol | None = None) -> None:
        super().__init__(client)

    def supports(self, resource: dict[str, Any]) -> bool:
        return True

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []

        kind = resource.get("kind")
        if not kind:
            return relationships

        relationships.extend(self._discover_owner_references(resource))

        if kind == "Service":
            relationships.extend(self._discover_service_relationships(resource))
        elif kind == "Pod":
            relationships.extend(self._discover_pod_relationships(resource))
        elif kind == "Ingress":
            relationships.extend(self._discover_ingress_relationships(resource))
        elif kind == "PersistentVolumeClaim":
            relationships.extend(self._discover_pvc_relationships(resource))
        elif kind == "PersistentVolume":
            relationships.extend(self._discover_pv_relationships(resource))
        elif kind in ["Deployment", "StatefulSet", "DaemonSet", "ReplicaSet"]:
            relationships.extend(await self._discover_workload_relationships(resource))

        return relationships

    def _discover_owner_references(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []
        metadata = resource.get("metadata", {})
        owner_refs = metadata.get("ownerReferences", [])

        if not owner_refs:
            return relationships

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError as e:
            logger.warning(f"Cannot extract resource identifier: {e}")
            return relationships

        for owner_ref in owner_refs:
            owner_kind = owner_ref.get("kind")
            owner_name = owner_ref.get("name")
            owner_api_version = owner_ref.get("apiVersion")

            if not owner_kind or not owner_name:
                continue

            target = ResourceIdentifier(
                kind=owner_kind,
                name=owner_name,
                namespace=metadata.get("namespace"),
                api_version=owner_api_version,
            )

            relationships.append(
                ResourceRelationship(
                    source=source,
                    target=target,
                    relationship_type=RelationshipType.OWNER,
                    details=f"{source.kind} owned by {owner_kind}",
                )
            )

        return relationships

    def _discover_service_relationships(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        spec = resource.get("spec", {})
        selector = spec.get("selector", {})

        if not selector:
            return relationships

        target = ResourceIdentifier(
            kind="Pod",
            name=f"*[{self._parse_label_selector(selector)}]",
            namespace=source.namespace,
        )

        relationships.append(
            ResourceRelationship(
                source=source,
                target=target,
                relationship_type=RelationshipType.LABEL_SELECTOR,
                details=f"Selects pods with labels: {self._parse_label_selector(selector)}",
            )
        )

        return relationships

    def _discover_pod_relationships(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        spec = resource.get("spec", {})

        service_account_name = spec.get("serviceAccountName") or spec.get("serviceAccount")
        if service_account_name:
            target = ResourceIdentifier(
                kind="ServiceAccount",
                name=service_account_name,
                namespace=source.namespace,
            )
            relationships.append(
                ResourceRelationship(
                    source=source,
                    target=target,
                    relationship_type=RelationshipType.SERVICE_ACCOUNT,
                    details="Pod uses ServiceAccount",
                )
            )

        relationships.extend(self._discover_pod_volumes(resource, source))
        relationships.extend(self._discover_pod_env_from(resource, source))

        return relationships

    def _discover_pod_volumes(
        self, resource: dict[str, Any], source: ResourceIdentifier
    ) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []
        spec = resource.get("spec", {})
        volumes = spec.get("volumes") or []

        for volume in volumes:
            volume_name = volume.get("name", "")

            config_map = volume.get("configMap")
            if config_map and isinstance(config_map, dict):
                cm_name = config_map.get("name")
                if cm_name:
                    target = ResourceIdentifier(
                        kind="ConfigMap",
                        name=cm_name,
                        namespace=source.namespace,
                    )
                    relationships.append(
                        ResourceRelationship(
                            source=source,
                            target=target,
                            relationship_type=RelationshipType.VOLUME,
                            details=f"Mounts ConfigMap as volume '{volume_name}'",
                        )
                    )

            secret = volume.get("secret")
            if secret and isinstance(secret, dict):
                secret_name = secret.get("secretName")
                if secret_name:
                    target = ResourceIdentifier(
                        kind="Secret",
                        name=secret_name,
                        namespace=source.namespace,
                    )
                    relationships.append(
                        ResourceRelationship(
                            source=source,
                            target=target,
                            relationship_type=RelationshipType.VOLUME,
                            details=f"Mounts Secret as volume '{volume_name}'",
                        )
                    )

            pvc = volume.get("persistentVolumeClaim")
            if pvc and isinstance(pvc, dict):
                pvc_name = pvc.get("claimName")
                if pvc_name:
                    target = ResourceIdentifier(
                        kind="PersistentVolumeClaim",
                        name=pvc_name,
                        namespace=source.namespace,
                    )
                    relationships.append(
                        ResourceRelationship(
                            source=source,
                            target=target,
                            relationship_type=RelationshipType.PVC,
                            details=f"Uses PVC '{pvc_name}'",
                        )
                    )

        return relationships

    def _discover_pod_env_from(
        self, resource: dict[str, Any], source: ResourceIdentifier
    ) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []
        spec = resource.get("spec", {})
        containers = (spec.get("containers") or []) + (spec.get("initContainers") or [])

        for container in containers:
            container_name = container.get("name", "")

            env_from = container.get("envFrom") or []
            for env_from_source in env_from:
                cm_ref = env_from_source.get("configMapRef")
                if cm_ref and isinstance(cm_ref, dict):
                    cm_name = cm_ref.get("name")
                    if cm_name:
                        target = ResourceIdentifier(
                            kind="ConfigMap",
                            name=cm_name,
                            namespace=source.namespace,
                        )
                        relationships.append(
                            ResourceRelationship(
                                source=source,
                                target=target,
                                relationship_type=RelationshipType.ENV_FROM,
                                details=f"Container '{container_name}' uses ConfigMap for env",
                            )
                        )

                secret_ref = env_from_source.get("secretRef")
                if secret_ref and isinstance(secret_ref, dict):
                    secret_name = secret_ref.get("name")
                    if secret_name:
                        target = ResourceIdentifier(
                            kind="Secret",
                            name=secret_name,
                            namespace=source.namespace,
                        )
                        relationships.append(
                            ResourceRelationship(
                                source=source,
                                target=target,
                                relationship_type=RelationshipType.ENV_FROM,
                                details=f"Container '{container_name}' uses Secret for env",
                            )
                        )

            env = container.get("env") or []
            for env_var in env:
                value_from = env_var.get("valueFrom", {})

                cm_key_ref = value_from.get("configMapKeyRef")
                if cm_key_ref and isinstance(cm_key_ref, dict):
                    cm_name = cm_key_ref.get("name")
                    if cm_name:
                        target = ResourceIdentifier(
                            kind="ConfigMap",
                            name=cm_name,
                            namespace=source.namespace,
                        )
                        relationships.append(
                            ResourceRelationship(
                                source=source,
                                target=target,
                                relationship_type=RelationshipType.ENV_VAR,
                                details=f"Container '{container_name}' uses ConfigMap key for env var",
                            )
                        )

                secret_key_ref = value_from.get("secretKeyRef")
                if secret_key_ref and isinstance(secret_key_ref, dict):
                    secret_name = secret_key_ref.get("name")
                    if secret_name:
                        target = ResourceIdentifier(
                            kind="Secret",
                            name=secret_name,
                            namespace=source.namespace,
                        )
                        relationships.append(
                            ResourceRelationship(
                                source=source,
                                target=target,
                                relationship_type=RelationshipType.ENV_VAR,
                                details=f"Container '{container_name}' uses Secret key for env var",
                            )
                        )

        return relationships

    def _discover_ingress_relationships(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        spec = resource.get("spec", {})

        default_backend = spec.get("defaultBackend", {})
        if default_backend:
            service_name = default_backend.get("service", {}).get("name")
            if service_name:
                target = ResourceIdentifier(
                    kind="Service",
                    name=service_name,
                    namespace=source.namespace,
                )
                relationships.append(
                    ResourceRelationship(
                        source=source,
                        target=target,
                        relationship_type=RelationshipType.INGRESS_BACKEND,
                        details="Default backend service",
                    )
                )

        rules = spec.get("rules", [])
        for rule in rules:
            http = rule.get("http", {})
            paths = http.get("paths", [])

            for path in paths:
                backend = path.get("backend", {})
                service_name = backend.get("service", {}).get("name")
                if service_name:
                    target = ResourceIdentifier(
                        kind="Service",
                        name=service_name,
                        namespace=source.namespace,
                    )
                    path_value = path.get("path", "/")
                    relationships.append(
                        ResourceRelationship(
                            source=source,
                            target=target,
                            relationship_type=RelationshipType.INGRESS_BACKEND,
                            details=f"Backend service for path '{path_value}'",
                        )
                    )

        return relationships

    def _discover_pvc_relationships(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        spec = resource.get("spec", {})
        storage_class_name = spec.get("storageClassName")

        if storage_class_name:
            target = ResourceIdentifier(
                kind="StorageClass",
                name=storage_class_name,
                namespace=None,
            )
            relationships.append(
                ResourceRelationship(
                    source=source,
                    target=target,
                    relationship_type=RelationshipType.STORAGE_CLASS,
                    details="Uses StorageClass",
                )
            )

        status = resource.get("status", {})
        volume_name = status.get("volumeName")
        if volume_name:
            target = ResourceIdentifier(
                kind="PersistentVolume",
                name=volume_name,
                namespace=None,
            )
            relationships.append(
                ResourceRelationship(
                    source=source,
                    target=target,
                    relationship_type=RelationshipType.PV,
                    details="Bound to PersistentVolume",
                )
            )

        return relationships

    def _discover_pv_relationships(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        spec = resource.get("spec", {})

        claim_ref = spec.get("claimRef")
        if claim_ref:
            pvc_name = claim_ref.get("name")
            pvc_namespace = claim_ref.get("namespace")
            if pvc_name:
                target = ResourceIdentifier(
                    kind="PersistentVolumeClaim",
                    name=pvc_name,
                    namespace=pvc_namespace,
                )
                relationships.append(
                    ResourceRelationship(
                        source=source,
                        target=target,
                        relationship_type=RelationshipType.PVC,
                        details="Bound to PVC",
                    )
                )

        storage_class_name = spec.get("storageClassName")
        if storage_class_name:
            target = ResourceIdentifier(
                kind="StorageClass",
                name=storage_class_name,
                namespace=None,
            )
            relationships.append(
                ResourceRelationship(
                    source=source,
                    target=target,
                    relationship_type=RelationshipType.STORAGE_CLASS,
                    details="Uses StorageClass",
                )
            )

        return relationships

    async def _discover_workload_relationships(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        spec = resource.get("spec", {})
        template = spec.get("template", {})
        template_spec = template.get("spec", {})

        service_account_name = template_spec.get("serviceAccountName") or template_spec.get(
            "serviceAccount"
        )
        if service_account_name:
            target = ResourceIdentifier(
                kind="ServiceAccount",
                name=service_account_name,
                namespace=source.namespace,
            )
            relationships.append(
                ResourceRelationship(
                    source=source,
                    target=target,
                    relationship_type=RelationshipType.SERVICE_ACCOUNT,
                    details=f"{source.kind} uses ServiceAccount",
                )
            )

        if self.client and source.kind in ["Deployment", "StatefulSet", "DaemonSet"]:
            owned_kind = "ReplicaSet" if source.kind == "Deployment" else "Pod"
            try:
                owned_resources, _ = await self.client.list_resources(
                    kind=owned_kind, namespace=source.namespace
                )

                source_name = source.name

                for owned in owned_resources:
                    owner_refs = owned.get("metadata", {}).get("ownerReferences", [])
                    for owner_ref in owner_refs:
                        if (
                            owner_ref.get("name") == source_name
                            and owner_ref.get("kind") == source.kind
                        ):
                            owned_metadata = owned.get("metadata", {})
                            target = ResourceIdentifier(
                                kind=owned_kind,
                                name=owned_metadata.get("name"),
                                namespace=owned_metadata.get("namespace"),
                            )
                            relationships.append(
                                ResourceRelationship(
                                    source=source,
                                    target=target,
                                    relationship_type=RelationshipType.OWNED,
                                    details=f"{source.kind} owns {owned_kind}",
                                )
                            )
                            break
            except Exception as e:
                logger.debug(
                    f"Error discovering owned resources for {source.kind}/{source.name}: {e}"
                )

        elif self.client and source.kind == "ReplicaSet":
            try:
                pods, _ = await self.client.list_resources(kind="Pod", namespace=source.namespace)

                source_name = source.name

                for pod in pods:
                    owner_refs = pod.get("metadata", {}).get("ownerReferences", [])
                    for owner_ref in owner_refs:
                        if (
                            owner_ref.get("name") == source_name
                            and owner_ref.get("kind") == "ReplicaSet"
                        ):
                            pod_metadata = pod.get("metadata", {})
                            target = ResourceIdentifier(
                                kind="Pod",
                                name=pod_metadata.get("name"),
                                namespace=pod_metadata.get("namespace"),
                            )
                            relationships.append(
                                ResourceRelationship(
                                    source=source,
                                    target=target,
                                    relationship_type=RelationshipType.OWNED,
                                    details="ReplicaSet owns Pod",
                                )
                            )
                            break
            except Exception as e:
                logger.debug(f"Error discovering owned Pods for ReplicaSet/{source.name}: {e}")

        return relationships
