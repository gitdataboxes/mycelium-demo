import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.profile import AttributeResponse


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class OrgMemberResponse(BaseModel):
    node_id: uuid.UUID
    username: str | None
    name: str | None
    joined_at: datetime


class OrgResponse(BaseModel):
    node_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    member_count: int
    is_member: bool = False
    graph_distance: int | None = None
    inputs: list[AttributeResponse] = []
    outputs: list[AttributeResponse] = []


class OrgListResponse(BaseModel):
    organizations: list[OrgResponse]
    total: int


class ResponderRequest(BaseModel):
    node_id: uuid.UUID


class ResponderResponse(BaseModel):
    node_id: uuid.UUID
    username: str | None
