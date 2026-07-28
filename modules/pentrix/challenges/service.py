import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.pentrix.challenges.models import Challenge
from modules.pentrix.challenges.repository import ChallengeRepository
from modules.pentrix.labs.repository import LabRepository

logger = get_logger(__name__)


class ChallengeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ChallengeRepository(db)
        self.lab_repo = LabRepository(db)

    async def create_challenge(self, organization_id: uuid.UUID, **fields) -> Challenge:
        lab_id = fields.get("lab_id")
        if lab_id is not None:
            lab = await self.lab_repo.get_by_id(lab_id, organization_id)
            if not lab:
                raise NotFoundError("Lab", lab_id)
        challenge = await self.repo.create(organization_id=organization_id, **fields)
        logger.info("challenge_created", challenge_id=str(challenge.id))
        return challenge

    async def get_challenge(self, challenge_id: uuid.UUID, organization_id: uuid.UUID) -> Challenge:
        challenge = await self.repo.get_by_id(challenge_id, organization_id)
        if not challenge:
            raise NotFoundError("Challenge", challenge_id)
        return challenge

    async def list_challenges(
        self, organization_id: uuid.UUID, category: str | None
    ) -> list[Challenge]:
        return await self.repo.list_for_organization(organization_id, category)

    async def update_challenge(
        self, challenge_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Challenge:
        challenge = await self.get_challenge(challenge_id, organization_id)
        updated = await self.repo.update(challenge, **fields)
        logger.info("challenge_updated", challenge_id=str(challenge_id))
        return updated

    async def delete_challenge(self, challenge_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        challenge = await self.get_challenge(challenge_id, organization_id)
        await self.repo.delete(challenge)
        logger.info("challenge_deleted", challenge_id=str(challenge_id))
