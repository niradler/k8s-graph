from enum import Enum, Flag, auto

from pydantic import BaseModel, Field, field_validator


class DiscovererCategory(Flag):
    """
    Categories for discoverers, used for filtering during graph building.

    Uses Flag enum to support multiple categories per discoverer.
    """

    NATIVE = auto()
    RBAC = auto()
    NETWORK = auto()
    CRD = auto()


class ResourceIdentifier(BaseModel):
    """
    Unique identifier for a Kubernetes resource.

    A resource is uniquely identified by its kind, name, and optionally namespace.
    For cluster-scoped resources, namespace should be None.
    """

    kind: str = Field(..., description="Kubernetes resource kind (e.g., 'Pod', 'Service')")
    name: str = Field(..., description="Resource name")
    namespace: str | None = Field(
        default=None, description="Resource namespace (None for cluster-scoped resources)"
    )
    api_version: str | None = Field(default=None, description="API version (e.g., 'v1', 'apps/v1')")

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        if not v:
            raise ValueError("kind cannot be empty")
        if not v[0].isupper():
            raise ValueError("kind must start with an uppercase letter")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v:
            raise ValueError("name cannot be empty")
        return v

    def __str__(self) -> str:
        if self.namespace:
            return f"{self.kind}/{self.name} (ns: {self.namespace})"
        return f"{self.kind}/{self.name}"

    def __repr__(self) -> str:
        parts = [f"kind={self.kind!r}", f"name={self.name!r}"]
        if self.namespace:
            parts.append(f"namespace={self.namespace!r}")
        if self.api_version:
            parts.append(f"api_version={self.api_version!r}")
        return f"ResourceIdentifier({', '.join(parts)})"


class RelationshipType(str, Enum):
    """
    Types of relationships between Kubernetes resources.
    """

    OWNER = "owner"
    OWNED = "owned"
    LABEL_SELECTOR = "label_selector"
    VOLUME = "volume"
    ENV_FROM = "env_from"
    ENV_VAR = "env_var"
    SERVICE_ACCOUNT = "service_account"
    NETWORK_POLICY = "network_policy"
    NETWORK_POLICY_INGRESS = "network_policy_ingress"
    NETWORK_POLICY_EGRESS = "network_policy_egress"
    INGRESS_BACKEND = "ingress_backend"
    SERVICE_ENDPOINT = "service_endpoint"
    ROLE_BINDING = "role_binding"
    CLUSTER_ROLE_BINDING = "cluster_role_binding"
    PVC = "pvc"
    PV = "pv"
    STORAGE_CLASS = "storage_class"
    MANAGED = "managed"
    AUTOSCALING = "autoscaling"
    POD_DISRUPTION_BUDGET = "pod_disruption_budget"


class ResourceRelationship(BaseModel):
    """
    A relationship between two Kubernetes resources.

    Represents a directed edge in the resource graph from source to target.
    """

    source: ResourceIdentifier = Field(..., description="Source resource")
    target: ResourceIdentifier = Field(..., description="Target resource")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    details: str | None = Field(
        default=None, description="Additional details about the relationship"
    )

    model_config = {"frozen": True, "extra": "forbid"}

    def __str__(self) -> str:
        base = f"{self.source} --[{self.relationship_type.value}]--> {self.target}"
        if self.details:
            return f"{base} ({self.details})"
        return base

    def __repr__(self) -> str:
        parts = [
            f"source={self.source!r}",
            f"target={self.target!r}",
            f"relationship_type={self.relationship_type!r}",
        ]
        if self.details:
            parts.append(f"details={self.details!r}")
        return f"ResourceRelationship({', '.join(parts)})"


class BuildOptions(BaseModel):
    """
    Options for building a resource graph.
    """

    include_rbac: bool = Field(
        default=True, description="Include RBAC relationships (ServiceAccount, Role, etc.)"
    )
    include_network: bool = Field(default=True, description="Include NetworkPolicy relationships")
    include_crds: bool = Field(default=True, description="Include custom resource definitions")
    max_nodes: int = Field(default=500, description="Maximum number of nodes in the graph", gt=0)
    sample_pods: bool = Field(
        default=False,
        description="Sample pods by template (only include one pod per ReplicaSet/template). Set to True for large clusters to reduce graph size.",
    )
    cluster_id: str | None = Field(
        default=None, description="Optional cluster identifier for multi-cluster scenarios"
    )

    model_config = {"extra": "forbid"}

    @field_validator("max_nodes")
    @classmethod
    def validate_max_nodes(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_nodes must be at least 1")
        if v > 10000:
            raise ValueError("max_nodes cannot exceed 10000 (performance limit)")
        return v


class DiscoveryOptions(BaseModel):
    """
    Options for relationship discovery.
    """

    include_rbac: bool = Field(
        default=True, description="Discover RBAC relationships (ServiceAccount, Role, etc.)"
    )
    include_network: bool = Field(default=True, description="Discover NetworkPolicy relationships")
    include_crds: bool = Field(default=True, description="Discover custom resource relationships")

    model_config = {"extra": "forbid"}
