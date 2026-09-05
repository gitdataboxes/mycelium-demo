import pytest
from sqlalchemy import func, select

from app.models.community import Community
from app.models.edge import Edge, EdgeType
from app.models.graph_analytics import GraphAnalytics
from app.models.node import Node, NodeType
from app.models.user import User
from app.services.graph_analytics import (
    _upsert_analytics,
    compute_centrality,
    compute_health,
    detect_communities,
    get_analytics,
    load_community_graph,
)


async def _create_community(db, name: str) -> Community:
    community = Community(name=name)
    db.add(community)
    await db.flush()
    return community


async def _create_user(db, community: Community, email: str) -> User:
    node = Node(community_id=community.id, type=NodeType.USER)
    db.add(node)
    await db.flush()

    user = User(node_id=node.id, email=email, is_active=True)
    db.add(user)
    await db.flush()
    return user


async def _create_context_node(db, community: Community) -> Node:
    node = Node(community_id=community.id, type=NodeType.EVENT)
    db.add(node)
    await db.flush()
    return node


async def _add_vouch(db, source: User, target: User, context_node_id=None) -> Edge:
    edge = Edge(
        source_node_id=source.node_id,
        target_node_id=target.node_id,
        type=EdgeType.VOUCH,
        context_node_id=context_node_id,
    )
    db.add(edge)
    await db.flush()
    return edge


@pytest.mark.asyncio
async def test_load_community_graph(db):
    primary = await _create_community(db, "Primary")
    secondary = await _create_community(db, "Secondary")

    alice = await _create_user(db, primary, "alice@example.com")
    bob = await _create_user(db, primary, "bob@example.com")
    carol = await _create_user(db, primary, "carol@example.com")
    dave = await _create_user(db, secondary, "dave@example.com")
    erin = await _create_user(db, secondary, "erin@example.com")
    scoped_context = await _create_context_node(db, primary)

    await _add_vouch(db, alice, bob)
    await _add_vouch(db, bob, carol)
    await _add_vouch(db, alice, carol, scoped_context.id)
    await _add_vouch(db, dave, erin)
    await _add_vouch(db, alice, dave)

    graph = await load_community_graph(db, primary.id)

    assert set(graph.nodes) == {str(alice.node_id), str(bob.node_id), str(carol.node_id)}
    assert {frozenset(edge) for edge in graph.edges} == {
        frozenset((str(alice.node_id), str(bob.node_id))),
        frozenset((str(bob.node_id), str(carol.node_id))),
    }


@pytest.mark.asyncio
async def test_detect_communities(db):
    community = await _create_community(db, "Partitioned")
    a = await _create_user(db, community, "a@example.com")
    b = await _create_user(db, community, "b@example.com")
    c = await _create_user(db, community, "c@example.com")
    d = await _create_user(db, community, "d@example.com")

    await _add_vouch(db, a, b)
    await _add_vouch(db, c, d)

    result = await detect_communities(db, community.id)

    assert result["num_communities"] == 2
    assert sorted(group["size"] for group in result["communities"]) == [2, 2]
    assert {frozenset(group["members"]) for group in result["communities"]} == {
        frozenset((str(a.node_id), str(b.node_id))),
        frozenset((str(c.node_id), str(d.node_id))),
    }


@pytest.mark.asyncio
async def test_compute_centrality(db):
    community = await _create_community(db, "Centrality")
    hub = await _create_user(db, community, "hub@example.com")
    leaves = [
        await _create_user(db, community, f"leaf{i}@example.com")
        for i in range(4)
    ]

    for leaf in leaves:
        await _add_vouch(db, hub, leaf)

    result = await compute_centrality(db, community.id)

    hub_id = str(hub.node_id)
    leaf_ids = [str(leaf.node_id) for leaf in leaves]

    assert result["betweenness"][hub_id] > 0
    assert all(result["betweenness"][hub_id] > result["betweenness"][leaf_id] for leaf_id in leaf_ids)
    assert all(result["degree"][hub_id] > result["degree"][leaf_id] for leaf_id in leaf_ids)


@pytest.mark.asyncio
async def test_compute_health(db):
    community = await _create_community(db, "Health")
    a = await _create_user(db, community, "a@example.com")
    b = await _create_user(db, community, "b@example.com")
    c = await _create_user(db, community, "c@example.com")
    d = await _create_user(db, community, "d@example.com")

    await _add_vouch(db, a, b)
    await _add_vouch(db, b, c)

    result = await compute_health(db, community.id)

    assert result["total_nodes"] == 4
    assert result["total_edges"] == 2
    assert result["connected_components"] == 2
    assert result["largest_component_size"] == 3
    assert result["density"] == pytest.approx(2 / 6)
    assert result["avg_clustering"] == pytest.approx(0.0)
    assert result["isolated_nodes"] == [str(d.node_id)]


@pytest.mark.asyncio
async def test_upsert_overwrites(db):
    community = await _create_community(db, "Overwrite")

    await _upsert_analytics(db, community.id, "health", {"version": 1})
    await _upsert_analytics(db, community.id, "health", {"version": 2})

    count_result = await db.execute(select(func.count()).select_from(GraphAnalytics))
    analytics_result = await db.execute(select(GraphAnalytics))
    analytics = analytics_result.scalar_one()

    assert count_result.scalar_one() == 1
    assert analytics.results == {"version": 2}


@pytest.mark.asyncio
async def test_empty_graph(db):
    community = await _create_community(db, "Empty")

    communities = await detect_communities(db, community.id)
    centrality = await compute_centrality(db, community.id)
    health = await compute_health(db, community.id)

    assert communities == {"num_communities": 0, "communities": []}
    assert centrality == {"betweenness": {}, "degree": {}}
    assert health == {
        "total_nodes": 0,
        "total_edges": 0,
        "connected_components": 0,
        "largest_component_size": 0,
        "density": 0.0,
        "avg_clustering": 0.0,
        "isolated_nodes": [],
    }


@pytest.mark.asyncio
async def test_get_analytics_returns_none(db):
    community = await _create_community(db, "Missing")

    result = await get_analytics(db, community.id, "health")

    assert result is None
