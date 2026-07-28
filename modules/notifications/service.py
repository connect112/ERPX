import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.notifications.models import Notification, NotificationType
from modules.notifications.repository import NotificationRepository

logger = get_logger(__name__)


class NotificationService:
    """
    The reusable entry point: any module can `NotificationService(db).create_notification(...)`
    to put something in a user's tray without knowing anything about how
    notifications are displayed or delivered.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = NotificationRepository(db)

    async def create_notification(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        body: str | None = None,
        notification_type: NotificationType = NotificationType.INFO,
        link_url: str | None = None,
        source: str | None = None,
    ) -> Notification:
        notification = await self.repo.create(
            organization_id=organization_id,
            user_id=user_id,
            title=title,
            body=body,
            notification_type=notification_type,
            link_url=link_url,
            source=source,
        )
        logger.info("notification_created", notification_id=str(notification.id), user_id=str(user_id))
        return notification

    async def broadcast_to_organization(
        self,
        organization_id: uuid.UUID,
        title: str,
        body: str | None = None,
        notification_type: NotificationType = NotificationType.INFO,
        link_url: str | None = None,
        source: str | None = "broadcast",
    ) -> int:
        user_ids = await self.repo.list_user_ids_for_organization(organization_id)
        if not user_ids:
            return 0
        rows = [
            {
                "organization_id": organization_id,
                "user_id": user_id,
                "title": title,
                "body": body,
                "notification_type": notification_type,
                "link_url": link_url,
                "source": source,
            }
            for user_id in user_ids
        ]
        created = await self.repo.bulk_create(rows)
        logger.info("notification_broadcast", organization_id=str(organization_id), count=len(created))
        return len(created)

    async def list_for_user(self, user_id: uuid.UUID, **filters):
        return await self.repo.list_for_user(user_id, **filters)

    async def unread_count(self, user_id: uuid.UUID) -> int:
        return await self.repo.unread_count(user_id)

    async def mark_read(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification:
        notification = await self.repo.get_by_id(notification_id, user_id)
        if not notification:
            raise NotFoundError("Notification", notification_id)
        return await self.repo.mark_read(notification)

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        return await self.repo.mark_all_read(user_id)
