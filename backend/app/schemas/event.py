import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.event import EventUrgency
from app.schemas.profile import AttributeResponse


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    location: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    urgency: EventUrgency = EventUrgency.STANDARD


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    location: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    urgency: EventUrgency | None = None


class EventParticipantResponse(BaseModel):
    node_id: uuid.UUID
    username: str | None
    name: str | None
    joined_at: datetime


class EventResponse(BaseModel):
    node_id: uuid.UUID
    title: str
    description: str | None
    location: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    urgency: EventUrgency
    created_at: datetime
    participant_count: int
    is_participant: bool = False
    graph_distance: int | None = None
    inputs: list[AttributeResponse] = []
    outputs: list[AttributeResponse] = []


class EventListResponse(BaseModel):
    events: list[EventResponse]
    total: int
