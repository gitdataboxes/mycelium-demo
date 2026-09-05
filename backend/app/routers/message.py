import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.message import (
    ContactResponse,
    MarkReadResponse,
    MessageResponse,
    MessageSend,
    ThreadListResponse,
    ThreadResponse,
    UnreadCountResponse,
)
from app.services.message import (
    get_contacts,
    get_thread_messages,
    get_threads,
    get_unread_count,
    mark_read,
    send_message,
)

router = APIRouter()


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_msg(
    body: MessageSend,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        msg = await send_message(
            db, user.node_id, body.content,
            to_node_id=body.to_node_id,
            context_node_id=body.context_node_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Build response with usernames and context name
    from app.services.message import _get_context_name
    from sqlalchemy import select

    sender_result = await db.execute(select(User).where(User.node_id == msg.from_user))
    sender = sender_result.scalar_one_or_none()
    recip_result = await db.execute(select(User).where(User.node_id == msg.to_user))
    recip = recip_result.scalar_one_or_none()
    context_name = None
    if msg.context_node_id:
        context_name = await _get_context_name(db, msg.context_node_id)

    return MessageResponse(
        id=msg.id,
        from_node_id=msg.from_user,
        from_username=sender.username if sender else None,
        to_node_id=msg.to_user,
        to_username=recip.username if recip else None,
        context_node_id=msg.context_node_id,
        context_name=context_name,
        content=msg.content,
        created_at=msg.created_at,
        read_at=msg.read_at,
    )


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    threads = await get_threads(db, user.node_id)
    return ThreadListResponse(threads=threads)


@router.get("/contacts", response_model=list[ContactResponse])
async def list_contacts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contacts = await get_contacts(db, user.node_id)
    return contacts


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await get_unread_count(db, user.node_id)
    return UnreadCountResponse(count=count)


@router.get("/thread/{other_node_id}")
async def get_thread(
    other_node_id: uuid.UUID,
    context: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages, total = await get_thread_messages(
        db, user.node_id, other_node_id, context, limit=limit, offset=offset,
    )
    return {"messages": messages, "total": total}


@router.post("/thread/{other_node_id}/read", response_model=MarkReadResponse)
async def mark_thread_read(
    other_node_id: uuid.UUID,
    context: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    marked = await mark_read(db, user.node_id, other_node_id, context)
    return MarkReadResponse(marked=marked)
