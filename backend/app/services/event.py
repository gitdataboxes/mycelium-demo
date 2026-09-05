import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.edge import Edge, EdgeType
from app.models.event import Event, EventUrgency
from app.models.node import Node, NodeType
from app.models.user import User

logger = logging.getLogger(__name__)


async def create_event(
    db: AsyncSession,
    creator: User,
    title: str,
    description: str | None = None,
    location: str | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    urgency: EventUrgency = EventUrgency.STANDARD,
) -> Event:
    """Create an event. The creator becomes the first participant."""
    node = Node(community_id=creator.node.community_id, type=NodeType.EVENT)
    db.add(node)
    await db.flush()

    event = Event(
        node_id=node.id,
        title=title,
        description=description,
        location=location,
        starts_at=starts_at,
        ends_at=ends_at,
        urgency=urgency,
    )
    db.add(event)

    # Creator is the first participant
    participation = Edge(
        source_node_id=creator.node_id,
        target_node_id=node.id,
        type=EdgeType.PARTICIPANT,
    )
    db.add(participation)

    # Creator is the default responder for messaging
    responder = Edge(
        source_node_id=creator.node_id,
        target_node_id=node.id,
        type=EdgeType.RESPONDER,
    )
    db.add(responder)
    await db.commit()
    await db.refresh(event)
    return event


async def get_event(db: AsyncSession, event_node_id: UUID) -> Event | None:
    result = await db.execute(
        select(Event).join(Node).where(Event.node_id == event_node_id)
    )
    return result.scalar_one_or_none()


async def list_events(
    db: AsyncSession,
    community_id: UUID,
    search: str | None = None,
    upcoming_only: bool = False,
) -> list[Event]:
    query = select(Event).join(Node).where(Node.community_id == community_id)
    if search:
        query = query.where(Event.title.ilike(f"%{search}%"))
    if upcoming_only:
        now = func.now()
        query = query.where(
            (Event.ends_at.is_(None)) | (Event.ends_at > now)
        )
    query = query.order_by(Event.starts_at.asc().nullslast(), Node.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_event(
    db: AsyncSession,
    event: Event,
    title: str | None = None,
    description: str | None = None,
    location: str | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    urgency: EventUrgency | None = None,
) -> Event:
    if title is not None:
        event.title = title
    if description is not None:
        event.description = description
    if location is not None:
        event.location = location
    if starts_at is not None:
        event.starts_at = starts_at
    if ends_at is not None:
        event.ends_at = ends_at
    if urgency is not None:
        event.urgency = urgency
    await db.commit()
    await db.refresh(event)
    return event


async def delete_event(db: AsyncSession, event_node_id: UUID) -> None:
    """Delete an event and all its edges."""
    await db.execute(
        Edge.__table__.delete().where(
            (Edge.source_node_id == event_node_id)
            | (Edge.target_node_id == event_node_id)
            | (Edge.context_node_id == event_node_id)
        )
    )

    result = await db.execute(select(Event).where(Event.node_id == event_node_id))
    event = result.scalar_one_or_none()
    if event:
        await db.delete(event)

    result = await db.execute(select(Node).where(Node.id == event_node_id))
    node = result.scalar_one_or_none()
    if node:
        await db.delete(node)

    await db.commit()


# --- Participation ---


async def is_participant(db: AsyncSession, user_node_id: UUID, event_node_id: UUID) -> bool:
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == user_node_id,
            Edge.target_node_id == event_node_id,
            Edge.type == EdgeType.PARTICIPANT,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_participant_count(db: AsyncSession, event_node_id: UUID) -> int:
    result = await db.execute(
        select(func.count()).where(
            Edge.target_node_id == event_node_id,
            Edge.type == EdgeType.PARTICIPANT,
        )
    )
    return result.scalar()


async def get_participants(db: AsyncSession, event_node_id: UUID) -> list[tuple[User, Edge]]:
    result = await db.execute(
        select(User, Edge)
        .join(Edge, Edge.source_node_id == User.node_id)
        .where(
            Edge.target_node_id == event_node_id,
            Edge.type == EdgeType.PARTICIPANT,
        )
        .order_by(Edge.created_at)
    )
    return list(result.all())


async def add_participant(db: AsyncSession, user_node_id: UUID, event_node_id: UUID) -> Edge:
    if await is_participant(db, user_node_id, event_node_id):
        raise ValueError("Already participating")

    edge = Edge(
        source_node_id=user_node_id,
        target_node_id=event_node_id,
        type=EdgeType.PARTICIPANT,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return edge


async def remove_participant(db: AsyncSession, user_node_id: UUID, event_node_id: UUID) -> None:
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == user_node_id,
            Edge.target_node_id == event_node_id,
            Edge.type == EdgeType.PARTICIPANT,
        )
    )
    edge = result.scalar_one_or_none()
    if edge is None:
        raise ValueError("Not a participant")

    await db.delete(edge)

    # Remove any vouches scoped to this event that this user issued
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == user_node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id == event_node_id,
        )
    )
    for vouch_edge in result.scalars().all():
        await db.delete(vouch_edge)

    await db.commit()


# --- Responders ---


async def is_responder(db: AsyncSession, user_node_id: UUID, event_node_id: UUID) -> bool:
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == user_node_id,
            Edge.target_node_id == event_node_id,
            Edge.type == EdgeType.RESPONDER,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_responders(db: AsyncSession, event_node_id: UUID) -> list[tuple[User, Edge]]:
    result = await db.execute(
        select(User, Edge)
        .join(Edge, Edge.source_node_id == User.node_id)
        .where(
            Edge.target_node_id == event_node_id,
            Edge.type == EdgeType.RESPONDER,
        )
        .order_by(Edge.created_at)
    )
    return list(result.all())


async def add_responder(
    db: AsyncSession, adder_node_id: UUID, event_node_id: UUID, responder_node_id: UUID
) -> Edge:
    if not await is_responder(db, adder_node_id, event_node_id):
        raise ValueError("Only existing responders can add new responders")

    if await is_responder(db, responder_node_id, event_node_id):
        raise ValueError("Already a responder")

    result = await db.execute(
        select(User).where(User.node_id == responder_node_id, User.is_active == True)
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("User not found")

    edge = Edge(
        source_node_id=responder_node_id,
        target_node_id=event_node_id,
        type=EdgeType.RESPONDER,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return edge


async def remove_responder(
    db: AsyncSession, remover_node_id: UUID, event_node_id: UUID, responder_node_id: UUID
) -> None:
    if not await is_responder(db, remover_node_id, event_node_id):
        raise ValueError("Only existing responders can remove responders")

    responders = await get_responders(db, event_node_id)
    if len(responders) <= 1:
        raise ValueError("Cannot remove the last responder")

    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == responder_node_id,
            Edge.target_node_id == event_node_id,
            Edge.type == EdgeType.RESPONDER,
        )
    )
    edge = result.scalar_one_or_none()
    if edge is None:
        raise ValueError("Not a responder")

    await db.delete(edge)
    await db.commit()


async def vouch_into_event(
    db: AsyncSession, voucher_node_id: UUID, vouchee_node_id: UUID, event_node_id: UUID
) -> Edge:
    """Vouch a user into an event. Voucher must be an existing participant."""
    if not await is_participant(db, voucher_node_id, event_node_id):
        raise ValueError("You must be a participant to vouch someone in")

    if await is_participant(db, vouchee_node_id, event_node_id):
        raise ValueError("User is already a participant")

    if voucher_node_id == vouchee_node_id:
        raise ValueError("Cannot vouch for yourself")

    result = await db.execute(
        select(User).where(User.node_id == vouchee_node_id, User.is_active == True)
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("User not found")

    # Check for existing vouch in this event context
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == voucher_node_id,
            Edge.target_node_id == vouchee_node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id == event_node_id,
        )
    )
    if result.scalar_one_or_none():
        raise ValueError("Already vouched for this user in this event")

    vouch = Edge(
        source_node_id=voucher_node_id,
        target_node_id=vouchee_node_id,
        type=EdgeType.VOUCH,
        context_node_id=event_node_id,
    )
    db.add(vouch)

    participation = await add_participant(db, vouchee_node_id, event_node_id)
    return participation
