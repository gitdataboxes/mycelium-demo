import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.edge import Edge, EdgeType
from app.models.node import Node
from app.models.user import User
from app.schemas.graph_analytics import (
    CentralityResult,
    CommunityDetectionResult,
    HealthResult,
)
from app.services.graph_analytics import get_analytics

router = APIRouter()


async def _require_community_access(
    db: AsyncSession, user: User, community_id: uuid.UUID
) -> None:
    if user.node.community_id == community_id:
        return

    result = await db.execute(
        select(Node.id)
        .join(Edge, Edge.target_node_id == Node.id)
        .where(
            Edge.source_node_id == user.node_id,
            Edge.type.in_([EdgeType.MEMBER, EdgeType.PARTICIPANT, EdgeType.RESPONDER]),
            Node.community_id == community_id,
        )
        .limit(1)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this community",
        )


async def _get_cached_analytics_or_404(
    db: AsyncSession, community_id: uuid.UUID, analysis_type: str
):
    analytics = await get_analytics(db, community_id, analysis_type)
    if analytics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analytics not found for this community",
        )
    return analytics


@router.get("/communities", response_model=CommunityDetectionResult)
async def get_community_detection(
    community_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_community_access(db, user, community_id)
    analytics = await _get_cached_analytics_or_404(db, community_id, "communities")
    return CommunityDetectionResult(computed_at=analytics.computed_at, **analytics.results)


@router.get("/centrality", response_model=CentralityResult)
async def get_centrality(
    community_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_community_access(db, user, community_id)
    analytics = await _get_cached_analytics_or_404(db, community_id, "centrality")
    return CentralityResult(computed_at=analytics.computed_at, **analytics.results)


@router.get("/health", response_model=HealthResult)
async def get_health(
    community_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_community_access(db, user, community_id)
    analytics = await _get_cached_analytics_or_404(db, community_id, "health")
    return HealthResult(computed_at=analytics.computed_at, **analytics.results)
