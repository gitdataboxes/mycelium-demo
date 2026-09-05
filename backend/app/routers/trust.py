import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.trust import (
    TrustGraphResponse,
    VouchCreatedResponse,
    VouchRequest,
    VouchResponse,
)
from app.services.email import send_invite_email
from app.services.trust import (
    add_block,
    add_cooling,
    can_vouch,
    get_vouches_given,
    get_vouches_received,
    remove_block,
    remove_cooling,
    vouch_for_user,
    withdraw_vouch,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _edge_to_vouch_response(db: AsyncSession, edge) -> VouchResponse:
    voucher = await db.execute(select(User).where(User.node_id == edge.source_node_id))
    voucher = voucher.scalar_one_or_none()
    vouchee = await db.execute(select(User).where(User.node_id == edge.target_node_id))
    vouchee = vouchee.scalar_one_or_none()
    return VouchResponse(
        id=edge.id,
        voucher_node_id=edge.source_node_id,
        voucher_username=voucher.username if voucher else None,
        vouchee_node_id=edge.target_node_id,
        vouchee_username=vouchee.username if vouchee else None,
        vouchee_email=vouchee.email if vouchee else "",
        created_at=edge.created_at,
    )


@router.get("/graph", response_model=TrustGraphResponse)
async def get_trust_graph(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    given = await get_vouches_given(db, user.node_id)
    received = await get_vouches_received(db, user.node_id)
    user_can_vouch = await can_vouch(db, user.node_id)

    return TrustGraphResponse(
        vouches_given=[await _edge_to_vouch_response(db, e) for e in given],
        vouches_received=[await _edge_to_vouch_response(db, e) for e in received],
        can_vouch=user_can_vouch,
    )


@router.post("/vouch", response_model=VouchCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_vouch(
    body: VouchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        edge, vouchee, raw_token = await vouch_for_user(db, user, body.email)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    invite_sent = False
    if raw_token:
        try:
            await send_invite_email(
                body.email,
                user.username or user.email,
                raw_token,
            )
            invite_sent = True
        except Exception:
            logger.warning("Failed to send invite email to %s", body.email)

    vouch_resp = await _edge_to_vouch_response(db, edge)
    return VouchCreatedResponse(vouch=vouch_resp, invite_sent=invite_sent)


@router.delete("/vouch/{vouch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vouch(
    vouch_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await withdraw_vouch(db, user.node_id, vouch_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/cool/{target_node_id}", status_code=status.HTTP_201_CREATED)
async def cool_user(
    target_node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await add_cooling(db, user.node_id, target_node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": "cooled"}


@router.delete("/cool/{target_node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def uncool_user(
    target_node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await remove_cooling(db, user.node_id, target_node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/block/{target_node_id}", status_code=status.HTTP_201_CREATED)
async def block_user(
    target_node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await add_block(db, user.node_id, target_node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": "blocked"}


@router.delete("/block/{target_node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_user(
    target_node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await remove_block(db, user.node_id, target_node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
