import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.profile import AttributeDirection


class AttributeCreate(BaseModel):
    direction: AttributeDirection
    content: str = Field(min_length=1, max_length=2000)


class AttributeUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class AttributeResponse(BaseModel):
    id: uuid.UUID
    direction: AttributeDirection
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    node_id: uuid.UUID
    username: str | None
    email: str
    inputs: list[AttributeResponse]
    outputs: list[AttributeResponse]


class UsernameUpdate(BaseModel):
    username: str = Field(min_length=2, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
