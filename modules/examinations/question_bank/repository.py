import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.examinations.question_bank.models import Question


class QuestionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Question:
        question = Question(**fields)
        self.db.add(question)
        await self.db.flush()
        await self.db.refresh(question)
        return question

    async def get_by_id(self, question_id: uuid.UUID, organization_id: uuid.UUID) -> Question | None:
        result = await self.db.execute(
            select(Question).where(
                Question.id == question_id, Question.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, course_id: uuid.UUID | None = None
    ) -> list[Question]:
        conditions = [Question.organization_id == organization_id]
        if course_id is not None:
            conditions.append(Question.course_id == course_id)
        result = await self.db.execute(select(Question).where(*conditions))
        return list(result.scalars().all())

    async def update(self, question: Question, **fields) -> Question:
        for key, value in fields.items():
            if value is not None:
                setattr(question, key, value)
        await self.db.flush()
        await self.db.refresh(question)
        return question

    async def delete(self, question: Question) -> None:
        await self.db.delete(question)
        await self.db.flush()
