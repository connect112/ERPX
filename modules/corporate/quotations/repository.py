import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.corporate.quotations.models import Quotation, QuotationLine, QuotationStatus


class QuotationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, lines: list[dict], **fields) -> Quotation:
        quotation = Quotation(**fields)
        self.db.add(quotation)
        await self.db.flush()
        for line in lines:
            self.db.add(QuotationLine(quotation_id=quotation.id, **line))
        await self.db.flush()
        return await self.get_by_id(quotation.id, quotation.organization_id)

    async def replace_lines(self, quotation: Quotation, lines: list[dict]) -> None:
        for line in list(quotation.lines):
            await self.db.delete(line)
        await self.db.flush()
        for line in lines:
            self.db.add(QuotationLine(quotation_id=quotation.id, **line))
        await self.db.flush()

    async def get_by_id(self, quotation_id: uuid.UUID, organization_id: uuid.UUID) -> Quotation | None:
        result = await self.db.execute(
            select(Quotation)
            .where(Quotation.id == quotation_id, Quotation.organization_id == organization_id)
            .options(selectinload(Quotation.lines))
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, organization_id: uuid.UUID, quotation_number: str) -> Quotation | None:
        result = await self.db.execute(
            select(Quotation).where(
                Quotation.organization_id == organization_id, Quotation.quotation_number == quotation_number
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        client_id: uuid.UUID | None = None,
        status: QuotationStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Quotation], int]:
        conditions = [Quotation.organization_id == organization_id]
        if client_id is not None:
            conditions.append(Quotation.client_id == client_id)
        if status is not None:
            conditions.append(Quotation.status == status)

        count_result = await self.db.execute(select(func.count()).select_from(Quotation).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Quotation)
            .where(*conditions)
            .options(selectinload(Quotation.lines))
            .order_by(Quotation.quotation_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().unique().all()), total

    async def update(self, quotation: Quotation, **fields) -> Quotation:
        for key, value in fields.items():
            if value is not None:
                setattr(quotation, key, value)
        await self.db.flush()
        await self.db.refresh(quotation)
        return quotation
