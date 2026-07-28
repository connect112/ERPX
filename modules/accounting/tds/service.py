import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.accounting.tds.models import TDSDeduction, TDSSection
from modules.accounting.tds.repository import TDSDeductionRepository, TDSSectionRepository

logger = get_logger(__name__)


def financial_year_for(as_of: datetime) -> str:
    """Indian financial year: 1 April - 31 March."""
    if as_of.month >= 4:
        return f"{as_of.year}-{as_of.year + 1}"
    return f"{as_of.year - 1}-{as_of.year}"


class TDSService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.section_repo = TDSSectionRepository(db)
        self.deduction_repo = TDSDeductionRepository(db)

    # ---- Sections ----

    async def create_section(self, organization_id: uuid.UUID, section_code: str, **fields) -> TDSSection:
        existing = await self.section_repo.get_by_code(organization_id, section_code)
        if existing:
            raise ConflictError(f"A TDS section '{section_code}' already exists.")
        section = await self.section_repo.create(
            organization_id=organization_id, section_code=section_code, **fields
        )
        logger.info("tds_section_created", section_id=str(section.id))
        return section

    async def get_section(self, section_id: uuid.UUID, organization_id: uuid.UUID) -> TDSSection:
        section = await self.section_repo.get_by_id(section_id, organization_id)
        if not section:
            raise NotFoundError("TDS section", section_id)
        return section

    async def list_sections(self, organization_id: uuid.UUID, is_active: bool | None = None) -> list[TDSSection]:
        return await self.section_repo.list_for_organization(organization_id, is_active)

    async def update_section(
        self, section_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> TDSSection:
        section = await self.get_section(section_id, organization_id)
        updated = await self.section_repo.update(section, **fields)
        logger.info("tds_section_updated", section_id=str(section_id))
        return updated

    # ---- Deductions ----

    async def compute_and_record_deduction(
        self,
        organization_id: uuid.UUID,
        vendor_id: uuid.UUID,
        tds_section_id: uuid.UUID,
        gross_amount: float,
        deduction_date: datetime,
        payment_id: uuid.UUID | None = None,
    ) -> TDSDeduction:
        section = await self.get_section(tds_section_id, organization_id)
        financial_year = financial_year_for(deduction_date)

        cumulative = await self.deduction_repo.total_deducted_for_vendor_fy(vendor_id, financial_year)
        if (cumulative + gross_amount) < float(section.threshold_amount):
            tds_amount = 0.0
        else:
            tds_amount = round(gross_amount * float(section.rate_percent) / 100, 2)

        net_amount = round(gross_amount - tds_amount, 2)
        deduction = await self.deduction_repo.create(
            organization_id=organization_id,
            vendor_id=vendor_id,
            tds_section_id=tds_section_id,
            payment_id=payment_id,
            gross_amount=gross_amount,
            tds_amount=tds_amount,
            net_amount=net_amount,
            financial_year=financial_year,
            deduction_date=deduction_date,
        )
        logger.info(
            "tds_deduction_recorded",
            deduction_id=str(deduction.id),
            vendor_id=str(vendor_id),
            tds_amount=tds_amount,
        )
        return deduction

    async def get_deduction(self, deduction_id: uuid.UUID, organization_id: uuid.UUID) -> TDSDeduction:
        deduction = await self.deduction_repo.get_by_id(deduction_id, organization_id)
        if not deduction:
            raise NotFoundError("TDS deduction", deduction_id)
        return deduction

    async def list_deductions_for_vendor(
        self, vendor_id: uuid.UUID, financial_year: str | None = None
    ) -> list[TDSDeduction]:
        return await self.deduction_repo.list_for_vendor(vendor_id, financial_year)
