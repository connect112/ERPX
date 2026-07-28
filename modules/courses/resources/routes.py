import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.courses.resources.schemas import (
    MessageResponse,
    ResourceCreateRequest,
    ResourcePublic,
    ResourceUpdateRequest,
)
from modules.courses.resources.service import ResourceService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/{course_id}/chapters/{chapter_id}/lessons/{lesson_id}/resources"


@router.post(_PREFIX, response_model=ResourcePublic, status_code=status.HTTP_201_CREATED)
async def create_resource(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    lesson_id: uuid.UUID,
    payload: ResourceCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ResourceService(db)
    resource = await service.create_resource(
        lesson_id, chapter_id, course_id, organization_id, **payload.model_dump()
    )
    return ResourcePublic.model_validate(resource)


@router.get(_PREFIX, response_model=list[ResourcePublic])
async def list_resources(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    lesson_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ResourceService(db)
    resources = await service.list_resources(lesson_id, chapter_id, course_id, organization_id)
    return [ResourcePublic.model_validate(r) for r in resources]


@router.get(_PREFIX + "/{resource_id}", response_model=ResourcePublic)
async def get_resource(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    lesson_id: uuid.UUID,
    resource_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ResourceService(db)
    resource = await service.get_resource(
        resource_id, lesson_id, chapter_id, course_id, organization_id
    )
    return ResourcePublic.model_validate(resource)


@router.patch(_PREFIX + "/{resource_id}", response_model=ResourcePublic)
async def update_resource(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    lesson_id: uuid.UUID,
    resource_id: uuid.UUID,
    payload: ResourceUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ResourceService(db)
    resource = await service.update_resource(
        resource_id,
        lesson_id,
        chapter_id,
        course_id,
        organization_id,
        **payload.model_dump(exclude_unset=True),
    )
    return ResourcePublic.model_validate(resource)


@router.delete(_PREFIX + "/{resource_id}", response_model=MessageResponse)
async def delete_resource(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    lesson_id: uuid.UUID,
    resource_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ResourceService(db)
    await service.delete_resource(resource_id, lesson_id, chapter_id, course_id, organization_id)
    return MessageResponse(message="Resource deleted successfully.")
