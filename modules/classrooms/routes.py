import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.classrooms.schemas import (
    ClassroomCreateRequest,
    ClassroomListResponse,
    ClassroomPublic,
    ClassroomUpdateRequest,
    MessageResponse,
)
from modules.classrooms.service import ClassroomService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=ClassroomPublic, status_code=status.HTTP_201_CREATED)
async def create_classroom(
    payload: ClassroomCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("classrooms.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ClassroomService(db)
    classroom = await service.create_classroom(organization_id, **payload.model_dump())
    return ClassroomPublic.model_validate(classroom)


@router.get("", response_model=ClassroomListResponse)
async def list_classrooms(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("classrooms.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ClassroomService(db)
    items, total = await service.list_classrooms(organization_id, skip, limit)
    return ClassroomListResponse(items=[ClassroomPublic.model_validate(c) for c in items], total=total)


@router.get("/{classroom_id}", response_model=ClassroomPublic)
async def get_classroom(
    classroom_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("classrooms.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ClassroomService(db)
    classroom = await service.get_classroom(classroom_id, organization_id)
    return ClassroomPublic.model_validate(classroom)


@router.patch("/{classroom_id}", response_model=ClassroomPublic)
async def update_classroom(
    classroom_id: uuid.UUID,
    payload: ClassroomUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("classrooms.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ClassroomService(db)
    classroom = await service.update_classroom(
        classroom_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return ClassroomPublic.model_validate(classroom)


@router.delete("/{classroom_id}", response_model=MessageResponse)
async def delete_classroom(
    classroom_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("classrooms.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ClassroomService(db)
    await service.delete_classroom(classroom_id, organization_id)
    return MessageResponse(message="Classroom deleted successfully.")
