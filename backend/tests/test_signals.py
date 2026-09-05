import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.models.node import Node, NodeType
from app.models.profile import AttributeDirection
from app.models.signal import Signal
from app.services.signals import cleanup_expired_signals


def _uuid():
    return uuid.uuid4()


@pytest_asyncio.fixture
async def seed(db: AsyncSession):
    community = Community(id=_uuid(), name="test-community")
    db.add(community)
    await db.flush()

    node = Node(community_id=community.id, type=NodeType.USER)
    db.add(node)
    await db.flush()
    await db.commit()

    class Seed:
        pass

    s = Seed()
    s.node_id = node.id
    return s


@pytest.mark.asyncio
async def test_cleanup_expired_signals(db: AsyncSession, seed):
    now = datetime.now(timezone.utc)
    db.add(Signal(
        node_id=seed.node_id,
        direction=AttributeDirection.OUTPUT,
        content="Expired",
        expires_at=now - timedelta(hours=1),
    ))
    db.add(Signal(
        node_id=seed.node_id,
        direction=AttributeDirection.INPUT,
        content="Active",
        expires_at=now + timedelta(hours=1),
    ))
    await db.commit()

    count = await cleanup_expired_signals(db)
    assert count == 1


@pytest.mark.asyncio
async def test_cleanup_no_expired(db: AsyncSession, seed):
    now = datetime.now(timezone.utc)
    db.add(Signal(
        node_id=seed.node_id,
        direction=AttributeDirection.OUTPUT,
        content="Active",
        expires_at=now + timedelta(hours=1),
    ))
    await db.commit()

    count = await cleanup_expired_signals(db)
    assert count == 0


@pytest.mark.asyncio
async def test_cleanup_preserves_no_expiry(db: AsyncSession, seed):
    db.add(Signal(
        node_id=seed.node_id,
        direction=AttributeDirection.OUTPUT,
        content="Permanent",
        expires_at=None,
    ))
    await db.commit()

    count = await cleanup_expired_signals(db)
    assert count == 0
