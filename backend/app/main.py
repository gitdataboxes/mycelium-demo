import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import async_session
from app.middleware import admin_limiter
from app.routers import (
    analytics,
    auth,
    event,
    matches,
    message,
    organization,
    profile,
    signals,
    trust,
)
from app.scheduler import scheduler
from app.services.bootstrap import ensure_founding_user
from app.services.digest import run_digest
from app.services.graph_analytics import run_all_analytics, run_analytics_all_communities
from app.services.signals import cleanup_expired_signals

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def _run_signal_cleanup():
    async with async_session() as db:
        await cleanup_expired_signals(db)


async def _run_digest():
    async with async_session() as db:
        await run_digest(db)


async def _run_analytics(community_id: uuid.UUID | None = None):
    async with async_session() as db:
        if community_id is None:
            await run_analytics_all_communities(db)
        else:
            await run_all_analytics(db, community_id)


async def _seed_founding_user():
    if not settings.founding_user_email:
        return

    async with async_session() as db:
        await ensure_founding_user(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _seed_founding_user()
    scheduler.add_job(
        _run_signal_cleanup,
        "interval",
        hours=6,
        id="signal_cleanup",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_digest,
        "cron",
        hour=8,
        id="daily_digest",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_analytics,
        "interval",
        hours=settings.analytics_interval_hours,
        id="graph_analytics",
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()
    logger.info(
        "Scheduler started (signal cleanup every 6h, digest daily at 8am, analytics every %sh)",
        settings.analytics_interval_hours,
    )
    yield
    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(title="Mycelium", version="0.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(trust.router, prefix="/api/trust", tags=["trust"])
app.include_router(matches.router, prefix="/api/matches", tags=["matches"])
app.include_router(organization.router, prefix="/api/organizations", tags=["organizations"])
app.include_router(event.router, prefix="/api/events", tags=["events"])
app.include_router(message.router, prefix="/api/messages", tags=["messages"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/admin/run-digest")
async def trigger_digest(request: Request):
    """Manually trigger the matching + digest pipeline."""
    admin_limiter.check(request)
    async with async_session() as db:
        sent = await run_digest(db)
    return {"digests_sent": sent}


@app.post("/api/admin/run-analytics")
async def trigger_analytics(
    request: Request,
    community_id: uuid.UUID | None = None,
):
    admin_limiter.check(request)
    await _run_analytics(community_id)
    return {
        "status": "ok",
        "community_id": str(community_id) if community_id else None,
    }
