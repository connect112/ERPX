import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.expenses.models import Expense, ExpenseStatus
from modules.accounting.expenses.repository import ExpenseRepository
from modules.accounting.gst.service import GSTService
from modules.accounting.journals.models import JournalSourceModule
from modules.accounting.journals.service import JournalService
from modules.accounting.vendors.repository import VendorRepository

logger = get_logger(__name__)

_TERMINAL_STATUSES = {ExpenseStatus.PAID, ExpenseStatus.REJECTED, ExpenseStatus.CANCELLED}


class ExpenseService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ExpenseRepository(db)
        self.vendor_repo = VendorRepository(db)
        self.gst_service = GSTService(db)
        self.journal_service = JournalService(db)

    async def create_expense(
        self,
        organization_id: uuid.UUID,
        vendor_id: uuid.UUID,
        expense_number: str,
        subtotal_amount: float,
        gst_rate_id: uuid.UUID | None = None,
        is_interstate: bool = False,
        **fields,
    ) -> Expense:
        vendor = await self.vendor_repo.get_by_id(vendor_id, organization_id)
        if not vendor:
            raise NotFoundError("Vendor", vendor_id)

        existing = await self.repo.get_by_number(organization_id, expense_number)
        if existing:
            raise ConflictError(f"An expense with number '{expense_number}' already exists.")

        tax_amount = 0.0
        if gst_rate_id is not None:
            tax_result = await self.gst_service.compute_tax(
                organization_id, subtotal_amount, gst_rate_id, is_interstate
            )
            tax_amount = tax_result["total_tax"]

        total_amount = round(subtotal_amount + tax_amount, 2)

        expense = await self.repo.create(
            organization_id=organization_id,
            vendor_id=vendor_id,
            expense_number=expense_number,
            subtotal_amount=subtotal_amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            gst_rate_id=gst_rate_id,
            is_interstate=is_interstate,
            **fields,
        )
        logger.info("expense_created", expense_id=str(expense.id), expense_number=expense_number)
        return expense

    async def get_expense(self, expense_id: uuid.UUID, organization_id: uuid.UUID) -> Expense:
        expense = await self.repo.get_by_id(expense_id, organization_id)
        if not expense:
            raise NotFoundError("Expense", expense_id)
        return expense

    async def list_expenses(self, organization_id: uuid.UUID, **filters) -> tuple[list[Expense], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_expense(
        self, expense_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Expense:
        expense = await self.get_expense(expense_id, organization_id)
        if expense.status != ExpenseStatus.DRAFT:
            raise ValidationError("Only draft expenses can be edited.")

        subtotal_amount = fields.get("subtotal_amount", expense.subtotal_amount)
        gst_rate_id = fields.get("gst_rate_id", expense.gst_rate_id)
        is_interstate = fields.get("is_interstate", expense.is_interstate)

        tax_amount = 0.0
        if gst_rate_id is not None:
            tax_result = await self.gst_service.compute_tax(
                organization_id, float(subtotal_amount), gst_rate_id, is_interstate
            )
            tax_amount = tax_result["total_tax"]
        fields["tax_amount"] = tax_amount
        fields["total_amount"] = round(float(subtotal_amount) + tax_amount, 2)

        updated = await self.repo.update(expense, **fields)
        logger.info("expense_updated", expense_id=str(expense_id))
        return updated

    async def approve_expense(
        self, expense_id: uuid.UUID, organization_id: uuid.UUID, approved_by_user_id: uuid.UUID
    ) -> Expense:
        expense = await self.get_expense(expense_id, organization_id)
        if expense.status != ExpenseStatus.DRAFT:
            raise ValidationError(f"Only draft expenses can be approved (this one is '{expense.status.value}').")

        lines = [{"account_id": expense.expense_account_id, "debit": float(expense.subtotal_amount), "credit": 0}]
        if float(expense.tax_amount) > 0:
            lines.append(
                {"account_id": expense.input_tax_credit_account_id, "debit": float(expense.tax_amount), "credit": 0}
            )
        lines.append({"account_id": expense.payable_account_id, "debit": 0, "credit": float(expense.total_amount)})

        entry = await self.journal_service.post_transaction(
            organization_id=organization_id,
            entry_date=expense.expense_date,
            memo=f"Expense {expense.expense_number}",
            source_module=JournalSourceModule.EXPENSES,
            source_id=expense.id,
            lines=lines,
            branch_id=expense.branch_id,
            created_by_user_id=approved_by_user_id,
        )

        updated = await self.repo.update(
            expense,
            status=ExpenseStatus.APPROVED,
            journal_entry_id=entry.id,
            approved_by_user_id=approved_by_user_id,
            approved_at=datetime.now(timezone.utc),
        )
        logger.info("expense_approved", expense_id=str(expense_id), journal_entry_id=str(entry.id))
        return updated

    async def reject_expense(
        self, expense_id: uuid.UUID, organization_id: uuid.UUID, rejection_reason: str
    ) -> Expense:
        expense = await self.get_expense(expense_id, organization_id)
        if expense.status != ExpenseStatus.DRAFT:
            raise ValidationError("Only draft expenses can be rejected.")
        updated = await self.repo.update(
            expense, status=ExpenseStatus.REJECTED, rejection_reason=rejection_reason
        )
        logger.info("expense_rejected", expense_id=str(expense_id))
        return updated

    async def cancel_expense(self, expense_id: uuid.UUID, organization_id: uuid.UUID) -> Expense:
        expense = await self.get_expense(expense_id, organization_id)
        if expense.status in _TERMINAL_STATUSES:
            raise ValidationError(f"An expense that is '{expense.status.value}' cannot be cancelled.")
        if float(expense.amount_paid) > 0:
            raise ValidationError(
                "This expense has recorded payments; void the associated payments before cancelling."
            )
        if expense.journal_entry_id is not None:
            await self.journal_service.reverse_entry(
                expense.journal_entry_id, organization_id, memo=f"Cancellation of expense {expense.expense_number}"
            )
        updated = await self.repo.update(expense, status=ExpenseStatus.CANCELLED)
        logger.info("expense_cancelled", expense_id=str(expense_id))
        return updated

    async def apply_payment(self, expense_id: uuid.UUID, organization_id: uuid.UUID, amount: float) -> Expense:
        expense = await self.get_expense(expense_id, organization_id)
        if expense.status not in (ExpenseStatus.APPROVED, ExpenseStatus.PARTIALLY_PAID):
            raise ValidationError(f"Cannot apply a payment to an expense that is '{expense.status.value}'.")

        new_amount_paid = round(float(expense.amount_paid) + amount, 2)
        if new_amount_paid > float(expense.total_amount) + 0.01:
            raise ValidationError("Payment amount exceeds the outstanding balance on this expense.")

        new_status = (
            ExpenseStatus.PAID if new_amount_paid >= float(expense.total_amount) else ExpenseStatus.PARTIALLY_PAID
        )
        return await self.repo.update(expense, amount_paid=new_amount_paid, status=new_status)

    async def revert_payment(self, expense_id: uuid.UUID, organization_id: uuid.UUID, amount: float) -> Expense:
        expense = await self.get_expense(expense_id, organization_id)
        new_amount_paid = max(round(float(expense.amount_paid) - amount, 2), 0)
        new_status = ExpenseStatus.PARTIALLY_PAID if new_amount_paid > 0 else ExpenseStatus.APPROVED
        return await self.repo.update(expense, amount_paid=new_amount_paid, status=new_status)
