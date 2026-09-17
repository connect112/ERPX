import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.dependencies import require_superuser
from modules.organizations.schemas import (
    MessageResponse,
    OrganizationCreateRequest,
    OrganizationPublic,
    OrganizationUpdateRequest,
)
from modules.organizations.service import OrganizationService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

# Creating, listing every tenant, and editing/deleting a tenant are
# platform-operator actions (onboarding a new customer, offboarding one)
# — never a single tenant's own business, so these are is_superuser-only,
# not permission-gated. See require_superuser()'s docstring and
# modules/authorization/service.py's _PLATFORM_ONLY_PERMISSIONS for why
# this is enforced here too, not just by what Administrator gets granted
# by default.


@router.post("", response_model=OrganizationPublic, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreateRequest,
    user: User = Depends(require_superuser()),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    org = await service.create_organization(**payload.model_dump())
    return OrganizationPublic.model_validate(org)


@router.get("", response_model=list[OrganizationPublic])
async def list_organizations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(require_superuser()),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    orgs = await service.list_organizations(skip, limit)
    return [OrganizationPublic.model_validate(o) for o in orgs]


@router.get("/{org_id}", response_model=OrganizationPublic)
async def get_organization(
    org_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    caller_organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    db: AsyncSession = Depends(get_db),
):
    """The one exception to the superuser-only rule above: any user can
    view their *own* organization's record (name/slug/settings), same
    ownership-is-authorization reasoning as every other module's "me"
    endpoint — they just can't browse or touch anyone else's."""
    if not user.is_superuser and org_id != caller_organization_id:
        raise AuthorizationError("This action requires platform Super Admin access.")
    service = OrganizationService(db)
    org = await service.get_organization(org_id)
    return OrganizationPublic.model_validate(org)


@router.patch("/{org_id}", response_model=OrganizationPublic)
async def update_organization(
    org_id: uuid.UUID,
    payload: OrganizationUpdateRequest,
    user: User = Depends(require_superuser()),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    org = await service.update_organization(org_id, **payload.model_dump(exclude_unset=True))
    return OrganizationPublic.model_validate(org)


@router.delete("/{org_id}", response_model=MessageResponse)
async def delete_organization(
    org_id: uuid.UUID,
    user: User = Depends(require_superuser()),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    await service.delete_organization(org_id)
    return MessageResponse(message="Organization deleted successfully.")
