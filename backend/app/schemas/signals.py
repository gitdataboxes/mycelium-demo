import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.profile import AttributeDirection


class SignalCreate(BaseModel):
    direction: AttributeDirection
    content: str = Field(min_length=1, max_length=2000)
    expires_in_days: int = Field(default=30, ge=1, le=90)


class SignalResponse(BaseModel):
    id: uuid.UUID
    direction: AttributeDirection
    content: str
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
