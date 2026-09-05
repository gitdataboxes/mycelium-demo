# Verification

## Frontend

Use Node.js 22.18+ with the committed npm lockfile:

```bash
cd frontend
npm ci
npm test
npm run typecheck
npm run build:demo
npm run demo
```

The sample preview uses fictional, in-memory data. Inspect profile editing, organization/event details, connections, network, and messages. A refresh restores the sample data. The production-mode frontend is also built by CI with mock mode disabled.

## Backend

Use Python 3.12 and a dedicated PostgreSQL 16 database with pgvector. Never point tests at an application database: the fixtures create and drop tables.

```bash
python3 -m venv .venv
.venv/bin/pip install -e './backend[dev]'
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://mycelium:mycelium_demo@localhost:5432/mycelium_test ../.venv/bin/python -m pytest tests -q
```

Create `mycelium_test` and enable `CREATE EXTENSION IF NOT EXISTS vector` before running. The CI service provisions this automatically. Service tests cover authentication, membership, event participation, graph proximity, trust operations, messaging, signal cleanup, and analytics.

## Fresh database and email flow

CI applies `alembic upgrade head` against a separate fresh database, runs `seed_synthetic.py` twice to exercise its populated-database guard, and builds both container images. The documented Compose path includes Mailpit so magic-link login needs no external SMTP account.

Automated service tests and seeded scores do not establish production scale, real embedding quality, or end-user outcomes. The database-backed demo must remain local until development admin routes and deployment policy are hardened.

The container check also runs `python3 scripts/smoke_stack.py`: it requests a login email in the local Mailpit inbox, exchanges its token for a session, and verifies authenticated organization/event discovery and seeded connections. This sends no external email.
