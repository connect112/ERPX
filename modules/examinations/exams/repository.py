import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.examinations.exams.models import Exam, ExamQuestion


class ExamRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Exam:
        exam = Exam(**fields)
        self.db.add(exam)
        await self.db.flush()
        await self.db.refresh(exam)
        return exam

    async def get_by_id(self, exam_id: uuid.UUID) -> Exam | None:
        result = await self.db.execute(select(Exam).where(Exam.id == exam_id))
        return result.scalar_one_or_none()

    async def list_for_course(self, course_id: uuid.UUID) -> list[Exam]:
        result = await self.db.execute(select(Exam).where(Exam.course_id == course_id))
        return list(result.scalars().all())

    async def update(self, exam: Exam, **fields) -> Exam:
        for key, value in fields.items():
            if value is not None:
                setattr(exam, key, value)
        await self.db.flush()
        await self.db.refresh(exam)
        return exam

    async def delete(self, exam: Exam) -> None:
        await self.db.delete(exam)
        await self.db.flush()

    async def total_marks(self, exam_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.sum(ExamQuestion.marks_allocated), 0)).where(
                ExamQuestion.exam_id == exam_id
            )
        )
        return result.scalar_one()

    async def add_question(self, **fields) -> ExamQuestion:
        entry = ExamQuestion(**fields)
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def list_questions(self, exam_id: uuid.UUID) -> list[ExamQuestion]:
        result = await self.db.execute(
            select(ExamQuestion)
            .where(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.order_index)
        )
        return list(result.scalars().all())

    async def get_exam_question(self, exam_id: uuid.UUID, question_id: uuid.UUID) -> ExamQuestion | None:
        result = await self.db.execute(
            select(ExamQuestion).where(
                ExamQuestion.exam_id == exam_id, ExamQuestion.question_id == question_id
            )
        )
        return result.scalar_one_or_none()

    async def remove_question(self, exam_id: uuid.UUID, question_id: uuid.UUID) -> None:
        from sqlalchemy import delete

        await self.db.execute(
            delete(ExamQuestion).where(
                ExamQuestion.exam_id == exam_id, ExamQuestion.question_id == question_id
            )
        )
        await self.db.flush()
