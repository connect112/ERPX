import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.organizations.schemas import (
    MessageResponse,
    OrganizationCreateRequest,
    OrganizationPublic,
    OrganizationUpdateRequest,
)
from modules.organizations.service import OrganizationService

router = APIRouter()


@router.post("", response_model=OrganizationPublic, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreateRequest,
    user: User = Depends(require_permissions("organizations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    org = await service.create_organization(**payload.model_dump())
    return OrganizationPublic.model_validate(org)


@router.get("", response_model=list[OrganizationPublic])
async def list_organizations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(require_permissions("organizations.view")),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    orgs = await service.list_organizations(skip, limit)
    return [OrganizationPublic.model_validate(o) for o in orgs]


@router.get("/{org_id}", response_model=OrganizationPublic)
async def get_organization(
    org_id: uuid.UUID,
    user: User = Depends(require_permissions("organizations.view")),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    org = await service.get_organization(org_id)
    return OrganizationPublic.model_validate(org)


@router.patch("/{org_id}", response_model=OrganizationPublic)
async def update_organization(
    org_id: uuid.UUID,
    payload: OrganizationUpdateRequest,
    user: User = Depends(require_permissions("organizations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    org = await service.update_organization(org_id, **payload.model_dump(exclude_unset=True))
    return OrganizationPublic.model_validate(org)


@router.delete("/{org_id}", response_model=MessageResponse)
async def delete_organization(
    org_id: uuid.UUID,
    user: User = Depends(require_permissions("organizations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    await service.delete_organization(org_id)
    return MessageResponse(message="Organization deleted successfully.")
