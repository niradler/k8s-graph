import logging
from typing import Any

from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.models import (
    RelationshipType,
    ResourceIdentifier,
    ResourceRelationship,
)

logger = logging.getLogger(__name__)


class TemporalHandler(BaseCRDHandler):
    """
    Discoverer for Temporal workflow resources.

    Identifies Temporal workers, scheduled workflows (CronJobs), and their
    connections to the Temporal server. Temporal uses standard K8s resources
    (Deployments, CronJobs) rather than CRDs.

    Key relationships:
    - Worker Deployments → Temporal Frontend Service
    - CronJobs (Schedules) → Spawned Jobs/Pods
    - Worker Pods → Temporal Frontend Service
    """

    def supports(self, resource: dict[str, Any]) -> bool:
        labels = resource.get("metadata", {}).get("labels", {})
        spec = resource.get("spec", {})
        kind = resource.get("kind")

        if kind == "Deployment":
            component = labels.get("component", "")
            return "workflow" in component.lower() or "worker" in component.lower()

        elif kind == "CronJob":
            component = labels.get("component", "")
            return "workflow" in component.lower()

        elif kind == "Pod":
            component = labels.get("component", "")
            app = labels.get("app", "")
            return (
                "workflow" in component.lower()
                or "worker" in component.lower()
                or "workflow" in app.lower()
            )

        elif kind == "Service":
            component = labels.get("app.kubernetes.io/component", "")
            return component == "frontend" and "temporal" in labels.get(
                "app.kubernetes.io/name", ""
            )

        return False

    async def discover(self, resource: dict[str, Any]) -> list[ResourceRelationship]:
        relationships = []
        kind = resource.get("kind")

        if kind == "Deployment":
            relationships.extend(await self._discover_worker_deployment(resource))
        elif kind == "CronJob":
            relationships.extend(await self._discover_scheduled_workflow(resource))
        elif kind == "Pod":
            relationships.extend(await self._discover_worker_pod(resource))
        elif kind == "Service":
            relationships.extend(await self._discover_temporal_frontend(resource))

        return relationships

    async def _discover_worker_deployment(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        """
        Discover relationships for Temporal worker Deployments.

        Workers connect to the Temporal frontend service via TEMPORAL_HOST env var.
        """
        relationships = []
        metadata = resource.get("metadata", {})
        namespace = metadata.get("namespace")
        source_id = self._extract_resource_identifier(resource)

        temporal_host = self._extract_temporal_host(resource)
        if temporal_host:
            service_name, service_namespace = self._parse_temporal_host(
                temporal_host, namespace
            )

            temporal_frontend_id = ResourceIdentifier(
                kind="Service",
                name=service_name,
                namespace=service_namespace or namespace,
            )

            relationships.append(
                ResourceRelationship(
                    source=source_id,
                    target=temporal_frontend_id,
                    relationship_type=RelationshipType.TEMPORAL_WORKER,
                    details=f"Temporal worker connecting to {temporal_host}",
                )
            )

        return relationships

    async def _discover_scheduled_workflow(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        """
        Discover relationships for Temporal scheduled workflows (CronJobs).

        CronJobs create Jobs that spawn Pods executing scheduled workflows.
        """
        relationships = []
        metadata = resource.get("metadata", {})
        namespace = metadata.get("namespace")
        source_id = self._extract_resource_identifier(resource)

        cronjob_name = metadata.get("name")
        if cronjob_name and self.client:
            try:
                jobs = await self._find_resources_by_label(
                    kind="Job",
                    namespace=namespace,
                    label_selector={"batch.kubernetes.io/job-name": f"{cronjob_name}*"},
                )

                for job in jobs:
                    job_metadata = job.get("metadata", {})
                    job_name = job_metadata.get("name", "")

                    if cronjob_name in job_name:
                        job_id = ResourceIdentifier(
                            kind="Job",
                            name=job_name,
                            namespace=namespace,
                        )

                        relationships.append(
                            ResourceRelationship(
                                source=source_id,
                                target=job_id,
                                relationship_type=RelationshipType.TEMPORAL_SCHEDULE,
                                details=f"CronJob schedules workflow execution via Job",
                            )
                        )

            except Exception as e:
                logger.debug(
                    f"Could not find Jobs for CronJob {cronjob_name}: {e}",
                    exc_info=True,
                )

        temporal_host = self._extract_temporal_host(resource)
        if temporal_host:
            service_name, service_namespace = self._parse_temporal_host(
                temporal_host, namespace
            )

            temporal_frontend_id = ResourceIdentifier(
                kind="Service",
                name=service_name,
                namespace=service_namespace or namespace,
            )

            relationships.append(
                ResourceRelationship(
                    source=source_id,
                    target=temporal_frontend_id,
                    relationship_type=RelationshipType.TEMPORAL_WORKFLOW,
                    details=f"Scheduled workflow connects to {temporal_host}",
                )
            )

        return relationships

    async def _discover_worker_pod(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        """
        Discover relationships for Temporal worker Pods.

        Worker pods connect to the Temporal frontend service.
        """
        relationships = []
        metadata = resource.get("metadata", {})
        namespace = metadata.get("namespace")
        source_id = self._extract_resource_identifier(resource)

        temporal_host = self._extract_temporal_host(resource)
        if temporal_host:
            service_name, service_namespace = self._parse_temporal_host(
                temporal_host, namespace
            )

            temporal_frontend_id = ResourceIdentifier(
                kind="Service",
                name=service_name,
                namespace=service_namespace or namespace,
            )

            relationships.append(
                ResourceRelationship(
                    source=source_id,
                    target=temporal_frontend_id,
                    relationship_type=RelationshipType.TEMPORAL_WORKER,
                    details=f"Worker pod connects to {temporal_host}",
                )
            )

        return relationships

    async def _discover_temporal_frontend(
        self, resource: dict[str, Any]
    ) -> list[ResourceRelationship]:
        """
        Discover relationships for Temporal frontend Service.

        The frontend service is the entry point for workers and workflows.
        This can discover which workers/schedules connect to it.
        """
        relationships = []

        return relationships

    def _extract_temporal_host(self, resource: dict[str, Any]) -> str | None:
        """
        Extract TEMPORAL_HOST environment variable from resource containers.

        Returns:
            Temporal host string (e.g., "temporal-frontend.temporal-main.svc:7233")
            or None if not found.
        """
        spec = resource.get("spec", {})

        containers = []
        if resource.get("kind") == "CronJob":
            containers = (
                spec.get("jobTemplate", {})
                .get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("containers", [])
            )
        elif resource.get("kind") in ["Deployment", "StatefulSet", "DaemonSet"]:
            containers = spec.get("template", {}).get("spec", {}).get("containers", [])
        elif resource.get("kind") == "Pod":
            containers = spec.get("containers", [])

        for container in containers:
            env_vars = container.get("env", [])
            for env_var in env_vars:
                if env_var.get("name") == "TEMPORAL_HOST":
                    return env_var.get("value")

        return None

    def _parse_temporal_host(
        self, temporal_host: str, default_namespace: str | None
    ) -> tuple[str, str | None]:
        """
        Parse TEMPORAL_HOST value into service name and namespace.

        Examples:
            "temporal-frontend.temporal-main.svc" -> ("temporal-frontend", "temporal-main")
            "temporal-frontend.temporal-main.svc:7233" -> ("temporal-frontend", "temporal-main")
            "temporal-frontend" -> ("temporal-frontend", None)

        Returns:
            Tuple of (service_name, namespace)
        """
        if ":" in temporal_host:
            temporal_host = temporal_host.split(":")[0]

        parts = temporal_host.split(".")

        if len(parts) >= 2:
            service_name = parts[0]
            namespace = parts[1]
            return service_name, namespace
        elif len(parts) == 1:
            return parts[0], default_namespace

        return temporal_host, default_namespace

    @property
    def priority(self) -> int:
        return 50

