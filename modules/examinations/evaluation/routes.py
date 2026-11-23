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
from modules.students.actor import ensure_own_or_staff, resolve_actor
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

# Staff who may act for a student, or read and grade any student's attempt. A student (the Student role holds the "attempt" and
# "view" permissions) reaches only their own attempts: before this an attempt id was enough to read, answer or submit anyone's.
STAFF = {"examinations.evaluation.grade", "examinations.exams.manage"}


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
    student = await resolve_actor(db, user, organization_id, payload.student_id, STAFF)
    service = EvaluationService(db)
    attempt = await service.start_attempt(exam_id, organization_id, student)
    return ExamAttemptPublic.model_validate(attempt)


@router.post("/attempts/{attempt_id}/answers", response_model=ExamAnswerPublic)
async def submit_answer(
    attempt_id: uuid.UUID,
    payload: SubmitAnswerRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.evaluation.attempt")),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    attempt = await service.attempt_in_org(attempt_id, organization_id)
    await ensure_own_or_staff(db, user, attempt.student_id, STAFF)
    answer = await service.submit_answer(attempt_id, payload.question_id, payload.answer_text)
    return ExamAnswerPublic.model_validate(answer)


@router.post("/attempts/{attempt_id}/submit", response_model=ExamAttemptPublic)
async def submit_attempt(
    attempt_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.evaluation.attempt")),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    attempt = await service.attempt_in_org(attempt_id, organization_id)
    await ensure_own_or_staff(db, user, attempt.student_id, STAFF)
    attempt = await service.submit_attempt(attempt_id)
    return ExamAttemptPublic.model_validate(attempt)


@router.get("/attempts/{attempt_id}/answers", response_model=list[ExamAnswerPublic])
async def list_answers(
    attempt_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.evaluation.view")),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    attempt = await service.attempt_in_org(attempt_id, organization_id)
    await ensure_own_or_staff(db, user, attempt.student_id, STAFF)
    answers = await service.list_answers(attempt_id)
    return [ExamAnswerPublic.model_validate(a) for a in answers]


@router.post("/answers/{answer_id}/grade", response_model=ExamAnswerPublic)
async def grade_answer(
    answer_id: uuid.UUID,
    payload: GradeAnswerRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.evaluation.grade")),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    await service.answer_in_org(answer_id, organization_id)
    answer = await service.grade_answer(answer_id, payload.marks_awarded, user.id)
    return ExamAnswerPublic.model_validate(answer)


@router.post("/attempts/{attempt_id}/finalize", response_model=ExamAttemptPublic)
async def finalize_evaluation(
    attempt_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.evaluation.grade")),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    await service.attempt_in_org(attempt_id, organization_id)
    attempt = await service.finalize_evaluation(attempt_id)
    return ExamAttemptPublic.model_validate(attempt)
