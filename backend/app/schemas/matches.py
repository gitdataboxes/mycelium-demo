import uuid
from datetime import datetime

from pydantic import BaseModel


class MatchNodeInfo(BaseModel):
    node_id: uuid.UUID
    username: str | None
    attribute_content: str
    attribute_direction: str
    attribute_type: str  # "membrane" or "signal"


class MatchDetailResponse(BaseModel):
    match_id: uuid.UUID
    similarity: float
    matched_at: datetime
    node_a: MatchNodeInfo
    node_b: MatchNodeInfo


class MatchListItem(BaseModel):
    match_id: uuid.UUID
    other_username: str | None
    own_content: str
    own_direction: str
    other_content: str
    other_direction: str
    similarity: float
    matched_at: datetime
