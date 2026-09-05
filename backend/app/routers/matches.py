import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.match import MatchHistory
from app.models.profile import MembraneEntry
from app.models.signal import Signal
from app.models.user import User
from app.schemas.matches import MatchDetailResponse, MatchListItem, MatchNodeInfo

router = APIRouter()


async def _resolve_attribute(db: AsyncSession, attr_id: uuid.UUID, attr_type: str) -> tuple[str, str]:
    """Look up attribute content and direction from either membrane_entries or signals."""
    if attr_type == "membrane":
        result = await db.execute(select(MembraneEntry).where(MembraneEntry.id == attr_id))
        entry = result.scalar_one_or_none()
        if entry:
            return entry.content, entry.direction.value
    else:
        result = await db.execute(select(Signal).where(Signal.id == attr_id))
        sig = result.scalar_one_or_none()
        if sig:
            return sig.content, sig.direction.value
    return "[removed]", "unknown"


@router.get("", response_model=list[MatchListItem])
async def list_my_matches(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, le=50),
):
    """List recent matches for the current user."""
    result = await db.execute(
        select(MatchHistory)
        .where(or_(
            MatchHistory.node_a_id == user.node_id,
            MatchHistory.node_b_id == user.node_id,
        ))
        .order_by(MatchHistory.digest_sent_at.desc())
        .limit(limit)
    )
    matches = result.scalars().all()

    items = []
    for m in matches:
        if m.node_a_id == user.node_id:
            other_node_id = m.node_b_id
            own_attr_id, own_type = m.attribute_a_id, m.attribute_a_type
            other_attr_id, other_type = m.attribute_b_id, m.attribute_b_type
        else:
            other_node_id = m.node_a_id
            own_attr_id, own_type = m.attribute_b_id, m.attribute_b_type
            other_attr_id, other_type = m.attribute_a_id, m.attribute_a_type

        result = await db.execute(select(User).where(User.node_id == other_node_id))
        other_user = result.scalar_one_or_none()
        own_content, own_dir = await _resolve_attribute(db, own_attr_id, own_type)
        other_content, other_dir = await _resolve_attribute(db, other_attr_id, other_type)

        items.append(MatchListItem(
            match_id=m.id,
            other_username=other_user.username if other_user else None,
            own_content=own_content,
            own_direction=own_dir,
            other_content=other_content,
            other_direction=other_dir,
            similarity=m.similarity,
            matched_at=m.digest_sent_at,
        ))

    return items


@router.get("/{match_id}", response_model=MatchDetailResponse)
async def get_match_detail(
    match_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific match. Only accessible by involved nodes."""
    result = await db.execute(select(MatchHistory).where(MatchHistory.id == match_id))
    match = result.scalar_one_or_none()

    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    if user.node_id not in (match.node_a_id, match.node_b_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your match")

    result_a = await db.execute(select(User).where(User.node_id == match.node_a_id))
    user_a = result_a.scalar_one_or_none()
    result_b = await db.execute(select(User).where(User.node_id == match.node_b_id))
    user_b = result_b.scalar_one_or_none()

    content_a, dir_a = await _resolve_attribute(db, match.attribute_a_id, match.attribute_a_type)
    content_b, dir_b = await _resolve_attribute(db, match.attribute_b_id, match.attribute_b_type)

    return MatchDetailResponse(
        match_id=match.id,
        similarity=match.similarity,
        matched_at=match.digest_sent_at,
        node_a=MatchNodeInfo(
            node_id=match.node_a_id,
            username=user_a.username if user_a else None,
            attribute_content=content_a,
            attribute_direction=dir_a,
            attribute_type=match.attribute_a_type,
        ),
        node_b=MatchNodeInfo(
            node_id=match.node_b_id,
            username=user_b.username if user_b else None,
            attribute_content=content_b,
            attribute_direction=dir_b,
            attribute_type=match.attribute_b_type,
        ),
    )
