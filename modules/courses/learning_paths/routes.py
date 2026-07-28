import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.courses.learning_paths.schemas import (
    AddCourseToPathRequest,
    LearningPathCoursePublic,
    LearningPathCreateRequest,
    LearningPathPublic,
    LearningPathUpdateRequest,
    MessageResponse,
)
from modules.courses.learning_paths.service import LearningPathService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=LearningPathPublic, status_code=status.HTTP_201_CREATED)
async def create_learning_path(
    payload: LearningPathCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.learning_paths.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LearningPathService(db)
    path = await service.create_path(organization_id, **payload.model_dump())
    return LearningPathPublic.model_validate(path)


@router.get("", response_model=list[LearningPathPublic])
async def list_learning_paths(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.learning_paths.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LearningPathService(db)
    paths = await service.list_paths(organization_id)
    return [LearningPathPublic.model_validate(p) for p in paths]


@router.get("/{path_id}", response_model=LearningPathPublic)
async def get_learning_path(
    path_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.learning_paths.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LearningPathService(db)
    path = await service.get_path(path_id, organization_id)
    return LearningPathPublic.model_validate(path)


@router.patch("/{path_id}", response_model=LearningPathPublic)
async def update_learning_path(
    path_id: uuid.UUID,
    payload: LearningPathUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.learning_paths.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LearningPathService(db)
    path = await service.update_path(
        path_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return LearningPathPublic.model_validate(path)


@router.delete("/{path_id}", response_model=MessageResponse)
async def delete_learning_path(
    path_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.learning_paths.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LearningPathService(db)
    await service.delete_path(path_id, organization_id)
    return MessageResponse(message="Learning path deleted successfully.")


@router.post(
    "/{path_id}/courses", response_model=LearningPathCoursePublic, status_code=status.HTTP_201_CREATED
)
async def add_course_to_path(
    path_id: uuid.UUID,
    payload: AddCourseToPathRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.learning_paths.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LearningPathService(db)
    entry = await service.add_course_to_path(
        path_id, organization_id, payload.course_id, payload.order_index
    )
    return LearningPathCoursePublic.model_validate(entry)


@router.get("/{path_id}/courses", response_model=list[LearningPathCoursePublic])
async def list_path_courses(
    path_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.learning_paths.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LearningPathService(db)
    entries = await service.list_path_courses(path_id, organization_id)
    return [LearningPathCoursePublic.model_validate(e) for e in entries]


@router.delete("/{path_id}/courses/{course_id}", response_model=MessageResponse)
async def remove_course_from_path(
    path_id: uuid.UUID,
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.learning_paths.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LearningPathService(db)
    await service.remove_course_from_path(path_id, organization_id, course_id)
    return MessageResponse(message="Course removed from learning path.")
