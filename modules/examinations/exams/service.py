import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.examinations.exams.models import Exam, ExamQuestion, ExamStatus
from modules.examinations.exams.repository import ExamRepository
from modules.examinations.question_bank.repository import QuestionRepository

logger = get_logger(__name__)


class ExamService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ExamRepository(db)
        self.course_repo = CourseRepository(db)
        self.question_repo = QuestionRepository(db)

    async def create_exam(self, course_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Exam:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        exam = await self.repo.create(course_id=course_id, **fields)
        logger.info("exam_created", exam_id=str(exam.id))
        return exam

    async def _get_owned_exam(
        self, exam_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Exam:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        exam = await self.repo.get_by_id(exam_id)
        if not exam or exam.course_id != course_id:
            raise NotFoundError("Exam", exam_id)
        return exam

    async def list_exams(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> list[Exam]:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        return await self.repo.list_for_course(course_id)

    async def get_exam(
        self, exam_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> tuple[Exam, int]:
        exam = await self._get_owned_exam(exam_id, course_id, organization_id)
        total = await self.repo.total_marks(exam_id)
        return exam, total

    async def update_exam(
        self, exam_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Exam:
        exam = await self._get_owned_exam(exam_id, course_id, organization_id)
        updated = await self.repo.update(exam, **fields)
        logger.info("exam_updated", exam_id=str(exam_id))
        return updated

    async def delete_exam(
        self, exam_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        exam = await self._get_owned_exam(exam_id, course_id, organization_id)
        if exam.status == ExamStatus.COMPLETED:
            raise ValidationError("A completed exam cannot be deleted.")
        await self.repo.delete(exam)
        logger.info("exam_deleted", exam_id=str(exam_id))

    async def add_question(
        self,
        exam_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        question_id: uuid.UUID,
        marks_allocated: int,
        order_index: int,
    ) -> ExamQuestion:
        exam = await self._get_owned_exam(exam_id, course_id, organization_id)
        question = await self.question_repo.get_by_id(question_id, organization_id)
        if not question:
            raise NotFoundError("Question", question_id)

        try:
            return await self.repo.add_question(
                exam_id=exam_id,
                question_id=question_id,
                marks_allocated=marks_allocated,
                order_index=order_index,
            )
        except Exception as exc:
            await self.db.rollback()
            raise ConflictError(
                "This question is already on the exam, or the order index is already used."
            ) from exc

    async def list_questions(
        self, exam_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[ExamQuestion]:
        await self._get_owned_exam(exam_id, course_id, organization_id)
        return await self.repo.list_questions(exam_id)

    async def remove_question(
        self, exam_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, question_id: uuid.UUID
    ) -> None:
        await self._get_owned_exam(exam_id, course_id, organization_id)
        await self.repo.remove_question(exam_id, question_id)
        logger.info("exam_question_removed", exam_id=str(exam_id), question_id=str(question_id))
