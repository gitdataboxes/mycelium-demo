"""
Tests for graph-proximity discovery.

Seed graph:
    alice --vouch--> bob --vouch--> carol --vouch--> dave
    alice --vouch--> eve

    org_close:    members = [bob]           -> distance 1 from alice
    org_medium:   members = [carol]         -> distance 2 from alice
    org_far:      members = [dave]          -> distance 3 from alice
    org_isolated: members = [frank]         -> no path from alice
    evt_close:    participants = [eve]      -> distance 1 from alice
    evt_cooled:   participants = [bob]      -> distance 1, but alice cooled this event
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.models.edge import Edge, EdgeType
from app.models.event import Event
from app.models.node import Node, NodeType
from app.models.organization import Organization
from app.models.user import User
from app.services.discovery import discover


def _uuid():
    return uuid.uuid4()


@pytest_asyncio.fixture
async def seed(db: AsyncSession):
    """Build the test graph and return a namespace of node IDs."""
    # Community
    community = Community(id=_uuid(), name="test-community")
    db.add(community)
    await db.flush()

    # Helper to create a user node + user record
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
    dave = await make_user("dave@test.com")
    eve = await make_user("eve@test.com")
    frank = await make_user("frank@test.com")

    # Vouch chain: alice -> bob -> carol -> dave
    for src, tgt in [(alice, bob), (bob, carol), (carol, dave)]:
        db.add(Edge(source_node_id=src.node_id, target_node_id=tgt.node_id, type=EdgeType.VOUCH))
    # alice -> eve
    db.add(Edge(source_node_id=alice.node_id, target_node_id=eve.node_id, type=EdgeType.VOUCH))
    await db.flush()

    # Helper to create an org with members
    async def make_org(name: str, members: list[User]) -> Organization:
        node = Node(community_id=community.id, type=NodeType.ORGANIZATION)
        db.add(node)
        await db.flush()
        org = Organization(node_id=node.id, name=name, description=f"{name} description")
        db.add(org)
        for m in members:
            db.add(Edge(source_node_id=m.node_id, target_node_id=node.id, type=EdgeType.MEMBER))
        await db.flush()
        return org

    org_close = await make_org("Close Org", [bob])
    org_medium = await make_org("Medium Org", [carol])
    org_far = await make_org("Far Org", [dave])
    org_isolated = await make_org("Isolated Org", [frank])

    # Helper to create an event with participants
    now = datetime.now(timezone.utc)

    async def make_event(title: str, participants: list[User], past: bool = False) -> Event:
        node = Node(community_id=community.id, type=NodeType.EVENT)
        db.add(node)
        await db.flush()
        starts = now + timedelta(days=3) if not past else now - timedelta(days=3)
        ends = starts + timedelta(hours=3)
        event = Event(
            node_id=node.id,
            title=title,
            starts_at=starts,
            ends_at=ends,
        )
        db.add(event)
        for p in participants:
            db.add(
                Edge(source_node_id=p.node_id, target_node_id=node.id, type=EdgeType.PARTICIPANT)
            )
        await db.flush()
        return event

    evt_close = await make_event("Close Event", [eve])
    evt_cooled = await make_event("Cooled Event", [bob])
    evt_past = await make_event("Past Event", [bob], past=True)

    # Alice cools evt_cooled
    db.add(
        Edge(
            source_node_id=alice.node_id,
            target_node_id=evt_cooled.node_id,
            type=EdgeType.COOL,
        )
    )

    # Also: alice cools bob (for testing that cooling bob doesn't hide his orgs)
    db.add(
        Edge(
            source_node_id=alice.node_id,
            target_node_id=bob.node_id,
            type=EdgeType.COOL,
        )
    )

    # Org where alice is a member (for self-membership test)
    org_self = await make_org("Alice Org", [alice])

    await db.commit()

    class Seed:
        pass

    s = Seed()
    s.community_id = community.id
    s.alice = alice
    s.bob = bob
    s.carol = carol
    s.dave = dave
    s.eve = eve
    s.frank = frank
    s.org_close = org_close
    s.org_medium = org_medium
    s.org_far = org_far
    s.org_isolated = org_isolated
    s.org_self = org_self
    s.evt_close = evt_close
    s.evt_cooled = evt_cooled
    s.evt_past = evt_past
    return s


@pytest.mark.asyncio
async def test_proximity_ordering(db: AsyncSession, seed):
    """Orgs ordered: org_self (0), org_close (1), org_medium (2), org_far (3), org_isolated (None)."""
    results, total = await discover(
        db, seed.alice.node_id, seed.community_id, node_types=["organization"]
    )

    ids = [r.node_id for r in results]
    distances = [r.graph_distance for r in results]

    # org_self should be first (distance 0)
    assert results[0].node_id == seed.org_self.node_id
    assert results[0].graph_distance == 0

    # org_close (distance 1) before org_medium (distance 2) before org_far (distance 3)
    close_idx = ids.index(seed.org_close.node_id)
    medium_idx = ids.index(seed.org_medium.node_id)
    far_idx = ids.index(seed.org_far.node_id)
    assert close_idx < medium_idx < far_idx

    assert results[close_idx].graph_distance == 1
    assert results[medium_idx].graph_distance == 2
    assert results[far_idx].graph_distance == 3

    # org_isolated appears last with graph_distance=None
    assert ids[-1] == seed.org_isolated.node_id
    assert results[-1].graph_distance is None

    assert total == 5  # org_self + org_close + org_medium + org_far + org_isolated


@pytest.mark.asyncio
async def test_cooling_exclusion(db: AsyncSession, seed):
    """Cooled event is excluded from results."""
    results, total = await discover(
        db, seed.alice.node_id, seed.community_id, node_types=["event"]
    )
    event_ids = {r.node_id for r in results}
    assert seed.evt_cooled.node_id not in event_ids


@pytest.mark.asyncio
async def test_cooling_scoping(db: AsyncSession, seed):
    """Cooling bob does NOT hide orgs where bob is a member."""
    results, _ = await discover(
        db, seed.alice.node_id, seed.community_id, node_types=["organization"]
    )
    org_ids = {r.node_id for r in results}
    # org_close has bob as member — should still appear
    assert seed.org_close.node_id in org_ids


@pytest.mark.asyncio
async def test_text_search(db: AsyncSession, seed):
    """Search filters results while preserving proximity ordering."""
    results, total = await discover(
        db, seed.alice.node_id, seed.community_id,
        node_types=["organization"], search="Close",
    )
    assert total == 1
    assert results[0].node_id == seed.org_close.node_id
    assert results[0].graph_distance == 1


@pytest.mark.asyncio
async def test_upcoming_filter(db: AsyncSession, seed):
    """Past events excluded when upcoming_only=True."""
    results, _ = await discover(
        db, seed.alice.node_id, seed.community_id,
        node_types=["event"], upcoming_only=True,
    )
    event_ids = {r.node_id for r in results}
    assert seed.evt_past.node_id not in event_ids
    assert seed.evt_close.node_id in event_ids


@pytest.mark.asyncio
async def test_upcoming_false_includes_past(db: AsyncSession, seed):
    """Past events included when upcoming_only=False."""
    results, _ = await discover(
        db, seed.alice.node_id, seed.community_id,
        node_types=["event"], upcoming_only=False,
    )
    event_ids = {r.node_id for r in results}
    assert seed.evt_past.node_id in event_ids


@pytest.mark.asyncio
async def test_pagination(db: AsyncSession, seed):
    """Limit and offset work correctly; total_count is stable."""
    results_p1, total1 = await discover(
        db, seed.alice.node_id, seed.community_id,
        node_types=["organization"], limit=2, offset=0,
    )
    results_p2, total2 = await discover(
        db, seed.alice.node_id, seed.community_id,
        node_types=["organization"], limit=2, offset=2,
    )

    assert len(results_p1) == 2
    assert len(results_p2) == 2
    assert total1 == total2 == 5

    # No overlap between pages
    ids_p1 = {r.node_id for r in results_p1}
    ids_p2 = {r.node_id for r in results_p2}
    assert ids_p1.isdisjoint(ids_p2)


@pytest.mark.asyncio
async def test_self_membership(db: AsyncSession, seed):
    """If alice is a member of org_self, it gets graph_distance=0."""
    results, _ = await discover(
        db, seed.alice.node_id, seed.community_id, node_types=["organization"]
    )
    for r in results:
        if r.node_id == seed.org_self.node_id:
            assert r.graph_distance == 0
            break
    else:
        pytest.fail("org_self not found in results")


@pytest.mark.asyncio
async def test_no_reachable_members(db: AsyncSession, seed):
    """Org with no reachable members gets graph_distance=None and sorts last."""
    results, _ = await discover(
        db, seed.alice.node_id, seed.community_id, node_types=["organization"]
    )
    isolated = [r for r in results if r.node_id == seed.org_isolated.node_id]
    assert len(isolated) == 1
    assert isolated[0].graph_distance is None
    # Should be last
    assert results[-1].node_id == seed.org_isolated.node_id
