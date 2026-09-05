# Mycelium Data Model

## Design Principles

The data model follows a **fractal node pattern** -- simple, reusable structures that build emergent complexity. Users, Organizations, and Events are all **nodes** with the same fundamental shape: a membrane (inputs/outputs), signals (ephemeral intent), and relationships (edges to other nodes). The same trust pattern (vouch-gated entry) repeats at every scale.

## Entity Overview

```
Community
 └── Node (User | Organization | Event)
       ├── Membrane Entries (persistent inputs/outputs)
       ├── Signals (ephemeral, time-bound intent)
       └── Edges (relationships to other nodes)
```

**Community** -- the deployment-level container. Each self-hosted instance is a community. Holds the code of conduct and community-level configuration.

**Node** -- the shared abstraction. Every participant in the system (person, group, gathering) is a node with a type discriminator. Type-specific data lives in extension tables.

**Membrane Entry** -- a persistent input (what a node seeks) or output (what a node offers). Free-text content with a vector embedding for semantic matching.

**Signal** -- an ephemeral expression of intent with a natural expiration. Same input/output direction as membrane entries, but time-bound.

**Edge** -- a directional relationship between nodes. Covers the full spectrum: vouch, cool, block, report, member, participant, host. An optional context reference scopes an edge to a specific node (e.g. "vouch for this user *in the context of* this organization").

**Message** -- platform-mediated direct messaging between users for brokered introductions.

---

## Schema

### Community

The top-level container. One per deployment.

```sql
CREATE TABLE communities (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    description     text,
    code_of_conduct text,                   -- markdown
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
```

### Nodes

The shared base for all entity types.

```sql
CREATE TYPE node_type AS ENUM ('user', 'organization', 'event');

CREATE TABLE nodes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id    uuid NOT NULL REFERENCES communities(id),
    type            node_type NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_nodes_community ON nodes(community_id);
CREATE INDEX idx_nodes_type ON nodes(community_id, type);
```

### Type Extensions

Each node type has a table for type-specific fields. The `node_id` is both the primary key and a foreign key to `nodes`.

```sql
-- Users: individual community members
CREATE TYPE notification_pref AS ENUM ('instant', 'batched');

CREATE TABLE users (
    node_id             uuid PRIMARY KEY REFERENCES nodes(id),
    email               text NOT NULL,
    username            text,
    name                text,
    notification_pref   notification_pref NOT NULL DEFAULT 'batched',
    is_active           boolean NOT NULL DEFAULT false,

    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT uq_users_username UNIQUE (username)
);

-- Organizations: group nodes with vouch-gated membership
CREATE TABLE organizations (
    node_id     uuid PRIMARY KEY REFERENCES nodes(id),
    name        text NOT NULL,
    description text
);

-- Events: time-bound gatherings
CREATE TYPE event_urgency AS ENUM ('standard', 'spontaneous');

CREATE TABLE events (
    node_id     uuid PRIMARY KEY REFERENCES nodes(id),
    title       text NOT NULL,
    description text,
    location    text,
    starts_at   timestamptz,
    ends_at     timestamptz,
    urgency     event_urgency NOT NULL DEFAULT 'standard'
);
```

### Auth

Magic-link authentication (existing pattern, now references nodes).

```sql
CREATE TABLE magic_link_tokens (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES users(node_id),
    token_hash  text NOT NULL,
    expires_at  timestamptz NOT NULL,
    used        boolean NOT NULL DEFAULT false
);

CREATE INDEX idx_magic_link_token_hash ON magic_link_tokens(token_hash);

CREATE TABLE sessions (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES users(node_id),
    expires_at  timestamptz NOT NULL
);
```

### Membrane Entries

Persistent inputs and outputs. Shared across all node types.

```sql
CREATE TYPE attribute_direction AS ENUM ('input', 'output');

CREATE TABLE membrane_entries (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id     uuid NOT NULL REFERENCES nodes(id),
    direction   attribute_direction NOT NULL,
    content     text NOT NULL,
    embedding   vector(1024),               -- voyage-context-3
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_membrane_node ON membrane_entries(node_id);
```

### Signals

Ephemeral, time-bound intent.

```sql
CREATE TABLE signals (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id     uuid NOT NULL REFERENCES nodes(id),
    direction   attribute_direction NOT NULL,
    content     text NOT NULL,
    embedding   vector(1024),
    expires_at  timestamptz,                -- null = default decay applies
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_signals_node ON signals(node_id);
CREATE INDEX idx_signals_expires ON signals(expires_at);
```

### Edges

All node-to-node relationships. The `context_node_id` scopes relationship actions to a specific node (e.g. vouching someone into an organization or event).

```sql
CREATE TYPE edge_type AS ENUM (
    'vouch',        -- trust endorsement
    'cool',         -- personal distance (visibility reduction)
    'block',        -- message wall
    'report',       -- flag for community review
    'member',       -- user belongs to organization
    'participant',  -- user attending event
    'host'          -- organization hosting event
);

CREATE TABLE edges (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id      uuid NOT NULL REFERENCES nodes(id),
    target_node_id      uuid NOT NULL REFERENCES nodes(id),
    type                edge_type NOT NULL,
    context_node_id     uuid REFERENCES nodes(id),  -- optional: scopes vouch to an org/event
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_edge UNIQUE (source_node_id, target_node_id, type, context_node_id)
);

CREATE INDEX idx_edges_source ON edges(source_node_id);
CREATE INDEX idx_edges_target ON edges(target_node_id);
CREATE INDEX idx_edges_type ON edges(type);
CREATE INDEX idx_edges_context ON edges(context_node_id) WHERE context_node_id IS NOT NULL;
```

### Messages

Minimal brokered messaging for introductions.

```sql
CREATE TABLE messages (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_user   uuid NOT NULL REFERENCES users(node_id),
    to_user     uuid NOT NULL REFERENCES users(node_id),
    content     text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    read_at     timestamptz
);

CREATE INDEX idx_messages_to ON messages(to_user, created_at);
```

### Match History

Records connections surfaced by the matching engine for digest delivery.

```sql
CREATE TABLE match_history (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    node_a_id       uuid NOT NULL REFERENCES nodes(id),
    node_b_id       uuid NOT NULL REFERENCES nodes(id),
    attribute_a_id  uuid NOT NULL,
    attribute_b_id  uuid NOT NULL,
    attribute_a_type text NOT NULL,         -- 'membrane' or 'signal'
    attribute_b_type text NOT NULL,
    similarity      float NOT NULL,
    digest_sent_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_match_history_nodes ON match_history(node_a_id, node_b_id);
```

---

## Decay Mechanics

Decay is a **computed behavior**, not stored state. Timestamps drive all decay calculations at query time.

**Vouch rate-limiting:** A user's available vouches are determined by counting vouches issued within a rolling time window. The same decay rate applies regardless of context (community, organization, or event vouching).

**Cooling decay:** Cooling strength is a function of `(now - updated_at)`. A cooling that hasn't been reinforced gradually fades. If a user re-cools someone, `updated_at` resets and the cooling is fresh. No stored strength value -- the passage of time *is* the decay.

**Signal expiration:** Signals with an explicit `expires_at` expire on that date. Signals with `expires_at = null` are subject to a default decay window (configurable per community). Expired signals are excluded from matching but retained for history.

---

## Relationship Semantics

The relationship action spectrum, from trust to intervention:

| Action | Effect | Reversible |
|--------|--------|------------|
| **Vouch** | Endorses a node into a trust boundary | Yes (withdrawal) |
| **Cool** | Reduces visibility of target *to the source only* | Yes (remove) |
| **Block** | Prevents target from messaging source | Yes (remove) |
| **Report** | Flags target for community review | N/A |

Cooling is **localized and personal**. If Alice cools Bob, only Alice sees less of Bob. If everyone cools Bob, Bob becomes naturally invisible -- but no algorithm computes a "coolness score." The network topology reshapes around friction organically.

Vouch withdrawal severs the target's access to the trust boundary where the vouch was issued. At the community level, this is the "immune response" -- loss of all community vouches removes network access entirely.

---

## Browsability

| Entity | Browsable | Discovery |
|--------|-----------|-----------|
| User | No | Encountered through events, orgs, and digest matches |
| Organization | Yes | Search, cards, browsable listing |
| Event | Yes | Search, cards, community calendar, upcoming list |

---

## Graph Query Patterns

The graph is queried at two layers: **real-time traversal** via Postgres recursive CTEs (integrated with pgvector in a single query plan) and **periodic analytics** via NetworkX (in-memory Python, run as background tasks).

### Layer 1: Recursive CTEs (Real-Time)

For hot-path queries where graph distance and embedding similarity need to combine in a single SQL query.

#### Trust Path Discovery

Find all nodes reachable within N hops through the vouch graph from a given user:

```sql
WITH RECURSIVE trust_reach AS (
    -- Direct vouches (depth 1)
    SELECT target_node_id AS node_id, 1 AS depth,
           ARRAY[source_node_id, target_node_id] AS path
    FROM edges
    WHERE source_node_id = :user_id
      AND type = 'vouch'
      AND context_node_id IS NULL  -- community-level vouches

    UNION ALL

    -- Transitive vouches (depth 2..N)
    SELECT e.target_node_id, tr.depth + 1,
           tr.path || e.target_node_id
    FROM edges e
    JOIN trust_reach tr ON e.source_node_id = tr.node_id
    WHERE e.type = 'vouch'
      AND e.context_node_id IS NULL
      AND e.target_node_id != ALL(tr.path)  -- cycle detection
      AND tr.depth < :max_depth              -- depth limit
)
SELECT node_id, MIN(depth) AS shortest_distance
FROM trust_reach
GROUP BY node_id;
```

#### Trust-Weighted Matching

Combine embedding similarity with graph proximity for discovering events near you in the network. Nodes closer in the vouch graph and more semantically relevant score higher:

```sql
WITH RECURSIVE trust_reach AS (
    SELECT target_node_id AS node_id, 1 AS depth,
           ARRAY[source_node_id, target_node_id] AS path
    FROM edges
    WHERE source_node_id = :user_id AND type = 'vouch'
      AND context_node_id IS NULL
    UNION ALL
    SELECT e.target_node_id, tr.depth + 1, tr.path || e.target_node_id
    FROM edges e JOIN trust_reach tr ON e.source_node_id = tr.node_id
    WHERE e.type = 'vouch' AND e.context_node_id IS NULL
      AND e.target_node_id != ALL(tr.path) AND tr.depth < :max_depth
),
reachable_nodes AS (
    SELECT node_id, MIN(depth) AS graph_distance
    FROM trust_reach GROUP BY node_id
)
SELECT
    n.id,
    ev.title,
    me.content,
    1 - (me.embedding <=> :query_embedding) AS similarity,
    rn.graph_distance,
    -- Combined score: weighted blend of semantic similarity and graph proximity
    (:similarity_weight * (1 - (me.embedding <=> :query_embedding))
     + :proximity_weight * (1.0 / rn.graph_distance)) AS combined_score
FROM nodes n
JOIN events ev ON ev.node_id = n.id
JOIN membrane_entries me ON me.node_id = n.id
JOIN reachable_nodes rn ON rn.node_id = n.id
WHERE n.type = 'event'
  -- Exclude events the user has cooled
  AND NOT EXISTS (
      SELECT 1 FROM edges cool
      WHERE cool.source_node_id = :user_id
        AND cool.target_node_id = n.id
        AND cool.type = 'cool'
  )
ORDER BY combined_score DESC
LIMIT :limit;
```

#### Graph-Proximity Discovery

Order browsable orgs and events by closeness in the vouch network -- campfires nearer to you appear brighter:

```sql
WITH RECURSIVE trust_reach AS (
    -- ... same CTE as above ...
),
reachable_nodes AS (
    SELECT node_id, MIN(depth) AS graph_distance
    FROM trust_reach GROUP BY node_id
)
SELECT n.id, n.type,
       COALESCE(org.name, ev.title) AS display_name,
       rn.graph_distance
FROM nodes n
LEFT JOIN organizations org ON org.node_id = n.id
LEFT JOIN events ev ON ev.node_id = n.id
JOIN reachable_nodes rn ON rn.node_id = n.id
WHERE n.type IN ('organization', 'event')
ORDER BY rn.graph_distance ASC, n.created_at DESC;
```

#### Cooling-Aware Filtering

Cooling is applied as a filter or dampening factor in all queries. Since cooling is localized, it only affects the querying user's view:

```sql
-- As a filter (hard exclusion):
WHERE NOT EXISTS (
    SELECT 1 FROM edges
    WHERE source_node_id = :user_id
      AND target_node_id = n.id
      AND type = 'cool'
)

-- As a dampening factor (soft reduction, with time decay):
LEFT JOIN edges cool ON cool.source_node_id = :user_id
    AND cool.target_node_id = n.id AND cool.type = 'cool'
...
ORDER BY combined_score * CASE
    WHEN cool.id IS NULL THEN 1.0
    -- Cooling decays over time: full effect at 0 days, half at 30 days
    ELSE 1.0 / (1.0 + EXP(-EXTRACT(EPOCH FROM (now() - cool.updated_at)) / 2592000))
END DESC;
```

### Layer 2: NetworkX (Periodic Analytics)

For graph algorithms that don't need real-time results. Run as background tasks, cache results to Postgres.

#### Graph Analytics Cache Table

```sql
CREATE TABLE graph_analytics (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id    uuid NOT NULL REFERENCES communities(id),
    analysis_type   text NOT NULL,          -- 'communities', 'centrality', 'health'
    results         jsonb NOT NULL,
    computed_at     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_analytics UNIQUE (community_id, analysis_type)
);
```

#### Community Detection

Identifies emergent subgroups within the network using the Louvain algorithm:

```python
import networkx as nx
from networkx.algorithms.community import louvain_communities

async def detect_communities(db, community_id: uuid.UUID):
    # Load vouch edges (active, non-withdrawn)
    edges = await db.execute(
        select(Edge.source_node_id, Edge.target_node_id)
        .where(Edge.type == 'vouch', Edge.context_node_id.is_(None))
        .join(Node, Edge.source_node_id == Node.id)
        .where(Node.community_id == community_id)
    )

    G = nx.Graph()  # undirected for community detection
    G.add_edges_from(edges.all())

    communities = louvain_communities(G, seed=42)

    # Cache results
    result = {
        "num_communities": len(communities),
        "communities": [
            {"id": i, "members": list(members)}
            for i, members in enumerate(communities)
        ]
    }
    await cache_analytics(db, community_id, "communities", result)
    return result
```

#### Centrality Analysis

Identifies connectors and monitors network health:

```python
async def compute_centrality(db, community_id: uuid.UUID):
    G = await load_community_graph(db, community_id)

    result = {
        "betweenness": {
            str(node): score
            for node, score in nx.betweenness_centrality(G).items()
        },
        "degree": {
            str(node): score
            for node, score in nx.degree_centrality(G).items()
        },
    }
    await cache_analytics(db, community_id, "centrality", result)
    return result
```

#### Network Health Metrics

Tracks overall community health -- fragmentation, new member integration, clustering:

```python
async def compute_health_metrics(db, community_id: uuid.UUID):
    G = await load_community_graph(db, community_id)

    components = list(nx.connected_components(G))
    result = {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "connected_components": len(components),
        "largest_component_size": max(len(c) for c in components) if components else 0,
        "density": nx.density(G),
        "avg_clustering": nx.average_clustering(G),
        # Isolates: nodes with no vouch connections (may need attention)
        "isolated_nodes": list(nx.isolates(G)),
    }
    await cache_analytics(db, community_id, "health", result)
    return result
```

#### Scheduling

Analytics run as background tasks, triggered on a schedule or by significant graph changes (new vouches, withdrawals):

```python
# Periodic: run every N hours via task scheduler
# Event-driven: re-run after vouch/withdrawal events
# At community scale (100s-1000s nodes), full analysis completes in <200ms
```

### Why This Hybrid Approach

| Concern | Solution | Why |
|---------|----------|-----|
| Trust-weighted matching | Recursive CTEs + pgvector | Single query plan, no orchestration overhead |
| Graph-proximity discovery | Recursive CTEs | Integrated with existing SQL queries |
| Community detection | NetworkX (Louvain) | Best algorithm library, trivial at our scale |
| Centrality analysis | NetworkX | Betweenness, PageRank, etc. built-in |
| Network health | NetworkX | Connected components, clustering, density |
| Deployment complexity | None added | Postgres (existing) + `pip install networkx` |

Apache AGE was considered but rejected: no async driver (our stack is fully async), no SQLAlchemy integration, no built-in analytics algorithms, and requires a custom Docker image. At community scale, recursive CTEs are faster for pathfinding. Neo4j was rejected for adding deployment complexity (separate JVM service, dual-write sync) that violates the single-deployable, self-hostable constraint.

---

## Migration Path

The existing codebase has user-centric models (`users`, `membrane_attributes`, `signals`, `vouches`, `coolings`, `match_history`). The migration to the node-based model involves:

1. Introduce `communities` and `nodes` tables
2. Refactor `users` to extend `nodes` (user.id becomes user.node_id)
3. Rename `membrane_attributes` to `membrane_entries`, replace `user_id` with `node_id`
4. Replace `user_id` with `node_id` on `signals`
5. Consolidate `vouches` and `coolings` into unified `edges` table
6. Add `organizations` and `events` extension tables
7. Add `messages` table
8. Update `match_history` to reference `nodes` instead of `users`

This can be done incrementally with Alembic migrations.
