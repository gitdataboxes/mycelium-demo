import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.profile import AttributeDirection, MembraneEntry
from app.models.user import User
from app.schemas.organization import (
    OrgCreate,
    OrgListResponse,
    OrgMemberResponse,
    OrgResponse,
    OrgUpdate,
    ResponderRequest,
    ResponderResponse,
)
from app.schemas.profile import AttributeCreate, AttributeResponse, AttributeUpdate
from app.services.embedding import embed_node_attributes
from app.services.discovery import discover
from app.services.organization import (
    add_member,
    add_responder,
    create_organization,
    delete_organization,
    get_member_count,
    get_members,
    get_organization,
    get_responders,
    is_member,
    remove_member,
    remove_responder,
    update_organization,
    vouch_into_org,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _build_org_response(
    db: AsyncSession, org, user_node_id: uuid.UUID, graph_distance: int | None = None
) -> OrgResponse:
    result = await db.execute(
        select(MembraneEntry)
        .where(MembraneEntry.node_id == org.node_id)
        .order_by(MembraneEntry.created_at)
    )
    entries = list(result.scalars().all())

    return OrgResponse(
        node_id=org.node_id,
        name=org.name,
        description=org.description,
        created_at=org.node.created_at,
        member_count=await get_member_count(db, org.node_id),
        is_member=await is_member(db, user_node_id, org.node_id),
        graph_distance=graph_distance,
        inputs=[
            AttributeResponse.model_validate(e)
            for e in entries
            if e.direction == AttributeDirection.INPUT
        ],
        outputs=[
            AttributeResponse.model_validate(e)
            for e in entries
            if e.direction == AttributeDirection.OUTPUT
        ],
    )


async def _get_org_or_404(db: AsyncSession, node_id: uuid.UUID):
    org = await get_organization(db, node_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


async def _require_membership(db: AsyncSession, user_node_id: uuid.UUID, org_node_id: uuid.UUID):
    if not await is_member(db, user_node_id, org_node_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")


# --- CRUD ---


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    body: OrgCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = await create_organization(db, user, body.name, body.description)
    return await _build_org_response(db, org, user.node_id)


@router.get("", response_model=OrgListResponse)
async def list_orgs(
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results, total = await discover(
        db, user.node_id, user.node.community_id,
        node_types=["organization"], search=search,
        limit=limit, offset=offset,
    )
    items = []
    for r in results:
        org = await get_organization(db, r.node_id)
        if org:
            items.append(await _build_org_response(db, org, user.node_id, r.graph_distance))
    return OrgListResponse(organizations=items, total=total)


@router.get("/{node_id}", response_model=OrgResponse)
async def get_org(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = await _get_org_or_404(db, node_id)
    return await _build_org_response(db, org, user.node_id)


@router.put("/{node_id}", response_model=OrgResponse)
async def update_org(
    node_id: uuid.UUID,
    body: OrgUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = await _get_org_or_404(db, node_id)
    await _require_membership(db, user.node_id, node_id)
    org = await update_organization(db, org, body.name, body.description)
    return await _build_org_response(db, org, user.node_id)


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_org_or_404(db, node_id)
    await _require_membership(db, user.node_id, node_id)
    await delete_organization(db, node_id)


# --- Membership ---


@router.get("/{node_id}/members", response_model=list[OrgMemberResponse])
async def list_members(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_org_or_404(db, node_id)
    members = await get_members(db, node_id)
    return [
        OrgMemberResponse(
            node_id=u.node_id,
            username=u.username,
            name=u.name,
            joined_at=edge.created_at,
        )
        for u, edge in members
    ]


@router.post("/{node_id}/vouch", response_model=OrgMemberResponse, status_code=status.HTTP_201_CREATED)
async def vouch_member(
    node_id: uuid.UUID,
    vouchee_node_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Vouch a user into this organization. You must be an existing member."""
    await _get_org_or_404(db, node_id)
    try:
        membership = await vouch_into_org(db, user.node_id, vouchee_node_id, node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    result = await db.execute(select(User).where(User.node_id == vouchee_node_id))
    vouchee = result.scalar_one()
    return OrgMemberResponse(
        node_id=vouchee.node_id,
        username=vouchee.username,
        name=vouchee.name,
        joined_at=membership.created_at,
    )


@router.delete("/{node_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_org(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_org_or_404(db, node_id)
    try:
        await remove_member(db, user.node_id, node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Responders ---


@router.get("/{node_id}/responders", response_model=list[ResponderResponse])
async def list_org_responders(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_org_or_404(db, node_id)
    responders = await get_responders(db, node_id)
    return [
        ResponderResponse(node_id=u.node_id, username=u.username)
        for u, edge in responders
    ]


@router.post("/{node_id}/responders", response_model=ResponderResponse, status_code=status.HTTP_201_CREATED)
async def add_org_responder(
    node_id: uuid.UUID,
    body: ResponderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_org_or_404(db, node_id)
    try:
        await add_responder(db, user.node_id, node_id, body.node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    result = await db.execute(select(User).where(User.node_id == body.node_id))
    u = result.scalar_one()
    return ResponderResponse(node_id=u.node_id, username=u.username)


@router.delete("/{node_id}/responders/{responder_node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_org_responder(
    node_id: uuid.UUID,
    responder_node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_org_or_404(db, node_id)
    try:
        await remove_responder(db, user.node_id, node_id, responder_node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Org Membrane ---


@router.post("/{node_id}/attributes", response_model=AttributeResponse, status_code=status.HTTP_201_CREATED)
async def create_org_attribute(
    node_id: uuid.UUID,
    body: AttributeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_org_or_404(db, node_id)
    await _require_membership(db, user.node_id, node_id)

    entry = MembraneEntry(node_id=node_id, direction=body.direction, content=body.content)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    try:
        await embed_node_attributes(db, node_id)
    except Exception:
        logger.exception("Embedding failed for org node %s", node_id)

    return AttributeResponse.model_validate(entry)


@router.put("/{node_id}/attributes/{attribute_id}", response_model=AttributeResponse)
async def update_org_attribute(
    node_id: uuid.UUID,
    attribute_id: uuid.UUID,
    body: AttributeUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_org_or_404(db, node_id)
    await _require_membership(db, user.node_id, node_id)

    result = await db.execute(
        select(MembraneEntry).where(
            MembraneEntry.id == attribute_id,
            MembraneEntry.node_id == node_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found")

    entry.content = body.content
    await db.commit()
    await db.refresh(entry)

    try:
        await embed_node_attributes(db, node_id)
    except Exception:
        logger.exception("Embedding failed for org node %s", node_id)

    return AttributeResponse.model_validate(entry)


@router.delete("/{node_id}/attributes/{attribute_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_attribute(
    node_id: uuid.UUID,
    attribute_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_org_or_404(db, node_id)
    await _require_membership(db, user.node_id, node_id)

    result = await db.execute(
        select(MembraneEntry).where(
            MembraneEntry.id == attribute_id,
            MembraneEntry.node_id == node_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found")

    await db.delete(entry)
    await db.commit()

    try:
        await embed_node_attributes(db, node_id)
    except Exception:
        logger.exception("Embedding failed for org node %s", node_id)
