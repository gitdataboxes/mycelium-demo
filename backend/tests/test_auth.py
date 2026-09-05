import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.community import Community
from app.models.node import Node, NodeType
from app.models.user import MagicLinkToken, Session, User
from app.services.auth import (
    create_magic_link,
    delete_session,
    get_session,
    verify_magic_link,
)


def _uuid():
    return uuid.uuid4()


@pytest_asyncio.fixture
async def seed(db: AsyncSession):
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
        return user

    alice = await make_user("alice@test.com")
    bob = await make_user("bob@test.com", active=False)
    await db.commit()

    class Seed:
        pass

    s = Seed()
    s.alice = alice
    s.bob = bob
    return s


# --- create_magic_link ---


@pytest.mark.asyncio
async def test_create_magic_link(db: AsyncSession, seed):
    raw_token, user = await create_magic_link(db, "alice@test.com")
    assert raw_token is not None
    assert len(raw_token) > 0
    assert user.email == "alice@test.com"


@pytest.mark.asyncio
async def test_create_magic_link_no_user(db: AsyncSession, seed):
    with pytest.raises(ValueError, match="No account found"):
        await create_magic_link(db, "nobody@test.com")


@pytest.mark.asyncio
async def test_create_magic_link_bootstraps_founding_user(db: AsyncSession, monkeypatch):
    monkeypatch.setattr(settings, "founding_user_email", "founder@test.com")

    raw_token, user = await create_magic_link(db, "Founder@Test.com")

    assert raw_token is not None
    assert user.email == "founder@test.com"
    assert user.is_active is True

    result = await db.execute(select(User).where(User.email == "founder@test.com"))
    stored_user = result.scalar_one()
    assert stored_user.is_active is True


# --- verify_magic_link ---


@pytest.mark.asyncio
async def test_verify_magic_link(db: AsyncSession, seed):
    raw_token, _ = await create_magic_link(db, "alice@test.com")
    session = await verify_magic_link(db, raw_token)
    assert session.user_id == seed.alice.node_id


@pytest.mark.asyncio
async def test_verify_magic_link_activates_inactive(db: AsyncSession, seed):
    raw_token, _ = await create_magic_link(db, "bob@test.com")
    await verify_magic_link(db, raw_token)

    result = await db.execute(select(User).where(User.node_id == seed.bob.node_id))
    bob = result.scalar_one()
    assert bob.is_active is True


@pytest.mark.asyncio
async def test_verify_magic_link_expired(db: AsyncSession, seed):
    raw_token, _ = await create_magic_link(db, "alice@test.com")

    result = await db.execute(
        select(MagicLinkToken).order_by(MagicLinkToken.expires_at.desc()).limit(1)
    )
    token = result.scalar_one()
    token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db.commit()

    with pytest.raises(ValueError, match="Invalid or expired"):
        await verify_magic_link(db, raw_token)


@pytest.mark.asyncio
async def test_verify_magic_link_used(db: AsyncSession, seed):
    raw_token, _ = await create_magic_link(db, "alice@test.com")
    await verify_magic_link(db, raw_token)
    with pytest.raises(ValueError, match="Invalid or expired"):
        await verify_magic_link(db, raw_token)


# --- get_session ---


@pytest.mark.asyncio
async def test_get_session(db: AsyncSession, seed):
    raw_token, _ = await create_magic_link(db, "alice@test.com")
    session = await verify_magic_link(db, raw_token)
    fetched = await get_session(db, str(session.id))
    assert fetched is not None
    assert fetched.user_id == seed.alice.node_id


@pytest.mark.asyncio
async def test_get_session_expired(db: AsyncSession, seed):
    raw_token, _ = await create_magic_link(db, "alice@test.com")
    session = await verify_magic_link(db, raw_token)
    session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db.commit()
    assert await get_session(db, str(session.id)) is None


@pytest.mark.asyncio
async def test_get_session_invalid_id(db: AsyncSession, seed):
    assert await get_session(db, "not-a-uuid") is None


# --- delete_session ---


@pytest.mark.asyncio
async def test_delete_session(db: AsyncSession, seed):
    raw_token, _ = await create_magic_link(db, "alice@test.com")
    session = await verify_magic_link(db, raw_token)
    await delete_session(db, str(session.id))
    assert await get_session(db, str(session.id)) is None
