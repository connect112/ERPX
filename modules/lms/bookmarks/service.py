import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.courses.lessons.repository import LessonRepository
from modules.lms.bookmarks.repository import BookmarkRepository
from modules.lms.bookmarks.schemas import BookmarkPublic
from modules.students.models import Student

logger = get_logger(__name__)


class BookmarkService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BookmarkRepository(db)
        self.lesson_repo = LessonRepository(db)

    async def add_bookmark(self, student: Student, lesson_id: uuid.UUID) -> None:
        lesson = await self.lesson_repo.get_by_id(lesson_id)
        if not lesson:
            raise NotFoundError("Lesson", lesson_id)

        existing = await self.repo.get(student.id, lesson_id)
        if existing:
            raise ConflictError("This lesson is already bookmarked.")

        await self.repo.create(student.id, lesson_id)
        logger.info("lesson_bookmarked", student_id=str(student.id), lesson_id=str(lesson_id))

    async def remove_bookmark(self, student: Student, lesson_id: uuid.UUID) -> None:
        existing = await self.repo.get(student.id, lesson_id)
        if not existing:
            raise NotFoundError("Bookmark", lesson_id)
        await self.repo.delete(existing)
        logger.info("lesson_bookmark_removed", student_id=str(student.id), lesson_id=str(lesson_id))

    async def list_my_bookmarks(self, student: Student) -> list[BookmarkPublic]:
        rows = await self.repo.list_for_student(student.id)
        return [
            BookmarkPublic(
                id=bookmark.id,
                lesson_id=lesson.id,
                lesson_title=lesson.title,
                course_id=course.id,
                course_title=course.title,
                created_at=bookmark.created_at,
            )
            for bookmark, lesson, course in rows
        ]
