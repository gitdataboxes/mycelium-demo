import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.models.edge import Edge, EdgeType
from app.models.event import Event, EventUrgency
from app.models.node import Node, NodeType
from app.models.user import User
from app.services.event import (
    add_participant,
    add_responder,
    create_event,
    delete_event,
    get_event,
    get_participants,
    get_responders,
    is_participant,
    is_responder,
    list_events,
    remove_participant,
    remove_responder,
    update_event,
    vouch_into_event,
)


def _uuid():
    return uuid.uuid4()


@pytest_asyncio.fixture
async def seed(db: AsyncSession):
    community = Community(id=_uuid(), name="test-community")
    db.add(community)
    await db.flush()

    async def make_user(email: str) -> User:
        node = Node(community_id=community.id, type=NodeType.USER)
        db.add(node)
        await db.flush()
        user = User(node_id=node.id, email=email, is_active=True)
        db.add(user)
        await db.flush()
        user.node = node
        return user

    alice = await make_user("alice@test.com")
    bob = await make_user("bob@test.com")
    carol = await make_user("carol@test.com")
    await db.commit()

    class Seed:
        pass

    s = Seed()
    s.community = community
    s.alice = alice
    s.bob = bob
    s.carol = carol
    return s


# --- CRUD ---


@pytest.mark.asyncio
async def test_create_event(db: AsyncSession, seed):
    now = datetime.now(timezone.utc)
    event = await create_event(
        db, seed.alice, "Test Event",
        description="A description",
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, hours=3),
    )
    assert event.title == "Test Event"
    assert event.description == "A description"
    assert await is_participant(db, seed.alice.node_id, event.node_id) is True
    assert await is_responder(db, seed.alice.node_id, event.node_id) is True


@pytest.mark.asyncio
async def test_get_event(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    fetched = await get_event(db, event.node_id)
    assert fetched is not None
    assert fetched.title == "Test Event"


@pytest.mark.asyncio
async def test_get_event_not_found(db: AsyncSession, seed):
    assert await get_event(db, _uuid()) is None


@pytest.mark.asyncio
async def test_list_events(db: AsyncSession, seed):
    now = datetime.now(timezone.utc)
    await create_event(db, seed.alice, "Alpha Event", starts_at=now + timedelta(days=2))
    await create_event(db, seed.bob, "Beta Event", starts_at=now + timedelta(days=1))
    events = await list_events(db, seed.community.id)
    assert len(events) == 2
    assert events[0].title == "Beta Event"
    assert events[1].title == "Alpha Event"


@pytest.mark.asyncio
async def test_list_events_search(db: AsyncSession, seed):
    await create_event(db, seed.alice, "Alpha Event")
    await create_event(db, seed.bob, "Beta Event")
    events = await list_events(db, seed.community.id, search="Alpha")
    assert len(events) == 1
    assert events[0].title == "Alpha Event"


@pytest.mark.asyncio
async def test_list_events_upcoming_only(db: AsyncSession, seed):
    now = datetime.now(timezone.utc)
    await create_event(db, seed.alice, "Future", ends_at=now + timedelta(days=1))
    await create_event(db, seed.bob, "Past", ends_at=now - timedelta(days=1))
    events = await list_events(db, seed.community.id, upcoming_only=True)
    assert len(events) == 1
    assert events[0].title == "Future"


@pytest.mark.asyncio
async def test_update_event(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Old Title")
    updated = await update_event(db, event, title="New Title", location="Downtown")
    assert updated.title == "New Title"
    assert updated.location == "Downtown"


@pytest.mark.asyncio
async def test_delete_event(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "To Delete")
    node_id = event.node_id
    await delete_event(db, node_id)
    assert await get_event(db, node_id) is None
    result = await db.execute(select(Edge).where(Edge.target_node_id == node_id))
    assert result.scalars().all() == []


# --- Participation ---


@pytest.mark.asyncio
async def test_add_participant(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    edge = await add_participant(db, seed.bob.node_id, event.node_id)
    assert edge.type == EdgeType.PARTICIPANT
    assert await is_participant(db, seed.bob.node_id, event.node_id) is True


@pytest.mark.asyncio
async def test_add_participant_duplicate(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    with pytest.raises(ValueError, match="Already participating"):
        await add_participant(db, seed.alice.node_id, event.node_id)


@pytest.mark.asyncio
async def test_get_participants(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    await add_participant(db, seed.bob.node_id, event.node_id)
    participants = await get_participants(db, event.node_id)
    assert len(participants) == 2
    user_ids = {u.node_id for u, _ in participants}
    assert seed.alice.node_id in user_ids
    assert seed.bob.node_id in user_ids


@pytest.mark.asyncio
async def test_remove_participant(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    await add_participant(db, seed.bob.node_id, event.node_id)
    await remove_participant(db, seed.bob.node_id, event.node_id)
    assert await is_participant(db, seed.bob.node_id, event.node_id) is False


@pytest.mark.asyncio
async def test_remove_participant_not_participant(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    with pytest.raises(ValueError, match="Not a participant"):
        await remove_participant(db, seed.bob.node_id, event.node_id)


@pytest.mark.asyncio
async def test_remove_participant_cleans_scoped_vouches(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    await vouch_into_event(db, seed.alice.node_id, seed.carol.node_id, event.node_id)

    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == seed.alice.node_id,
            Edge.target_node_id == seed.carol.node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id == event.node_id,
        )
    )
    assert result.scalar_one_or_none() is not None

    await remove_participant(db, seed.alice.node_id, event.node_id)

    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == seed.alice.node_id,
            Edge.target_node_id == seed.carol.node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id == event.node_id,
        )
    )
    assert result.scalar_one_or_none() is None


# --- Responders ---


@pytest.mark.asyncio
async def test_add_responder(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    edge = await add_responder(db, seed.alice.node_id, event.node_id, seed.bob.node_id)
    assert edge.type == EdgeType.RESPONDER
    assert await is_responder(db, seed.bob.node_id, event.node_id) is True


@pytest.mark.asyncio
async def test_add_responder_not_responder(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    with pytest.raises(ValueError, match="Only existing responders"):
        await add_responder(db, seed.bob.node_id, event.node_id, seed.carol.node_id)


@pytest.mark.asyncio
async def test_add_responder_duplicate(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    with pytest.raises(ValueError, match="Already a responder"):
        await add_responder(db, seed.alice.node_id, event.node_id, seed.alice.node_id)


@pytest.mark.asyncio
async def test_remove_responder(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    await add_responder(db, seed.alice.node_id, event.node_id, seed.bob.node_id)
    await remove_responder(db, seed.alice.node_id, event.node_id, seed.bob.node_id)
    assert await is_responder(db, seed.bob.node_id, event.node_id) is False


@pytest.mark.asyncio
async def test_remove_last_responder(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    with pytest.raises(ValueError, match="Cannot remove the last responder"):
        await remove_responder(db, seed.alice.node_id, event.node_id, seed.alice.node_id)


@pytest.mark.asyncio
async def test_get_responders(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    await add_responder(db, seed.alice.node_id, event.node_id, seed.bob.node_id)
    responders = await get_responders(db, event.node_id)
    assert len(responders) == 2
    user_ids = {u.node_id for u, _ in responders}
    assert seed.alice.node_id in user_ids
    assert seed.bob.node_id in user_ids


# --- vouch_into_event ---


@pytest.mark.asyncio
async def test_vouch_into_event(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    participation = await vouch_into_event(db, seed.alice.node_id, seed.bob.node_id, event.node_id)
    assert participation.type == EdgeType.PARTICIPANT
    assert await is_participant(db, seed.bob.node_id, event.node_id) is True


@pytest.mark.asyncio
async def test_vouch_into_event_not_participant(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    with pytest.raises(ValueError, match="must be a participant"):
        await vouch_into_event(db, seed.bob.node_id, seed.carol.node_id, event.node_id)


@pytest.mark.asyncio
async def test_vouch_into_event_already_participant(db: AsyncSession, seed):
    event = await create_event(db, seed.alice, "Test Event")
    await add_participant(db, seed.bob.node_id, event.node_id)
    with pytest.raises(ValueError, match="already a participant"):
        await vouch_into_event(db, seed.alice.node_id, seed.bob.node_id, event.node_id)
