import logging
from collections import deque
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.edge import Edge, EdgeType
from app.models.node import Node, NodeType
from app.models.user import User
from app.scheduler import scheduler
from app.services.auth import create_magic_link
from app.services.graph_analytics import run_analytics_for_community_job

logger = logging.getLogger(__name__)


def _schedule_analytics_recompute(community_id: UUID) -> None:
    if not getattr(scheduler, "running", False):
        return

    scheduler.add_job(
        run_analytics_for_community_job,
        "date",
        run_date=(
            datetime.now(timezone.utc)
            + timedelta(seconds=settings.analytics_debounce_seconds)
        ),
        args=[community_id],
        id=f"analytics-recompute-{community_id}",
        replace_existing=True,
    )


async def can_vouch(db: AsyncSession, node_id: UUID) -> bool:
    """Check if user has used their vouch this week."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.vouch_cooldown_days)
    result = await db.execute(
        select(func.count()).where(
            Edge.source_node_id == node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id.is_(None),
            Edge.created_at > cutoff,
        )
    )
    count = result.scalar()
    return count == 0


async def vouch_for_user(
    db: AsyncSession, voucher: User, vouchee_email: str
) -> tuple[Edge, User, str | None]:
    """Vouch for a user by email. Creates user+node if needed. Returns (edge, vouchee, raw_token_or_none)."""
    if not await can_vouch(db, voucher.node_id):
        raise ValueError("You can only vouch for one person per week")

    if vouchee_email == voucher.email:
        raise ValueError("You cannot vouch for yourself")

    # Find or create user
    result = await db.execute(select(User).where(User.email == vouchee_email))
    vouchee = result.scalar_one_or_none()

    raw_token = None
    is_new = vouchee is None

    if vouchee is None:
        # Create node + user together
        node = Node(community_id=voucher.node.community_id, type=NodeType.USER)
        db.add(node)
        await db.flush()

        vouchee = User(node_id=node.id, email=vouchee_email, is_active=False)
        db.add(vouchee)
        await db.flush()

    # Check if already vouched (active vouch edge exists)
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == voucher.node_id,
            Edge.target_node_id == vouchee.node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id.is_(None),
        )
    )
    if result.scalar_one_or_none():
        raise ValueError("You already have an active vouch for this person")

    edge = Edge(
        source_node_id=voucher.node_id,
        target_node_id=vouchee.node_id,
        type=EdgeType.VOUCH,
    )
    db.add(edge)
    await db.commit()
    _schedule_analytics_recompute(voucher.node.community_id)

    # Generate magic link for the vouchee if they're new or inactive
    if is_new or not vouchee.is_active:
        try:
            raw_token, _ = await create_magic_link(db, vouchee_email)
        except ValueError:
            pass

    return edge, vouchee, raw_token


async def withdraw_vouch(db: AsyncSession, voucher_node_id: UUID, edge_id: UUID) -> None:
    """Withdraw a vouch. If the vouchee has no remaining vouches, deactivate them."""
    result = await db.execute(
        select(Edge).where(
            Edge.id == edge_id,
            Edge.source_node_id == voucher_node_id,
            Edge.type == EdgeType.VOUCH,
        )
    )
    edge = result.scalar_one_or_none()
    if edge is None:
        raise ValueError("Vouch not found")

    target_node_id = edge.target_node_id
    await db.delete(edge)

    # Check if vouchee has any remaining community-level vouches
    result = await db.execute(
        select(func.count()).where(
            Edge.target_node_id == target_node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id.is_(None),
            Edge.id != edge_id,
        )
    )
    remaining = result.scalar()

    if remaining == 0:
        result = await db.execute(select(User).where(User.node_id == target_node_id))
        vouchee = result.scalar_one_or_none()
        if vouchee:
            vouchee.is_active = False
            logger.info("Deactivated user %s — no remaining vouches", target_node_id)

    await db.commit()
    result = await db.execute(select(Node.community_id).where(Node.id == voucher_node_id))
    community_id = result.scalar_one_or_none()
    if community_id is not None:
        _schedule_analytics_recompute(community_id)


async def add_cooling(db: AsyncSession, cooler_node_id: UUID, target_node_id: UUID) -> Edge:
    """Add a cooling toward a target node."""
    if cooler_node_id == target_node_id:
        raise ValueError("You cannot cool yourself")

    # Check target exists and is an active user
    result = await db.execute(
        select(User).where(User.node_id == target_node_id, User.is_active == True)
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("User not found")

    # Check not already cooling
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == cooler_node_id,
            Edge.target_node_id == target_node_id,
            Edge.type == EdgeType.COOL,
        )
    )
    if result.scalar_one_or_none():
        raise ValueError("Already cooling this user")

    edge = Edge(
        source_node_id=cooler_node_id,
        target_node_id=target_node_id,
        type=EdgeType.COOL,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return edge


async def remove_cooling(db: AsyncSession, cooler_node_id: UUID, target_node_id: UUID) -> None:
    """Remove a cooling toward a target node."""
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == cooler_node_id,
            Edge.target_node_id == target_node_id,
            Edge.type == EdgeType.COOL,
        )
    )
    edge = result.scalar_one_or_none()
    if edge is None:
        raise ValueError("No cooling found for this user")

    await db.delete(edge)
    await db.commit()


async def get_cooling_count(db: AsyncSession, node_id: UUID) -> int:
    """Get the number of coolings a node has received."""
    result = await db.execute(
        select(func.count()).where(
            Edge.target_node_id == node_id,
            Edge.type == EdgeType.COOL,
        )
    )
    return result.scalar()


def cooling_penalty(cooling_count: int) -> float:
    """Calculate the cooling penalty multiplier. Each cooling reduces visibility by 15%."""
    return settings.cooling_decay_factor ** cooling_count


async def get_trust_distance(
    db: AsyncSession, from_id: UUID, to_id: UUID, max_hops: int = 3
) -> int | None:
    """BFS on vouch graph to find shortest path between two nodes. Returns hop count or None."""
    if from_id == to_id:
        return 0

    # Load active community-level vouch edges
    result = await db.execute(
        select(Edge.source_node_id, Edge.target_node_id).where(
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id.is_(None),
        )
    )
    edges = result.all()

    # Build adjacency list (undirected — vouching is a mutual connection)
    adjacency: dict[UUID, set[UUID]] = {}
    for source_id, target_id in edges:
        adjacency.setdefault(source_id, set()).add(target_id)
        adjacency.setdefault(target_id, set()).add(source_id)

    # BFS
    visited = {from_id}
    queue = deque([(from_id, 0)])

    while queue:
        current, depth = queue.popleft()
        if depth >= max_hops:
            continue

        for neighbor in adjacency.get(current, set()):
            if neighbor == to_id:
                return depth + 1
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

    return None


def trust_score(distance: int | None) -> float:
    """Convert vouch graph distance to a trust multiplier."""
    if distance is None:
        return 0.1  # stranger
    if distance == 0:
        return 1.0  # self
    if distance == 1:
        return 1.0  # direct vouch
    if distance == 2:
        return 0.5
    if distance == 3:
        return 0.25
    return 0.1


async def add_block(db: AsyncSession, blocker_node_id: UUID, target_node_id: UUID) -> Edge:
    """Block a user. Prevents them from sending you messages."""
    if blocker_node_id == target_node_id:
        raise ValueError("You cannot block yourself")

    result = await db.execute(
        select(User).where(User.node_id == target_node_id, User.is_active == True)
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("User not found")

    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == blocker_node_id,
            Edge.target_node_id == target_node_id,
            Edge.type == EdgeType.BLOCK,
        )
    )
    if result.scalar_one_or_none():
        raise ValueError("Already blocked")

    edge = Edge(
        source_node_id=blocker_node_id,
        target_node_id=target_node_id,
        type=EdgeType.BLOCK,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return edge


async def remove_block(db: AsyncSession, blocker_node_id: UUID, target_node_id: UUID) -> None:
    """Unblock a user."""
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == blocker_node_id,
            Edge.target_node_id == target_node_id,
            Edge.type == EdgeType.BLOCK,
        )
    )
    edge = result.scalar_one_or_none()
    if edge is None:
        raise ValueError("Not blocked")

    await db.delete(edge)
    await db.commit()


async def is_blocked(db: AsyncSession, sender_node_id: UUID, recipient_node_id: UUID) -> bool:
    """Check if recipient has blocked sender. Directional: returns True if recipient blocked sender."""
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == recipient_node_id,
            Edge.target_node_id == sender_node_id,
            Edge.type == EdgeType.BLOCK,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_vouches_given(db: AsyncSession, node_id: UUID) -> list[Edge]:
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id.is_(None),
        )
    )
    return list(result.scalars().all())


async def get_vouches_received(db: AsyncSession, node_id: UUID) -> list[Edge]:
    result = await db.execute(
        select(Edge).where(
            Edge.target_node_id == node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id.is_(None),
        )
    )
    return list(result.scalars().all())
