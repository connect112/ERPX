import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.courses.chapters.schemas import (
    ChapterCreateRequest,
    ChapterPublic,
    ChapterUpdateRequest,
    MessageResponse,
)
from modules.courses.chapters.service import ChapterService
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/{course_id}/chapters/me", response_model=list[ChapterPublic])
async def list_my_chapters(
    course_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    enrollment = await EnrollmentRepository(db).get_by_student_and_course(student.id, course_id)
    if not enrollment:
        raise AuthorizationError("You are not enrolled in this course.")
    service = ChapterService(db)
    chapters = await service.list_chapters(course_id, student.organization_id)
    return [ChapterPublic.model_validate(c) for c in chapters]


@router.post(
    "/{course_id}/chapters", response_model=ChapterPublic, status_code=status.HTTP_201_CREATED
)
async def create_chapter(
    course_id: uuid.UUID,
    payload: ChapterCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ChapterService(db)
    chapter = await service.create_chapter(course_id, organization_id, **payload.model_dump())
    return ChapterPublic.model_validate(chapter)


@router.get("/{course_id}/chapters", response_model=list[ChapterPublic])
async def list_chapters(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ChapterService(db)
    chapters = await service.list_chapters(course_id, organization_id)
    return [ChapterPublic.model_validate(c) for c in chapters]


@router.get("/{course_id}/chapters/{chapter_id}", response_model=ChapterPublic)
async def get_chapter(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ChapterService(db)
    chapter = await service.get_chapter(chapter_id, course_id, organization_id)
    return ChapterPublic.model_validate(chapter)


@router.patch("/{course_id}/chapters/{chapter_id}", response_model=ChapterPublic)
async def update_chapter(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    payload: ChapterUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ChapterService(db)
    chapter = await service.update_chapter(
        chapter_id, course_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return ChapterPublic.model_validate(chapter)


@router.delete("/{course_id}/chapters/{chapter_id}", response_model=MessageResponse)
async def delete_chapter(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ChapterService(db)
    await service.delete_chapter(chapter_id, course_id, organization_id)
    return MessageResponse(message="Chapter deleted successfully.")
