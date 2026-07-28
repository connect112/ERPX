import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.examinations.exams.schemas import (
    AddQuestionToExamRequest,
    ExamCreateRequest,
    ExamPublic,
    ExamQuestionPublic,
    ExamUpdateRequest,
    ExamWithTotalMarks,
    MessageResponse,
)
from modules.examinations.exams.service import ExamService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/courses/{course_id}/exams"


@router.post(_PREFIX, response_model=ExamPublic, status_code=status.HTTP_201_CREATED)
async def create_exam(
    course_id: uuid.UUID,
    payload: ExamCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.exams.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ExamService(db)
    exam = await service.create_exam(course_id, organization_id, **payload.model_dump())
    return ExamPublic.model_validate(exam)


@router.get(_PREFIX, response_model=list[ExamPublic])
async def list_exams(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.exams.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ExamService(db)
    exams = await service.list_exams(course_id, organization_id)
    return [ExamPublic.model_validate(e) for e in exams]


@router.get(_PREFIX + "/{exam_id}", response_model=ExamWithTotalMarks)
async def get_exam(
    course_id: uuid.UUID,
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.exams.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ExamService(db)
    exam, total_marks = await service.get_exam(exam_id, course_id, organization_id)
    return ExamWithTotalMarks(**ExamPublic.model_validate(exam).model_dump(), total_marks=total_marks)


@router.patch(_PREFIX + "/{exam_id}", response_model=ExamPublic)
async def update_exam(
    course_id: uuid.UUID,
    exam_id: uuid.UUID,
    payload: ExamUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.exams.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ExamService(db)
    exam = await service.update_exam(
        exam_id, course_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return ExamPublic.model_validate(exam)


@router.delete(_PREFIX + "/{exam_id}", response_model=MessageResponse)
async def delete_exam(
    course_id: uuid.UUID,
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.exams.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ExamService(db)
    await service.delete_exam(exam_id, course_id, organization_id)
    return MessageResponse(message="Exam deleted successfully.")


@router.post(_PREFIX + "/{exam_id}/questions", response_model=ExamQuestionPublic, status_code=status.HTTP_201_CREATED)
async def add_question_to_exam(
    course_id: uuid.UUID,
    exam_id: uuid.UUID,
    payload: AddQuestionToExamRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.exams.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ExamService(db)
    entry = await service.add_question(
        exam_id, course_id, organization_id, payload.question_id, payload.marks_allocated, payload.order_index
    )
    return ExamQuestionPublic.model_validate(entry)


@router.get(_PREFIX + "/{exam_id}/questions", response_model=list[ExamQuestionPublic])
async def list_exam_questions(
    course_id: uuid.UUID,
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.exams.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ExamService(db)
    entries = await service.list_questions(exam_id, course_id, organization_id)
    return [ExamQuestionPublic.model_validate(e) for e in entries]


@router.delete(_PREFIX + "/{exam_id}/questions/{question_id}", response_model=MessageResponse)
async def remove_question_from_exam(
    course_id: uuid.UUID,
    exam_id: uuid.UUID,
    question_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.exams.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ExamService(db)
    await service.remove_question(exam_id, course_id, organization_id, question_id)
    return MessageResponse(message="Question removed from exam.")
