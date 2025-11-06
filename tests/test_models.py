"""Tests for k8s_graph.models."""

import pytest
from pydantic import ValidationError

from k8s_graph.models import (
    BuildOptions,
    DiscoveryOptions,
    RelationshipType,
    ResourceIdentifier,
    ResourceRelationship,
)


def test_resource_identifier_creation():
    """Test basic ResourceIdentifier creation."""
    rid = ResourceIdentifier(kind="Pod", name="nginx", namespace="default")
    assert rid.kind == "Pod"
    assert rid.name == "nginx"
    assert rid.namespace == "default"
    assert rid.api_version is None


def test_resource_identifier_validation():
    """Test ResourceIdentifier validation."""
    with pytest.raises(ValidationError):
        ResourceIdentifier(kind="", name="nginx")

    with pytest.raises(ValidationError):
        ResourceIdentifier(kind="pod", name="nginx")

    with pytest.raises(ValidationError):
        ResourceIdentifier(kind="Pod", name="")


def test_resource_identifier_immutable():
    """Test that ResourceIdentifier is immutable."""
    rid = ResourceIdentifier(kind="Pod", name="nginx")
    with pytest.raises(ValidationError):
        rid.kind = "Service"


def test_resource_identifier_str():
    """Test ResourceIdentifier string representation."""
    rid = ResourceIdentifier(kind="Pod", name="nginx", namespace="default")
    assert str(rid) == "Pod/nginx (ns: default)"

    rid_cluster = ResourceIdentifier(kind="Node", name="node-1")
    assert str(rid_cluster) == "Node/node-1"


def test_relationship_type_enum():
    """Test RelationshipType enum values."""
    assert RelationshipType.OWNER == "owner"
    assert RelationshipType.OWNED == "owned"
    assert RelationshipType.LABEL_SELECTOR == "label_selector"


def test_resource_relationship_creation():
    """Test ResourceRelationship creation."""
    source = ResourceIdentifier(kind="Service", name="web", namespace="default")
    target = ResourceIdentifier(kind="Pod", name="web-pod", namespace="default")

    rel = ResourceRelationship(
        source=source,
        target=target,
        relationship_type=RelationshipType.LABEL_SELECTOR,
        details="Selects pods with app=web",
    )

    assert rel.source == source
    assert rel.target == target
    assert rel.relationship_type == RelationshipType.LABEL_SELECTOR
    assert rel.details == "Selects pods with app=web"


def test_resource_relationship_immutable():
    """Test that ResourceRelationship is immutable."""
    source = ResourceIdentifier(kind="Service", name="web")
    target = ResourceIdentifier(kind="Pod", name="web-pod")
    rel = ResourceRelationship(
        source=source, target=target, relationship_type=RelationshipType.OWNER
    )

    with pytest.raises(ValidationError):
        rel.relationship_type = RelationshipType.OWNED


def test_build_options_defaults():
    """Test BuildOptions default values."""
    options = BuildOptions()
    assert options.include_rbac is True
    assert options.include_network is True
    assert options.include_crds is True
    assert options.max_nodes == 500
    assert options.cluster_id is None


def test_build_options_validation():
    """Test BuildOptions validation."""
    with pytest.raises(ValidationError):
        BuildOptions(max_nodes=0)

    with pytest.raises(ValidationError):
        BuildOptions(max_nodes=20000)

    options = BuildOptions(max_nodes=100)
    assert options.max_nodes == 100


def test_discovery_options_defaults():
    """Test DiscoveryOptions default values."""
    options = DiscoveryOptions()
    assert options.include_rbac is True
    assert options.include_network is True
    assert options.include_crds is True
