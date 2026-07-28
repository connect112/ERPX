import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.courses.categories.schemas import (
    CategoryCreateRequest,
    CategoryPublic,
    CategoryUpdateRequest,
    MessageResponse,
)
from modules.courses.categories.service import CategoryService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=CategoryPublic, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.categories.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CategoryService(db)
    category = await service.create_category(organization_id, **payload.model_dump())
    return CategoryPublic.model_validate(category)


@router.get("", response_model=list[CategoryPublic])
async def list_categories(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.categories.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CategoryService(db)
    categories = await service.list_categories(organization_id)
    return [CategoryPublic.model_validate(c) for c in categories]


@router.get("/{category_id}", response_model=CategoryPublic)
async def get_category(
    category_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.categories.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CategoryService(db)
    category = await service.get_category(category_id, organization_id)
    return CategoryPublic.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryPublic)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.categories.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CategoryService(db)
    category = await service.update_category(
        category_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return CategoryPublic.model_validate(category)


@router.delete("/{category_id}", response_model=MessageResponse)
async def delete_category(
    category_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.categories.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CategoryService(db)
    await service.delete_category(category_id, organization_id)
    return MessageResponse(message="Category deleted successfully.")
