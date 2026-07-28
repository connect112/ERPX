import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.examinations.results.schemas import StudentCourseResultResponse
from modules.examinations.results.service import ResultsService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/{student_id}/course/{course_id}", response_model=StudentCourseResultResponse)
async def get_student_course_result(
    student_id: uuid.UUID,
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.results.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ResultsService(db)
    return await service.get_student_course_result(student_id, course_id, organization_id)
