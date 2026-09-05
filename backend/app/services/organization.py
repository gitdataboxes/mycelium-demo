import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.edge import Edge, EdgeType
from app.models.node import Node, NodeType
from app.models.organization import Organization
from app.models.user import User

logger = logging.getLogger(__name__)


async def create_organization(
    db: AsyncSession, creator: User, name: str, description: str | None = None
) -> Organization:
    """Create an organization. The creator becomes the first member."""
    node = Node(community_id=creator.node.community_id, type=NodeType.ORGANIZATION)
    db.add(node)
    await db.flush()

    org = Organization(node_id=node.id, name=name, description=description)
    db.add(org)

    # Creator is the first member
    membership = Edge(
        source_node_id=creator.node_id,
        target_node_id=node.id,
        type=EdgeType.MEMBER,
    )
    db.add(membership)

    # Creator is the default responder for messaging
    responder = Edge(
        source_node_id=creator.node_id,
        target_node_id=node.id,
        type=EdgeType.RESPONDER,
    )
    db.add(responder)
    await db.commit()
    await db.refresh(org)
    return org


async def get_organization(db: AsyncSession, org_node_id: UUID) -> Organization | None:
    result = await db.execute(
        select(Organization).join(Node).where(Organization.node_id == org_node_id)
    )
    return result.scalar_one_or_none()


async def list_organizations(
    db: AsyncSession, community_id: UUID, search: str | None = None
) -> list[Organization]:
    query = select(Organization).join(Node).where(Node.community_id == community_id)
    if search:
        query = query.where(Organization.name.ilike(f"%{search}%"))
    query = query.order_by(Organization.name)
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_organization(
    db: AsyncSession, org: Organization, name: str | None = None, description: str | None = None
) -> Organization:
    if name is not None:
        org.name = name
    if description is not None:
        org.description = description
    await db.commit()
    await db.refresh(org)
    return org


async def delete_organization(db: AsyncSession, org_node_id: UUID) -> None:
    """Delete an organization and all its edges."""
    # Remove all edges referencing this org (memberships, vouches scoped to it, etc.)
    await db.execute(
        Edge.__table__.delete().where(
            (Edge.source_node_id == org_node_id)
            | (Edge.target_node_id == org_node_id)
            | (Edge.context_node_id == org_node_id)
        )
    )

    result = await db.execute(select(Organization).where(Organization.node_id == org_node_id))
    org = result.scalar_one_or_none()
    if org:
        await db.delete(org)

    result = await db.execute(select(Node).where(Node.id == org_node_id))
    node = result.scalar_one_or_none()
    if node:
        await db.delete(node)

    await db.commit()


# --- Membership ---


async def is_member(db: AsyncSession, user_node_id: UUID, org_node_id: UUID) -> bool:
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == user_node_id,
            Edge.target_node_id == org_node_id,
            Edge.type == EdgeType.MEMBER,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_member_count(db: AsyncSession, org_node_id: UUID) -> int:
    result = await db.execute(
        select(func.count()).where(
            Edge.target_node_id == org_node_id,
            Edge.type == EdgeType.MEMBER,
        )
    )
    return result.scalar()


async def get_members(db: AsyncSession, org_node_id: UUID) -> list[tuple[User, Edge]]:
    """Return (user, membership_edge) pairs for all org members."""
    result = await db.execute(
        select(User, Edge)
        .join(Edge, Edge.source_node_id == User.node_id)
        .where(
            Edge.target_node_id == org_node_id,
            Edge.type == EdgeType.MEMBER,
        )
        .order_by(Edge.created_at)
    )
    return list(result.all())


async def add_member(db: AsyncSession, user_node_id: UUID, org_node_id: UUID) -> Edge:
    """Add a user as a member of an organization."""
    if await is_member(db, user_node_id, org_node_id):
        raise ValueError("Already a member")

    edge = Edge(
        source_node_id=user_node_id,
        target_node_id=org_node_id,
        type=EdgeType.MEMBER,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return edge


async def remove_member(db: AsyncSession, user_node_id: UUID, org_node_id: UUID) -> None:
    """Remove a user's membership from an organization."""
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == user_node_id,
            Edge.target_node_id == org_node_id,
            Edge.type == EdgeType.MEMBER,
        )
    )
    edge = result.scalar_one_or_none()
    if edge is None:
        raise ValueError("Not a member")

    await db.delete(edge)

    # Also remove any vouches scoped to this org that this user issued
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == user_node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id == org_node_id,
        )
    )
    for vouch_edge in result.scalars().all():
        await db.delete(vouch_edge)

    await db.commit()


# --- Responders ---


async def is_responder(db: AsyncSession, user_node_id: UUID, org_node_id: UUID) -> bool:
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == user_node_id,
            Edge.target_node_id == org_node_id,
            Edge.type == EdgeType.RESPONDER,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_responders(db: AsyncSession, org_node_id: UUID) -> list[tuple[User, Edge]]:
    result = await db.execute(
        select(User, Edge)
        .join(Edge, Edge.source_node_id == User.node_id)
        .where(
            Edge.target_node_id == org_node_id,
            Edge.type == EdgeType.RESPONDER,
        )
        .order_by(Edge.created_at)
    )
    return list(result.all())


async def add_responder(
    db: AsyncSession, adder_node_id: UUID, org_node_id: UUID, responder_node_id: UUID
) -> Edge:
    if not await is_responder(db, adder_node_id, org_node_id):
        raise ValueError("Only existing responders can add new responders")

    if await is_responder(db, responder_node_id, org_node_id):
        raise ValueError("Already a responder")

    result = await db.execute(
        select(User).where(User.node_id == responder_node_id, User.is_active == True)
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("User not found")

    edge = Edge(
        source_node_id=responder_node_id,
        target_node_id=org_node_id,
        type=EdgeType.RESPONDER,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return edge


async def remove_responder(
    db: AsyncSession, remover_node_id: UUID, org_node_id: UUID, responder_node_id: UUID
) -> None:
    if not await is_responder(db, remover_node_id, org_node_id):
        raise ValueError("Only existing responders can remove responders")

    responders = await get_responders(db, org_node_id)
    if len(responders) <= 1:
        raise ValueError("Cannot remove the last responder")

    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == responder_node_id,
            Edge.target_node_id == org_node_id,
            Edge.type == EdgeType.RESPONDER,
        )
    )
    edge = result.scalar_one_or_none()
    if edge is None:
        raise ValueError("Not a responder")

    await db.delete(edge)
    await db.commit()


async def vouch_into_org(
    db: AsyncSession, voucher_node_id: UUID, vouchee_node_id: UUID, org_node_id: UUID
) -> Edge:
    """Vouch a user into an organization. Voucher must be an existing member."""
    if not await is_member(db, voucher_node_id, org_node_id):
        raise ValueError("You must be a member to vouch someone in")

    if await is_member(db, vouchee_node_id, org_node_id):
        raise ValueError("User is already a member")

    if voucher_node_id == vouchee_node_id:
        raise ValueError("Cannot vouch for yourself")

    # Vouchee must be an active community user
    result = await db.execute(
        select(User).where(User.node_id == vouchee_node_id, User.is_active == True)
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("User not found")

    # Check for existing vouch in this org context
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == voucher_node_id,
            Edge.target_node_id == vouchee_node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id == org_node_id,
        )
    )
    if result.scalar_one_or_none():
        raise ValueError("Already vouched for this user in this organization")

    # Create the context-scoped vouch
    vouch = Edge(
        source_node_id=voucher_node_id,
        target_node_id=vouchee_node_id,
        type=EdgeType.VOUCH,
        context_node_id=org_node_id,
    )
    db.add(vouch)

    # Add membership
    membership = await add_member(db, vouchee_node_id, org_node_id)
    return membership
