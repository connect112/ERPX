"""
ERPX release 0107 -- ROLLBACK GUARD for the LMS course-progress endpoint.   NEVER PART OF THE APPLICATION.

90_rollback_code_only.sh bakes this file into a derived copy of the PREVIOUS api image, in place of modules/lms/progress/routes.py, only after checking
that the file it replaces is byte-for-byte the previous release's (REPLACES_SHA256).

WHY. In the previous release GET /api/v1/lms/progress/{student_id}/course/{course_id} needs only ``lms.progress.view``, which every Student holds, and it
never asks whose progress is requested: any student could read any other student's lesson progress. A code-only rollback would restore that, so the
previous image gets this guard. RULE: the caller is the student the progress is for, a platform superuser, or staff (holds ``lms.progress.manage``);
everyone else gets 403. Fails closed. Every other route in the file is the previous release's code, unchanged.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.authorization.repository import AuthorizationRepository
from modules.lms.enrollment.access import course_of_lesson, require_live_enrollment
from modules.lms.progress.schemas import (
    CourseProgressResponse,
    LessonProgressPublic,
    MarkLessonCompleteRequest,
    MessageResponse,
)
from modules.lms.progress.service import ProgressService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.students.repository import StudentRepository
from modules.users.dependencies import get_current_user_organization_id

ROLLBACK_GUARD = "progress-0107"
# sha256 of the previous release's modules/lms/progress/routes.py (the file this one replaces; the rollback refuses to build over any other)
REPLACES_SHA256 = "49600eff4e7ca07d0fa34e014b525e7500dfbfdfc97bb3eb9bcac5a03bc16b9b"
STAFF = {"lms.progress.manage"}
NOT_YOURS = "You can only view your own progress."

router = APIRouter()


async def _ensure_own_or_staff(db: AsyncSession, user: User, student_id: uuid.UUID) -> None:
    if user.is_superuser:
        return
    own = await StudentRepository(db).get_by_user_id(user.id)
    if own is not None and own.id == student_id:
        return
    codes = await AuthorizationRepository(db).get_permission_codes_for_user(user.id)
    if STAFF & set(codes):
        return
    raise AuthorizationError(NOT_YOURS)


@router.get("/me/course/{course_id}", response_model=CourseProgressResponse)
async def get_my_course_progress(
    course_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    await require_live_enrollment(db, student, course_id)
    service = ProgressService(db)
    return await service.get_course_progress(student.organization_id, student.id, course_id)


@router.post("/me/complete/{lesson_id}", response_model=LessonProgressPublic)
async def mark_my_lesson_complete(
    lesson_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    # progress counts only on a course the student is really enrolled in (not a dropped one, and not another organization's)
    await require_live_enrollment(db, student, await course_of_lesson(db, lesson_id))
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
    await _ensure_own_or_staff(db, user, student_id)
    service = ProgressService(db)
    return await service.get_course_progress(organization_id, student_id, course_id)
