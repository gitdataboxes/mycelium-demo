# Mycelium — Agent Guide

## What This Is

Mycelium is a community coordination platform built on a **fractal node pattern**. Users, Organizations, and Events are all nodes with the same shape: a membrane (inputs/outputs), signals (ephemeral intent), and edges (relationships). Trust is vouch-gated at every level. The network uses semantic matching (pgvector) and graph proximity (recursive CTEs) to surface connections.

## Architecture

```
Mycelium-Project/
├── backend/           # Python FastAPI + async SQLAlchemy + pgvector
├── frontend/          # Next.js 16 (App Router, client components)
├── docs/              # Design specs and data model
├── docker-compose.yml # Postgres (pgvector/pgvector:pg16)
├── seed.py            # Bootstrap root user
└── Makefile           # Dev workflow commands
```

**Stack:** Python 3.12+ / FastAPI / async SQLAlchemy 2.0 / asyncpg / pgvector / NetworkX | Next.js 16 / TypeScript / Tailwind | Postgres 16 with pgvector extension

**Single deployable unit.** Self-hostable. One Postgres instance for everything (relational data, vector embeddings, graph traversal via CTEs).

## Core Patterns

### Fractal Node Abstraction

Every entity is a `Node` with a type discriminator. Type-specific data lives in extension tables (`users`, `organizations`, `events`). Shared behaviors (membrane entries, signals, edges) reference `nodes.id`. When adding new node types, follow this pattern.

### Unified Edges

All relationships live in a single `edges` table with a `type` enum (vouch, cool, block, report, member, participant, host, responder). An optional `context_node_id` scopes edges to a specific org/event. When adding new relationship types, add to `EdgeType` enum and create a migration.

### Vouch-Gated Entry

The same trust pattern repeats at every scale:
- Community: vouch from existing member
- Organization: vouch from existing org member
- Event: vouch from existing participant

The creator of an org/event is automatically the first member/participant.

### Cooling is Localized

Cooling affects only the cooling user's view. No global reputation score. Binary exclusion in queries: `NOT EXISTS (... type = 'cool')`.

### Brokered Messaging

Users make first contact through events/organizations, not directly. Messages are tied to context nodes (the org/event where conversation started). Contacts are emergent: once you've exchanged messages, you become contacts and can message directly. Responder edges designate who receives messages on behalf of an entity. Block edges are directional and prevent message delivery.

### Graph-Proximity Discovery

Organizations and events are ranked by trust-graph distance from the requesting user. A recursive CTE walks the vouch/membership graph up to configurable depth, returning results sorted by minimum distance. Implemented in `services/discovery.py`, integrated into org/event routers.

### Embedding Strategy

Voyage `voyage-context-3`, 1024 dimensions. Each membrane entry/signal is embedded with the full node profile as context. Embeddings are re-computed when any attribute on a node changes.

## Development

See README.md for the no-account preview (`make preview`) and Docker stack (`make up`, then `make seed`). The public snapshot uses synthetic data and Mailpit. Verification commands and boundaries are in docs/VERIFICATION.md; CI checks frontend builds, service behavior, migrations, seed data, and containers.

## Conventions

- **Async everywhere** in backend. All DB operations use `async/await` with `AsyncSession`.
- **Services do business logic**, routers do HTTP. Routers call services, never write queries directly.
- **Schemas (Pydantic)** validate input/output at the API boundary. Models (SQLAlchemy) define DB schema.
- **Frontend uses `"use client"` components** with hooks (`useState`, `useEffect`, `useCallback`). The `api.ts` file has a mock mode (`NEXT_PUBLIC_DEV_MOCK=true`) for development without a backend. API methods are namespaced by feature (e.g., `api.messages.*`, `api.trust.*`).
- **Tests** should use pytest with async fixtures and the existing service layer (don't insert raw SQL).

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/models/node.py` | Node base model, NodeType enum |
| `backend/app/models/edge.py` | Edge model, EdgeType enum |
| `backend/app/services/trust.py` | Vouch/cool/block operations, BFS trust distance |
| `backend/app/services/matching.py` | Semantic matching engine (pgvector) |
| `backend/app/services/embedding.py` | Voyage AI contextual embeddings |
| `backend/app/services/discovery.py` | Graph-proximity discovery (recursive CTEs) |
| `backend/app/services/graph_analytics.py` | NetworkX analytics (community detection, centrality, health) |
| `backend/app/services/message.py` | Messaging (threads, contacts, context-brokered) |
| `backend/app/services/email.py` | Transactional email (magic links, invitations) |
| `backend/app/services/organization.py` | Org CRUD + vouch-gated membership |
| `backend/app/services/event.py` | Event CRUD + vouch-gated participation |
| `backend/app/scheduler.py` | Shared APScheduler instance |
| `backend/app/config.py` | All settings with env var overrides |
| `frontend/src/lib/api.ts` | API client (real + mock implementations) |
| `frontend/src/lib/useAuth.ts` | Auth hook (session management) |
| `docs/data-model.md` | Full schema, graph query patterns, migration path |
| `docs/browsable-discovery.md` | Spec for graph-proximity discovery (implemented) |
| `docs/messaging.md` | Messaging spec: brokered contact, threads, responders |
