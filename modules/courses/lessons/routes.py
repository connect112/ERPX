import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.courses.lessons.schemas import (
    LessonCreateRequest,
    LessonPublic,
    LessonUpdateRequest,
    MessageResponse,
)
from modules.courses.lessons.service import LessonService
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/{course_id}/chapters/{chapter_id}/lessons"


@router.get(_PREFIX + "/me", response_model=list[LessonPublic])
async def list_my_lessons(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    enrollment = await EnrollmentRepository(db).get_by_student_and_course(student.id, course_id)
    if not enrollment:
        raise AuthorizationError("You are not enrolled in this course.")
    service = LessonService(db)
    lessons = await service.list_lessons(chapter_id, course_id, student.organization_id)
    return [LessonPublic.model_validate(lesson) for lesson in lessons]


@router.post(_PREFIX, response_model=LessonPublic, status_code=status.HTTP_201_CREATED)
async def create_lesson(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    payload: LessonCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LessonService(db)
    lesson = await service.create_lesson(
        chapter_id, course_id, organization_id, **payload.model_dump()
    )
    return LessonPublic.model_validate(lesson)


@router.get(_PREFIX, response_model=list[LessonPublic])
async def list_lessons(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LessonService(db)
    lessons = await service.list_lessons(chapter_id, course_id, organization_id)
    return [LessonPublic.model_validate(l) for l in lessons]


@router.get(_PREFIX + "/{lesson_id}", response_model=LessonPublic)
async def get_lesson(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    lesson_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LessonService(db)
    lesson = await service.get_lesson(lesson_id, chapter_id, course_id, organization_id)
    return LessonPublic.model_validate(lesson)


@router.patch(_PREFIX + "/{lesson_id}", response_model=LessonPublic)
async def update_lesson(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    lesson_id: uuid.UUID,
    payload: LessonUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LessonService(db)
    lesson = await service.update_lesson(
        lesson_id, chapter_id, course_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return LessonPublic.model_validate(lesson)


@router.delete(_PREFIX + "/{lesson_id}", response_model=MessageResponse)
async def delete_lesson(
    course_id: uuid.UUID,
    chapter_id: uuid.UUID,
    lesson_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LessonService(db)
    await service.delete_lesson(lesson_id, chapter_id, course_id, organization_id)
    return MessageResponse(message="Lesson deleted successfully.")
