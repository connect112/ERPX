import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.lms.progress.schemas import (
    CourseProgressResponse,
    LessonProgressPublic,
    MarkLessonCompleteRequest,
    MessageResponse,
)
from modules.lms.progress.service import ProgressService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/me/course/{course_id}", response_model=CourseProgressResponse)
async def get_my_course_progress(
    course_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = ProgressService(db)
    return await service.get_course_progress(student.organization_id, student.id, course_id)


@router.post("/me/complete/{lesson_id}", response_model=LessonProgressPublic)
async def mark_my_lesson_complete(
    lesson_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = ProgressService(db)
    record = await service.mark_lesson_complete(student.organization_id, student.id, lesson_id)
    return LessonProgressPublic.model_validate(record)


@router.post("/complete", response_model=LessonProgressPublic)
async def mark_lesson_complete(
    payload: MarkLessonCompleteRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.progress.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ProgressService(db)
    record = await service.mark_lesson_complete(
        organization_id, payload.student_id, payload.lesson_id
    )
    return LessonProgressPublic.model_validate(record)


@router.post("/uncomplete", response_model=MessageResponse)
async def unmark_lesson_complete(
    payload: MarkLessonCompleteRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.progress.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ProgressService(db)
    await service.unmark_lesson_complete(organization_id, payload.student_id, payload.lesson_id)
    return MessageResponse(message="Lesson marked incomplete.")


@router.get("/{student_id}/course/{course_id}", response_model=CourseProgressResponse)
async def get_course_progress(
    student_id: uuid.UUID,
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.progress.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ProgressService(db)
    return await service.get_course_progress(organization_id, student_id, course_id)
