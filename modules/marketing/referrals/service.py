import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.marketing.referrals.models import Referral, ReferralProgram, ReferralStatus
from modules.marketing.referrals.repository import ReferralProgramRepository, ReferralRepository
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class ReferralProgramService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ReferralProgramRepository(db)

    async def create_program(self, organization_id: uuid.UUID, code: str, **fields) -> ReferralProgram:
        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"A referral program with code '{code}' already exists.")
        program = await self.repo.create(organization_id=organization_id, code=code, **fields)
        logger.info("referral_program_created", program_id=str(program.id))
        return program

    async def get_program(self, program_id: uuid.UUID, organization_id: uuid.UUID) -> ReferralProgram:
        program = await self.repo.get_by_id(program_id, organization_id)
        if not program:
            raise NotFoundError("Referral program", program_id)
        return program

    async def list_programs(self, organization_id: uuid.UUID, is_active: bool | None = None) -> list[ReferralProgram]:
        return await self.repo.list_for_organization(organization_id, is_active)

    async def update_program(self, program_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> ReferralProgram:
        program = await self.get_program(program_id, organization_id)
        updated = await self.repo.update(program, **fields)
        logger.info("referral_program_updated", program_id=str(program_id))
        return updated


class ReferralService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ReferralRepository(db)
        self.program_repo = ReferralProgramRepository(db)
        self.student_repo = StudentRepository(db)

    async def create_referral(
        self,
        organization_id: uuid.UUID,
        referral_program_id: uuid.UUID,
        referrer_student_id: uuid.UUID | None = None,
        **fields,
    ) -> Referral:
        program = await self.program_repo.get_by_id(referral_program_id, organization_id)
        if not program:
            raise NotFoundError("Referral program", referral_program_id)
        if not program.is_active:
            raise ValidationError("This referral program is not currently active.")
        if program.valid_until is not None and date.today() > program.valid_until:
            raise ValidationError("This referral program has expired.")

        if referrer_student_id is not None:
            student = await self.student_repo.get_by_id(referrer_student_id, organization_id)
            if not student:
                raise NotFoundError("Student", referrer_student_id)
            if program.max_referrals_per_referrer is not None:
                existing_count = await self.repo.count_for_referrer(referral_program_id, referrer_student_id)
                if existing_count >= program.max_referrals_per_referrer:
                    raise ValidationError(
                        f"This referrer has reached the maximum of {program.max_referrals_per_referrer} referral(s) for this program."
                    )

        referral = await self.repo.create(
            organization_id=organization_id,
            referral_program_id=referral_program_id,
            referrer_student_id=referrer_student_id,
            **fields,
        )
        logger.info("referral_created", referral_id=str(referral.id), program_id=str(referral_program_id))
        return referral

    async def get_referral(self, referral_id: uuid.UUID, organization_id: uuid.UUID) -> Referral:
        referral = await self.repo.get_by_id(referral_id, organization_id)
        if not referral:
            raise NotFoundError("Referral", referral_id)
        return referral

    async def list_referrals(self, organization_id: uuid.UUID, **filters) -> tuple[list[Referral], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def list_for_referrer(self, referrer_student_id: uuid.UUID, organization_id: uuid.UUID) -> list[Referral]:
        student = await self.student_repo.get_by_id(referrer_student_id, organization_id)
        if not student:
            raise NotFoundError("Student", referrer_student_id)
        return await self.repo.list_for_referrer(referrer_student_id)

    async def mark_converted(
        self, referral_id: uuid.UUID, organization_id: uuid.UUID, converted_lead_id: uuid.UUID
    ) -> Referral:
        referral = await self.get_referral(referral_id, organization_id)
        if referral.status != ReferralStatus.PENDING:
            raise ValidationError(f"Only pending referrals can be converted (this one is '{referral.status.value}').")
        updated = await self.repo.update(
            referral, status=ReferralStatus.CONVERTED, converted_lead_id=converted_lead_id
        )
        logger.info("referral_converted", referral_id=str(referral_id))
        return updated

    async def mark_rewarded(self, referral_id: uuid.UUID, organization_id: uuid.UUID) -> Referral:
        referral = await self.get_referral(referral_id, organization_id)
        if referral.status != ReferralStatus.CONVERTED:
            raise ValidationError("Only converted referrals can be marked rewarded.")
        program = await self.program_repo.get_by_id(referral.referral_program_id, organization_id)
        updated = await self.repo.update(
            referral,
            status=ReferralStatus.REWARDED,
            reward_amount=program.referrer_reward_amount,
            rewarded_at=datetime.now(timezone.utc),
        )
        logger.info("referral_rewarded", referral_id=str(referral_id), reward_amount=float(program.referrer_reward_amount))
        return updated

    async def reject_referral(self, referral_id: uuid.UUID, organization_id: uuid.UUID) -> Referral:
        referral = await self.get_referral(referral_id, organization_id)
        if referral.status != ReferralStatus.PENDING:
            raise ValidationError("Only pending referrals can be rejected.")
        updated = await self.repo.update(referral, status=ReferralStatus.REJECTED)
        logger.info("referral_rejected", referral_id=str(referral_id))
        return updated
