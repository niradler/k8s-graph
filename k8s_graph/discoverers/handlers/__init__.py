from k8s_graph.discoverers.handlers.airflow import AirflowHandler
from k8s_graph.discoverers.handlers.argocd import ArgoCDHandler
from k8s_graph.discoverers.handlers.argo_workflows import ArgoWorkflowsHandler
from k8s_graph.discoverers.handlers.base import BaseCRDHandler
from k8s_graph.discoverers.handlers.cert_manager import CertManagerHandler
from k8s_graph.discoverers.handlers.crossplane import CrossplaneHandler
from k8s_graph.discoverers.handlers.flux import FluxCDHandler
from k8s_graph.discoverers.handlers.helm import HelmHandler
from k8s_graph.discoverers.handlers.istio import IstioHandler
from k8s_graph.discoverers.handlers.keda import KEDAHandler
from k8s_graph.discoverers.handlers.knative import KnativeHandler
from k8s_graph.discoverers.handlers.prometheus import PrometheusHandler
from k8s_graph.discoverers.handlers.spark import SparkHandler
from k8s_graph.discoverers.handlers.tekton import TektonHandler
from k8s_graph.discoverers.handlers.velero import VeleroHandler


def get_all_handlers() -> list[BaseCRDHandler]:
    return [
        HelmHandler(),
        ArgoCDHandler(),
        ArgoWorkflowsHandler(),
        AirflowHandler(),
        FluxCDHandler(),
        IstioHandler(),
        KnativeHandler(),
        CertManagerHandler(),
        TektonHandler(),
        PrometheusHandler(),
        KEDAHandler(),
        VeleroHandler(),
        SparkHandler(),
        CrossplaneHandler(),
    ]


__all__ = [
    "BaseCRDHandler",
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
    "get_all_handlers",
]

