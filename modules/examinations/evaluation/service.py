import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.examinations.evaluation.models import AttemptStatus, ExamAnswer, ExamAttempt
from modules.examinations.evaluation.repository import ExamAnswerRepository, ExamAttemptRepository
from modules.examinations.exams.models import ExamStatus
from modules.examinations.exams.repository import ExamRepository
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class EvaluationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.attempt_repo = ExamAttemptRepository(db)
        self.answer_repo = ExamAnswerRepository(db)
        self.exam_repo = ExamRepository(db)
        self.student_repo = StudentRepository(db)

    async def start_attempt(
        self, exam_id: uuid.UUID, organization_id: uuid.UUID, student_id: uuid.UUID
    ) -> ExamAttempt:
        exam = await self.exam_repo.get_by_id(exam_id)
        if not exam:
            raise NotFoundError("Exam", exam_id)
        if exam.status != ExamStatus.SCHEDULED:
            raise ValidationError(
                f"This exam is not open for attempts (current status: '{exam.status.value}')."
            )

        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        existing = await self.attempt_repo.get_by_exam_and_student(exam_id, student_id)
        if existing:
            raise ConflictError("This student has already attempted this exam.")

        attempt = await self.attempt_repo.create(
            exam_id=exam_id, student_id=student_id, started_at=datetime.now(timezone.utc)
        )
        logger.info("exam_attempt_started", attempt_id=str(attempt.id))
        return attempt

    async def _get_attempt_in_progress(self, attempt_id: uuid.UUID) -> ExamAttempt:
        attempt = await self.attempt_repo.get_by_id(attempt_id)
        if not attempt:
            raise NotFoundError("Attempt", attempt_id)
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise ValidationError(
                f"This attempt is no longer in progress (status: '{attempt.status.value}')."
            )
        return attempt

    async def submit_answer(
        self, attempt_id: uuid.UUID, question_id: uuid.UUID, answer_text: str | None
    ) -> ExamAnswer:
        await self._get_attempt_in_progress(attempt_id)
        answer = await self.answer_repo.upsert(attempt_id, question_id, answer_text)
        logger.info("exam_answer_submitted", attempt_id=str(attempt_id), question_id=str(question_id))
        return answer

    async def submit_attempt(self, attempt_id: uuid.UUID) -> ExamAttempt:
        attempt = await self._get_attempt_in_progress(attempt_id)
        submitted = await self.attempt_repo.submit(attempt)
        logger.info("exam_attempt_submitted", attempt_id=str(attempt_id))
        return submitted

    async def list_answers(self, attempt_id: uuid.UUID) -> list[ExamAnswer]:
        attempt = await self.attempt_repo.get_by_id(attempt_id)
        if not attempt:
            raise NotFoundError("Attempt", attempt_id)
        return await self.answer_repo.list_for_attempt(attempt_id)

    async def grade_answer(
        self, answer_id: uuid.UUID, marks_awarded: int, evaluated_by_user_id: uuid.UUID
    ) -> ExamAnswer:
        answer = await self.answer_repo.get_by_id(answer_id)
        if not answer:
            raise NotFoundError("Answer", answer_id)

        attempt = await self.attempt_repo.get_by_id(answer.attempt_id)
        if attempt.status == AttemptStatus.IN_PROGRESS:
            raise ValidationError("Cannot grade an answer before the attempt has been submitted.")

        exam_question = await self.exam_repo.get_exam_question(attempt.exam_id, answer.question_id)
        if exam_question and marks_awarded > exam_question.marks_allocated:
            raise ValidationError(
                f"Marks awarded cannot exceed the {exam_question.marks_allocated} allocated "
                "for this question."
            )

        graded = await self.answer_repo.grade(answer, marks_awarded, evaluated_by_user_id)
        logger.info("exam_answer_graded", answer_id=str(answer_id), marks_awarded=marks_awarded)
        return graded

    async def finalize_evaluation(self, attempt_id: uuid.UUID) -> ExamAttempt:
        attempt = await self.attempt_repo.get_by_id(attempt_id)
        if not attempt:
            raise NotFoundError("Attempt", attempt_id)
        if attempt.status != AttemptStatus.SUBMITTED:
            raise ValidationError(
                f"Only a submitted attempt can be finalized (current status: '{attempt.status.value}')."
            )

        ungraded = await self.answer_repo.count_ungraded(attempt_id)
        if ungraded > 0:
            raise ValidationError(f"{ungraded} answer(s) still need to be graded before finalizing.")

        total = await self.answer_repo.sum_marks_for_attempt(attempt_id)
        finalized = await self.attempt_repo.finalize_score(attempt, total)
        logger.info("exam_attempt_finalized", attempt_id=str(attempt_id), total_score=total)
        return finalized
