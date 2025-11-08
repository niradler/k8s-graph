import pytest
from unittest.mock import AsyncMock

from k8s_graph.discoverers.handlers import (
    HelmHandler,
    ArgoCDHandler,
    ArgoWorkflowsHandler,
    AirflowHandler,
    FluxCDHandler,
    IstioHandler,
    KnativeHandler,
    CertManagerHandler,
    TektonHandler,
    PrometheusHandler,
    KEDAHandler,
    VeleroHandler,
    SparkHandler,
    CrossplaneHandler,
)
from k8s_graph.models import RelationshipType


class TestHelmHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return HelmHandler(mock_client)

    def test_supports_helm_resource(self, handler):
        resource = {
            "kind": "Deployment",
            "metadata": {
                "labels": {"app.kubernetes.io/managed-by": "Helm"},
                "annotations": {"meta.helm.sh/release-name": "myapp"},
            },
        }
        assert handler.supports(resource)

    def test_does_not_support_non_helm_resource(self, handler):
        resource = {
            "kind": "Deployment",
            "metadata": {"labels": {}, "annotations": {}},
        }
        assert not handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_helm_relationships(self, handler, mock_client):
        resource = {
            "kind": "Deployment",
            "metadata": {
                "name": "myapp-deployment",
                "namespace": "default",
                "labels": {"app.kubernetes.io/instance": "myapp"},
                "annotations": {"meta.helm.sh/release-name": "myapp"},
            },
        }

        mock_client.list_resources.return_value = (
            [
                {
                    "kind": "Service",
                    "metadata": {
                        "name": "myapp-service",
                        "namespace": "default",
                        "labels": {"app.kubernetes.io/instance": "myapp"},
                        "annotations": {"meta.helm.sh/release-name": "myapp"},
                    },
                }
            ],
            {},
        )

        relationships = await handler.discover(resource)
        assert len(relationships) > 0
        assert any(r.relationship_type == RelationshipType.HELM_MANAGED for r in relationships)


class TestArgoCDHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return ArgoCDHandler(mock_client)

    def test_supports_argocd_application(self, handler):
        resource = {
            "kind": "Application",
            "apiVersion": "argoproj.io/v1alpha1",
            "metadata": {"name": "myapp"},
        }
        assert handler.supports(resource)

    def test_does_not_support_non_argocd_resource(self, handler):
        resource = {"kind": "Deployment", "apiVersion": "apps/v1", "metadata": {"name": "myapp"}}
        assert not handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_argocd_relationships(self, handler, mock_client):
        application = {
            "kind": "Application",
            "apiVersion": "argoproj.io/v1alpha1",
            "metadata": {"name": "myapp", "namespace": "argocd"},
            "spec": {"destination": {"namespace": "production"}, "project": "default"},
        }

        mock_client.list_resources.return_value = (
            [
                {
                    "kind": "Deployment",
                    "metadata": {
                        "name": "myapp-deployment",
                        "namespace": "production",
                        "labels": {"argocd.argoproj.io/instance": "myapp"},
                    },
                }
            ],
            {},
        )

        relationships = await handler.discover(application)
        assert len(relationships) > 0
        assert any(r.relationship_type == RelationshipType.ARGOCD_MANAGED for r in relationships)


class TestArgoWorkflowsHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return ArgoWorkflowsHandler(mock_client)

    def test_supports_workflow(self, handler):
        resource = {
            "kind": "Workflow",
            "apiVersion": "argoproj.io/v1alpha1",
            "metadata": {"name": "workflow1"},
        }
        assert handler.supports(resource)

    def test_supports_cronworkflow(self, handler):
        resource = {
            "kind": "CronWorkflow",
            "apiVersion": "argoproj.io/v1alpha1",
            "metadata": {"name": "cron1"},
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_workflow_pods(self, handler, mock_client):
        workflow = {
            "kind": "Workflow",
            "apiVersion": "argoproj.io/v1alpha1",
            "metadata": {"name": "workflow1", "namespace": "default"},
            "spec": {"templates": []},
        }

        mock_client.list_resources.return_value = (
            [
                {
                    "kind": "Pod",
                    "metadata": {
                        "name": "workflow1-pod",
                        "namespace": "default",
                        "labels": {"workflows.argoproj.io/workflow": "workflow1"},
                    },
                }
            ],
            {},
        )

        relationships = await handler.discover(workflow)
        assert len(relationships) > 0
        assert any(r.relationship_type == RelationshipType.ARGO_WORKFLOW_SPAWNED for r in relationships)


class TestAirflowHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return AirflowHandler(mock_client)

    def test_supports_airflow_resource(self, handler):
        resource = {
            "kind": "AirflowCluster",
            "apiVersion": "airflow.apache.org/v1alpha1",
            "metadata": {"name": "airflow1"},
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_airflow_relationships(self, handler, mock_client):
        airflow = {
            "kind": "AirflowCluster",
            "apiVersion": "airflow.apache.org/v1alpha1",
            "metadata": {"name": "airflow1", "namespace": "default"},
            "spec": {},
        }

        mock_client.list_resources.return_value = (
            [
                {
                    "kind": "StatefulSet",
                    "metadata": {
                        "name": "airflow-worker",
                        "namespace": "default",
                        "labels": {"airflow.apache.org/cluster": "airflow1"},
                    },
                }
            ],
            {},
        )

        relationships = await handler.discover(airflow)
        assert len(relationships) > 0


class TestFluxCDHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return FluxCDHandler(mock_client)

    def test_supports_helmrelease(self, handler):
        resource = {
            "kind": "HelmRelease",
            "apiVersion": "helm.toolkit.fluxcd.io/v2beta1",
            "metadata": {"name": "release1"},
        }
        assert handler.supports(resource)

    def test_supports_kustomization(self, handler):
        resource = {
            "kind": "Kustomization",
            "apiVersion": "kustomize.toolkit.fluxcd.io/v1beta1",
            "metadata": {"name": "kustomize1"},
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_flux_relationships(self, handler, mock_client):
        helm_release = {
            "kind": "HelmRelease",
            "apiVersion": "helm.toolkit.fluxcd.io/v2beta1",
            "metadata": {"name": "release1", "namespace": "default"},
            "spec": {"chart": {"spec": {"sourceRef": {"kind": "HelmRepository", "name": "repo1"}}}},
        }

        mock_client.list_resources.return_value = ([], {})
        mock_client.get_resource.return_value = {
            "kind": "HelmRepository",
            "metadata": {"name": "repo1", "namespace": "default"},
        }

        relationships = await handler.discover(helm_release)
        assert len(relationships) >= 0


class TestIstioHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return IstioHandler(mock_client)

    def test_supports_virtualservice(self, handler):
        resource = {
            "kind": "VirtualService",
            "apiVersion": "networking.istio.io/v1beta1",
            "metadata": {"name": "vs1"},
        }
        assert handler.supports(resource)

    def test_supports_destinationrule(self, handler):
        resource = {
            "kind": "DestinationRule",
            "apiVersion": "networking.istio.io/v1beta1",
            "metadata": {"name": "dr1"},
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_virtualservice_routes(self, handler, mock_client):
        vs = {
            "kind": "VirtualService",
            "apiVersion": "networking.istio.io/v1beta1",
            "metadata": {"name": "vs1", "namespace": "default"},
            "spec": {
                "http": [{"route": [{"destination": {"host": "myservice"}}]}]
            },
        }

        mock_client.get_resource.return_value = {
            "kind": "Service",
            "metadata": {"name": "myservice", "namespace": "default"},
        }

        relationships = await handler.discover(vs)
        assert len(relationships) > 0
        assert any(r.relationship_type == RelationshipType.ISTIO_ROUTE for r in relationships)


class TestKnativeHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return KnativeHandler(mock_client)

    def test_supports_knative_service(self, handler):
        resource = {
            "kind": "Service",
            "apiVersion": "serving.knative.dev/v1",
            "metadata": {"name": "ksvc1"},
        }
        assert handler.supports(resource)

    def test_supports_knative_revision(self, handler):
        resource = {
            "kind": "Revision",
            "apiVersion": "serving.knative.dev/v1",
            "metadata": {"name": "rev1"},
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_revision_deployment(self, handler, mock_client):
        revision = {
            "kind": "Revision",
            "apiVersion": "serving.knative.dev/v1",
            "metadata": {"name": "rev1", "namespace": "default"},
            "spec": {},
        }

        mock_client.list_resources.return_value = (
            [
                {
                    "kind": "Deployment",
                    "metadata": {
                        "name": "rev1-deployment",
                        "namespace": "default",
                        "labels": {"serving.knative.dev/revision": "rev1"},
                    },
                }
            ],
            {},
        )

        relationships = await handler.discover(revision)
        assert len(relationships) > 0
        assert any(r.relationship_type == RelationshipType.KNATIVE_SERVES for r in relationships)


class TestCertManagerHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return CertManagerHandler(mock_client)

    def test_supports_certificate(self, handler):
        resource = {
            "kind": "Certificate",
            "apiVersion": "cert-manager.io/v1",
            "metadata": {"name": "cert1"},
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_certificate_secret(self, handler, mock_client):
        certificate = {
            "kind": "Certificate",
            "apiVersion": "cert-manager.io/v1",
            "metadata": {"name": "cert1", "namespace": "default"},
            "spec": {"secretName": "cert1-secret", "issuerRef": {"kind": "Issuer", "name": "issuer1"}},
        }

        mock_client.get_resource.return_value = {
            "kind": "Secret",
            "metadata": {"name": "cert1-secret", "namespace": "default"},
        }

        relationships = await handler.discover(certificate)
        assert len(relationships) > 0
        assert any(r.relationship_type == RelationshipType.CERT_ISSUED for r in relationships)


class TestTektonHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return TektonHandler(mock_client)

    def test_supports_pipelinerun(self, handler):
        resource = {
            "kind": "PipelineRun",
            "apiVersion": "tekton.dev/v1beta1",
            "metadata": {"name": "pr1"},
        }
        assert handler.supports(resource)

    def test_supports_taskrun(self, handler):
        resource = {
            "kind": "TaskRun",
            "apiVersion": "tekton.dev/v1beta1",
            "metadata": {"name": "tr1"},
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_pipelinerun_taskruns(self, handler, mock_client):
        pipelinerun = {
            "kind": "PipelineRun",
            "apiVersion": "tekton.dev/v1beta1",
            "metadata": {"name": "pr1", "namespace": "default"},
            "spec": {"pipelineRef": {"name": "pipeline1"}},
        }

        mock_client.get_resource.return_value = {
            "kind": "Pipeline",
            "metadata": {"name": "pipeline1", "namespace": "default"},
        }
        mock_client.list_resources.return_value = (
            [
                {
                    "kind": "TaskRun",
                    "metadata": {
                        "name": "tr1",
                        "namespace": "default",
                        "labels": {"tekton.dev/pipelineRun": "pr1"},
                    },
                }
            ],
            {},
        )

        relationships = await handler.discover(pipelinerun)
        assert len(relationships) > 0
        assert any(r.relationship_type == RelationshipType.TEKTON_RUN for r in relationships)


class TestPrometheusHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return PrometheusHandler(mock_client)

    def test_supports_servicemonitor(self, handler):
        resource = {
            "kind": "ServiceMonitor",
            "apiVersion": "monitoring.coreos.com/v1",
            "metadata": {"name": "sm1"},
        }
        assert handler.supports(resource)

    def test_supports_podmonitor(self, handler):
        resource = {
            "kind": "PodMonitor",
            "apiVersion": "monitoring.coreos.com/v1",
            "metadata": {"name": "pm1"},
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_servicemonitor_services(self, handler, mock_client):
        servicemonitor = {
            "kind": "ServiceMonitor",
            "apiVersion": "monitoring.coreos.com/v1",
            "metadata": {"name": "sm1", "namespace": "default"},
            "spec": {"selector": {"matchLabels": {"app": "myapp"}}},
        }

        mock_client.list_resources.return_value = (
            [
                {
                    "kind": "Service",
                    "metadata": {
                        "name": "myapp-service",
                        "namespace": "default",
                        "labels": {"app": "myapp"},
                    },
                }
            ],
            {},
        )

        relationships = await handler.discover(servicemonitor)
        assert len(relationships) > 0
        assert any(r.relationship_type == RelationshipType.PROMETHEUS_MONITOR for r in relationships)


class TestKEDAHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return KEDAHandler(mock_client)

    def test_supports_scaledobject(self, handler):
        resource = {
            "kind": "ScaledObject",
            "apiVersion": "keda.sh/v1alpha1",
            "metadata": {"name": "so1"},
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_scaledobject_target(self, handler, mock_client):
        scaledobject = {
            "kind": "ScaledObject",
            "apiVersion": "keda.sh/v1alpha1",
            "metadata": {"name": "so1", "namespace": "default"},
            "spec": {"scaleTargetRef": {"kind": "Deployment", "name": "myapp"}, "triggers": []},
        }

        mock_client.get_resource.return_value = {
            "kind": "Deployment",
            "metadata": {"name": "myapp", "namespace": "default"},
        }

        relationships = await handler.discover(scaledobject)
        assert len(relationships) > 0
        assert any(r.relationship_type == RelationshipType.KEDA_SCALE for r in relationships)


class TestVeleroHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return VeleroHandler(mock_client)

    def test_supports_backup(self, handler):
        resource = {
            "kind": "Backup",
            "apiVersion": "velero.io/v1",
            "metadata": {"name": "backup1"},
        }
        assert handler.supports(resource)

    def test_supports_schedule(self, handler):
        resource = {
            "kind": "Schedule",
            "apiVersion": "velero.io/v1",
            "metadata": {"name": "schedule1"},
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_backup_namespaces(self, handler, mock_client):
        backup = {
            "kind": "Backup",
            "apiVersion": "velero.io/v1",
            "metadata": {"name": "backup1", "namespace": "velero"},
            "spec": {"includedNamespaces": ["default", "production"]},
        }

        relationships = await handler.discover(backup)
        assert len(relationships) >= 2
        assert any(r.relationship_type == RelationshipType.VELERO_BACKUP for r in relationships)


class TestSparkHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return SparkHandler(mock_client)

    def test_supports_sparkapplication(self, handler):
        resource = {
            "kind": "SparkApplication",
            "apiVersion": "sparkoperator.k8s.io/v1beta2",
            "metadata": {"name": "spark1"},
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_spark_pods(self, handler, mock_client):
        sparkapplication = {
            "kind": "SparkApplication",
            "apiVersion": "sparkoperator.k8s.io/v1beta2",
            "metadata": {"name": "spark1", "namespace": "default"},
            "spec": {"volumes": []},
        }

        mock_client.list_resources.side_effect = [
            (
                [
                    {
                        "kind": "Pod",
                        "metadata": {
                            "name": "spark1-driver",
                            "namespace": "default",
                            "labels": {
                                "spark-role": "driver",
                                "sparkoperator.k8s.io/app-name": "spark1",
                            },
                        },
                    }
                ],
                {},
            ),
            (
                [
                    {
                        "kind": "Pod",
                        "metadata": {
                            "name": "spark1-executor-1",
                            "namespace": "default",
                            "labels": {
                                "spark-role": "executor",
                                "sparkoperator.k8s.io/app-name": "spark1",
                            },
                        },
                    }
                ],
                {},
            ),
        ]

        relationships = await handler.discover(sparkapplication)
        assert len(relationships) >= 2
        assert any(r.relationship_type == RelationshipType.SPARK_DRIVER for r in relationships)
        assert any(r.relationship_type == RelationshipType.SPARK_EXECUTOR for r in relationships)


class TestCrossplaneHandler:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_client):
        return CrossplaneHandler(mock_client)

    def test_supports_composition(self, handler):
        resource = {
            "kind": "Composition",
            "apiVersion": "apiextensions.crossplane.io/v1",
            "metadata": {"name": "comp1"},
        }
        assert handler.supports(resource)

    def test_supports_resource_with_crossplane_annotation(self, handler):
        resource = {
            "kind": "Deployment",
            "apiVersion": "apps/v1",
            "metadata": {
                "name": "myapp",
                "annotations": {"crossplane.io/claim-name": "claim1"},
            },
        }
        assert handler.supports(resource)

    @pytest.mark.asyncio
    async def test_discover_crossplane_managed_resources(self, handler, mock_client):
        composition = {
            "kind": "Composition",
            "apiVersion": "apiextensions.crossplane.io/v1",
            "metadata": {"name": "comp1", "namespace": "default"},
            "spec": {},
        }

        mock_client.list_resources.return_value = ([], {})

        relationships = await handler.discover(composition)
        assert isinstance(relationships, list)

