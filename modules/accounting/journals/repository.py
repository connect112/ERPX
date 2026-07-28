import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.accounting.journals.models import (
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
    JournalSourceModule,
)


class JournalRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_entry(self, lines: list[dict], **fields) -> JournalEntry:
        entry = JournalEntry(**fields)
        self.db.add(entry)
        await self.db.flush()

        for index, line in enumerate(lines):
            self.db.add(JournalLine(journal_entry_id=entry.id, line_order=index, **line))
        await self.db.flush()
        return await self.get_by_id(entry.id, entry.organization_id)

    async def get_by_id(self, entry_id: uuid.UUID, organization_id: uuid.UUID) -> JournalEntry | None:
        result = await self.db.execute(
            select(JournalEntry)
            .where(JournalEntry.id == entry_id, JournalEntry.organization_id == organization_id)
            .options(selectinload(JournalEntry.lines))
        )
        return result.scalar_one_or_none()

    async def count_for_organization(self, organization_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(JournalEntry).where(JournalEntry.organization_id == organization_id)
        )
        return result.scalar_one()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: JournalEntryStatus | None = None,
        source_module: JournalSourceModule | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[JournalEntry], int]:
        conditions = [JournalEntry.organization_id == organization_id]
        if status is not None:
            conditions.append(JournalEntry.status == status)
        if source_module is not None:
            conditions.append(JournalEntry.source_module == source_module)
        if date_from is not None:
            conditions.append(JournalEntry.entry_date >= date_from)
        if date_to is not None:
            conditions.append(JournalEntry.entry_date <= date_to)

        count_result = await self.db.execute(
            select(func.count()).select_from(JournalEntry).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(JournalEntry)
            .where(*conditions)
            .options(selectinload(JournalEntry.lines))
            .order_by(JournalEntry.entry_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().unique().all()), total

    async def mark_posted(self, entry: JournalEntry, posted_at: datetime) -> JournalEntry:
        entry.status = JournalEntryStatus.POSTED
        entry.posted_at = posted_at
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def mark_reversed(self, entry: JournalEntry, reversed_by_entry_id: uuid.UUID) -> JournalEntry:
        entry.status = JournalEntryStatus.REVERSED
        entry.reversed_by_entry_id = reversed_by_entry_id
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def next_entry_number(self, organization_id: uuid.UUID) -> str:
        total = await self.count_for_organization(organization_id)
        return f"JE-{total + 1:06d}"
