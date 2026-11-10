"""Who may read a course's content as a student: only someone whose enrolment in it is live.

An enrolment that was dropped (LMS access revoked, or the student withdrawn) must not keep opening the course, so the student-facing
endpoints ask here instead of only checking that an enrolment row exists.
"""

import uuid

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.repository import AuthorizationRepository
from modules.courses.chapters.models import Chapter
from modules.courses.lessons.models import Lesson
from modules.lms.enrollment.models import Enrollment, EnrollmentStatus
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.students.models import Student
from modules.students.repository import StudentRepository

NOT_ENROLLED = "You are not enrolled in this course."
LIVE = (EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)


async def require_live_enrollment(db: AsyncSession, student: Student, course_id: uuid.UUID) -> Enrollment:
    enrollment = await EnrollmentRepository(db).get_by_student_and_course(student.id, course_id)
    if enrollment is None or enrollment.status not in LIVE:
        raise AuthorizationError(NOT_ENROLLED)
    return enrollment


async def course_of_lesson(db: AsyncSession, lesson_id: uuid.UUID) -> uuid.UUID:
    course_id = (
        await db.execute(select(Chapter.course_id).join(Lesson, Lesson.chapter_id == Chapter.id).where(Lesson.id == lesson_id))
    ).scalar_one_or_none()
    if course_id is None:
        raise NotFoundError("Lesson", lesson_id)
    return course_id


# People who author course content are not held to enrolment: the guard below is for students reading what they are taught.
AUTHORING = {"courses.manage", "lms.assignments.manage", "lms.assessments.manage"}


async def student_course_guard(
    request: Request,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Router-level guard for everything under ``/courses/{course_id}/...`` (chapters, lessons, resources, assessments, assignments,
    discussions): a student may use it only while their enrolment in that course is live.

    The routes behind it are permission-gated, and the Student role holds the *view* permissions, so before this a student who was never
    enrolled, or whose access was revoked, could read lesson resources, assessments and assignments straight from the API. Staff and
    trainers (no student record) are decided by their own permissions as before; so is anyone who authors course content."""
    raw = request.path_params.get("course_id")
    if raw is None or user.is_superuser:
        return
    student = await StudentRepository(db).get_by_user_id(user.id)
    if student is None:
        return
    if AUTHORING & await AuthorizationRepository(db).get_permission_codes_for_user(user.id):
        return
    try:
        course_id = uuid.UUID(str(raw))
    except ValueError:
        return  # not a course id: the route itself answers with its own 422
    await require_live_enrollment(db, student, course_id)
