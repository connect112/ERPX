import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.schemas import (
    MessageResponse,
    UserProfileCreateRequest,
    UserProfilePublic,
    UserProfileUpdateRequest,
    UserWithProfilePublic,
)
from modules.users.service import UserProfileService

router = APIRouter()


@router.get("", response_model=list[UserWithProfilePublic])
async def list_users(
    organization_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(require_permissions("users.view")),
    db: AsyncSession = Depends(get_db),
):
    service = UserProfileService(db)
    rows = await service.list_users_for_organization(organization_id, skip, limit)
    return [
        UserWithProfilePublic(
            id=account.id,
            email=account.email,
            full_name=account.full_name,
            status=account.status.value,
            is_email_verified=account.is_email_verified,
            profile=UserProfilePublic.model_validate(profile),
        )
        for account, profile in rows
    ]


@router.post("/profiles", response_model=UserProfilePublic, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: UserProfileCreateRequest,
    user: User = Depends(require_permissions("users.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = UserProfileService(db)
    profile = await service.create_profile(**payload.model_dump())
    return UserProfilePublic.model_validate(profile)


@router.get("/profiles", response_model=list[UserProfilePublic])
async def list_profiles(
    organization_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(require_permissions("users.view")),
    db: AsyncSession = Depends(get_db),
):
    service = UserProfileService(db)
    profiles = await service.list_profiles_for_organization(organization_id, skip, limit)
    return [UserProfilePublic.model_validate(p) for p in profiles]


@router.get("/profiles/{user_id}", response_model=UserProfilePublic)
async def get_profile(
    user_id: uuid.UUID,
    user: User = Depends(require_permissions("users.view")),
    db: AsyncSession = Depends(get_db),
):
    service = UserProfileService(db)
    profile = await service.get_profile_by_user_id(user_id)
    return UserProfilePublic.model_validate(profile)


@router.patch("/profiles/{user_id}", response_model=UserProfilePublic)
async def update_profile(
    user_id: uuid.UUID,
    payload: UserProfileUpdateRequest,
    user: User = Depends(require_permissions("users.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = UserProfileService(db)
    profile = await service.update_profile(user_id, **payload.model_dump(exclude_unset=True))
    return UserProfilePublic.model_validate(profile)
