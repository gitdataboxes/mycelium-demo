import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.edge import Edge, EdgeType
from app.models.event import Event
from app.models.message import Message
from app.models.node import Node, NodeType
from app.models.organization import Organization
from app.models.user import User
from app.services.trust import is_blocked

logger = logging.getLogger(__name__)


async def _get_context_name(db: AsyncSession, context_node_id: UUID) -> str | None:
    """Look up the display name for a context node (event title or org name)."""
    result = await db.execute(select(Node).where(Node.id == context_node_id))
    node = result.scalar_one_or_none()
    if node is None:
        return None
    if node.type == NodeType.EVENT:
        result = await db.execute(select(Event.title).where(Event.node_id == context_node_id))
        row = result.first()
        return row[0] if row else None
    if node.type == NodeType.ORGANIZATION:
        result = await db.execute(select(Organization.name).where(Organization.node_id == context_node_id))
        row = result.first()
        return row[0] if row else None
    return None


async def _resolve_responder(db: AsyncSession, context_node_id: UUID) -> UUID:
    """Get the primary (oldest) responder for a context node."""
    result = await db.execute(
        select(Edge.source_node_id)
        .where(
            Edge.target_node_id == context_node_id,
            Edge.type == EdgeType.RESPONDER,
        )
        .order_by(Edge.created_at)
        .limit(1)
    )
    row = result.first()
    if row is None:
        raise ValueError("No responder configured for this entity")
    return row[0]


async def _has_prior_contact(db: AsyncSession, user_a: UUID, user_b: UUID) -> bool:
    """Check if two users have ever exchanged messages (through any thread)."""
    result = await db.execute(
        select(func.count()).select_from(Message).where(
            or_(
                and_(Message.from_user == user_a, Message.to_user == user_b),
                and_(Message.from_user == user_b, Message.to_user == user_a),
            )
        )
    )
    return result.scalar() > 0


async def send_message(
    db: AsyncSession,
    from_node_id: UUID,
    content: str,
    *,
    to_node_id: UUID | None = None,
    context_node_id: UUID | None = None,
) -> Message:
    """Send a message. Provide to_node_id for direct, context_node_id for context thread."""
    # Validate sender is active
    result = await db.execute(
        select(User).where(User.node_id == from_node_id, User.is_active == True)
    )
    sender = result.scalar_one_or_none()
    if sender is None:
        raise ValueError("Sender not found")

    if context_node_id:
        # --- Context thread ---
        result = await db.execute(select(Node).where(Node.id == context_node_id))
        ctx_node = result.scalar_one_or_none()
        if ctx_node is None:
            raise ValueError("Entity not found")
        if ctx_node.type not in (NodeType.EVENT, NodeType.ORGANIZATION):
            raise ValueError("Can only message events or organizations")

        recipient_id = await _resolve_responder(db, context_node_id)

        if recipient_id == from_node_id:
            raise ValueError("Cannot message yourself")

        if await is_blocked(db, from_node_id, recipient_id):
            raise ValueError("Cannot send message to this user")

    else:
        # --- Direct thread ---
        recipient_id = to_node_id

        if recipient_id == from_node_id:
            raise ValueError("Cannot message yourself")

        result = await db.execute(
            select(User).where(User.node_id == recipient_id, User.is_active == True)
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("User not found or inactive")

        if not await _has_prior_contact(db, from_node_id, recipient_id):
            raise ValueError("Must have prior contact through an event or organization")

        if await is_blocked(db, from_node_id, recipient_id):
            raise ValueError("Cannot send message to this user")

    msg = Message(
        from_user=from_node_id,
        to_user=recipient_id,
        context_node_id=context_node_id,
        content=content,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_threads(db: AsyncSession, user_node_id: UUID) -> list[dict]:
    """Get all threads for a user, grouped by (other_user, context_node_id)."""
    # Subquery: compute other_id for each message
    other_id = case(
        (Message.from_user == user_node_id, Message.to_user),
        else_=Message.from_user,
    ).label("other_id")

    # Get all messages involving this user
    all_msgs = (
        select(
            Message,
            other_id,
        )
        .where(or_(Message.from_user == user_node_id, Message.to_user == user_node_id))
        .subquery()
    )

    # For each (other_id, context_node_id), get the most recent message id
    latest = (
        select(
            all_msgs.c.other_id,
            all_msgs.c.context_node_id,
            func.max(all_msgs.c.created_at).label("max_created"),
        )
        .group_by(all_msgs.c.other_id, all_msgs.c.context_node_id)
        .subquery()
    )

    # Get the actual message rows for the latest messages
    result = await db.execute(
        select(Message)
        .join(
            latest,
            and_(
                or_(
                    and_(Message.from_user == user_node_id, Message.to_user == latest.c.other_id),
                    and_(Message.to_user == user_node_id, Message.from_user == latest.c.other_id),
                ),
                Message.context_node_id.is_not_distinct_from(latest.c.context_node_id),
                Message.created_at == latest.c.max_created,
            ),
        )
        .order_by(Message.created_at.desc())
    )
    latest_messages = list(result.scalars().all())

    # Deduplicate in case of ties
    seen = set()
    threads = []
    for msg in latest_messages:
        other = msg.to_user if msg.from_user == user_node_id else msg.from_user
        key = (other, msg.context_node_id)
        if key in seen:
            continue
        seen.add(key)

        # Count unread in this thread
        unread_result = await db.execute(
            select(func.count()).select_from(Message).where(
                Message.from_user == other,
                Message.to_user == user_node_id,
                Message.context_node_id.is_not_distinct_from(msg.context_node_id),
                Message.read_at.is_(None),
            )
        )
        unread_count = unread_result.scalar()

        # Get other user info
        user_result = await db.execute(select(User).where(User.node_id == other))
        other_user = user_result.scalar_one_or_none()

        # Get context name
        context_name = None
        if msg.context_node_id:
            context_name = await _get_context_name(db, msg.context_node_id)

        # Get sender/recipient info for the message
        sender_result = await db.execute(select(User).where(User.node_id == msg.from_user))
        sender_user = sender_result.scalar_one_or_none()
        recip_result = await db.execute(select(User).where(User.node_id == msg.to_user))
        recip_user = recip_result.scalar_one_or_none()

        threads.append({
            "other_node_id": other,
            "other_username": other_user.username if other_user else None,
            "context_node_id": msg.context_node_id,
            "context_name": context_name,
            "last_message": {
                "id": msg.id,
                "from_node_id": msg.from_user,
                "from_username": sender_user.username if sender_user else None,
                "to_node_id": msg.to_user,
                "to_username": recip_user.username if recip_user else None,
                "context_node_id": msg.context_node_id,
                "context_name": context_name,
                "content": msg.content,
                "created_at": msg.created_at,
                "read_at": msg.read_at,
            },
            "unread_count": unread_count,
        })

    return threads


async def get_thread_messages(
    db: AsyncSession,
    user_node_id: UUID,
    other_node_id: UUID,
    context_node_id: UUID | None = None,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Get messages in a thread, chronologically."""
    base_filter = and_(
        or_(
            and_(Message.from_user == user_node_id, Message.to_user == other_node_id),
            and_(Message.from_user == other_node_id, Message.to_user == user_node_id),
        ),
        Message.context_node_id.is_not_distinct_from(context_node_id),
    )

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(Message).where(base_filter)
    )
    total = count_result.scalar()

    # Get messages
    result = await db.execute(
        select(Message)
        .where(base_filter)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    messages = list(result.scalars().all())

    context_name = None
    if context_node_id:
        context_name = await _get_context_name(db, context_node_id)

    # Build response dicts
    msg_dicts = []
    for msg in messages:
        sender_result = await db.execute(select(User).where(User.node_id == msg.from_user))
        sender = sender_result.scalar_one_or_none()
        recip_result = await db.execute(select(User).where(User.node_id == msg.to_user))
        recip = recip_result.scalar_one_or_none()
        msg_dicts.append({
            "id": msg.id,
            "from_node_id": msg.from_user,
            "from_username": sender.username if sender else None,
            "to_node_id": msg.to_user,
            "to_username": recip.username if recip else None,
            "context_node_id": msg.context_node_id,
            "context_name": context_name,
            "content": msg.content,
            "created_at": msg.created_at,
            "read_at": msg.read_at,
        })

    return msg_dicts, total


async def mark_read(
    db: AsyncSession,
    user_node_id: UUID,
    other_node_id: UUID,
    context_node_id: UUID | None = None,
) -> int:
    """Mark all unread messages from other_node_id to user_node_id in thread as read."""
    result = await db.execute(
        update(Message)
        .where(
            Message.from_user == other_node_id,
            Message.to_user == user_node_id,
            Message.context_node_id.is_not_distinct_from(context_node_id),
            Message.read_at.is_(None),
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return result.rowcount


async def get_unread_count(db: AsyncSession, user_node_id: UUID) -> int:
    """Total unread messages across all threads."""
    result = await db.execute(
        select(func.count()).select_from(Message).where(
            Message.to_user == user_node_id,
            Message.read_at.is_(None),
        )
    )
    return result.scalar()


async def get_contacts(db: AsyncSession, user_node_id: UUID) -> list[dict]:
    """All distinct users this user has exchanged messages with."""
    other_id = case(
        (Message.from_user == user_node_id, Message.to_user),
        else_=Message.from_user,
    ).label("other_id")

    subq = (
        select(func.distinct(other_id))
        .where(or_(Message.from_user == user_node_id, Message.to_user == user_node_id))
        .subquery()
    )

    result = await db.execute(
        select(User).where(User.node_id.in_(select(subq)))
    )
    users = list(result.scalars().all())

    return [
        {"node_id": u.node_id, "username": u.username}
        for u in users
    ]
