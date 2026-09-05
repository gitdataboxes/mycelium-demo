import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class MessageSend(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    to_node_id: uuid.UUID | None = None
    context_node_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def exactly_one_target(self):
        if not self.to_node_id and not self.context_node_id:
            raise ValueError("Provide to_node_id (direct) or context_node_id (context)")
        if self.to_node_id and self.context_node_id:
            raise ValueError("Provide to_node_id or context_node_id, not both")
        return self


class MessageResponse(BaseModel):
    id: uuid.UUID
    from_node_id: uuid.UUID
    from_username: str | None
    to_node_id: uuid.UUID
    to_username: str | None
    context_node_id: uuid.UUID | None
    context_name: str | None
    content: str
    created_at: datetime
    read_at: datetime | None


class ThreadResponse(BaseModel):
    other_node_id: uuid.UUID
    other_username: str | None
    context_node_id: uuid.UUID | None
    context_name: str | None
    last_message: MessageResponse
    unread_count: int


class ThreadListResponse(BaseModel):
    threads: list[ThreadResponse]


class ContactResponse(BaseModel):
    node_id: uuid.UUID
    username: str | None


class UnreadCountResponse(BaseModel):
    count: int


class MarkReadResponse(BaseModel):
    marked: int
