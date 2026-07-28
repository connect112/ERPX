import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.lms.badges.models import Badge, StudentBadge
from modules.lms.badges.repository import BadgeRepository
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class BadgeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BadgeRepository(db)
        self.student_repo = StudentRepository(db)

    async def create_badge(self, organization_id: uuid.UUID, **fields) -> Badge:
        badge = await self.repo.create(organization_id=organization_id, **fields)
        logger.info("badge_created", badge_id=str(badge.id))
        return badge

    async def list_badges(self, organization_id: uuid.UUID) -> list[Badge]:
        return await self.repo.list_for_organization(organization_id)

    async def award_badge(
        self, organization_id: uuid.UUID, student_id: uuid.UUID, badge_id: uuid.UUID
    ) -> StudentBadge:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        badge = await self.repo.get_by_id(badge_id, organization_id)
        if not badge:
            raise NotFoundError("Badge", badge_id)

        existing = await self.repo.get_award(student_id, badge_id)
        if existing:
            raise ConflictError("This student already has this badge.")

        award = await self.repo.award(student_id, badge_id)
        logger.info("badge_awarded", student_id=str(student_id), badge_id=str(badge_id))
        return award

    async def list_student_badges(
        self, organization_id: uuid.UUID, student_id: uuid.UUID
    ) -> list[StudentBadge]:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        return await self.repo.list_for_student(student_id)
