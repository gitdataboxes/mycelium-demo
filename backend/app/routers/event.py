import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.profile import AttributeDirection, MembraneEntry
from app.models.user import User
from app.schemas.event import (
    EventCreate,
    EventListResponse,
    EventParticipantResponse,
    EventResponse,
    EventUpdate,
)
from app.schemas.profile import AttributeCreate, AttributeResponse, AttributeUpdate
from app.services.embedding import embed_node_attributes
from app.services.discovery import discover
from app.schemas.organization import ResponderRequest, ResponderResponse
from app.services.event import (
    add_responder,
    create_event,
    delete_event,
    get_event,
    get_participant_count,
    get_participants,
    get_responders,
    is_participant,
    remove_participant,
    remove_responder,
    update_event,
    vouch_into_event,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _build_event_response(
    db: AsyncSession, event, user_node_id: uuid.UUID, graph_distance: int | None = None
) -> EventResponse:
    result = await db.execute(
        select(MembraneEntry)
        .where(MembraneEntry.node_id == event.node_id)
        .order_by(MembraneEntry.created_at)
    )
    entries = list(result.scalars().all())

    return EventResponse(
        node_id=event.node_id,
        title=event.title,
        description=event.description,
        location=event.location,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        urgency=event.urgency,
        created_at=event.node.created_at,
        participant_count=await get_participant_count(db, event.node_id),
        is_participant=await is_participant(db, user_node_id, event.node_id),
        graph_distance=graph_distance,
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


async def _get_event_or_404(db: AsyncSession, node_id: uuid.UUID):
    event = await get_event(db, node_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


async def _require_participant(db: AsyncSession, user_node_id: uuid.UUID, event_node_id: uuid.UUID):
    if not await is_participant(db, user_node_id, event_node_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")


# --- CRUD ---


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_evt(
    body: EventCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await create_event(
        db, user, body.title, body.description, body.location,
        body.starts_at, body.ends_at, body.urgency,
    )
    return await _build_event_response(db, event, user.node_id)


@router.get("", response_model=EventListResponse)
async def list_evts(
    search: str | None = Query(default=None, max_length=200),
    upcoming: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results, total = await discover(
        db, user.node_id, user.node.community_id,
        node_types=["event"], search=search, upcoming_only=upcoming,
        limit=limit, offset=offset,
    )
    items = []
    for r in results:
        event = await get_event(db, r.node_id)
        if event:
            items.append(await _build_event_response(db, event, user.node_id, r.graph_distance))
    return EventListResponse(events=items, total=total)


@router.get("/{node_id}", response_model=EventResponse)
async def get_evt(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _get_event_or_404(db, node_id)
    return await _build_event_response(db, event, user.node_id)


@router.put("/{node_id}", response_model=EventResponse)
async def update_evt(
    node_id: uuid.UUID,
    body: EventUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _get_event_or_404(db, node_id)
    await _require_participant(db, user.node_id, node_id)
    event = await update_event(
        db, event, body.title, body.description, body.location,
        body.starts_at, body.ends_at, body.urgency,
    )
    return await _build_event_response(db, event, user.node_id)


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evt(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_event_or_404(db, node_id)
    await _require_participant(db, user.node_id, node_id)
    await delete_event(db, node_id)


# --- Participation ---


@router.get("/{node_id}/participants", response_model=list[EventParticipantResponse])
async def list_participants(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_event_or_404(db, node_id)
    participants = await get_participants(db, node_id)
    return [
        EventParticipantResponse(
            node_id=u.node_id,
            username=u.username,
            name=u.name,
            joined_at=edge.created_at,
        )
        for u, edge in participants
    ]


@router.post("/{node_id}/vouch", response_model=EventParticipantResponse, status_code=status.HTTP_201_CREATED)
async def vouch_participant(
    node_id: uuid.UUID,
    vouchee_node_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Vouch a user into this event. You must be an existing participant."""
    await _get_event_or_404(db, node_id)
    try:
        participation = await vouch_into_event(db, user.node_id, vouchee_node_id, node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    result = await db.execute(select(User).where(User.node_id == vouchee_node_id))
    vouchee = result.scalar_one()
    return EventParticipantResponse(
        node_id=vouchee.node_id,
        username=vouchee.username,
        name=vouchee.name,
        joined_at=participation.created_at,
    )


@router.delete("/{node_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_evt(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_event_or_404(db, node_id)
    try:
        await remove_participant(db, user.node_id, node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Responders ---


@router.get("/{node_id}/responders", response_model=list[ResponderResponse])
async def list_responders(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_event_or_404(db, node_id)
    responders = await get_responders(db, node_id)
    return [
        ResponderResponse(node_id=u.node_id, username=u.username)
        for u, edge in responders
    ]


@router.post("/{node_id}/responders", response_model=ResponderResponse, status_code=status.HTTP_201_CREATED)
async def add_evt_responder(
    node_id: uuid.UUID,
    body: ResponderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_event_or_404(db, node_id)
    try:
        await add_responder(db, user.node_id, node_id, body.node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    result = await db.execute(select(User).where(User.node_id == body.node_id))
    u = result.scalar_one()
    return ResponderResponse(node_id=u.node_id, username=u.username)


@router.delete("/{node_id}/responders/{responder_node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_evt_responder(
    node_id: uuid.UUID,
    responder_node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_event_or_404(db, node_id)
    try:
        await remove_responder(db, user.node_id, node_id, responder_node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Event Membrane ---


@router.post("/{node_id}/attributes", response_model=AttributeResponse, status_code=status.HTTP_201_CREATED)
async def create_event_attribute(
    node_id: uuid.UUID,
    body: AttributeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_event_or_404(db, node_id)
    await _require_participant(db, user.node_id, node_id)

    entry = MembraneEntry(node_id=node_id, direction=body.direction, content=body.content)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    try:
        await embed_node_attributes(db, node_id)
    except Exception:
        logger.exception("Embedding failed for event node %s", node_id)

    return AttributeResponse.model_validate(entry)


@router.put("/{node_id}/attributes/{attribute_id}", response_model=AttributeResponse)
async def update_event_attribute(
    node_id: uuid.UUID,
    attribute_id: uuid.UUID,
    body: AttributeUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_event_or_404(db, node_id)
    await _require_participant(db, user.node_id, node_id)

    result = await db.execute(
        select(MembraneEntry).where(
            MembraneEntry.id == attribute_id,
            MembraneEntry.node_id == node_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found")

    entry.content = body.content
    await db.commit()
    await db.refresh(entry)

    try:
        await embed_node_attributes(db, node_id)
    except Exception:
        logger.exception("Embedding failed for event node %s", node_id)

    return AttributeResponse.model_validate(entry)


@router.delete("/{node_id}/attributes/{attribute_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event_attribute(
    node_id: uuid.UUID,
    attribute_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_event_or_404(db, node_id)
    await _require_participant(db, user.node_id, node_id)

    result = await db.execute(
        select(MembraneEntry).where(
            MembraneEntry.id == attribute_id,
            MembraneEntry.node_id == node_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found")

    await db.delete(entry)
    await db.commit()

    try:
        await embed_node_attributes(db, node_id)
    except Exception:
        logger.exception("Embedding failed for event node %s", node_id)
