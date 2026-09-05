import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.signal import Signal
from app.models.user import User
from app.schemas.signals import SignalCreate, SignalResponse
from app.services.embedding import embed_signal

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[SignalResponse])
async def list_signals(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Signal)
        .where(
            Signal.node_id == user.node_id,
            Signal.expires_at > datetime.now(timezone.utc),
        )
        .order_by(Signal.created_at.desc())
    )
    return [SignalResponse.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=SignalResponse, status_code=status.HTTP_201_CREATED)
async def create_signal(
    body: SignalCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    signal = Signal(
        node_id=user.node_id,
        direction=body.direction,
        content=body.content,
        expires_at=datetime.now(timezone.utc) + timedelta(days=body.expires_in_days),
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    try:
        await embed_signal(db, signal.id)
    except Exception:
        logger.exception("Signal embedding failed for signal %s", signal.id)

    return SignalResponse.model_validate(signal)


@router.delete("/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_signal(
    signal_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Signal).where(Signal.id == signal_id, Signal.node_id == user.node_id)
    )
    signal = result.scalar_one_or_none()
    if signal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")

    await db.delete(signal)
    await db.commit()
