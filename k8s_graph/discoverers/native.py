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


class NativeResourceDiscoverer(BaseDiscoverer):
    """
    Discoverer for native Kubernetes resource relationships.

    Handles standard relationships including:
    - Owner references (ReplicaSet -> Deployment, Pod -> Job)
    - Owned resources (Deployment -> ReplicaSets -> Pods, CronJob -> Jobs -> Pods)
    - Label selectors (Service -> Pods)
    - Volume mounts (Pod -> ConfigMap/Secret/PVC)
    - Environment variables (Pod -> ConfigMap/Secret)
    - Service accounts (Pod/Job/CronJob -> ServiceAccount)
    - Service endpoints (Service -> Pods)
    - Ingress backends (Ingress -> Service)
    - PV/PVC relationships (PVC -> PV, Pod -> PVC)
    - Autoscaling (HPA -> Deployment/StatefulSet/ReplicaSet)
    - Pod disruption (PDB -> Deployment/StatefulSet)
    """

    def __init__(self, client: K8sClientProtocol | None = None) -> None:
        super().__init__(client)

    def supports(self, resource: dict[str, Any]) -> bool:
        return True

    @property
    def categories(self) -> DiscovererCategory:
        return DiscovererCategory.NATIVE

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships: list[ResourceRelationship] = []

        kind = resource.get("kind")
        if not kind:
            return relationships

        relationships.extend(self._discover_owner_references(resource))

        if kind == "Service":
            relationships.extend(self._discover_service_relationships(resource))
        elif kind == "Endpoints":
            relationships.extend(self._discover_endpoints_relationships(resource))
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
        elif kind == "Job":
            relationships.extend(await self._discover_job_relationships(resource))
        elif kind == "CronJob":
            relationships.extend(await self._discover_cronjob_relationships(resource))
        elif kind == "HorizontalPodAutoscaler":
            relationships.extend(self._discover_hpa_relationships(resource))
        elif kind == "PodDisruptionBudget":
            relationships.extend(self._discover_pdb_relationships(resource))

        return relationships

    def _discover_owner_references(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        """
        Discover owner reference relationships.

        Creates edges from parent to child for proper K8s hierarchy visualization:
        Deployment → ReplicaSet → Pod
        """
        relationships: list[ResourceRelationship] = []
        metadata = resource.get("metadata", {})
        owner_refs = metadata.get("ownerReferences", [])

        if not owner_refs:
            return relationships

        try:
            child = self._extract_resource_identifier(resource)
        except ValueError as e:
            logger.warning(f"Cannot extract resource identifier: {e}")
            return relationships

        for owner_ref in owner_refs:
            owner_kind = owner_ref.get("kind")
            owner_name = owner_ref.get("name")
            owner_api_version = owner_ref.get("apiVersion")

            if not owner_kind or not owner_name:
                continue

            parent = ResourceIdentifier(
                kind=owner_kind,
                name=owner_name,
                namespace=metadata.get("namespace"),
                api_version=owner_api_version,
            )

            # Create edge from parent to child (correct hierarchy direction)
            relationships.append(
                ResourceRelationship(
                    source=parent,
                    target=child,
                    relationship_type=RelationshipType.OWNED,
                    details=f"{owner_kind} owns {child.kind}",
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

        # Service -> Pods via label selector
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

        # Service -> Endpoints (automatically created with same name)
        endpoints_target = ResourceIdentifier(
            kind="Endpoints",
            name=source.name,
            namespace=source.namespace,
        )
        relationships.append(
            ResourceRelationship(
                source=source,
                target=endpoints_target,
                relationship_type=RelationshipType.SERVICE_ENDPOINT,
                details="Service manages Endpoints",
            )
        )

        return relationships

    def _discover_endpoints_relationships(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        """Discover relationships from Endpoints to Pods."""
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        # Endpoints contain subsets with addresses that reference Pods
        subsets = resource.get("subsets", [])
        for subset in subsets:
            addresses = subset.get("addresses", [])
            for address in addresses:
                target_ref = address.get("targetRef", {})
                if target_ref.get("kind") == "Pod":
                    pod_name = target_ref.get("name")
                    pod_namespace = target_ref.get("namespace")
                    if pod_name:
                        target = ResourceIdentifier(
                            kind="Pod",
                            name=pod_name,
                            namespace=pod_namespace or source.namespace,
                        )
                        relationships.append(
                            ResourceRelationship(
                                source=source,
                                target=target,
                                relationship_type=RelationshipType.SERVICE_ENDPOINT,
                                details=f"Endpoints routes to Pod IP {address.get('ip')}",
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
                            break  # Break inner loop after finding matching owner ref
            except Exception as e:
                logger.debug(f"Error discovering owned Pods for ReplicaSet/{source.name}: {e}")

        return relationships

    async def _discover_job_relationships(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        """
        Discover relationships for Job resources.

        Jobs:
        - Own Pods
        - Reference ServiceAccount (from pod template)
        - Reference ConfigMaps/Secrets (from pod template)
        """
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
                    details="Job uses ServiceAccount",
                )
            )

        if self.client:
            try:
                pods, _ = await self.client.list_resources(kind="Pod", namespace=source.namespace)

                source_name = source.name

                for pod in pods:
                    owner_refs = pod.get("metadata", {}).get("ownerReferences", [])
                    for owner_ref in owner_refs:
                        if owner_ref.get("name") == source_name and owner_ref.get("kind") == "Job":
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
                                    details="Job owns Pod",
                                )
                            )
                            break
            except Exception as e:
                logger.debug(f"Error discovering owned Pods for Job/{source.name}: {e}")

        return relationships

    async def _discover_cronjob_relationships(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        """
        Discover relationships for CronJob resources.

        CronJobs:
        - Create Jobs
        - Reference ServiceAccount (from job template)
        """
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        spec = resource.get("spec", {})
        job_template = spec.get("jobTemplate", {})
        job_spec = job_template.get("spec", {})
        template = job_spec.get("template", {})
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
                    details="CronJob uses ServiceAccount",
                )
            )

        if self.client:
            try:
                jobs, _ = await self.client.list_resources(kind="Job", namespace=source.namespace)

                source_name = source.name

                for job in jobs:
                    owner_refs = job.get("metadata", {}).get("ownerReferences", [])
                    for owner_ref in owner_refs:
                        if (
                            owner_ref.get("name") == source_name
                            and owner_ref.get("kind") == "CronJob"
                        ):
                            job_metadata = job.get("metadata", {})
                            target = ResourceIdentifier(
                                kind="Job",
                                name=job_metadata.get("name"),
                                namespace=job_metadata.get("namespace"),
                            )
                            relationships.append(
                                ResourceRelationship(
                                    source=source,
                                    target=target,
                                    relationship_type=RelationshipType.OWNED,
                                    details="CronJob creates Job",
                                )
                            )
                            break
            except Exception as e:
                logger.debug(f"Error discovering owned Jobs for CronJob/{source.name}: {e}")

        return relationships

    def _discover_hpa_relationships(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        """
        Discover relationships for HorizontalPodAutoscaler resources.

        HPA scales target workloads (Deployment, StatefulSet, ReplicaSet).
        """
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        spec = resource.get("spec", {})
        scale_target_ref = spec.get("scaleTargetRef", {})

        target_kind = scale_target_ref.get("kind")
        target_name = scale_target_ref.get("name")

        if target_kind and target_name:
            target = ResourceIdentifier(
                kind=target_kind,
                name=target_name,
                namespace=source.namespace,
                api_version=scale_target_ref.get("apiVersion"),
            )
            relationships.append(
                ResourceRelationship(
                    source=source,
                    target=target,
                    relationship_type=RelationshipType.AUTOSCALING,
                    details=f"HPA scales {target_kind}",
                )
            )

        return relationships

    def _discover_pdb_relationships(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        """
        Discover relationships for PodDisruptionBudget resources.

        PDB protects pods via label selector.
        """
        relationships: list[ResourceRelationship] = []

        try:
            source = self._extract_resource_identifier(resource)
        except ValueError:
            return relationships

        spec = resource.get("spec", {})
        selector = spec.get("selector", {})

        if not selector:
            return relationships

        match_labels = selector.get("matchLabels", {})
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
                    relationship_type=RelationshipType.POD_DISRUPTION_BUDGET,
                    details=f"PDB protects pods with labels: {self._parse_label_selector(match_labels)}",
                )
            )

        return relationships
