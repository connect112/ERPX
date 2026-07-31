import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.marketing.referrals.models import Referral, ReferralProgram, ReferralStatus


class ReferralProgramRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> ReferralProgram:
        program = ReferralProgram(**fields)
        self.db.add(program)
        await self.db.flush()
        await self.db.refresh(program)
        return program

    async def get_by_id(self, program_id: uuid.UUID, organization_id: uuid.UUID) -> ReferralProgram | None:
        result = await self.db.execute(
            select(ReferralProgram).where(
                ReferralProgram.id == program_id, ReferralProgram.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> ReferralProgram | None:
        result = await self.db.execute(
            select(ReferralProgram).where(
                ReferralProgram.organization_id == organization_id, ReferralProgram.code == code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[ReferralProgram]:
        conditions = [ReferralProgram.organization_id == organization_id]
        if is_active is not None:
            conditions.append(ReferralProgram.is_active == is_active)
        result = await self.db.execute(
            select(ReferralProgram).where(*conditions).order_by(ReferralProgram.name.asc())
        )
        return list(result.scalars().all())

    async def update(self, program: ReferralProgram, **fields) -> ReferralProgram:
        for key, value in fields.items():
            if value is not None:
                setattr(program, key, value)
        await self.db.flush()
        await self.db.refresh(program)
        return program


class ReferralRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Referral:
        referral = Referral(**fields)
        self.db.add(referral)
        await self.db.flush()
        await self.db.refresh(referral)
        return referral

    async def get_by_id(self, referral_id: uuid.UUID, organization_id: uuid.UUID) -> Referral | None:
        result = await self.db.execute(
            select(Referral).where(Referral.id == referral_id, Referral.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def count_for_referrer(self, referral_program_id: uuid.UUID, referrer_student_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Referral)
            .where(
                Referral.referral_program_id == referral_program_id,
                Referral.referrer_student_id == referrer_student_id,
            )
        )
        return result.scalar_one()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        referral_program_id: uuid.UUID | None = None,
        status: ReferralStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Referral], int]:
        conditions = [Referral.organization_id == organization_id]
        if referral_program_id is not None:
            conditions.append(Referral.referral_program_id == referral_program_id)
        if status is not None:
            conditions.append(Referral.status == status)

        count_result = await self.db.execute(select(func.count()).select_from(Referral).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Referral).where(*conditions).order_by(Referral.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def status_breakdown_for_organization(
        self, organization_id: uuid.UUID
    ) -> dict[ReferralStatus, int]:
        """Referral counts grouped by status for one org, in a single query.

        Replaces materialising the whole referral list only to tally statuses in
        Python — the sum of the values is the org's total referral count, and
        individual buckets give the converted/rewarded figures. Only statuses
        that actually occur are returned; callers default the rest to 0."""
        result = await self.db.execute(
            select(Referral.status, func.count())
            .where(Referral.organization_id == organization_id)
            .group_by(Referral.status)
        )
        return {
            (status if isinstance(status, ReferralStatus) else ReferralStatus(status)): int(count)
            for status, count in result.all()
        }

    async def list_for_referrer(self, referrer_student_id: uuid.UUID) -> list[Referral]:
        result = await self.db.execute(
            select(Referral).where(Referral.referrer_student_id == referrer_student_id)
        )
        return list(result.scalars().all())

    async def update(self, referral: Referral, **fields) -> Referral:
        for key, value in fields.items():
            if value is not None:
                setattr(referral, key, value)
        await self.db.flush()
        await self.db.refresh(referral)
        return referral
