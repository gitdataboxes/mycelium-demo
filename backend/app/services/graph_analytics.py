import logging
from datetime import datetime, timezone
from uuid import UUID

import networkx as nx
from networkx.algorithms.community import louvain_communities
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database import async_session
from app.models.community import Community
from app.models.edge import Edge, EdgeType
from app.models.graph_analytics import GraphAnalytics
from app.models.node import Node, NodeType

logger = logging.getLogger(__name__)


async def load_community_graph(db: AsyncSession, community_id: UUID) -> nx.Graph:
    """Load a community's user-level vouch graph into an undirected NetworkX graph."""
    graph = nx.Graph()

    node_result = await db.execute(
        select(Node.id).where(
            Node.community_id == community_id,
            Node.type == NodeType.USER,
        )
    )
    node_ids = [str(node_id) for node_id in node_result.scalars().all()]
    graph.add_nodes_from(node_ids)

    source_node = aliased(Node)
    target_node = aliased(Node)
    edge_result = await db.execute(
        select(Edge.source_node_id, Edge.target_node_id)
        .join(source_node, Edge.source_node_id == source_node.id)
        .join(target_node, Edge.target_node_id == target_node.id)
        .where(
            Edge.type == EdgeType.VOUCH,
            Edge.context_node_id.is_(None),
            source_node.community_id == community_id,
            target_node.community_id == community_id,
            source_node.type == NodeType.USER,
            target_node.type == NodeType.USER,
        )
    )
    graph.add_edges_from(
        (str(source_node_id), str(target_node_id))
        for source_node_id, target_node_id in edge_result.all()
    )

    return graph


async def _upsert_analytics(
    db: AsyncSession, community_id: UUID, analysis_type: str, results: dict
) -> None:
    computed_at = datetime.now(timezone.utc)
    statement = insert(GraphAnalytics).values(
        community_id=community_id,
        analysis_type=analysis_type,
        results=results,
        computed_at=computed_at,
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_analytics",
        set_={
            "results": results,
            "computed_at": computed_at,
        },
    )
    await db.execute(statement)
    await db.commit()


async def detect_communities(db: AsyncSession, community_id: UUID) -> dict:
    graph = await load_community_graph(db, community_id)
    if graph.number_of_nodes() == 0:
        result = {"num_communities": 0, "communities": []}
        await _upsert_analytics(db, community_id, "communities", result)
        return result

    partitions = [
        sorted(str(member) for member in members)
        for members in louvain_communities(graph, seed=42)
    ]
    partitions.sort(key=lambda members: (-len(members), members))

    result = {
        "num_communities": len(partitions),
        "communities": [
            {"id": index, "members": members, "size": len(members)}
            for index, members in enumerate(partitions)
        ],
    }
    await _upsert_analytics(db, community_id, "communities", result)
    return result


async def compute_centrality(db: AsyncSession, community_id: UUID) -> dict:
    graph = await load_community_graph(db, community_id)
    result = {
        "betweenness": {
            str(node_id): score for node_id, score in nx.betweenness_centrality(graph).items()
        },
        "degree": {
            str(node_id): score for node_id, score in nx.degree_centrality(graph).items()
        },
    }
    await _upsert_analytics(db, community_id, "centrality", result)
    return result


async def compute_health(db: AsyncSession, community_id: UUID) -> dict:
    graph = await load_community_graph(db, community_id)
    components = list(nx.connected_components(graph))
    total_nodes = graph.number_of_nodes()

    result = {
        "total_nodes": total_nodes,
        "total_edges": graph.number_of_edges(),
        "connected_components": len(components),
        "largest_component_size": max((len(component) for component in components), default=0),
        "density": nx.density(graph) if total_nodes > 1 else 0.0,
        "avg_clustering": nx.average_clustering(graph) if total_nodes > 0 else 0.0,
        "isolated_nodes": sorted(str(node_id) for node_id in nx.isolates(graph)),
    }
    await _upsert_analytics(db, community_id, "health", result)
    return result


async def run_all_analytics(db: AsyncSession, community_id: UUID) -> dict:
    logger.info("Running graph analytics for community %s", community_id)
    return {
        "communities": await detect_communities(db, community_id),
        "centrality": await compute_centrality(db, community_id),
        "health": await compute_health(db, community_id),
    }


async def run_analytics_all_communities(db: AsyncSession) -> None:
    result = await db.execute(select(Community.id).order_by(Community.created_at))
    for community_id in result.scalars().all():
        await run_all_analytics(db, community_id)


async def run_analytics_for_community_job(community_id: UUID) -> None:
    async with async_session() as db:
        await run_all_analytics(db, community_id)


async def run_analytics_for_all_communities_job() -> None:
    async with async_session() as db:
        await run_analytics_all_communities(db)


async def get_analytics(
    db: AsyncSession, community_id: UUID, analysis_type: str
) -> GraphAnalytics | None:
    result = await db.execute(
        select(GraphAnalytics).where(
            GraphAnalytics.community_id == community_id,
            GraphAnalytics.analysis_type == analysis_type,
        )
    )
    return result.scalar_one_or_none()
