import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.pentrix.challenges.repository import ChallengeRepository
from modules.pentrix.hints.models import Hint
from modules.pentrix.hints.repository import HintRepository
from modules.pentrix.hints.schemas import HintLocked, HintUnlockResponse
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class HintService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = HintRepository(db)
        self.challenge_repo = ChallengeRepository(db)
        self.student_repo = StudentRepository(db)

    async def create_hint(
        self, challenge_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Hint:
        challenge = await self.challenge_repo.get_by_id(challenge_id, organization_id)
        if not challenge:
            raise NotFoundError("Challenge", challenge_id)
        hint = await self.repo.create(challenge_id=challenge_id, **fields)
        logger.info("hint_created", hint_id=str(hint.id))
        return hint

    async def list_hints_for_student(
        self, challenge_id: uuid.UUID, organization_id: uuid.UUID, student_id: uuid.UUID
    ) -> list[HintLocked]:
        challenge = await self.challenge_repo.get_by_id(challenge_id, organization_id)
        if not challenge:
            raise NotFoundError("Challenge", challenge_id)

        hints = await self.repo.list_for_challenge(challenge_id)
        unlocked_ids = await self.repo.list_unlocked_hint_ids(student_id, challenge_id)

        return [
            HintLocked(
                id=h.id,
                challenge_id=h.challenge_id,
                point_cost=h.point_cost,
                order_index=h.order_index,
                unlocked=h.id in unlocked_ids,
            )
            for h in hints
        ]

    async def unlock_hint(
        self, hint_id: uuid.UUID, organization_id: uuid.UUID, student_id: uuid.UUID
    ) -> HintUnlockResponse:
        hint = await self.repo.get_by_id(hint_id)
        if not hint:
            raise NotFoundError("Hint", hint_id)
        challenge = await self.challenge_repo.get_by_id(hint.challenge_id, organization_id)
        if not challenge:
            raise NotFoundError("Hint", hint_id)

        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        existing = await self.repo.get_unlock(student_id, hint_id)
        if not existing:
            await self.repo.unlock(student_id, hint_id)
            logger.info("hint_unlocked", hint_id=str(hint_id), student_id=str(student_id))

        return HintUnlockResponse(hint_id=hint.id, hint_text=hint.hint_text, point_cost=hint.point_cost)
