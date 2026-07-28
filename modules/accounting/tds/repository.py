import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.tds.models import TDSDeduction, TDSSection


class TDSSectionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> TDSSection:
        section = TDSSection(**fields)
        self.db.add(section)
        await self.db.flush()
        await self.db.refresh(section)
        return section

    async def get_by_id(self, section_id: uuid.UUID, organization_id: uuid.UUID) -> TDSSection | None:
        result = await self.db.execute(
            select(TDSSection).where(
                TDSSection.id == section_id, TDSSection.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, section_code: str) -> TDSSection | None:
        result = await self.db.execute(
            select(TDSSection).where(
                TDSSection.organization_id == organization_id, TDSSection.section_code == section_code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[TDSSection]:
        conditions = [TDSSection.organization_id == organization_id]
        if is_active is not None:
            conditions.append(TDSSection.is_active == is_active)
        result = await self.db.execute(
            select(TDSSection).where(*conditions).order_by(TDSSection.section_code.asc())
        )
        return list(result.scalars().all())

    async def update(self, section: TDSSection, **fields) -> TDSSection:
        for key, value in fields.items():
            if value is not None:
                setattr(section, key, value)
        await self.db.flush()
        await self.db.refresh(section)
        return section


class TDSDeductionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> TDSDeduction:
        deduction = TDSDeduction(**fields)
        self.db.add(deduction)
        await self.db.flush()
        await self.db.refresh(deduction)
        return deduction

    async def get_by_id(self, deduction_id: uuid.UUID, organization_id: uuid.UUID) -> TDSDeduction | None:
        result = await self.db.execute(
            select(TDSDeduction).where(
                TDSDeduction.id == deduction_id, TDSDeduction.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_vendor(self, vendor_id: uuid.UUID, financial_year: str | None = None) -> list[TDSDeduction]:
        conditions = [TDSDeduction.vendor_id == vendor_id]
        if financial_year:
            conditions.append(TDSDeduction.financial_year == financial_year)
        result = await self.db.execute(
            select(TDSDeduction).where(*conditions).order_by(TDSDeduction.deduction_date.desc())
        )
        return list(result.scalars().all())

    async def total_deducted_for_vendor_fy(self, vendor_id: uuid.UUID, financial_year: str) -> float:
        result = await self.db.execute(
            select(func.coalesce(func.sum(TDSDeduction.gross_amount), 0)).where(
                TDSDeduction.vendor_id == vendor_id, TDSDeduction.financial_year == financial_year
            )
        )
        return float(result.scalar_one())
