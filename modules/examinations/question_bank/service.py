import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.examinations.question_bank.models import Question
from modules.examinations.question_bank.repository import QuestionRepository

logger = get_logger(__name__)


class QuestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = QuestionRepository(db)
        self.course_repo = CourseRepository(db)

    async def create_question(self, organization_id: uuid.UUID, **fields) -> Question:
        course_id = fields.get("course_id")
        if course_id is not None:
            course = await self.course_repo.get_by_id(course_id, organization_id)
            if not course:
                raise NotFoundError("Course", course_id)
        question = await self.repo.create(organization_id=organization_id, **fields)
        logger.info("question_created", question_id=str(question.id))
        return question

    async def get_question(self, question_id: uuid.UUID, organization_id: uuid.UUID) -> Question:
        question = await self.repo.get_by_id(question_id, organization_id)
        if not question:
            raise NotFoundError("Question", question_id)
        return question

    async def list_questions(
        self, organization_id: uuid.UUID, course_id: uuid.UUID | None
    ) -> list[Question]:
        return await self.repo.list_for_organization(organization_id, course_id)

    async def update_question(
        self, question_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Question:
        question = await self.get_question(question_id, organization_id)
        updated = await self.repo.update(question, **fields)
        logger.info("question_updated", question_id=str(question_id))
        return updated

    async def delete_question(self, question_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        question = await self.get_question(question_id, organization_id)
        await self.repo.delete(question)
        logger.info("question_deleted", question_id=str(question_id))
