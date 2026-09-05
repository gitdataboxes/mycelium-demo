import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkResponse(BaseModel):
    message: str


class SessionResponse(BaseModel):
    node_id: uuid.UUID
    username: str | None
    email: str
    is_active: bool
