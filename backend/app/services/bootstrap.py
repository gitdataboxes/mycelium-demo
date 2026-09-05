import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.community import Community
from app.models.node import Node, NodeType
from app.models.user import User

logger = logging.getLogger(__name__)


async def ensure_founding_user(
    db: AsyncSession,
    email: str | None = None,
) -> User | None:
    founding_email = (email or settings.founding_user_email or "").strip().lower()
    if not founding_email:
        return None

    result = await db.execute(select(User).where(User.email == founding_email))
    user = result.scalar_one_or_none()

    if user is not None:
        if not user.is_active:
            user.is_active = True
            await db.commit()
            await db.refresh(user)
            logger.info("Activated founding user: %s", founding_email)
        return user

    result = await db.execute(select(Community).limit(1))
    community = result.scalar_one_or_none()
    if community is None:
        community = Community(name="Default")
        db.add(community)
        await db.flush()

    node = Node(community_id=community.id, type=NodeType.USER)
    db.add(node)
    await db.flush()

    user = User(node_id=node.id, email=founding_email, is_active=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("Created founding user: %s", founding_email)
    return user
