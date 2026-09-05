import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.models.edge import Edge, EdgeType
from app.models.node import Node, NodeType
from app.models.user import User
from app.services.trust import (
    add_block,
    add_cooling,
    can_vouch,
    get_trust_distance,
    get_vouches_given,
    get_vouches_received,
    is_blocked,
    remove_block,
    remove_cooling,
    trust_score,
    vouch_for_user,
    withdraw_vouch,
)


def _uuid():
    return uuid.uuid4()


@pytest_asyncio.fixture
async def seed(db: AsyncSession):
    """Build test graph: alice->bob->carol->dave vouch chain, eve standalone."""
    community = Community(id=_uuid(), name="test-community")
    db.add(community)
    await db.flush()

    async def make_user(email: str, active: bool = True) -> User:
        node = Node(community_id=community.id, type=NodeType.USER)
        db.add(node)
        await db.flush()
        user = User(node_id=node.id, email=email, is_active=active)
        db.add(user)
        await db.flush()
        user.node = node
        return user

    alice = await make_user("alice@test.com")
    bob = await make_user("bob@test.com")
    carol = await make_user("carol@test.com")
    dave = await make_user("dave@test.com")
    eve = await make_user("eve@test.com")

    for src, tgt in [(alice, bob), (bob, carol), (carol, dave)]:
        db.add(Edge(source_node_id=src.node_id, target_node_id=tgt.node_id, type=EdgeType.VOUCH))
    await db.flush()
    await db.commit()

    class Seed:
        pass

    s = Seed()
    s.community = community
    s.alice = alice
    s.bob = bob
    s.carol = carol
    s.dave = dave
    s.eve = eve
    s.make_user = make_user
    return s


# --- can_vouch ---


@pytest.mark.asyncio
async def test_can_vouch_no_recent(db: AsyncSession, seed):
    assert await can_vouch(db, seed.eve.node_id) is True


@pytest.mark.asyncio
async def test_can_vouch_blocked_by_recent(db: AsyncSession, seed):
    assert await can_vouch(db, seed.alice.node_id) is False


@pytest.mark.asyncio
async def test_can_vouch_old_vouch_ok(db: AsyncSession, seed):
    old = datetime.now(timezone.utc) - timedelta(days=8)
    db.add(Edge(
        source_node_id=seed.eve.node_id,
        target_node_id=seed.alice.node_id,
        type=EdgeType.VOUCH,
        created_at=old,
    ))
    await db.commit()
    assert await can_vouch(db, seed.eve.node_id) is True


# --- vouch_for_user ---


@pytest.mark.asyncio
async def test_vouch_for_existing_user(db: AsyncSession, seed):
    edge, vouchee, token = await vouch_for_user(db, seed.eve, "carol@test.com")
    assert edge.source_node_id == seed.eve.node_id
    assert edge.target_node_id == seed.carol.node_id
    assert vouchee.email == "carol@test.com"
    assert token is None


@pytest.mark.asyncio
async def test_vouch_for_new_user(db: AsyncSession, seed):
    edge, vouchee, token = await vouch_for_user(db, seed.eve, "newuser@test.com")
    assert vouchee.email == "newuser@test.com"
    assert vouchee.is_active is False
    assert token is not None


@pytest.mark.asyncio
async def test_vouch_self_prevention(db: AsyncSession, seed):
    with pytest.raises(ValueError, match="cannot vouch for yourself"):
        await vouch_for_user(db, seed.eve, "eve@test.com")


@pytest.mark.asyncio
async def test_vouch_duplicate_prevention(db: AsyncSession, seed):
    old = datetime.now(timezone.utc) - timedelta(days=8)
    db.add(Edge(
        source_node_id=seed.eve.node_id,
        target_node_id=seed.carol.node_id,
        type=EdgeType.VOUCH,
        created_at=old,
    ))
    await db.commit()
    with pytest.raises(ValueError, match="already have an active vouch"):
        await vouch_for_user(db, seed.eve, "carol@test.com")


@pytest.mark.asyncio
async def test_vouch_cooldown_enforcement(db: AsyncSession, seed):
    with pytest.raises(ValueError, match="one person per week"):
        await vouch_for_user(db, seed.alice, "eve@test.com")


# --- withdraw_vouch ---


@pytest.mark.asyncio
async def test_withdraw_vouch_deactivates(db: AsyncSession, seed):
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == seed.alice.node_id,
            Edge.target_node_id == seed.bob.node_id,
            Edge.type == EdgeType.VOUCH,
        )
    )
    edge = result.scalar_one()
    await withdraw_vouch(db, seed.alice.node_id, edge.id)

    result = await db.execute(select(User).where(User.node_id == seed.bob.node_id))
    bob = result.scalar_one()
    assert bob.is_active is False


@pytest.mark.asyncio
async def test_withdraw_vouch_stays_active(db: AsyncSession, seed):
    db.add(Edge(
        source_node_id=seed.eve.node_id,
        target_node_id=seed.bob.node_id,
        type=EdgeType.VOUCH,
    ))
    await db.commit()

    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == seed.alice.node_id,
            Edge.target_node_id == seed.bob.node_id,
            Edge.type == EdgeType.VOUCH,
        )
    )
    edge = result.scalar_one()
    await withdraw_vouch(db, seed.alice.node_id, edge.id)

    result = await db.execute(select(User).where(User.node_id == seed.bob.node_id))
    bob = result.scalar_one()
    assert bob.is_active is True


@pytest.mark.asyncio
async def test_withdraw_vouch_not_found(db: AsyncSession, seed):
    with pytest.raises(ValueError, match="Vouch not found"):
        await withdraw_vouch(db, seed.alice.node_id, _uuid())


# --- cooling ---


@pytest.mark.asyncio
async def test_add_cooling(db: AsyncSession, seed):
    edge = await add_cooling(db, seed.alice.node_id, seed.bob.node_id)
    assert edge.type == EdgeType.COOL
    assert edge.source_node_id == seed.alice.node_id
    assert edge.target_node_id == seed.bob.node_id


@pytest.mark.asyncio
async def test_add_cooling_self(db: AsyncSession, seed):
    with pytest.raises(ValueError, match="cannot cool yourself"):
        await add_cooling(db, seed.alice.node_id, seed.alice.node_id)


@pytest.mark.asyncio
async def test_add_cooling_duplicate(db: AsyncSession, seed):
    await add_cooling(db, seed.alice.node_id, seed.bob.node_id)
    with pytest.raises(ValueError, match="Already cooling"):
        await add_cooling(db, seed.alice.node_id, seed.bob.node_id)


@pytest.mark.asyncio
async def test_add_cooling_inactive_user(db: AsyncSession, seed):
    inactive = await seed.make_user("inactive@test.com", active=False)
    await db.commit()
    with pytest.raises(ValueError, match="User not found"):
        await add_cooling(db, seed.alice.node_id, inactive.node_id)


@pytest.mark.asyncio
async def test_remove_cooling(db: AsyncSession, seed):
    await add_cooling(db, seed.alice.node_id, seed.bob.node_id)
    await remove_cooling(db, seed.alice.node_id, seed.bob.node_id)
    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == seed.alice.node_id,
            Edge.target_node_id == seed.bob.node_id,
            Edge.type == EdgeType.COOL,
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_remove_cooling_not_found(db: AsyncSession, seed):
    with pytest.raises(ValueError, match="No cooling found"):
        await remove_cooling(db, seed.alice.node_id, seed.bob.node_id)


# --- trust distance ---


@pytest.mark.asyncio
async def test_trust_distance_self(db: AsyncSession, seed):
    assert await get_trust_distance(db, seed.alice.node_id, seed.alice.node_id) == 0


@pytest.mark.asyncio
async def test_trust_distance_direct(db: AsyncSession, seed):
    assert await get_trust_distance(db, seed.alice.node_id, seed.bob.node_id) == 1


@pytest.mark.asyncio
async def test_trust_distance_two_hops(db: AsyncSession, seed):
    assert await get_trust_distance(db, seed.alice.node_id, seed.carol.node_id) == 2


@pytest.mark.asyncio
async def test_trust_distance_three_hops(db: AsyncSession, seed):
    assert await get_trust_distance(db, seed.alice.node_id, seed.dave.node_id) == 3


@pytest.mark.asyncio
async def test_trust_distance_unreachable(db: AsyncSession, seed):
    assert await get_trust_distance(db, seed.alice.node_id, seed.eve.node_id) is None


@pytest.mark.asyncio
async def test_trust_distance_bidirectional(db: AsyncSession, seed):
    assert await get_trust_distance(db, seed.bob.node_id, seed.alice.node_id) == 1


# --- trust_score ---


def test_trust_score_values():
    assert trust_score(None) == 0.1
    assert trust_score(0) == 1.0
    assert trust_score(1) == 1.0
    assert trust_score(2) == 0.5
    assert trust_score(3) == 0.25
    assert trust_score(4) == 0.1


# --- block ---


@pytest.mark.asyncio
async def test_add_block(db: AsyncSession, seed):
    edge = await add_block(db, seed.alice.node_id, seed.bob.node_id)
    assert edge.type == EdgeType.BLOCK


@pytest.mark.asyncio
async def test_add_block_self(db: AsyncSession, seed):
    with pytest.raises(ValueError, match="cannot block yourself"):
        await add_block(db, seed.alice.node_id, seed.alice.node_id)


@pytest.mark.asyncio
async def test_add_block_duplicate(db: AsyncSession, seed):
    await add_block(db, seed.alice.node_id, seed.bob.node_id)
    with pytest.raises(ValueError, match="Already blocked"):
        await add_block(db, seed.alice.node_id, seed.bob.node_id)


@pytest.mark.asyncio
async def test_remove_block(db: AsyncSession, seed):
    await add_block(db, seed.alice.node_id, seed.bob.node_id)
    await remove_block(db, seed.alice.node_id, seed.bob.node_id)
    assert await is_blocked(db, seed.bob.node_id, seed.alice.node_id) is False


@pytest.mark.asyncio
async def test_remove_block_not_found(db: AsyncSession, seed):
    with pytest.raises(ValueError, match="Not blocked"):
        await remove_block(db, seed.alice.node_id, seed.bob.node_id)


@pytest.mark.asyncio
async def test_is_blocked_directional(db: AsyncSession, seed):
    await add_block(db, seed.alice.node_id, seed.bob.node_id)
    assert await is_blocked(db, seed.bob.node_id, seed.alice.node_id) is True
    assert await is_blocked(db, seed.alice.node_id, seed.bob.node_id) is False


# --- vouches given / received ---


@pytest.mark.asyncio
async def test_get_vouches_given(db: AsyncSession, seed):
    vouches = await get_vouches_given(db, seed.alice.node_id)
    assert len(vouches) == 1
    assert vouches[0].target_node_id == seed.bob.node_id


@pytest.mark.asyncio
async def test_get_vouches_received(db: AsyncSession, seed):
    vouches = await get_vouches_received(db, seed.bob.node_id)
    assert len(vouches) == 1
    assert vouches[0].source_node_id == seed.alice.node_id
