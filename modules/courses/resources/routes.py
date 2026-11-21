import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.learning.access import course_read_access
from modules.courses.resources.schemas import (
    MessageResponse,
    ResourceCreateRequest,
    ResourceDownload,
    ResourcePublic,
    ResourceUpdateRequest,
)
from modules.courses.resources.models import ResourceType
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


@router.post(_PREFIX + "/upload", response_model=ResourcePublic, status_code=status.HTTP_201_CREATED)
async def upload_resource(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    lesson_id: uuid.UUID,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=255),
    resource_type: ResourceType = Form(ResourceType.OTHER),
    is_downloadable: bool = Form(True),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Attach an uploaded file to a lesson. The same permission as adding a link: course editing (``courses.manage``), which managing an
    internship's activities never grants."""
    service = ResourceService(db)
    resource = await service.create_upload(
        lesson_id, chapter_id, course_id, organization_id,
        upload=file, title=title, resource_type=resource_type, is_downloadable=is_downloadable, user_id=user.id,
    )
    return ResourcePublic.model_validate(resource)


@router.get(_PREFIX, response_model=list[ResourcePublic])
async def list_resources(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    lesson_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(course_read_access),
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
    user: User = Depends(course_read_access),
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


@router.get(_PREFIX + "/{resource_id}/download", response_model=ResourceDownload)
async def download_resource(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    lesson_id: uuid.UUID,
    resource_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(course_read_access),
    db: AsyncSession = Depends(get_db),
):
    """A short-lived link to an uploaded file. Reading rules are the resource's own: a student only through a live enrolment (the router's
    guard) and only when the resource is downloadable; staff who may read the curriculum always."""
    from app.core.exceptions import AuthorizationError
    from modules.learning.scope import has_permission
    from modules.students.repository import StudentRepository

    service = ResourceService(db)
    resource = await service.get_resource(resource_id, lesson_id, chapter_id, course_id, organization_id)
    is_student = await StudentRepository(db).get_by_user_id(user.id) is not None and not await has_permission(db, user, "courses.manage")
    if is_student and not resource.is_downloadable:
        raise AuthorizationError("This resource can be viewed but not downloaded.")
    url, filename = await service.download_link(resource)
    return ResourceDownload(url=url, filename=filename)
