import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.examinations.evaluation.schemas import (
    ExamAnswerPublic,
    ExamAttemptPublic,
    GradeAnswerRequest,
    StartExamAttemptRequest,
    SubmitAnswerRequest,
)
from modules.examinations.evaluation.service import EvaluationService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post(
    "/exams/{exam_id}/attempts", response_model=ExamAttemptPublic, status_code=status.HTTP_201_CREATED
)
async def start_attempt(
    exam_id: uuid.UUID,
    payload: StartExamAttemptRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.evaluation.attempt")),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    attempt = await service.start_attempt(exam_id, organization_id, payload.student_id)
    return ExamAttemptPublic.model_validate(attempt)


@router.post("/attempts/{attempt_id}/answers", response_model=ExamAnswerPublic)
async def submit_answer(
    attempt_id: uuid.UUID,
    payload: SubmitAnswerRequest,
    user: User = Depends(require_permissions("examinations.evaluation.attempt")),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    answer = await service.submit_answer(attempt_id, payload.question_id, payload.answer_text)
    return ExamAnswerPublic.model_validate(answer)


@router.post("/attempts/{attempt_id}/submit", response_model=ExamAttemptPublic)
async def submit_attempt(
    attempt_id: uuid.UUID,
    user: User = Depends(require_permissions("examinations.evaluation.attempt")),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    attempt = await service.submit_attempt(attempt_id)
    return ExamAttemptPublic.model_validate(attempt)


@router.get("/attempts/{attempt_id}/answers", response_model=list[ExamAnswerPublic])
async def list_answers(
    attempt_id: uuid.UUID,
    user: User = Depends(require_permissions("examinations.evaluation.view")),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    answers = await service.list_answers(attempt_id)
    return [ExamAnswerPublic.model_validate(a) for a in answers]


@router.post("/answers/{answer_id}/grade", response_model=ExamAnswerPublic)
async def grade_answer(
    answer_id: uuid.UUID,
    payload: GradeAnswerRequest,
    user: User = Depends(require_permissions("examinations.evaluation.grade")),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    answer = await service.grade_answer(answer_id, payload.marks_awarded, user.id)
    return ExamAnswerPublic.model_validate(answer)


@router.post("/attempts/{attempt_id}/finalize", response_model=ExamAttemptPublic)
async def finalize_evaluation(
    attempt_id: uuid.UUID,
    user: User = Depends(require_permissions("examinations.evaluation.grade")),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    attempt = await service.finalize_evaluation(attempt_id)
    return ExamAttemptPublic.model_validate(attempt)
