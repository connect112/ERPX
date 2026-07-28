import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.lms.discussions.models import DiscussionReply, DiscussionThread
from modules.lms.discussions.repository import DiscussionRepository

logger = get_logger(__name__)


class DiscussionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DiscussionRepository(db)
        self.course_repo = CourseRepository(db)

    async def create_thread(
        self, course_id: uuid.UUID, organization_id: uuid.UUID, created_by_user_id: uuid.UUID, **fields
    ) -> DiscussionThread:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        thread = await self.repo.create_thread(
            course_id=course_id, created_by_user_id=created_by_user_id, **fields
        )
        logger.info("discussion_thread_created", thread_id=str(thread.id))
        return thread

    async def list_threads(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> list[DiscussionThread]:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        return await self.repo.list_threads_for_course(course_id)

    async def _get_owned_thread(
        self, thread_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> DiscussionThread:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        thread = await self.repo.get_thread_by_id(thread_id)
        if not thread or thread.course_id != course_id:
            raise NotFoundError("Discussion thread", thread_id)
        return thread

    async def reply(
        self,
        thread_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        created_by_user_id: uuid.UUID,
        body: str,
    ) -> DiscussionReply:
        thread = await self._get_owned_thread(thread_id, course_id, organization_id)
        if thread.is_locked:
            raise ValidationError("This discussion thread is locked and no longer accepting replies.")
        reply = await self.repo.create_reply(
            thread_id=thread_id, created_by_user_id=created_by_user_id, body=body
        )
        logger.info("discussion_reply_created", reply_id=str(reply.id), thread_id=str(thread_id))
        return reply

    async def list_replies(
        self, thread_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[DiscussionReply]:
        await self._get_owned_thread(thread_id, course_id, organization_id)
        return await self.repo.list_replies_for_thread(thread_id)
