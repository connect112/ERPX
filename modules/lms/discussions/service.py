import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.authentication.models import User
from modules.courses.repository import CourseRepository
from modules.lms.discussions.models import DiscussionReply, DiscussionThread
from modules.lms.discussions.repository import DiscussionRepository

logger = get_logger(__name__)


class DiscussionService:
    """Course discussions. A thread with no ``internship_id`` is course-wide (everyone enrolled, as before); one with an ``internship_id`` is
    private to that internship, and who may see it is decided by the routes (modules/learning/scope.py): a thread that is not theirs is
    reported as "not found", never as forbidden, so its existence is not revealed."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DiscussionRepository(db)
        self.course_repo = CourseRepository(db)

    async def _course(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        if not await self.course_repo.get_by_id(course_id, organization_id):
            raise NotFoundError("Course", course_id)

    async def create_thread(
        self, course_id: uuid.UUID, organization_id: uuid.UUID, created_by_user_id: uuid.UUID, **fields
    ) -> DiscussionThread:
        await self._course(course_id, organization_id)
        thread = await self.repo.create_thread(course_id=course_id, created_by_user_id=created_by_user_id, **fields)
        logger.info("discussion_thread_created", thread_id=str(thread.id))
        return thread

    async def list_threads(
        self,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        *,
        internship_id: uuid.UUID | None = None,
        include_course: bool = False,
        internship_ids: set[uuid.UUID] | None = None,
    ) -> list[DiscussionThread]:
        """Course-wide threads (nothing given), or one internship's own (plus course-wide when asked), or, for a student, the course-wide
        ones and those of the internships in ``internship_ids``."""
        await self._course(course_id, organization_id)
        if internship_ids is not None:
            clause = DiscussionThread.internship_id.is_(None)
            if internship_ids:
                clause = or_(clause, DiscussionThread.internship_id.in_(list(internship_ids)))
        elif internship_id is not None:
            clause = DiscussionThread.internship_id == internship_id
            if include_course:
                clause = or_(clause, DiscussionThread.internship_id.is_(None))
        else:
            clause = DiscussionThread.internship_id.is_(None)
        rows = await self.db.execute(
            select(DiscussionThread).where(DiscussionThread.course_id == course_id, clause).order_by(DiscussionThread.created_at.desc())
        )
        return list(rows.scalars().all())

    async def get_thread(self, thread_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID) -> DiscussionThread:
        await self._course(course_id, organization_id)
        thread = await self.repo.get_thread_by_id(thread_id)
        if not thread or thread.course_id != course_id:
            raise NotFoundError("Discussion thread", thread_id)
        return thread

    async def reply(
        self, thread: DiscussionThread, created_by_user_id: uuid.UUID, body: str
    ) -> DiscussionReply:
        if thread.is_locked:
            raise ValidationError("This discussion thread is locked and no longer accepting replies.")
        reply = await self.repo.create_reply(thread_id=thread.id, created_by_user_id=created_by_user_id, body=body)
        logger.info("discussion_reply_created", reply_id=str(reply.id), thread_id=str(thread.id))
        return reply

    async def list_replies(self, thread: DiscussionThread) -> list[DiscussionReply]:
        return await self.repo.list_replies_for_thread(thread.id)

    async def set_locked(self, thread: DiscussionThread, locked: bool) -> DiscussionThread:
        thread.is_locked = locked
        await self.db.flush()
        return thread

    async def author_names(self, user_ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
        ids = [i for i in user_ids if i is not None]
        if not ids:
            return {}
        rows = await self.db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))
        return {i: n for i, n in rows.all()}
