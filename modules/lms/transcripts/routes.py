import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.lms.transcripts.schemas import TranscriptResponse
from modules.lms.transcripts.service import TranscriptService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/me", response_model=TranscriptResponse)
async def get_my_transcript(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = TranscriptService(db)
    return await service.get_student_transcript(student.organization_id, student.id)


@router.get("/{student_id}", response_model=TranscriptResponse)
async def get_student_transcript(
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.transcripts.view")),
    db: AsyncSession = Depends(get_db),
):
    service = TranscriptService(db)
    return await service.get_student_transcript(organization_id, student_id)
