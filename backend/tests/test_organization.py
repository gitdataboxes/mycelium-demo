import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.models.edge import Edge, EdgeType
from app.models.node import Node, NodeType
from app.models.organization import Organization
from app.models.user import User
from app.services.organization import (
    add_member,
    add_responder,
    create_organization,
    delete_organization,
    get_members,
    get_organization,
    get_responders,
    is_member,
    is_responder,
    list_organizations,
    remove_member,
    remove_responder,
    update_organization,
    vouch_into_org,
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
async def test_create_organization(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org", "A description")
    assert org.name == "Test Org"
    assert org.description == "A description"
    assert await is_member(db, seed.alice.node_id, org.node_id) is True
    assert await is_responder(db, seed.alice.node_id, org.node_id) is True


@pytest.mark.asyncio
async def test_get_organization(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    fetched = await get_organization(db, org.node_id)
    assert fetched is not None
    assert fetched.name == "Test Org"


@pytest.mark.asyncio
async def test_get_organization_not_found(db: AsyncSession, seed):
    assert await get_organization(db, _uuid()) is None


@pytest.mark.asyncio
async def test_list_organizations(db: AsyncSession, seed):
    await create_organization(db, seed.alice, "Alpha Org")
    await create_organization(db, seed.bob, "Beta Org")
    orgs = await list_organizations(db, seed.community.id)
    assert len(orgs) == 2
    assert orgs[0].name == "Alpha Org"
    assert orgs[1].name == "Beta Org"


@pytest.mark.asyncio
async def test_list_organizations_search(db: AsyncSession, seed):
    await create_organization(db, seed.alice, "Alpha Org")
    await create_organization(db, seed.bob, "Beta Org")
    orgs = await list_organizations(db, seed.community.id, search="Alpha")
    assert len(orgs) == 1
    assert orgs[0].name == "Alpha Org"


@pytest.mark.asyncio
async def test_update_organization(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Old Name")
    updated = await update_organization(db, org, name="New Name", description="Updated")
    assert updated.name == "New Name"
    assert updated.description == "Updated"


@pytest.mark.asyncio
async def test_delete_organization(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "To Delete")
    node_id = org.node_id
    await delete_organization(db, node_id)
    assert await get_organization(db, node_id) is None
    result = await db.execute(select(Edge).where(Edge.target_node_id == node_id))
    assert result.scalars().all() == []


# --- Membership ---


@pytest.mark.asyncio
async def test_add_member(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    edge = await add_member(db, seed.bob.node_id, org.node_id)
    assert edge.type == EdgeType.MEMBER
    assert await is_member(db, seed.bob.node_id, org.node_id) is True


@pytest.mark.asyncio
async def test_add_member_duplicate(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    with pytest.raises(ValueError, match="Already a member"):
        await add_member(db, seed.alice.node_id, org.node_id)


@pytest.mark.asyncio
async def test_get_members(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    await add_member(db, seed.bob.node_id, org.node_id)
    members = await get_members(db, org.node_id)
    assert len(members) == 2
    user_ids = {u.node_id for u, _ in members}
    assert seed.alice.node_id in user_ids
    assert seed.bob.node_id in user_ids


@pytest.mark.asyncio
async def test_remove_member(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    await add_member(db, seed.bob.node_id, org.node_id)
    await remove_member(db, seed.bob.node_id, org.node_id)
    assert await is_member(db, seed.bob.node_id, org.node_id) is False


@pytest.mark.asyncio
async def test_remove_member_not_member(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    with pytest.raises(ValueError, match="Not a member"):
        await remove_member(db, seed.bob.node_id, org.node_id)


@pytest.mark.asyncio
async def test_remove_member_cleans_scoped_vouches(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    await vouch_into_org(db, seed.alice.node_id, seed.carol.node_id, org.node_id)

    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == seed.alice.node_id,
            Edge.target_node_id == seed.carol.node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id == org.node_id,
        )
    )
    assert result.scalar_one_or_none() is not None

    await remove_member(db, seed.alice.node_id, org.node_id)

    result = await db.execute(
        select(Edge).where(
            Edge.source_node_id == seed.alice.node_id,
            Edge.target_node_id == seed.carol.node_id,
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id == org.node_id,
        )
    )
    assert result.scalar_one_or_none() is None


# --- Responders ---


@pytest.mark.asyncio
async def test_add_responder(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    edge = await add_responder(db, seed.alice.node_id, org.node_id, seed.bob.node_id)
    assert edge.type == EdgeType.RESPONDER
    assert await is_responder(db, seed.bob.node_id, org.node_id) is True


@pytest.mark.asyncio
async def test_add_responder_not_responder(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    with pytest.raises(ValueError, match="Only existing responders"):
        await add_responder(db, seed.bob.node_id, org.node_id, seed.carol.node_id)


@pytest.mark.asyncio
async def test_add_responder_duplicate(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    with pytest.raises(ValueError, match="Already a responder"):
        await add_responder(db, seed.alice.node_id, org.node_id, seed.alice.node_id)


@pytest.mark.asyncio
async def test_remove_responder(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    await add_responder(db, seed.alice.node_id, org.node_id, seed.bob.node_id)
    await remove_responder(db, seed.alice.node_id, org.node_id, seed.bob.node_id)
    assert await is_responder(db, seed.bob.node_id, org.node_id) is False


@pytest.mark.asyncio
async def test_remove_last_responder(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    with pytest.raises(ValueError, match="Cannot remove the last responder"):
        await remove_responder(db, seed.alice.node_id, org.node_id, seed.alice.node_id)


@pytest.mark.asyncio
async def test_get_responders(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    await add_responder(db, seed.alice.node_id, org.node_id, seed.bob.node_id)
    responders = await get_responders(db, org.node_id)
    assert len(responders) == 2
    user_ids = {u.node_id for u, _ in responders}
    assert seed.alice.node_id in user_ids
    assert seed.bob.node_id in user_ids


# --- vouch_into_org ---


@pytest.mark.asyncio
async def test_vouch_into_org(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    membership = await vouch_into_org(db, seed.alice.node_id, seed.bob.node_id, org.node_id)
    assert membership.type == EdgeType.MEMBER
    assert await is_member(db, seed.bob.node_id, org.node_id) is True


@pytest.mark.asyncio
async def test_vouch_into_org_not_member(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    with pytest.raises(ValueError, match="must be a member"):
        await vouch_into_org(db, seed.bob.node_id, seed.carol.node_id, org.node_id)


@pytest.mark.asyncio
async def test_vouch_into_org_already_member(db: AsyncSession, seed):
    org = await create_organization(db, seed.alice, "Test Org")
    await add_member(db, seed.bob.node_id, org.node_id)
    with pytest.raises(ValueError, match="already a member"):
        await vouch_into_org(db, seed.alice.node_id, seed.bob.node_id, org.node_id)
