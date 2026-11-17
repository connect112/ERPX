import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.examinations.results.schemas import StudentCourseResultResponse
from modules.examinations.results.service import ResultsService
from modules.learning.scope import student_internship_ids, visible_internship_ids
from modules.students.actor import ensure_own_or_staff
from modules.students.repository import StudentRepository
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

STAFF = {"examinations.evaluation.grade", "examinations.exams.manage", "examinations.practicals.manage", "examinations.viva.manage"}


@router.get("/{student_id}/course/{course_id}", response_model=StudentCourseResultResponse)
async def get_student_course_result(
    student_id: uuid.UUID,
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.results.view")),
    db: AsyncSession = Depends(get_db),
):
    # a student reads their own results only; staff read any student's of their organization
    await ensure_own_or_staff(db, user, student_id, STAFF)
    student = await StudentRepository(db).get_by_id(student_id, organization_id)
    if student is None:
        raise NotFoundError("Student", student_id)
    own = await StudentRepository(db).get_by_user_id(user.id)
    allowed = await student_internship_ids(db, student, course_id)
    if own is None or own.id != student_id:
        allowed &= await visible_internship_ids(db, user, organization_id, course_id, "view")
    service = ResultsService(db)
    return await service.get_student_course_result(student_id, course_id, organization_id, allowed)
