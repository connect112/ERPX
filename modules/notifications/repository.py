import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.notifications.models import Notification
from modules.users.models import UserProfile


class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Notification:
        notification = Notification(**fields)
        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)
        return notification

    async def bulk_create(self, rows: list[dict]) -> list[Notification]:
        notifications = [Notification(**row) for row in rows]
        self.db.add_all(notifications)
        await self.db.flush()
        for n in notifications:
            await self.db.refresh(n)
        return notifications

    async def get_by_id(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification | None:
        result = await self.db.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: uuid.UUID, unread_only: bool = False, skip: int = 0, limit: int = 50
    ) -> tuple[list[Notification], int]:
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.is_read.is_(False))
        count_result = await self.db.execute(
            select(func.count()).select_from(Notification).where(*conditions)
        )
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def unread_count(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        )
        return result.scalar_one()

    async def mark_read(self, notification: Notification) -> Notification:
        from datetime import datetime, timezone

        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(notification)
        return notification

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        from datetime import datetime, timezone

        result = await self.db.execute(
            select(Notification).where(
                Notification.user_id == user_id, Notification.is_read.is_(False)
            )
        )
        unread = list(result.scalars().all())
        now = datetime.now(timezone.utc)
        for notification in unread:
            notification.is_read = True
            notification.read_at = now
        await self.db.flush()
        return len(unread)

    async def list_user_ids_for_organization(self, organization_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self.db.execute(
            select(UserProfile.user_id).where(UserProfile.organization_id == organization_id)
        )
        return [row[0] for row in result.all()]
