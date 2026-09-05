from datetime import datetime

from pydantic import BaseModel


class CommunityMembershipResult(BaseModel):
    id: int
    members: list[str]
    size: int


class CommunityDetectionResult(BaseModel):
    computed_at: datetime
    num_communities: int
    communities: list[CommunityMembershipResult]


class CentralityResult(BaseModel):
    computed_at: datetime
    betweenness: dict[str, float]
    degree: dict[str, float]


class HealthResult(BaseModel):
    computed_at: datetime
    total_nodes: int
    total_edges: int
    connected_components: int
    largest_component_size: int
    density: float
    avg_clustering: float
    isolated_nodes: list[str]
