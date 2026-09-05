import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import MagicLinkToken, Session, User
from app.services.bootstrap import ensure_founding_user


def generate_token() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


async def create_magic_link(db: AsyncSession, email: str) -> tuple[str, User]:
    normalized_email = email.strip().lower()
    founding_email = settings.founding_user_email.strip().lower()

    if founding_email and normalized_email == founding_email:
        await ensure_founding_user(db, normalized_email)

    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()

    if user is None:
        raise ValueError("No account found for this email")

    raw_token, token_hash = generate_token()

    magic_link = MagicLinkToken(
        user_id=user.node_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.magic_link_ttl_minutes),
    )
    db.add(magic_link)
    await db.commit()

    return raw_token, user


async def verify_magic_link(db: AsyncSession, raw_token: str) -> Session:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    result = await db.execute(
        select(MagicLinkToken).where(
            MagicLinkToken.token_hash == token_hash,
            MagicLinkToken.used == False,
            MagicLinkToken.expires_at > datetime.now(timezone.utc),
        )
    )
    magic_link = result.scalar_one_or_none()

    if magic_link is None:
        raise ValueError("Invalid or expired token")

    magic_link.used = True

    # Activate user on first login
    result = await db.execute(select(User).where(User.node_id == magic_link.user_id))
    user = result.scalar_one()
    if not user.is_active:
        user.is_active = True

    session = Session(
        user_id=magic_link.user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.session_ttl_days),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return session


async def get_session(db: AsyncSession, session_id: str) -> Session | None:
    try:
        import uuid

        sid = uuid.UUID(session_id)
    except ValueError:
        return None

    result = await db.execute(
        select(Session)
        .where(Session.id == sid, Session.expires_at > datetime.now(timezone.utc))
    )
    session = result.scalar_one_or_none()

    if session is not None:
        result = await db.execute(select(User).where(User.node_id == session.user_id))
        session.user = result.scalar_one()

    return session


async def delete_session(db: AsyncSession, session_id: str) -> None:
    try:
        import uuid

        sid = uuid.UUID(session_id)
    except ValueError:
        return

    result = await db.execute(select(Session).where(Session.id == sid))
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.commit()
