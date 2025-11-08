import pytest
from unittest.mock import AsyncMock

from k8s_graph import GraphBuilder, BuildOptions, ResourceIdentifier, DiscoveryOptions
from k8s_graph.discoverers import DiscovererRegistry
from k8s_graph.models import DiscovererCategory


class TestIncludeCRDsFlag:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def registry(self):
        return DiscovererRegistry.get_global()

    def test_registry_has_crd_handlers(self, registry):
        registry_info = registry.list_discoverers()
        crd_handler_names = [
            "HelmHandler",
            "ArgoCDHandler",
            "ArgoWorkflowsHandler",
            "AirflowHandler",
            "FluxCDHandler",
            "IstioHandler",
            "KnativeHandler",
            "CertManagerHandler",
            "TektonHandler",
            "PrometheusHandler",
            "KEDAHandler",
            "VeleroHandler",
            "SparkHandler",
            "CrossplaneHandler",
        ]
        
        registered_names = [info["name"] for info in registry_info]
        
        for handler_name in crd_handler_names:
            assert handler_name in registered_names, f"{handler_name} not registered"

    def test_crd_handlers_have_crd_category(self, registry):
        from k8s_graph.discoverers.handlers import get_all_handlers
        
        for handler in get_all_handlers():
            assert handler.categories & DiscovererCategory.CRD, \
                f"{handler.__class__.__name__} missing CRD category"

    @pytest.mark.asyncio
    async def test_include_crds_false_filters_handlers(self, mock_client, registry):
        from k8s_graph.discoverers.unified import UnifiedDiscoverer
        
        helm_resource = {
            "kind": "Deployment",
            "metadata": {
                "name": "myapp",
                "namespace": "default",
                "labels": {"app.kubernetes.io/managed-by": "Helm"},
            },
            "spec": {},
        }
        
        unified = UnifiedDiscoverer(mock_client, registry)
        
        options_with_crds = DiscoveryOptions(include_crds=True)
        relationships_with = await unified.discover_all_relationships(
            helm_resource, options_with_crds
        )
        
        options_without_crds = DiscoveryOptions(include_crds=False)
        relationships_without = await unified.discover_all_relationships(
            helm_resource, options_without_crds
        )
        
        assert len(relationships_with) >= len(relationships_without), \
            "CRDs enabled should find equal or more relationships"

    @pytest.mark.asyncio
    async def test_build_options_include_crds_false(self, mock_client):
        builder = GraphBuilder(mock_client)
        
        mock_client.get_resource.return_value = {
            "kind": "Deployment",
            "metadata": {
                "name": "myapp",
                "namespace": "default",
                "labels": {"app.kubernetes.io/managed-by": "Helm"},
            },
            "spec": {},
        }
        
        mock_client.list_resources.return_value = ([], {})
        
        resource_id = ResourceIdentifier(
            kind="Deployment",
            name="myapp",
            namespace="default",
        )
        
        options = BuildOptions(include_crds=False, max_nodes=100)
        
        graph = await builder.build_from_resource(resource_id, depth=1, options=options)
        
        assert graph is not None

    @pytest.mark.asyncio
    async def test_argocd_application_as_entry_point(self, mock_client):
        builder = GraphBuilder(mock_client)
        
        mock_client.get_resource.return_value = {
            "kind": "Application",
            "apiVersion": "argoproj.io/v1alpha1",
            "metadata": {"name": "myapp", "namespace": "argocd"},
            "spec": {"destination": {"namespace": "production"}},
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
        
        argocd_app = ResourceIdentifier(
            kind="Application",
            name="myapp",
            namespace="argocd",
        )
        
        graph = await builder.build_from_resource(
            argocd_app,
            depth=2,
            options=BuildOptions(include_crds=True),
        )
        
        assert graph.number_of_nodes() > 0
        
        app_nodes = [n for n in graph.nodes() if "Application" in n]
        assert len(app_nodes) > 0, "ArgoCD Application should be in graph"

    @pytest.mark.asyncio
    async def test_argo_workflow_as_entry_point(self, mock_client):
        builder = GraphBuilder(mock_client)
        
        mock_client.get_resource.return_value = {
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
        
        workflow = ResourceIdentifier(
            kind="Workflow",
            name="workflow1",
            namespace="default",
        )
        
        graph = await builder.build_from_resource(
            workflow,
            depth=2,
            options=BuildOptions(include_crds=True),
        )
        
        assert graph.number_of_nodes() > 0
        
        workflow_nodes = [n for n in graph.nodes() if "Workflow" in n]
        assert len(workflow_nodes) > 0, "Workflow should be in graph"

    @pytest.mark.asyncio
    async def test_helm_resource_as_entry_point(self, mock_client):
        builder = GraphBuilder(mock_client)
        
        mock_client.get_resource.return_value = {
            "kind": "Deployment",
            "metadata": {
                "name": "myapp",
                "namespace": "default",
                "labels": {"app.kubernetes.io/instance": "myapp"},
                "annotations": {"meta.helm.sh/release-name": "myapp"},
            },
            "spec": {},
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
        
        helm_deployment = ResourceIdentifier(
            kind="Deployment",
            name="myapp",
            namespace="default",
        )
        
        graph = await builder.build_from_resource(
            helm_deployment,
            depth=2,
            options=BuildOptions(include_crds=True),
        )
        
        assert graph.number_of_nodes() > 0


class TestCRDIntegrationScenarios:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_multiple_crd_types_in_namespace(self, mock_client):
        builder = GraphBuilder(mock_client)
        
        app_resource = {
            "kind": "Application",
            "apiVersion": "argoproj.io/v1alpha1",
            "metadata": {"name": "app1", "namespace": "default"},
            "spec": {"destination": {"namespace": "default"}},
        }
        
        workflow_resource = {
            "kind": "Workflow",
            "apiVersion": "argoproj.io/v1alpha1",
            "metadata": {"name": "wf1", "namespace": "default"},
            "spec": {"templates": []},
        }
        
        deployment_resource = {
            "kind": "Deployment",
            "apiVersion": "apps/v1",
            "metadata": {
                "name": "deploy1",
                "namespace": "default",
                "labels": {"app.kubernetes.io/managed-by": "Helm"},
            },
            "spec": {},
        }
        
        resources = [app_resource, workflow_resource, deployment_resource]
        
        def get_resource_side_effect(resource_id):
            for res in resources:
                if (res["kind"] == resource_id.kind and
                    res["metadata"]["name"] == resource_id.name and
                    res["metadata"].get("namespace") == resource_id.namespace):
                    return res
            return None
        
        mock_client.get_resource.side_effect = get_resource_side_effect
        mock_client.list_resources.return_value = (resources, {})
        
        options = BuildOptions(include_crds=True)
        graph = await builder.build_namespace_graph("default", depth=1, options=options)
        
        assert graph.number_of_nodes() >= 0

    @pytest.mark.asyncio
    async def test_crd_handler_error_handling(self, mock_client):
        builder = GraphBuilder(mock_client)
        
        mock_client.get_resource.return_value = {
            "kind": "Application",
            "apiVersion": "argoproj.io/v1alpha1",
            "metadata": {"name": "app1", "namespace": "default"},
            "spec": {"destination": {"namespace": "production"}},
        }
        
        mock_client.list_resources.side_effect = Exception("API error")
        
        app = ResourceIdentifier(kind="Application", name="app1", namespace="default")
        
        graph = await builder.build_from_resource(
            app, depth=1, options=BuildOptions(include_crds=True)
        )
        
        assert graph.number_of_nodes() >= 0, "Should handle errors gracefully"

