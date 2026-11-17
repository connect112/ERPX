import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.courses.chapters.models import Chapter
from modules.courses.lessons.models import Lesson
from modules.courses.models import Course
from modules.lms.enrollment.models import Enrollment, EnrollmentStatus
from modules.lms.bookmarks.models import LessonBookmark


class BookmarkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, student_id: uuid.UUID, lesson_id: uuid.UUID) -> LessonBookmark | None:
        result = await self.db.execute(
            select(LessonBookmark).where(
                LessonBookmark.student_id == student_id, LessonBookmark.lesson_id == lesson_id
            )
        )
        return result.scalar_one_or_none()

    async def create(self, student_id: uuid.UUID, lesson_id: uuid.UUID) -> LessonBookmark:
        record = LessonBookmark(student_id=student_id, lesson_id=lesson_id)
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def delete(self, bookmark: LessonBookmark) -> None:
        await self.db.delete(bookmark)
        await self.db.flush()

    async def list_for_student(self, student_id: uuid.UUID) -> list[tuple[LessonBookmark, Lesson, Course]]:
        """The student's bookmarks in courses they are in NOW. A bookmark in a course whose enrolment was dropped (for example when
        LMS access through an internship was withdrawn) is kept but not shown, so it cannot reveal the course's lesson or course titles;
        it comes back if the enrolment is restored."""
        result = await self.db.execute(
            select(LessonBookmark, Lesson, Course)
            .join(Lesson, Lesson.id == LessonBookmark.lesson_id)
            .join(Chapter, Chapter.id == Lesson.chapter_id)
            .join(Course, Course.id == Chapter.course_id)
            .join(
                Enrollment,
                (Enrollment.course_id == Course.id)
                & (Enrollment.student_id == student_id)
                & (Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED])),
            )
            .where(LessonBookmark.student_id == student_id)
            .order_by(LessonBookmark.created_at.desc())
        )
        return [(row[0], row[1], row[2]) for row in result.all()]
