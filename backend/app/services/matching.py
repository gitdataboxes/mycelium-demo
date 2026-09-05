import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.match import MatchHistory
from app.models.profile import AttributeDirection, MembraneEntry
from app.models.signal import Signal
from app.models.user import User
from app.services.trust import cooling_penalty, get_cooling_count, get_trust_distance

logger = logging.getLogger(__name__)


class MatchCandidate:
    def __init__(
        self,
        node_a_id: UUID,
        node_b_id: UUID,
        attr_a_id: UUID,
        attr_b_id: UUID,
        attr_a_type: str,  # "membrane" or "signal"
        attr_b_type: str,
        attr_a_content: str,
        attr_b_content: str,
        attr_a_direction: str,
        attr_b_direction: str,
        similarity: float,
    ):
        self.node_a_id = node_a_id
        self.node_b_id = node_b_id
        self.attr_a_id = attr_a_id
        self.attr_b_id = attr_b_id
        self.attr_a_type = attr_a_type
        self.attr_b_type = attr_b_type
        self.attr_a_content = attr_a_content
        self.attr_b_content = attr_b_content
        self.attr_a_direction = attr_a_direction
        self.attr_b_direction = attr_b_direction
        self.similarity = similarity
        self.trust: float = 0.1
        self.cooling: float = 1.0
        self.score: float = 0.0


async def _find_attribute_matches(db: AsyncSession) -> list[MatchCandidate]:
    """Find output->input matches across membrane entries using pgvector cosine distance."""
    threshold = settings.similarity_threshold

    query = text("""
        SELECT
            a.node_id AS node_a_id,
            b.node_id AS node_b_id,
            a.id AS attr_a_id,
            b.id AS attr_b_id,
            a.content AS attr_a_content,
            b.content AS attr_b_content,
            a.direction AS attr_a_direction,
            b.direction AS attr_b_direction,
            1 - (a.embedding <=> b.embedding) AS similarity
        FROM membrane_entries a
        CROSS JOIN membrane_entries b
        WHERE a.direction = 'output'
          AND b.direction = 'input'
          AND a.node_id != b.node_id
          AND a.embedding IS NOT NULL
          AND b.embedding IS NOT NULL
          AND (1 - (a.embedding <=> b.embedding)) > :threshold
        ORDER BY similarity DESC
        LIMIT 500
    """)

    result = await db.execute(query, {"threshold": threshold})
    rows = result.all()

    return [
        MatchCandidate(
            node_a_id=row.node_a_id,
            node_b_id=row.node_b_id,
            attr_a_id=row.attr_a_id,
            attr_b_id=row.attr_b_id,
            attr_a_type="membrane",
            attr_b_type="membrane",
            attr_a_content=row.attr_a_content,
            attr_b_content=row.attr_b_content,
            attr_a_direction=row.attr_a_direction,
            attr_b_direction=row.attr_b_direction,
            similarity=float(row.similarity),
        )
        for row in rows
    ]


async def _find_signal_matches(db: AsyncSession) -> list[MatchCandidate]:
    """Find matches involving signals (signal<->attribute and signal<->signal)."""
    threshold = settings.similarity_threshold
    now = datetime.now(timezone.utc)

    query = text("""
        SELECT
            s.node_id AS node_a_id,
            a.node_id AS node_b_id,
            s.id AS attr_a_id,
            a.id AS attr_b_id,
            s.content AS attr_a_content,
            a.content AS attr_b_content,
            s.direction AS attr_a_direction,
            a.direction AS attr_b_direction,
            1 - (s.embedding <=> a.embedding) AS similarity,
            'signal' AS attr_a_type,
            'membrane' AS attr_b_type
        FROM signals s
        CROSS JOIN membrane_entries a
        WHERE s.direction = 'output'
          AND a.direction = 'input'
          AND s.node_id != a.node_id
          AND s.embedding IS NOT NULL
          AND a.embedding IS NOT NULL
          AND (s.expires_at IS NULL OR s.expires_at > :now)
          AND (1 - (s.embedding <=> a.embedding)) > :threshold

        UNION ALL

        SELECT
            a.node_id AS node_a_id,
            s.node_id AS node_b_id,
            a.id AS attr_a_id,
            s.id AS attr_b_id,
            a.content AS attr_a_content,
            s.content AS attr_b_content,
            a.direction AS attr_a_direction,
            s.direction AS attr_b_direction,
            1 - (a.embedding <=> s.embedding) AS similarity,
            'membrane' AS attr_a_type,
            'signal' AS attr_b_type
        FROM membrane_entries a
        CROSS JOIN signals s
        WHERE a.direction = 'output'
          AND s.direction = 'input'
          AND a.node_id != s.node_id
          AND a.embedding IS NOT NULL
          AND s.embedding IS NOT NULL
          AND (s.expires_at IS NULL OR s.expires_at > :now)
          AND (1 - (a.embedding <=> s.embedding)) > :threshold

        UNION ALL

        SELECT
            s1.node_id AS node_a_id,
            s2.node_id AS node_b_id,
            s1.id AS attr_a_id,
            s2.id AS attr_b_id,
            s1.content AS attr_a_content,
            s2.content AS attr_b_content,
            s1.direction AS attr_a_direction,
            s2.direction AS attr_b_direction,
            1 - (s1.embedding <=> s2.embedding) AS similarity,
            'signal' AS attr_a_type,
            'signal' AS attr_b_type
        FROM signals s1
        CROSS JOIN signals s2
        WHERE s1.direction = 'output'
          AND s2.direction = 'input'
          AND s1.node_id != s2.node_id
          AND s1.embedding IS NOT NULL
          AND s2.embedding IS NOT NULL
          AND (s1.expires_at IS NULL OR s1.expires_at > :now)
          AND (s2.expires_at IS NULL OR s2.expires_at > :now)
          AND (1 - (s1.embedding <=> s2.embedding)) > :threshold

        ORDER BY similarity DESC
        LIMIT 500
    """)

    result = await db.execute(query, {"threshold": threshold, "now": now})
    rows = result.all()

    return [
        MatchCandidate(
            node_a_id=row.node_a_id,
            node_b_id=row.node_b_id,
            attr_a_id=row.attr_a_id,
            attr_b_id=row.attr_b_id,
            attr_a_type=row.attr_a_type,
            attr_b_type=row.attr_b_type,
            attr_a_content=row.attr_a_content,
            attr_b_content=row.attr_b_content,
            attr_a_direction=row.attr_a_direction,
            attr_b_direction=row.attr_b_direction,
            similarity=float(row.similarity),
        )
        for row in rows
    ]


async def _get_recent_match_pairs(db: AsyncSession) -> set[tuple[UUID, UUID, UUID, UUID]]:
    """Get (node_a, node_b, attr_a, attr_b) tuples from recent match history for dedup."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.match_dedup_days)
    result = await db.execute(
        select(
            MatchHistory.node_a_id,
            MatchHistory.node_b_id,
            MatchHistory.attribute_a_id,
            MatchHistory.attribute_b_id,
        ).where(MatchHistory.digest_sent_at > cutoff)
    )
    return {(r[0], r[1], r[2], r[3]) for r in result.all()}


async def run_matching(db: AsyncSession) -> dict[UUID, list[MatchCandidate]]:
    """Run the full matching pipeline. Returns matches grouped by recipient node."""
    logger.info("Starting matching run")

    # 1. Gather all candidates
    attr_matches = await _find_attribute_matches(db)
    signal_matches = await _find_signal_matches(db)
    all_candidates = attr_matches + signal_matches
    logger.info("Found %d raw candidates", len(all_candidates))

    if not all_candidates:
        return {}

    # 2. Deduplicate against recent history
    recent = await _get_recent_match_pairs(db)
    candidates = [
        c for c in all_candidates
        if (c.node_a_id, c.node_b_id, c.attr_a_id, c.attr_b_id) not in recent
    ]
    logger.info("%d candidates after dedup", len(candidates))

    if not candidates:
        return {}

    # 3. Score with trust + cooling
    trust_cache: dict[tuple[UUID, UUID], int | None] = {}
    cooling_cache: dict[UUID, int] = {}

    for c in candidates:
        for pair in [(c.node_a_id, c.node_b_id), (c.node_b_id, c.node_a_id)]:
            if pair not in trust_cache:
                trust_cache[pair] = await get_trust_distance(db, pair[0], pair[1])

        dist = trust_cache.get((c.node_a_id, c.node_b_id))
        from app.services.trust import trust_score
        c.trust = trust_score(dist)

        for nid in [c.node_a_id, c.node_b_id]:
            if nid not in cooling_cache:
                cooling_cache[nid] = await get_cooling_count(db, nid)

        c.cooling = min(
            cooling_penalty(cooling_cache[c.node_a_id]),
            cooling_penalty(cooling_cache[c.node_b_id]),
        )

        c.score = c.similarity * c.trust * c.cooling

    # 4. Filter out zero-score matches
    candidates = [c for c in candidates if c.score > 0.01]

    # 5. Group by recipient and cap
    by_node: dict[UUID, list[MatchCandidate]] = defaultdict(list)
    for c in candidates:
        by_node[c.node_a_id].append(c)
        by_node[c.node_b_id].append(c)

    max_per_user = settings.max_matches_per_digest
    for nid in by_node:
        by_node[nid].sort(key=lambda m: m.score, reverse=True)
        by_node[nid] = by_node[nid][:max_per_user]

    # 6. Record matches to history
    seen = set()
    for nid, matches in by_node.items():
        for m in matches:
            key = (m.node_a_id, m.node_b_id, m.attr_a_id, m.attr_b_id)
            if key not in seen:
                seen.add(key)
                db.add(MatchHistory(
                    node_a_id=m.node_a_id,
                    node_b_id=m.node_b_id,
                    attribute_a_id=m.attr_a_id,
                    attribute_b_id=m.attr_b_id,
                    attribute_a_type=m.attr_a_type,
                    attribute_b_type=m.attr_b_type,
                    similarity=m.similarity,
                ))

    await db.commit()
    logger.info("Matching complete: %d nodes with matches", len(by_node))
    return dict(by_node)
