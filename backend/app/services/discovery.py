import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    node_id: UUID
    node_type: str
    graph_distance: int | None


async def discover(
    db: AsyncSession,
    user_node_id: UUID,
    community_id: UUID,
    node_types: list[str],
    search: str | None = None,
    upcoming_only: bool = False,
    max_depth: int = 3,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[DiscoveryResult], int]:
    """
    Graph-proximity discovery for organizations and events.

    Walks the vouch graph from the requesting user via recursive CTE,
    then ranks orgs/events by minimum graph distance to any member/participant.
    Cooled nodes are excluded. Unconnected nodes sort last.
    """
    allowed = {"organization", "event"}
    types = [t for t in node_types if t in allowed]
    if not types:
        return [], 0
    type_literals = ", ".join(f"'{t}'" for t in types)

    search_clause = ""
    if search:
        search_clause = """
            AND (
                org.name ILIKE '%' || :search || '%'
                OR ev.title ILIKE '%' || :search || '%'
                OR ev.description ILIKE '%' || :search || '%'
            )"""

    upcoming_clause = ""
    if upcoming_only:
        upcoming_clause = (
            "AND (n.type != 'event' OR ev.ends_at IS NULL OR ev.ends_at > NOW())"
        )

    sql = f"""
    WITH RECURSIVE trust_reach AS (
        -- Seed: the requesting user at depth 0
        SELECT CAST(:user_id AS uuid) AS node_id, 0 AS depth,
               ARRAY[CAST(:user_id AS uuid)] AS path
        UNION ALL
        -- Walk vouch edges bidirectionally (vouching is mutual)
        SELECT
            CASE WHEN e.source_node_id = tr.node_id
                 THEN e.target_node_id
                 ELSE e.source_node_id END,
            tr.depth + 1,
            tr.path || CASE WHEN e.source_node_id = tr.node_id
                            THEN e.target_node_id
                            ELSE e.source_node_id END
        FROM edges e
        JOIN trust_reach tr
            ON e.source_node_id = tr.node_id OR e.target_node_id = tr.node_id
        WHERE e.type = 'vouch'
          AND e.context_node_id IS NULL
          AND CASE WHEN e.source_node_id = tr.node_id
                   THEN e.target_node_id
                   ELSE e.source_node_id END != ALL(tr.path)
          AND tr.depth < :max_depth
    ),
    reachable AS (
        SELECT node_id, MIN(depth) AS distance
        FROM trust_reach
        GROUP BY node_id
    ),
    candidates AS (
        SELECT n.id AS node_id, n.type AS node_type, n.created_at
        FROM nodes n
        LEFT JOIN organizations org ON org.node_id = n.id
        LEFT JOIN events ev ON ev.node_id = n.id
        WHERE n.community_id = :community_id
          AND n.type IN ({type_literals})
          AND NOT EXISTS (
              SELECT 1 FROM edges
              WHERE source_node_id = :user_id
                AND target_node_id = n.id
                AND type = 'cool'
          )
          {search_clause}
          {upcoming_clause}
    ),
    ranked AS (
        SELECT
            c.node_id,
            c.node_type,
            c.created_at,
            MIN(r.distance) AS graph_distance
        FROM candidates c
        LEFT JOIN edges membership
            ON membership.target_node_id = c.node_id
            AND membership.type IN ('member', 'participant')
        LEFT JOIN reachable r ON r.node_id = membership.source_node_id
        GROUP BY c.node_id, c.node_type, c.created_at
    )
    SELECT
        node_id,
        node_type,
        graph_distance,
        COUNT(*) OVER() AS total_count
    FROM ranked
    ORDER BY
        COALESCE(graph_distance, 999) ASC,
        created_at DESC
    LIMIT :limit OFFSET :offset
    """

    params: dict = {
        "user_id": user_node_id,
        "community_id": community_id,
        "max_depth": max_depth,
        "limit": limit,
        "offset": offset,
    }
    if search:
        params["search"] = search

    result = await db.execute(text(sql), params)
    rows = result.all()

    if not rows:
        return [], 0

    total = rows[0].total_count
    results = [
        DiscoveryResult(
            node_id=row.node_id,
            node_type=row.node_type,
            graph_distance=row.graph_distance,
        )
        for row in rows
    ]

    return results, total
