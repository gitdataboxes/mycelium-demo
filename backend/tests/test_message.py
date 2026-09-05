import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.models.edge import Edge, EdgeType
from app.models.message import Message
from app.models.node import Node, NodeType
from app.models.organization import Organization
from app.models.user import User
from app.services.message import (
    get_contacts,
    get_thread_messages,
    get_threads,
    get_unread_count,
    mark_read,
    send_message,
)


def _uuid():
    return uuid.uuid4()


@pytest_asyncio.fixture
async def seed(db: AsyncSession):
    """Community with alice/bob/carol and an org where alice is responder."""
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
        return user

    alice = await make_user("alice@test.com")
    bob = await make_user("bob@test.com")
    carol = await make_user("carol@test.com")

    org_node = Node(community_id=community.id, type=NodeType.ORGANIZATION)
    db.add(org_node)
    await db.flush()
    org = Organization(node_id=org_node.id, name="Test Org")
    db.add(org)
    db.add(Edge(source_node_id=alice.node_id, target_node_id=org_node.id, type=EdgeType.RESPONDER))
    await db.flush()
    await db.commit()

    class Seed:
        pass

    s = Seed()
    s.community = community
    s.alice = alice
    s.bob = bob
    s.carol = carol
    s.org = org
    s.org_node_id = org_node.id
    return s


# --- send_message (context thread) ---


@pytest.mark.asyncio
async def test_send_context_message(db: AsyncSession, seed):
    msg = await send_message(db, seed.bob.node_id, "Hello org", context_node_id=seed.org_node_id)
    assert msg.from_user == seed.bob.node_id
    assert msg.to_user == seed.alice.node_id
    assert msg.context_node_id == seed.org_node_id
    assert msg.content == "Hello org"


@pytest.mark.asyncio
async def test_send_context_message_self(db: AsyncSession, seed):
    with pytest.raises(ValueError, match="Cannot message yourself"):
        await send_message(db, seed.alice.node_id, "Self", context_node_id=seed.org_node_id)


@pytest.mark.asyncio
async def test_send_context_message_blocked(db: AsyncSession, seed):
    db.add(Edge(
        source_node_id=seed.alice.node_id,
        target_node_id=seed.bob.node_id,
        type=EdgeType.BLOCK,
    ))
    await db.commit()
    with pytest.raises(ValueError, match="Cannot send message"):
        await send_message(db, seed.bob.node_id, "Blocked", context_node_id=seed.org_node_id)


# --- send_message (direct thread) ---


@pytest.mark.asyncio
async def test_send_direct_message(db: AsyncSession, seed):
    await send_message(db, seed.bob.node_id, "Via org", context_node_id=seed.org_node_id)
    msg = await send_message(db, seed.bob.node_id, "Direct hello", to_node_id=seed.alice.node_id)
    assert msg.from_user == seed.bob.node_id
    assert msg.to_user == seed.alice.node_id
    assert msg.context_node_id is None


@pytest.mark.asyncio
async def test_send_direct_message_no_prior_contact(db: AsyncSession, seed):
    with pytest.raises(ValueError, match="prior contact"):
        await send_message(db, seed.bob.node_id, "Hello", to_node_id=seed.carol.node_id)


@pytest.mark.asyncio
async def test_send_direct_message_blocked(db: AsyncSession, seed):
    await send_message(db, seed.bob.node_id, "Via org", context_node_id=seed.org_node_id)
    db.add(Edge(
        source_node_id=seed.alice.node_id,
        target_node_id=seed.bob.node_id,
        type=EdgeType.BLOCK,
    ))
    await db.commit()
    with pytest.raises(ValueError, match="Cannot send message"):
        await send_message(db, seed.bob.node_id, "Blocked", to_node_id=seed.alice.node_id)


@pytest.mark.asyncio
async def test_send_message_invalid_sender(db: AsyncSession, seed):
    with pytest.raises(ValueError, match="Sender not found"):
        await send_message(db, _uuid(), "Hi", context_node_id=seed.org_node_id)


# --- threads ---


@pytest.mark.asyncio
async def test_get_threads(db: AsyncSession, seed):
    await send_message(db, seed.bob.node_id, "Msg 1", context_node_id=seed.org_node_id)
    await send_message(db, seed.carol.node_id, "Msg 2", context_node_id=seed.org_node_id)

    threads = await get_threads(db, seed.alice.node_id)
    assert len(threads) == 2
    assert threads[0]["other_node_id"] == seed.carol.node_id
    assert threads[1]["other_node_id"] == seed.bob.node_id


@pytest.mark.asyncio
async def test_get_thread_messages(db: AsyncSession, seed):
    await send_message(db, seed.bob.node_id, "Hello", context_node_id=seed.org_node_id)
    await send_message(db, seed.bob.node_id, "Follow up", context_node_id=seed.org_node_id)

    messages, total = await get_thread_messages(
        db, seed.alice.node_id, seed.bob.node_id, seed.org_node_id
    )
    assert total == 2
    assert len(messages) == 2
    assert messages[0]["content"] == "Hello"
    assert messages[1]["content"] == "Follow up"


@pytest.mark.asyncio
async def test_mark_read(db: AsyncSession, seed):
    await send_message(db, seed.bob.node_id, "Msg 1", context_node_id=seed.org_node_id)
    await send_message(db, seed.bob.node_id, "Msg 2", context_node_id=seed.org_node_id)

    count = await mark_read(db, seed.alice.node_id, seed.bob.node_id, seed.org_node_id)
    assert count == 2
    assert await get_unread_count(db, seed.alice.node_id) == 0


@pytest.mark.asyncio
async def test_get_unread_count(db: AsyncSession, seed):
    await send_message(db, seed.bob.node_id, "Msg 1", context_node_id=seed.org_node_id)
    await send_message(db, seed.carol.node_id, "Msg 2", context_node_id=seed.org_node_id)

    assert await get_unread_count(db, seed.alice.node_id) == 2


@pytest.mark.asyncio
async def test_get_contacts(db: AsyncSession, seed):
    await send_message(db, seed.bob.node_id, "Hi", context_node_id=seed.org_node_id)
    await send_message(db, seed.carol.node_id, "Hey", context_node_id=seed.org_node_id)

    contacts = await get_contacts(db, seed.alice.node_id)
    contact_ids = {c["node_id"] for c in contacts}
    assert seed.bob.node_id in contact_ids
    assert seed.carol.node_id in contact_ids
    assert len(contacts) == 2
