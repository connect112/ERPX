import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from modules.pentrix.achievements.models import Achievement, AchievementCriteriaType, StudentAchievement
from modules.pentrix.achievements.repository import AchievementRepository
from modules.pentrix.flags.repository import SubmissionRepository

logger = get_logger(__name__)


class AchievementService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AchievementRepository(db)
        self.submission_repo = SubmissionRepository(db)

    async def create_achievement(self, organization_id: uuid.UUID, **fields) -> Achievement:
        achievement = await self.repo.create(organization_id=organization_id, **fields)
        logger.info("achievement_created", achievement_id=str(achievement.id))
        return achievement

    async def list_achievements(self, organization_id: uuid.UUID) -> list[Achievement]:
        return await self.repo.list_for_organization(organization_id)

    async def list_for_student(self, student_id: uuid.UUID) -> list[StudentAchievement]:
        return await self.repo.list_for_student(student_id)

    async def check_and_award(
        self, student_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[StudentAchievement]:
        """
        Called after a student solves a challenge. Evaluates every
        achievement for the organization and awards any the student now
        qualifies for but doesn't already hold. Idempotent — safe to call
        after every solve.
        """
        solves = await self.submission_repo.list_for_student(student_id)
        challenges_solved = len(solves)
        total_points = sum(s.points_awarded for s in solves)

        newly_awarded: list[StudentAchievement] = []
        for achievement in await self.repo.list_for_organization(organization_id):
            if await self.repo.has_award(student_id, achievement.id):
                continue

            qualifies = (
                achievement.criteria_type == AchievementCriteriaType.CHALLENGES_SOLVED
                and challenges_solved >= achievement.criteria_value
            ) or (
                achievement.criteria_type == AchievementCriteriaType.POINTS_THRESHOLD
                and total_points >= achievement.criteria_value
            )

            if qualifies:
                award = await self.repo.award(student_id, achievement.id)
                newly_awarded.append(award)
                logger.info(
                    "achievement_awarded", student_id=str(student_id), achievement_id=str(achievement.id)
                )

        return newly_awarded
