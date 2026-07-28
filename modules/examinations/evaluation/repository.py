import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.examinations.evaluation.models import AttemptStatus, ExamAnswer, ExamAttempt


class ExamAttemptRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> ExamAttempt:
        attempt = ExamAttempt(**fields)
        self.db.add(attempt)
        await self.db.flush()
        await self.db.refresh(attempt)
        return attempt

    async def get_by_id(self, attempt_id: uuid.UUID) -> ExamAttempt | None:
        result = await self.db.execute(select(ExamAttempt).where(ExamAttempt.id == attempt_id))
        return result.scalar_one_or_none()

    async def get_by_exam_and_student(
        self, exam_id: uuid.UUID, student_id: uuid.UUID
    ) -> ExamAttempt | None:
        result = await self.db.execute(
            select(ExamAttempt).where(
                ExamAttempt.exam_id == exam_id, ExamAttempt.student_id == student_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_exam(self, exam_id: uuid.UUID) -> list[ExamAttempt]:
        result = await self.db.execute(select(ExamAttempt).where(ExamAttempt.exam_id == exam_id))
        return list(result.scalars().all())

    async def submit(self, attempt: ExamAttempt) -> ExamAttempt:
        from datetime import datetime, timezone

        attempt.status = AttemptStatus.SUBMITTED
        attempt.submitted_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(attempt)
        return attempt

    async def finalize_score(self, attempt: ExamAttempt, total_score: int) -> ExamAttempt:
        attempt.total_score = total_score
        attempt.status = AttemptStatus.EVALUATED
        await self.db.flush()
        await self.db.refresh(attempt)
        return attempt


class ExamAnswerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(self, attempt_id: uuid.UUID, question_id: uuid.UUID, answer_text: str | None) -> ExamAnswer:
        existing = await self.get(attempt_id, question_id)
        if existing:
            existing.answer_text = answer_text
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        answer = ExamAnswer(attempt_id=attempt_id, question_id=question_id, answer_text=answer_text)
        self.db.add(answer)
        await self.db.flush()
        await self.db.refresh(answer)
        return answer

    async def get(self, attempt_id: uuid.UUID, question_id: uuid.UUID) -> ExamAnswer | None:
        result = await self.db.execute(
            select(ExamAnswer).where(
                ExamAnswer.attempt_id == attempt_id, ExamAnswer.question_id == question_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, answer_id: uuid.UUID) -> ExamAnswer | None:
        result = await self.db.execute(select(ExamAnswer).where(ExamAnswer.id == answer_id))
        return result.scalar_one_or_none()

    async def list_for_attempt(self, attempt_id: uuid.UUID) -> list[ExamAnswer]:
        result = await self.db.execute(select(ExamAnswer).where(ExamAnswer.attempt_id == attempt_id))
        return list(result.scalars().all())

    async def grade(self, answer: ExamAnswer, marks_awarded: int, evaluated_by_user_id: uuid.UUID) -> ExamAnswer:
        answer.marks_awarded = marks_awarded
        answer.evaluated_by_user_id = evaluated_by_user_id
        await self.db.flush()
        await self.db.refresh(answer)
        return answer

    async def sum_marks_for_attempt(self, attempt_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.sum(ExamAnswer.marks_awarded), 0)).where(
                ExamAnswer.attempt_id == attempt_id
            )
        )
        return result.scalar_one()

    async def count_ungraded(self, attempt_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(ExamAnswer)
            .where(ExamAnswer.attempt_id == attempt_id, ExamAnswer.marks_awarded.is_(None))
        )
        return result.scalar_one()
