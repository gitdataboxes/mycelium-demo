import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal

logger = logging.getLogger(__name__)


async def cleanup_expired_signals(db: AsyncSession) -> int:
    """Delete all expired signals. Returns count deleted."""
    result = await db.execute(
        delete(Signal).where(Signal.expires_at < datetime.now(timezone.utc))
    )
    await db.commit()
    count = result.rowcount
    if count:
        logger.info("Cleaned up %d expired signals", count)
    return count
