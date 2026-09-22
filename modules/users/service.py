import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.authentication.models import User
from modules.authentication.repository import AuthRepository
from modules.organizations.repository import OrganizationRepository
from modules.users.models import UserProfile
from modules.users.repository import UserProfileRepository

logger = get_logger(__name__)


class UserProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserProfileRepository(db)
        self.auth_repo = AuthRepository(db)
        self.org_repo = OrganizationRepository(db)

    async def create_profile(self, organization_id: uuid.UUID, **fields) -> UserProfile:
        user = await self.auth_repo.get_user_by_id(fields["user_id"])
        if not user:
            raise NotFoundError("User", fields["user_id"])

        org = await self.org_repo.get_by_id(organization_id)
        if not org:
            raise NotFoundError("Organization", organization_id)

        existing = await self.repo.get_by_user_id(fields["user_id"])
        if existing:
            raise ConflictError("This user already has a profile.")

        profile = await self.repo.create(organization_id=organization_id, **fields)
        logger.info("user_profile_created", user_id=str(fields["user_id"]), org_id=str(org.id))
        return profile

    async def _get_owned_profile(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> UserProfile:
        profile = await self.repo.get_by_user_id(user_id)
        if not profile or profile.organization_id != organization_id:
            # 404, not 403 — don't confirm another org's user even exists.
            raise NotFoundError("User profile", user_id)
        return profile

    async def get_profile_by_user_id(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> UserProfile:
        return await self._get_owned_profile(user_id, organization_id)

    async def list_profiles_for_organization(
        self, organization_id: uuid.UUID, skip: int, limit: int
    ) -> list[UserProfile]:
        return await self.repo.list_for_organization(organization_id, skip, limit)

    async def list_users_for_organization(
        self, organization_id: uuid.UUID, skip: int, limit: int
    ) -> list[tuple[User, UserProfile]]:
        return await self.repo.list_with_users_for_organization(organization_id, skip, limit)

    async def update_profile(self, user_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> UserProfile:
        profile = await self._get_owned_profile(user_id, organization_id)
        updated = await self.repo.update(profile, **fields)
        logger.info("user_profile_updated", user_id=str(user_id))
        return updated
