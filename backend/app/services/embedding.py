import logging
from uuid import UUID

import voyageai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.profile import MembraneEntry
from app.models.signal import Signal
from app.models.user import User

logger = logging.getLogger(__name__)


def _get_client() -> voyageai.Client:
    return voyageai.Client(api_key=settings.voyage_api_key)


async def embed_node_attributes(db: AsyncSession, node_id: UUID) -> None:
    """Re-embed ALL membrane entries for a node using contextual embeddings.

    Each entry is embedded as a chunk within the "document" of the node's
    full profile, so the embedding of "stage lighting" carries context like
    the user also being a gardener in Southeast Portland.
    """
    # Get display name for context (try user first)
    result = await db.execute(select(User).where(User.node_id == node_id))
    user = result.scalar_one_or_none()
    display_name = (user.username if user else None) or "node"

    result = await db.execute(
        select(MembraneEntry)
        .where(MembraneEntry.node_id == node_id)
        .order_by(MembraneEntry.created_at)
    )
    entries = list(result.scalars().all())

    if not entries:
        return

    if not settings.voyage_api_key:
        logger.warning("No VOYAGE_API_KEY set, skipping embedding")
        return

    # Build the document: first chunk is global context, rest are individual entries
    context_summary = f"{display_name}: " + "; ".join(
        f"[{e.direction.value}] {e.content}" for e in entries
    )
    chunks = [context_summary] + [e.content for e in entries]

    client = _get_client()
    response = client.contextualized_embed(
        inputs=[chunks],
        model=settings.voyage_model,
        input_type="document",
    )

    # response.results[0] is our single document
    # embeddings[0] is the context summary (we discard it)
    # embeddings[1:] correspond to individual entries
    doc_result = response.results[0]
    entry_embeddings = doc_result.embeddings[1:]

    for entry, embedding in zip(entries, entry_embeddings):
        entry.embedding = embedding

    await db.commit()
    logger.info("Embedded %d entries for node %s", len(entries), node_id)


async def embed_signal(db: AsyncSession, signal_id: UUID) -> None:
    """Embed a signal with the node's full profile as context."""
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one()

    node_id = signal.node_id

    # Get display name for context
    result = await db.execute(select(User).where(User.node_id == node_id))
    user = result.scalar_one_or_none()
    display_name = (user.username if user else None) or "node"

    result = await db.execute(
        select(MembraneEntry)
        .where(MembraneEntry.node_id == node_id)
        .order_by(MembraneEntry.created_at)
    )
    entries = list(result.scalars().all())

    if not settings.voyage_api_key:
        logger.warning("No VOYAGE_API_KEY set, skipping embedding")
        return

    # Build document: profile context + all entries + the signal as final chunk
    context_summary = f"{display_name}: " + "; ".join(
        f"[{e.direction.value}] {e.content}" for e in entries
    )
    chunks = [context_summary] + [e.content for e in entries] + [signal.content]

    client = _get_client()
    response = client.contextualized_embed(
        inputs=[chunks],
        model=settings.voyage_model,
        input_type="document",
    )

    # Last embedding corresponds to the signal
    doc_result = response.results[0]
    signal.embedding = doc_result.embeddings[-1]

    await db.commit()
    logger.info("Embedded signal %s for node %s", signal_id, node_id)
