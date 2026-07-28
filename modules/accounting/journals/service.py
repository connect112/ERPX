import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.journals.models import (
    JournalEntry,
    JournalEntryStatus,
    JournalSourceModule,
)
from modules.accounting.journals.repository import JournalRepository
from modules.accounting.ledger.repository import AccountRepository

logger = get_logger(__name__)


def _assert_balanced(lines: list[dict]) -> None:
    if len(lines) < 2:
        raise ValidationError("A journal entry must have at least two lines.")
    total_debit = round(sum(float(l.get("debit", 0)) for l in lines), 2)
    total_credit = round(sum(float(l.get("credit", 0)) for l in lines), 2)
    if total_debit != total_credit:
        raise ValidationError(
            f"Journal entry is not balanced: total debit {total_debit} != total credit {total_credit}."
        )


class JournalService:
    """
    Central posting engine. Every module that touches money (Invoices,
    Receipts, Expenses, Payments, Bank) creates its GL postings by calling
    `post_transaction`, never by writing JournalEntry/JournalLine rows
    directly — this is the one place the debit == credit invariant, the
    entry numbering sequence, and account-existence validation are
    enforced.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = JournalRepository(db)
        self.account_repo = AccountRepository(db)

    async def post_transaction(
        self,
        organization_id: uuid.UUID,
        entry_date: datetime,
        memo: str | None,
        source_module: JournalSourceModule,
        lines: list[dict],
        source_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        created_by_user_id: uuid.UUID | None = None,
    ) -> JournalEntry:
        _assert_balanced(lines)

        for line in lines:
            account = await self.account_repo.get_by_id(line["account_id"], organization_id)
            if not account:
                raise NotFoundError("Account", line["account_id"])
            if not account.is_active:
                raise ValidationError(f"Account '{account.code}' is inactive and cannot be posted to.")

        entry_number = await self.repo.next_entry_number(organization_id)
        entry = await self.repo.create_entry(
            lines=lines,
            organization_id=organization_id,
            branch_id=branch_id,
            entry_number=entry_number,
            entry_date=entry_date,
            memo=memo,
            source_module=source_module,
            source_id=source_id,
            status=JournalEntryStatus.POSTED,
            posted_at=datetime.now(timezone.utc),
            created_by_user_id=created_by_user_id,
        )
        logger.info(
            "journal_entry_posted",
            entry_id=str(entry.id),
            entry_number=entry_number,
            source_module=source_module.value,
        )
        return entry

    async def create_manual_draft(
        self,
        organization_id: uuid.UUID,
        entry_date: datetime,
        memo: str | None,
        lines: list[dict],
        branch_id: uuid.UUID | None = None,
        created_by_user_id: uuid.UUID | None = None,
    ) -> JournalEntry:
        _assert_balanced(lines)
        for line in lines:
            account = await self.account_repo.get_by_id(line["account_id"], organization_id)
            if not account:
                raise NotFoundError("Account", line["account_id"])

        entry_number = await self.repo.next_entry_number(organization_id)
        entry = await self.repo.create_entry(
            lines=lines,
            organization_id=organization_id,
            branch_id=branch_id,
            entry_number=entry_number,
            entry_date=entry_date,
            memo=memo,
            source_module=JournalSourceModule.MANUAL,
            source_id=None,
            status=JournalEntryStatus.DRAFT,
            created_by_user_id=created_by_user_id,
        )
        logger.info("journal_entry_draft_created", entry_id=str(entry.id))
        return entry

    async def post_draft_entry(self, entry_id: uuid.UUID, organization_id: uuid.UUID) -> JournalEntry:
        entry = await self.get_entry(entry_id, organization_id)
        if entry.status != JournalEntryStatus.DRAFT:
            raise ValidationError(f"Only draft entries can be posted (this entry is '{entry.status.value}').")
        posted = await self.repo.mark_posted(entry, datetime.now(timezone.utc))
        logger.info("journal_entry_posted", entry_id=str(entry_id))
        return posted

    async def reverse_entry(
        self, entry_id: uuid.UUID, organization_id: uuid.UUID, memo: str | None = None
    ) -> JournalEntry:
        original = await self.get_entry(entry_id, organization_id)
        if original.status != JournalEntryStatus.POSTED:
            raise ValidationError("Only posted entries can be reversed.")

        reversal_lines = [
            {
                "account_id": line.account_id,
                "description": line.description,
                "debit": line.credit,
                "credit": line.debit,
            }
            for line in original.lines
        ]
        reversal = await self.post_transaction(
            organization_id=organization_id,
            entry_date=datetime.now(timezone.utc),
            memo=memo or f"Reversal of {original.entry_number}",
            source_module=original.source_module,
            source_id=original.source_id,
            lines=reversal_lines,
            branch_id=original.branch_id,
        )
        await self.repo.mark_reversed(original, reversal.id)
        logger.info("journal_entry_reversed", entry_id=str(entry_id), reversal_id=str(reversal.id))
        return reversal

    async def get_entry(self, entry_id: uuid.UUID, organization_id: uuid.UUID) -> JournalEntry:
        entry = await self.repo.get_by_id(entry_id, organization_id)
        if not entry:
            raise NotFoundError("Journal entry", entry_id)
        return entry

    async def list_entries(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)
