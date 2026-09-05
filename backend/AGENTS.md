# Backend — Agent Guide

## Stack

Python 3.12+ / FastAPI / async SQLAlchemy 2.0 / asyncpg / pgvector / NetworkX / Pydantic v2 / APScheduler

## Structure

```
app/
├── main.py           # FastAPI app, lifespan, scheduler jobs, router registration
├── config.py         # Pydantic Settings (env vars)
├── database.py       # async engine + session factory
├── dependencies.py   # get_current_user (session cookie auth)
├── middleware.py      # Rate limiting
├── scheduler.py      # Shared APScheduler instance (imported by main.py and services)
├── models/           # SQLAlchemy ORM models
│   ├── node.py       # Node (base), NodeType enum
│   ├── user.py       # User extension, MagicLinkToken, Session
│   ├── organization.py # Organization extension
│   ├── event.py      # Event extension, EventUrgency enum
│   ├── edge.py       # Edge (unified relationships), EdgeType enum
│   ├── profile.py    # MembraneEntry, AttributeDirection enum
│   ├── signal.py     # Signal
│   ├── match.py      # MatchHistory
│   ├── message.py    # Message
│   ├── community.py  # Community
│   └── graph_analytics.py # Cached analytics results (JSONB, per community+type)
├── schemas/          # Pydantic request/response models
│   ├── auth.py
│   ├── profile.py
│   ├── trust.py
│   ├── signals.py
│   ├── matches.py
│   ├── message.py
│   ├── organization.py
│   ├── event.py
│   └── graph_analytics.py # CommunityDetection, Centrality, Health response models
├── services/         # Business logic (async, DB operations)
│   ├── auth.py       # Magic link auth, session management
│   ├── trust.py      # Vouch, cool, block, BFS trust distance + analytics recompute trigger
│   ├── matching.py   # Semantic matching engine (pgvector cosine)
│   ├── embedding.py  # Voyage AI contextual embeddings
│   ├── email.py      # Transactional email (magic links, invitations)
│   ├── digest.py     # Email digest pipeline (aiosmtplib)
│   ├── discovery.py  # Graph-proximity discovery (recursive CTEs)
│   ├── signals.py    # Expired signal cleanup
│   ├── message.py    # Messaging (threads, contacts, context-brokered)
│   ├── organization.py # Org CRUD + membership
│   ├── event.py      # Event CRUD + participation
│   └── graph_analytics.py # NetworkX analytics (community detection, centrality, health)
└── routers/          # HTTP endpoints
    ├── auth.py       # /api/auth/*
    ├── profile.py    # /api/profile/*
    ├── trust.py      # /api/trust/* (vouch, cool, block)
    ├── signals.py    # /api/signals/*
    ├── matches.py    # /api/matches/*
    ├── message.py    # /api/messages/*
    ├── organization.py # /api/organizations/*
    ├── event.py      # /api/events/*
    └── analytics.py  # /api/analytics/* (cached graph analytics)
```

## Conventions

### Adding a New Node Type

1. Create model in `models/` extending `Node` (PK = `node_id` FK to `nodes.id`)
2. Add to `NodeType` enum in `models/node.py`
3. Create schemas in `schemas/`
4. Create service in `services/` (CRUD + vouch-gated membership)
5. Create router in `routers/`, register in `main.py`
6. Membrane entries and signals work automatically (they reference `node_id`)

### Adding a New Edge Type

1. Add to `EdgeType` enum in `models/edge.py`
2. Create Alembic migration for the enum update (see `c3f14d567890` for responder example)
3. Add service logic for the new relationship

### Service Layer Rules

- All DB operations are `async` using `AsyncSession`
- Services take `db: AsyncSession` as first param
- Services raise `ValueError` for business logic errors; routers catch and return HTTP errors
- Services call `db.commit()` — routers don't commit

### Auth Pattern

All protected endpoints use `user: User = Depends(get_current_user)`. This reads the `session_id` cookie, validates the session, and returns the `User` with `.node` eagerly loaded.

### Embedding Pattern

When membrane entries change on any node, call `embed_node_attributes(db, node_id)` to re-embed all entries with updated context. This happens in routers after attribute create/update/delete. Failures are caught and logged, not raised.

## Scheduled Tasks

APScheduler instance lives in `scheduler.py` (shared module). Jobs are registered in `main.py` lifespan:
- Signal cleanup: every 6 hours
- Daily digest: 8am (matching + email)
- Graph analytics: every N hours (configurable via `analytics_interval_hours`, default 4)
- Debounced recompute: trust.py schedules a one-shot analytics job (configurable via `analytics_debounce_seconds`, default 30) when vouches are created or withdrawn
- Manual triggers: `POST /api/admin/run-digest`, `POST /api/admin/run-analytics`

## Migrations

Alembic in `backend/alembic/`. Five migrations exist:
1. `a0f05b925247` — initial user-centric schema
2. `b1e02c438a91` — node/edge migration
3. `c3f14d567890` — messaging context + responder edge type
4. `d4e25f678901` — graph analytics cache table
5. `e5f36a789012` — normalize attribute direction values (current)

Run with: `alembic upgrade head` (from `backend/` directory)

## Testing

Tests in `backend/tests/` using pytest-asyncio. Service-layer tests cover:
- `test_auth.py` — magic link creation, verification, session management
- `test_trust.py` — vouch, cool, block, withdrawal, trust distance
- `test_organization.py` — org CRUD, membership, responders
- `test_event.py` — event CRUD, participation, responders
- `test_message.py` — messaging, threads, contacts, block handling
- `test_signals.py` — signal cleanup
- `test_graph_analytics.py` — community detection, centrality, health, upsert, empty graphs

Run with: `pytest` (from `backend/` directory)
