# Docs — Agent Guide

This directory contains design specs and architectural documentation. These are living documents — update them when the implementation diverges.

## Files

| File | Purpose | Status |
|------|---------|--------|
| `data-model.md` | Full schema (SQL), graph query patterns (recursive CTEs), decay mechanics, relationship semantics, migration path | Authoritative — reflects current DB schema |
| `browsable-discovery.md` | Implementation spec for graph-proximity discovery | Implemented — discovery service uses recursive CTEs in org/event routers |
| `messaging.md` | Messaging spec: brokered first contact, threads, contacts, responders, block handling | Implemented — backend service/router + frontend inbox/thread pages |

## Conventions

- Specs should be precise enough for an agent to implement without additional context
- Include: what exists today, what to build, what NOT to build, files to modify, testing approach
- SQL patterns in `data-model.md` are reference implementations — adapt to SQLAlchemy as needed
- Keep specs updated when implementation deviates from the spec
