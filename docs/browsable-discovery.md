# Browsable Discovery — Implementation Spec

## What This Is

The browsable discovery layer is how community members find organizations and events. It's the "campfire" metaphor: you can see gatherings from a distance, and the ones closer to you in the trust network appear brighter. Users are NOT browsable — you encounter people through orgs, events, and digest matches.

Currently, the `/api/organizations` and `/api/events` endpoints return flat lists with optional text search. This spec adds **graph-proximity ordering** and **cooling-aware filtering** so that results are personalized to the requesting user's position in the network.

## What Exists Today

### Backend

- **Organization endpoints** (`backend/app/routers/organization.py`):
  - `GET /api/organizations?search=` — returns all orgs in the user's community, filtered by name search
  - Uses `services/organization.py` → `list_organizations()` which does a simple `ilike` query

- **Event endpoints** (`backend/app/routers/event.py`):
  - `GET /api/events?search=&upcoming=` — returns all events, optional text search and upcoming filter
  - Uses `services/event.py` → `list_events()` which does `ilike` + optional `ends_at > now()` filter

- **Trust service** (`backend/app/services/trust.py`):
  - `get_trust_distance()` — BFS pathfinding between two nodes (loads all vouch edges into Python, builds adjacency list, walks the graph). Works but doesn't scale to batch queries (one call per pair).

- **Edges table** (`backend/app/models/edge.py`):
  - Unified edges with types: vouch, cool, block, report, member, participant, host
  - `context_node_id` scopes vouches to orgs/events
  - Community-level vouches have `context_node_id IS NULL`

### Frontend

- `/organizations` page — cards with search, shows name/description/member count/membership badge
- `/events` page — cards with search + upcoming toggle, shows title/description/time/location/participant count

### Data Model (docs/data-model.md)

The data model doc already contains the SQL query patterns for graph-proximity discovery. See the "Graph Query Patterns" section — it has ready-to-use recursive CTEs for trust path discovery, graph-proximity ordering, cooling-aware filtering, and trust-weighted matching.

## What Needs to Be Built

### 1. Discovery Service (`backend/app/services/discovery.py`)

A new service that replaces the simple list queries with graph-aware discovery. Core function:

```python
async def discover(
    db: AsyncSession,
    user_node_id: UUID,
    community_id: UUID,
    node_types: list[str],          # ['organization', 'event'] or just one
    search: str | None = None,
    upcoming_only: bool = False,    # events only: filter to ends_at > now
    max_depth: int = 3,             # how far to walk the vouch graph
    limit: int = 50,
    offset: int = 0,                # cursor-based pagination can replace this later
) -> tuple[list[DiscoveryResult], int]:  # (results, total_count)
```

This function should:

1. **Walk the vouch graph** from the requesting user using a recursive CTE (NOT the Python BFS in `trust.py`). The CTE pattern is in `docs/data-model.md` under "Trust Path Discovery". Use community-level vouches only (`context_node_id IS NULL`).

2. **Join reachable user nodes to orgs/events** through membership/participation edges. An org is "close" to you if its members are close to you in the vouch graph. Specifically: find the minimum graph distance from the requesting user to any member/participant of each org/event.

3. **Apply cooling as exclusion only** (not dampening). If the user has directly cooled an org or event node, exclude it from results. Cooling of individual *members* of an org/event does NOT affect the org/event's visibility — cooling is personal and scoped to the cooled node, not transitive. Keep it simple: `NOT EXISTS (SELECT 1 FROM edges WHERE source_node_id = :user_id AND target_node_id = n.id AND type = 'cool')`.

4. **Apply text search early**. If a search string is provided, filter by `ilike` on org name / event title + description BEFORE joining with the trust_reach CTE. This means the CTE result set joins against an already-filtered candidate set, not the full table. Structure the query so the text filter is in a CTE or subquery that feeds into the proximity join:

    ```sql
    WITH candidates AS (
        SELECT n.id, n.type, org.name, ev.title, ...
        FROM nodes n
        LEFT JOIN organizations org ON ...
        LEFT JOIN events ev ON ...
        WHERE n.community_id = :community_id
          AND n.type IN ('organization', 'event')
          AND (org.name ILIKE :search OR ev.title ILIKE :search OR ev.description ILIKE :search)
    ),
    trust_reach AS ( ... ),
    ...
    ```

5. **Apply upcoming filter** for events (ends_at IS NULL OR ends_at > now). Also apply early, in the candidates CTE.

6. **Order results** by graph distance (ascending), then by created_at (descending). Orgs/events with no reachable members should appear last (they're the distant campfires), not be excluded entirely.

The return type should include `graph_distance: int | None` so the frontend can use it for visual treatment. Keep it as `int` — cooling doesn't adjust distance, it's binary exclusion. Distance stays a clean hop count.

### 2. Key Implementation Detail: Graph Distance to Orgs/Events

The tricky part: the vouch graph connects *users*. But we're ranking *orgs and events*. The bridge is membership/participation edges:

```sql
-- After computing trust_reach (user nodes reachable from requesting user),
-- find how close each org/event is:
SELECT
    n.id AS node_id,
    n.type,
    MIN(tr.depth) AS graph_distance  -- closest member's distance
FROM nodes n
JOIN edges membership ON membership.target_node_id = n.id
    AND membership.type IN ('member', 'participant')
JOIN trust_reach tr ON tr.node_id = membership.source_node_id
WHERE n.type IN ('organization', 'event')
GROUP BY n.id, n.type
```

This gives the minimum vouch-graph distance between the requesting user and any member/participant of each org/event. An org where your direct vouch is a member gets distance=1. An org where only a friend-of-a-friend is a member gets distance=2.

For orgs/events with NO reachable members, use a LEFT JOIN variant and COALESCE the distance to a high value (e.g., 999) so they sort last but still appear.

### 3. Update Existing Routers

Replace the current list queries in `organization.py` and `event.py` routers to use the discovery service. The endpoints stay the same, but results are now ordered by graph proximity. Add `graph_distance` to the response schemas.

### 4. Update Response Schemas

Add to `OrgResponse` and `EventResponse`:
```python
graph_distance: int | None = None  # null = no reachable members (distant campfire)
```

### 5. Frontend Changes

The current org/event list pages should:

- **Sort by graph distance** (already handled server-side, just render in order)
- **Visual proximity indicator** — subtle treatment showing how "close" an org/event is. Could be as simple as showing "1 hop", "2 hops", "distant" or a fading opacity. Don't over-design this.
- **"Distant" section** — orgs/events with no reachable members could be grouped under a "Discover" or "Beyond your network" divider at the bottom of the list.

### 6. Home Page: Upcoming Events Preview

Add an "Upcoming Events" section to the home page (`frontend/src/app/page.tsx`) showing the next 3-5 events, ordered by graph proximity, then by start time. This gives the community calendar feel without a separate calendar page (which can come later). Use the same discovery endpoint with `upcoming=true&limit=5`.

## Pagination

The `discover()` function accepts `limit` and `offset` and returns `(results, total_count)`. This is simple offset pagination — sufficient for communities of hundreds to low thousands of nodes. If the community grows large enough for this to matter, switch to cursor-based pagination keyed on `(graph_distance, created_at, node_id)`. Don't build cursor pagination now.

The routers should pass `limit` and `offset` query params through to the discovery service. The list response schemas already have a `total` field.

## What NOT to Build Yet

- **Semantic matching in discovery** (embedding similarity combined with graph distance). The data model doc has the query pattern for this (`trust_reach + pgvector`), but it requires a search query to embed. Save this for Phase 2 when the LLM chat interface can generate those queries.
- **Calendar view**. The list view with upcoming filter is sufficient for now.
- **NetworkX analytics integration**. Community detection / centrality can enhance discovery later but isn't needed for the initial graph-proximity ordering.
- **Cooling dampening / decay in discovery**. Cooling is binary exclusion for now (cooled node = hidden from your view). The time-decay sigmoid in the data model doc is available if we want softer cooling later, but it adds query complexity for marginal UX benefit at this stage.

## Files to Create/Modify

**Create:**
- `backend/app/services/discovery.py` — the graph-proximity discovery service

**Modify:**
- `backend/app/routers/organization.py` — use discovery service for list endpoint
- `backend/app/routers/event.py` — use discovery service for list endpoint
- `backend/app/schemas/organization.py` — add `graph_distance` to OrgResponse
- `backend/app/schemas/event.py` — add `graph_distance` to EventResponse
- `frontend/src/lib/api.ts` — add `graph_distance` to OrgInfo and EventInfo types
- `frontend/src/app/organizations/page.tsx` — render proximity indicator, distant section
- `frontend/src/app/events/page.tsx` — render proximity indicator, distant section
- `frontend/src/app/page.tsx` — add upcoming events preview section

## Reference

- `docs/data-model.md` — contains the SQL recursive CTE patterns, cooling-aware filtering, and graph-proximity ordering queries
- `backend/app/services/trust.py` — existing BFS trust distance (Python-based, reference for logic but should NOT be reused for batch discovery — use SQL CTEs instead)
- `backend/app/models/edge.py` — Edge model with EdgeType enum
- `backend/app/models/node.py` — Node model with NodeType enum

## Testing Approach

Use a pytest fixture (in `backend/tests/conftest.py` or a dedicated `backend/tests/test_discovery.py`) that builds the test graph programmatically using the existing service functions. The project uses async SQLAlchemy, so fixtures should use `@pytest.fixture` with the async test DB session.

### Test Fixture: Seed Graph

```python
# Build this graph:
#   alice --vouch--> bob --vouch--> carol --vouch--> dave
#   alice --vouch--> eve
#
#   org_close:    members = [bob]           → distance 1 from alice
#   org_medium:   members = [carol]         → distance 2 from alice
#   org_far:      members = [dave]          → distance 3 from alice
#   org_isolated: members = [frank]         → no path from alice (frank has no vouches)
#   evt_close:    participants = [eve]      → distance 1 from alice
#   evt_cooled:   participants = [bob]      → distance 1, but alice cooled this event
#
# Use create_organization(), create_event(), vouch_into_org(), etc.
# from the existing service layer — don't insert raw SQL.
```

### Test Cases

1. **Proximity ordering**: `discover(alice)` returns org_close before org_medium before org_far. org_isolated appears last with `graph_distance=None`.
2. **Cooling exclusion**: `discover(alice)` does NOT return evt_cooled (alice cooled the event node directly).
3. **Cooling scoping**: Alice cools bob. org_close (where bob is a member) still appears — cooling bob doesn't hide the org, only the bob node.
4. **Text search + proximity**: `discover(alice, search="close")` returns only matching results, still ordered by distance.
5. **Upcoming filter**: Events with `ends_at` in the past are excluded when `upcoming_only=True`. Events with `ends_at=None` are included.
6. **Pagination**: `discover(alice, limit=2, offset=0)` returns first 2, `discover(alice, limit=2, offset=2)` returns next 2. `total_count` reflects the full untruncated count.
7. **No reachable members**: org_isolated gets `graph_distance=None` and sorts after all distance-bearing results.
8. **Self-membership**: If alice is a member of org_x, org_x gets `graph_distance=0`.
