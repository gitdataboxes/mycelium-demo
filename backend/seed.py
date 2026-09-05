"""Bootstrap the first user in a Mycelium network.

Usage:
    python seed.py admin@example.com [username]

This creates an active user with no vouch required — the root of the trust graph.
All subsequent members must be vouched in by existing members.
"""
import asyncio
import sys

from sqlalchemy import select

from app.config import settings
from app.database import async_session, engine, Base
from app.models.user import User


async def seed(email: str, username: str | None = None):
    # Ensure tables exist (in case migrations haven't run)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"User already exists: {existing.email} (active={existing.is_active})")
            if not existing.is_active:
                existing.is_active = True
                await db.commit()
                print("  -> Activated.")
            return

        user = User(email=email, username=username, is_active=True)
        db.add(user)
        await db.commit()
        print(f"Created root user: {email}" + (f" ({username})" if username else ""))
        print("This user can now vouch for others to grow the network.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python seed.py <email> [username]")
        sys.exit(1)

    email = sys.argv[1]
    username = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(seed(email, username))
