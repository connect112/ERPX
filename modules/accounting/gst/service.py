import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.accounting.gst.models import GSTRate
from modules.accounting.gst.repository import GSTRateRepository

logger = get_logger(__name__)


class GSTService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = GSTRateRepository(db)

    async def create_rate(self, organization_id: uuid.UUID, name: str, **fields) -> GSTRate:
        existing = await self.repo.get_by_name(organization_id, name)
        if existing:
            raise ConflictError(f"A GST rate named '{name}' already exists.")
        rate = await self.repo.create(organization_id=organization_id, name=name, **fields)
        logger.info("gst_rate_created", rate_id=str(rate.id))
        return rate

    async def get_rate(self, rate_id: uuid.UUID, organization_id: uuid.UUID) -> GSTRate:
        rate = await self.repo.get_by_id(rate_id, organization_id)
        if not rate:
            raise NotFoundError("GST rate", rate_id)
        return rate

    async def list_rates(self, organization_id: uuid.UUID, is_active: bool | None = None) -> list[GSTRate]:
        return await self.repo.list_for_organization(organization_id, is_active)

    async def update_rate(self, rate_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> GSTRate:
        rate = await self.get_rate(rate_id, organization_id)
        updated = await self.repo.update(rate, **fields)
        logger.info("gst_rate_updated", rate_id=str(rate_id))
        return updated

    async def compute_tax(
        self, organization_id: uuid.UUID, taxable_amount: float, gst_rate_id: uuid.UUID, is_interstate: bool
    ) -> dict:
        rate = await self.get_rate(gst_rate_id, organization_id)
        rate_percent = float(rate.rate_percent)

        if is_interstate:
            igst_amount = round(taxable_amount * rate_percent / 100, 2)
            cgst_amount = 0.0
            sgst_amount = 0.0
        else:
            cgst_amount = round(taxable_amount * rate.half_rate_percent / 100, 2)
            sgst_amount = round(taxable_amount * rate.half_rate_percent / 100, 2)
            igst_amount = 0.0

        total_tax = round(cgst_amount + sgst_amount + igst_amount, 2)
        return {
            "taxable_amount": taxable_amount,
            "rate_percent": rate_percent,
            "is_interstate": is_interstate,
            "cgst_amount": cgst_amount,
            "sgst_amount": sgst_amount,
            "igst_amount": igst_amount,
            "total_tax": total_tax,
            "total_amount": round(taxable_amount + total_tax, 2),
        }

    async def get_return_summary(
        self, organization_id: uuid.UUID, period_from: date, period_to: date
    ) -> dict:
        """
        GSTR-style summary: output tax (from posted Invoices) minus input
        tax credit (from posted Expenses) for the period. Queried directly
        against Invoice/Expense line data rather than a stored return
        table, so it always reflects the current, posted state.
        """
        from datetime import datetime, time, timezone

        from sqlalchemy import func, select

        from modules.accounting.expenses.models import Expense, ExpenseStatus
        from modules.accounting.invoices.models import Invoice, InvoiceStatus

        period_start = datetime.combine(period_from, time.min, tzinfo=timezone.utc)
        period_end = datetime.combine(period_to, time.max, tzinfo=timezone.utc)

        output_result = await self.db.execute(
            select(
                func.coalesce(func.sum(Invoice.subtotal_amount), 0),
                func.coalesce(func.sum(Invoice.tax_amount), 0),
            ).where(
                Invoice.organization_id == organization_id,
                Invoice.status.notin_([InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]),
                Invoice.invoice_date >= period_start,
                Invoice.invoice_date <= period_end,
            )
        )
        output_taxable_value, output_tax_collected = output_result.one()

        input_result = await self.db.execute(
            select(
                func.coalesce(func.sum(Expense.subtotal_amount), 0),
                func.coalesce(func.sum(Expense.tax_amount), 0),
            ).where(
                Expense.organization_id == organization_id,
                Expense.status.notin_([ExpenseStatus.DRAFT, ExpenseStatus.REJECTED]),
                Expense.expense_date >= period_start,
                Expense.expense_date <= period_end,
            )
        )
        input_taxable_value, input_tax_credit = input_result.one()

        output_tax_collected = float(output_tax_collected)
        input_tax_credit = float(input_tax_credit)

        return {
            "period_from": period_from,
            "period_to": period_to,
            "output_taxable_value": float(output_taxable_value),
            "output_tax_collected": output_tax_collected,
            "input_taxable_value": float(input_taxable_value),
            "input_tax_credit": input_tax_credit,
            "net_tax_payable": round(output_tax_collected - input_tax_credit, 2),
        }
