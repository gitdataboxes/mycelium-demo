import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.profile import AttributeDirection, MembraneEntry
from app.models.user import User
from app.schemas.profile import (
    AttributeCreate,
    AttributeResponse,
    AttributeUpdate,
    ProfileResponse,
    UsernameUpdate,
)
from app.services.embedding import embed_node_attributes

logger = logging.getLogger(__name__)

router = APIRouter()


async def _build_profile(db: AsyncSession, user: User) -> ProfileResponse:
    result = await db.execute(
        select(MembraneEntry)
        .where(MembraneEntry.node_id == user.node_id)
        .order_by(MembraneEntry.created_at)
    )
    entries = list(result.scalars().all())

    return ProfileResponse(
        node_id=user.node_id,
        username=user.username,
        email=user.email,
        inputs=[
            AttributeResponse.model_validate(e)
            for e in entries
            if e.direction == AttributeDirection.INPUT
        ],
        outputs=[
            AttributeResponse.model_validate(e)
            for e in entries
            if e.direction == AttributeDirection.OUTPUT
        ],
    )


@router.get("", response_model=ProfileResponse)
async def get_own_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _build_profile(db, user)


@router.get("/{node_id}", response_model=ProfileResponse)
async def get_user_profile(
    node_id: uuid.UUID,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.node_id == node_id, User.is_active == True)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return await _build_profile(db, target)


@router.put("/username", response_model=ProfileResponse)
async def update_username(
    body: UsernameUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(User).where(User.username == body.username, User.node_id != user.node_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
        )

    user.username = body.username
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return await _build_profile(db, user)


@router.post("/attributes", response_model=AttributeResponse, status_code=status.HTTP_201_CREATED)
async def create_attribute(
    body: AttributeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = MembraneEntry(
        node_id=user.node_id,
        direction=body.direction,
        content=body.content,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    # Re-embed all entries with new context
    try:
        await embed_node_attributes(db, user.node_id)
    except Exception:
        logger.exception("Embedding failed for node %s", user.node_id)

    return AttributeResponse.model_validate(entry)


@router.put("/attributes/{attribute_id}", response_model=AttributeResponse)
async def update_attribute(
    attribute_id: uuid.UUID,
    body: AttributeUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MembraneEntry).where(
            MembraneEntry.id == attribute_id,
            MembraneEntry.node_id == user.node_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found")

    entry.content = body.content
    await db.commit()
    await db.refresh(entry)

    try:
        await embed_node_attributes(db, user.node_id)
    except Exception:
        logger.exception("Embedding failed for node %s", user.node_id)

    return AttributeResponse.model_validate(entry)


@router.delete("/attributes/{attribute_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attribute(
    attribute_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MembraneEntry).where(
            MembraneEntry.id == attribute_id,
            MembraneEntry.node_id == user.node_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found")

    await db.delete(entry)
    await db.commit()

    # Re-embed remaining entries (context changed)
    try:
        await embed_node_attributes(db, user.node_id)
    except Exception:
        logger.exception("Embedding failed for node %s", user.node_id)
