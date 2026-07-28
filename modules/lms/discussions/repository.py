import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.lms.discussions.models import DiscussionReply, DiscussionThread


class DiscussionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_thread(self, **fields) -> DiscussionThread:
        thread = DiscussionThread(**fields)
        self.db.add(thread)
        await self.db.flush()
        await self.db.refresh(thread)
        return thread

    async def get_thread_by_id(self, thread_id: uuid.UUID) -> DiscussionThread | None:
        result = await self.db.execute(
            select(DiscussionThread).where(DiscussionThread.id == thread_id)
        )
        return result.scalar_one_or_none()

    async def list_threads_for_course(self, course_id: uuid.UUID) -> list[DiscussionThread]:
        result = await self.db.execute(
            select(DiscussionThread)
            .where(DiscussionThread.course_id == course_id)
            .order_by(DiscussionThread.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_reply(self, **fields) -> DiscussionReply:
        reply = DiscussionReply(**fields)
        self.db.add(reply)
        await self.db.flush()
        await self.db.refresh(reply)
        return reply

    async def list_replies_for_thread(self, thread_id: uuid.UUID) -> list[DiscussionReply]:
        result = await self.db.execute(
            select(DiscussionReply)
            .where(DiscussionReply.thread_id == thread_id)
            .order_by(DiscussionReply.created_at)
        )
        return list(result.scalars().all())
