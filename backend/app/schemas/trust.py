import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class VouchRequest(BaseModel):
    email: EmailStr


class VouchResponse(BaseModel):
    id: uuid.UUID
    voucher_node_id: uuid.UUID
    voucher_username: str | None
    vouchee_node_id: uuid.UUID
    vouchee_username: str | None
    vouchee_email: str
    created_at: datetime


class CoolingResponse(BaseModel):
    target_id: uuid.UUID
    target_username: str | None
    created_at: datetime


class TrustGraphResponse(BaseModel):
    vouches_given: list[VouchResponse]
    vouches_received: list[VouchResponse]
    can_vouch: bool


class VouchCreatedResponse(BaseModel):
    vouch: VouchResponse
    invite_sent: bool
