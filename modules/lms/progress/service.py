import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.courses.lessons.repository import LessonRepository
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.lms.progress.models import LessonProgress
from modules.lms.progress.repository import ProgressRepository
from modules.lms.progress.schemas import CourseProgressResponse
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class ProgressService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ProgressRepository(db)
        self.lesson_repo = LessonRepository(db)
        self.student_repo = StudentRepository(db)
        self.enrollment_repo = EnrollmentRepository(db)

    async def mark_lesson_complete(
        self, organization_id: uuid.UUID, student_id: uuid.UUID, lesson_id: uuid.UUID
    ) -> LessonProgress:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        lesson = await self.lesson_repo.get_by_id(lesson_id)
        if not lesson:
            raise NotFoundError("Lesson", lesson_id)

        record = await self.repo.mark_complete(student_id, lesson_id)
        logger.info("lesson_marked_complete", student_id=str(student_id), lesson_id=str(lesson_id))
        return record

    async def unmark_lesson_complete(
        self, organization_id: uuid.UUID, student_id: uuid.UUID, lesson_id: uuid.UUID
    ) -> None:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        await self.repo.unmark_complete(student_id, lesson_id)
        logger.info("lesson_unmarked_complete", student_id=str(student_id), lesson_id=str(lesson_id))

    async def get_course_progress(
        self, organization_id: uuid.UUID, student_id: uuid.UUID, course_id: uuid.UUID
    ) -> CourseProgressResponse:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        total = await self.repo.count_total_lessons_for_course(course_id)
        progress_records = await self.repo.list_for_student_course(student_id, course_id)
        completed = len(progress_records)
        percent = round((completed / total) * 100, 2) if total > 0 else 0.0

        return CourseProgressResponse(
            student_id=student_id,
            course_id=course_id,
            total_lessons=total,
            completed_lessons=completed,
            percent_complete=percent,
            completed_lesson_ids=[record.lesson_id for record in progress_records],
        )
