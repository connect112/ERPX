import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.authentication.repository import AuthRepository
from modules.batches.repository import BatchEnrollmentRepository, BatchRepository
from modules.courses.repository import CourseRepository
from modules.lms.announcements.models import Announcement
from modules.lms.announcements.repository import AnnouncementRepository
from modules.lms.announcements.tasks import send_announcement_email_task
from modules.notifications.models import NotificationType
from modules.notifications.repository import NotificationRepository
from modules.notifications.service import NotificationService
from modules.trainers.repository import TrainerRepository

logger = get_logger(__name__)


class AnnouncementService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AnnouncementRepository(db)
        self.course_repo = CourseRepository(db)
        self.batch_repo = BatchRepository(db)
        self.batch_enrollment_repo = BatchEnrollmentRepository(db)
        self.auth_repo = AuthRepository(db)
        self.notification_repo = NotificationRepository(db)
        self.notification_service = NotificationService(db)
        self.trainer_repo = TrainerRepository(db)

    async def _resolve_recipient_user_ids(
        self, organization_id: uuid.UUID, course_id: uuid.UUID | None
    ) -> list[uuid.UUID]:
        """Org-wide (course_id=None) reaches every user in the org, same set
        Broadcast Notification already uses. Course-scoped reaches only the
        students enrolled in, and trainers teaching, a batch of that
        course -- the same audience list_for_student/list_for_trainer above
        already compute the announcement for, just inverted (who should see
        this, not what should this account see)."""
        if course_id is None:
            return await self.notification_repo.list_user_ids_for_organization(organization_id)

        batches, _total = await self.batch_repo.list_for_organization(
            organization_id, course_id=course_id, limit=10_000
        )
        batch_ids = [b.id for b in batches]

        students = await self.batch_enrollment_repo.list_students_for_batches(batch_ids, organization_id)
        student_user_ids = {s.user_id for s in students if s.user_id}

        trainer_ids = {b.trainer_id for b in batches if b.trainer_id}
        trainer_pairs = await self.trainer_repo.list_with_employee_for_ids(list(trainer_ids), organization_id)
        trainer_user_ids = {employee.user_id for _trainer, employee in trainer_pairs if employee.user_id}

        return list(student_user_ids | trainer_user_ids)

    async def _notify_recipients(
        self, organization_id: uuid.UUID, course_id: uuid.UUID | None, title: str, body: str
    ) -> None:
        user_ids = await self._resolve_recipient_user_ids(organization_id, course_id)
        if not user_ids:
            return

        rows = [
            {
                "organization_id": organization_id,
                "user_id": user_id,
                "title": title,
                "body": body,
                "notification_type": NotificationType.INFO,
                "link_url": None,
                "source": "announcement",
            }
            for user_id in user_ids
        ]
        await self.notification_repo.bulk_create(rows)

        scope_label = "org-wide" if course_id is None else "posted for a course you're in"
        users = await self.auth_repo.list_users_by_ids(user_ids)
        for user in users:
            send_announcement_email_task.delay(user.email, user.full_name, title, body, scope_label)

    async def create_announcement(
        self, organization_id: uuid.UUID, created_by_user_id: uuid.UUID, course_id: uuid.UUID | None, **fields
    ) -> Announcement:
        if course_id is not None:
            course = await self.course_repo.get_by_id(course_id, organization_id)
            if not course:
                raise NotFoundError("Course", course_id)

        announcement = await self.repo.create(
            organization_id=organization_id,
            course_id=course_id,
            created_by_user_id=created_by_user_id,
            **fields,
        )
        logger.info("announcement_created", announcement_id=str(announcement.id))
        await self._notify_recipients(organization_id, course_id, fields["title"], fields["body"])
        return announcement

    async def get_announcement(self, announcement_id: uuid.UUID, organization_id: uuid.UUID) -> Announcement:
        announcement = await self.repo.get_by_id(announcement_id, organization_id)
        if not announcement:
            raise NotFoundError("Announcement", announcement_id)
        return announcement

    async def list_announcements(
        self, organization_id: uuid.UUID, course_id: uuid.UUID | None
    ) -> list[Announcement]:
        return await self.repo.list_for_organization(organization_id, course_id)

    async def list_for_student(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> list[Announcement]:
        batch_ids = await self.batch_enrollment_repo.list_batch_ids_for_student(student_id, organization_id)
        batches = await self.batch_repo.list_for_ids(batch_ids, organization_id)
        course_ids = list({b.course_id for b in batches})
        return await self.repo.list_for_courses_or_org_wide(organization_id, course_ids)

    async def list_for_trainer(self, trainer_id: uuid.UUID, organization_id: uuid.UUID) -> list[Announcement]:
        batches = await self.batch_repo.list_for_trainer(trainer_id, organization_id)
        course_ids = list({b.course_id for b in batches})
        return await self.repo.list_for_courses_or_org_wide(organization_id, course_ids)

    async def update_announcement(
        self, announcement_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Announcement:
        announcement = await self.get_announcement(announcement_id, organization_id)
        updated = await self.repo.update(announcement, **fields)
        logger.info("announcement_updated", announcement_id=str(announcement_id))
        return updated

    async def delete_announcement(self, announcement_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        announcement = await self.get_announcement(announcement_id, organization_id)
        await self.repo.delete(announcement)
        logger.info("announcement_deleted", announcement_id=str(announcement_id))
