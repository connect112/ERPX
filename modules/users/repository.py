import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.authentication.models import User
from modules.users.models import UserProfile


class UserProfileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count_for_organization(self, organization_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(UserProfile)
            .where(UserProfile.organization_id == organization_id)
        )
        return result.scalar_one()

    async def list_with_users_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[tuple[User, UserProfile]]:
        result = await self.db.execute(
            select(User, UserProfile)
            .join(UserProfile, UserProfile.user_id == User.id)
            .where(UserProfile.organization_id == organization_id, User.deleted_at.is_(None))
            .order_by(User.full_name)
            .offset(skip)
            .limit(limit)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def create(self, **fields) -> UserProfile:
        profile = UserProfile(**fields)
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def get_by_user_id(self, user_id: uuid.UUID) -> UserProfile | None:
        result = await self.db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        return result.scalar_one_or_none()

    async def get_by_external_reference(self, external_reference: str) -> UserProfile | None:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.external_reference == external_reference)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, profile_id: uuid.UUID) -> UserProfile | None:
        result = await self.db.execute(select(UserProfile).where(UserProfile.id == profile_id))
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[UserProfile]:
        result = await self.db.execute(
            select(UserProfile)
            .where(UserProfile.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, profile: UserProfile, **fields) -> UserProfile:
        for key, value in fields.items():
            if value is not None:
                setattr(profile, key, value)
        await self.db.flush()
        return profile
