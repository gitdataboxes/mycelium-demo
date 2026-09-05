import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.middleware import auth_limiter
from app.models.user import User
from app.schemas.auth import MagicLinkRequest, MagicLinkResponse, SessionResponse
from app.services.auth import create_magic_link, verify_magic_link
from app.services.email import send_magic_link_email

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/request", response_model=MagicLinkResponse)
async def request_magic_link(
    body: MagicLinkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    auth_limiter.check(request)
    email = str(body.email).strip().lower()

    try:
        raw_token, user = await create_magic_link(db, email)
    except ValueError:
        # Don't reveal whether email exists
        logger.info("Magic link requested for unknown email %s", email)
        return MagicLinkResponse(message="If an account exists, a login link has been sent.")

    try:
        await send_magic_link_email(user.email, raw_token)
    except Exception:
        logger.warning("Email send failed for %s, token logged in dev mode", user.email)

    return MagicLinkResponse(message="If an account exists, a login link has been sent.")


@router.get("/verify")
async def verify_token(
    token: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    auth_limiter.check(request)

    try:
        session = await verify_magic_link(db, token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired link"
        )

    response.set_cookie(
        key="session_id",
        value=str(session.id),
        httponly=True,
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
    )

    return {"status": "ok", "node_id": str(session.user_id)}


@router.post("/logout")
async def logout(
    response: Response,
    user: User = Depends(get_current_user),
):
    response.delete_cookie("session_id")
    return {"status": "logged out"}


@router.get("/me", response_model=SessionResponse)
async def get_me(user: User = Depends(get_current_user)):
    return SessionResponse(
        node_id=user.node_id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
    )
