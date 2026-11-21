"""Learning: the read models behind the shared Learning workspace (staff), and the student's own view of a course.

Staff (``/learning``): context (the seven tabs and what the caller may do), enrollments, results. Reached through Our Internships access
to an internship, or the course permissions for a course; nothing here stores anything.
Students (``/my-learning``): ownership-gated by their own student record and a live enrolment; they see their own activities and grades.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.learning.my_learning import MyCourseLearning, MyLearningService
from modules.learning.schemas import EnrollmentsView, LearningContext, ResultsView
from modules.learning.service import LearningService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
my_router = APIRouter()


@router.get("/context", response_model=LearningContext)
async def learning_context(
    course_id: uuid.UUID | None = None,
    internship_id: uuid.UUID | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if (course_id is None) == (internship_id is None):
        raise ValidationError("Give either course_id or internship_id.")
    return await LearningService(db).context(user, organization_id, course_id=course_id, internship_id=internship_id)


@router.get("/enrollments", response_model=EnrollmentsView)
async def learning_enrollments(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await LearningService(db).enrollments(user, organization_id, internship_id)


@router.get("/results", response_model=ResultsView)
async def learning_results(
    internship_id: uuid.UUID | None = None,
    course_id: uuid.UUID | None = None,
    kind: str | None = Query(default=None, pattern="^(exam|assignment|assessment|project|practical|viva)$"),
    status: str | None = Query(default=None, pattern="^(completed|pending)$"),
    q: str | None = None,
    student: str | None = None,
    activity_id: uuid.UUID | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """One internship's results (its own activities and the course-native ones for its students), or, with only a course, the course-native
    results. Cohorts are never combined: an internship is always named for internship-owned data."""
    if internship_id is None and course_id is None:
        raise ValidationError("Give either internship_id or course_id.")
    return await LearningService(db).results(
        user, organization_id, internship_id=internship_id, course_id=course_id, kind=kind, status=status, q=q, student=student, activity_id=activity_id
    )


@my_router.get("/courses/{course_id}", response_model=MyCourseLearning)
async def my_course_learning(
    course_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """The caller's own learning in one course: the internships that gave them access (their own, linked to My Internship), the assessments,
    practicals and viva that apply to them with their own grades, and their progress. A student whose access was withdrawn gets nothing."""
    data = await MyLearningService(db).course(student, course_id)
    if data is None:
        raise NotFoundError("Course", course_id)
    return data
