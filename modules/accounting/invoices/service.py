import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.customers.repository import CustomerRepository
from modules.accounting.gst.service import GSTService
from modules.accounting.invoices.models import Invoice, InvoiceStatus
from modules.accounting.invoices.repository import InvoiceRepository
from modules.accounting.journals.models import JournalSourceModule
from modules.accounting.journals.service import JournalService

logger = get_logger(__name__)

_TERMINAL_STATUSES = {InvoiceStatus.PAID, InvoiceStatus.CANCELLED}


async def _build_lines(gst_service: GSTService, organization_id: uuid.UUID, raw_lines: list[dict], is_interstate: bool):
    computed = []
    for line in raw_lines:
        line_subtotal = round(float(line["quantity"]) * float(line["unit_price"]), 2)
        tax_amount = 0.0
        if line.get("gst_rate_id") is not None:
            tax_result = await gst_service.compute_tax(
                organization_id, line_subtotal, line["gst_rate_id"], is_interstate
            )
            tax_amount = tax_result["total_tax"]
        computed.append(
            {
                "revenue_account_id": line["revenue_account_id"],
                "gst_rate_id": line.get("gst_rate_id"),
                "description": line["description"],
                "quantity": line["quantity"],
                "unit_price": line["unit_price"],
                "line_subtotal": line_subtotal,
                "tax_amount": tax_amount,
                "line_total": round(line_subtotal + tax_amount, 2),
            }
        )
    return computed


class InvoiceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = InvoiceRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.gst_service = GSTService(db)
        self.journal_service = JournalService(db)

    async def create_invoice(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        invoice_number: str,
        lines: list[dict],
        discount_amount: float = 0,
        tax_payable_account_id: uuid.UUID | None = None,
        discount_account_id: uuid.UUID | None = None,
        **fields,
    ) -> Invoice:
        customer = await self.customer_repo.get_by_id(customer_id, organization_id)
        if not customer:
            raise NotFoundError("Customer", customer_id)

        existing = await self.repo.get_by_number(organization_id, invoice_number)
        if existing:
            raise ConflictError(f"An invoice with number '{invoice_number}' already exists.")

        is_interstate = fields.get("is_interstate", False)
        computed_lines = await _build_lines(self.gst_service, organization_id, lines, is_interstate)

        subtotal_amount = round(sum(l["line_subtotal"] for l in computed_lines), 2)
        tax_amount = round(sum(l["tax_amount"] for l in computed_lines), 2)

        if tax_amount > 0 and tax_payable_account_id is None:
            raise ValidationError("A tax payable account is required when any line carries GST.")
        if discount_amount > 0 and discount_account_id is None:
            raise ValidationError("A discount account is required when a discount amount is given.")

        total_amount = round(subtotal_amount + tax_amount - discount_amount, 2)
        if total_amount < 0:
            raise ValidationError("Discount amount cannot exceed the invoice subtotal plus tax.")

        invoice = await self.repo.create(
            lines=computed_lines,
            organization_id=organization_id,
            customer_id=customer_id,
            invoice_number=invoice_number,
            tax_payable_account_id=tax_payable_account_id,
            discount_account_id=discount_account_id,
            discount_amount=discount_amount,
            subtotal_amount=subtotal_amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            **fields,
        )
        logger.info("invoice_created", invoice_id=str(invoice.id), invoice_number=invoice_number)
        return invoice

    async def get_invoice(self, invoice_id: uuid.UUID, organization_id: uuid.UUID) -> Invoice:
        invoice = await self.repo.get_by_id(invoice_id, organization_id)
        if not invoice:
            raise NotFoundError("Invoice", invoice_id)
        return invoice

    async def list_invoices(self, organization_id: uuid.UUID, **filters) -> tuple[list[Invoice], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_invoice(
        self, invoice_id: uuid.UUID, organization_id: uuid.UUID, lines: list[dict] | None = None, **fields
    ) -> Invoice:
        invoice = await self.get_invoice(invoice_id, organization_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValidationError("Only draft invoices can be edited.")

        is_interstate = fields.get("is_interstate", invoice.is_interstate)
        if lines is not None:
            computed_lines = await _build_lines(self.gst_service, organization_id, lines, is_interstate)
            await self.repo.replace_lines(invoice, computed_lines)
            fields["subtotal_amount"] = round(sum(l["line_subtotal"] for l in computed_lines), 2)
            fields["tax_amount"] = round(sum(l["tax_amount"] for l in computed_lines), 2)

        discount_amount = fields.get("discount_amount", invoice.discount_amount)
        subtotal_amount = fields.get("subtotal_amount", invoice.subtotal_amount)
        tax_amount = fields.get("tax_amount", invoice.tax_amount)
        fields["total_amount"] = round(float(subtotal_amount) + float(tax_amount) - float(discount_amount), 2)

        updated = await self.repo.update(invoice, **fields)
        logger.info("invoice_updated", invoice_id=str(invoice_id))
        return updated

    async def post_invoice(
        self, invoice_id: uuid.UUID, organization_id: uuid.UUID, created_by_user_id: uuid.UUID | None = None
    ) -> Invoice:
        invoice = await self.get_invoice(invoice_id, organization_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValidationError(f"Only draft invoices can be posted (this one is '{invoice.status.value}').")

        revenue_totals: dict[uuid.UUID, float] = {}
        for line in invoice.lines:
            revenue_totals[line.revenue_account_id] = (
                revenue_totals.get(line.revenue_account_id, 0) + float(line.line_subtotal)
            )

        journal_lines = [
            {"account_id": invoice.receivable_account_id, "debit": float(invoice.total_amount), "credit": 0}
        ]
        for account_id, amount in revenue_totals.items():
            journal_lines.append({"account_id": account_id, "debit": 0, "credit": round(amount, 2)})
        if float(invoice.tax_amount) > 0:
            journal_lines.append(
                {"account_id": invoice.tax_payable_account_id, "debit": 0, "credit": float(invoice.tax_amount)}
            )
        if float(invoice.discount_amount) > 0:
            journal_lines.append(
                {"account_id": invoice.discount_account_id, "debit": float(invoice.discount_amount), "credit": 0}
            )

        entry = await self.journal_service.post_transaction(
            organization_id=organization_id,
            entry_date=invoice.invoice_date,
            memo=f"Invoice {invoice.invoice_number}",
            source_module=JournalSourceModule.INVOICES,
            source_id=invoice.id,
            lines=journal_lines,
            branch_id=invoice.branch_id,
            created_by_user_id=created_by_user_id,
        )

        updated = await self.repo.update(
            invoice, status=InvoiceStatus.SENT, journal_entry_id=entry.id
        )
        logger.info("invoice_posted", invoice_id=str(invoice_id), journal_entry_id=str(entry.id))
        return updated

    async def cancel_invoice(self, invoice_id: uuid.UUID, organization_id: uuid.UUID) -> Invoice:
        invoice = await self.get_invoice(invoice_id, organization_id)
        if invoice.status in _TERMINAL_STATUSES:
            raise ValidationError(f"An invoice that is '{invoice.status.value}' cannot be cancelled.")
        if float(invoice.amount_paid) > 0:
            raise ValidationError(
                "This invoice has received payments; void the associated receipts before cancelling."
            )

        if invoice.journal_entry_id is not None:
            await self.journal_service.reverse_entry(
                invoice.journal_entry_id, organization_id, memo=f"Cancellation of invoice {invoice.invoice_number}"
            )

        updated = await self.repo.update(invoice, status=InvoiceStatus.CANCELLED)
        logger.info("invoice_cancelled", invoice_id=str(invoice_id))
        return updated

    async def apply_payment(self, invoice_id: uuid.UUID, organization_id: uuid.UUID, amount: float) -> Invoice:
        invoice = await self.get_invoice(invoice_id, organization_id)
        if invoice.status not in (InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE):
            raise ValidationError(f"Cannot apply a payment to an invoice that is '{invoice.status.value}'.")

        new_amount_paid = round(float(invoice.amount_paid) + amount, 2)
        if new_amount_paid > float(invoice.total_amount) + 0.01:
            raise ValidationError("Payment amount exceeds the outstanding balance on this invoice.")

        new_status = (
            InvoiceStatus.PAID if new_amount_paid >= float(invoice.total_amount) else InvoiceStatus.PARTIALLY_PAID
        )
        updated = await self.repo.update(invoice, amount_paid=new_amount_paid, status=new_status)
        return updated

    async def revert_payment(self, invoice_id: uuid.UUID, organization_id: uuid.UUID, amount: float) -> Invoice:
        invoice = await self.get_invoice(invoice_id, organization_id)
        new_amount_paid = max(round(float(invoice.amount_paid) - amount, 2), 0)
        new_status = InvoiceStatus.PARTIALLY_PAID if new_amount_paid > 0 else InvoiceStatus.SENT
        updated = await self.repo.update(invoice, amount_paid=new_amount_paid, status=new_status)
        return updated

    async def refresh_overdue_statuses(self, organization_id: uuid.UUID) -> int:
        """Flip SENT/PARTIALLY_PAID invoices past their due date to OVERDUE. Run daily via Celery beat."""
        now = datetime.now(timezone.utc)
        invoices = await self.repo.list_all_outstanding(organization_id)
        count = 0
        for invoice in invoices:
            if invoice.status != InvoiceStatus.OVERDUE and invoice.due_date < now:
                await self.repo.update(invoice, status=InvoiceStatus.OVERDUE)
                count += 1
        return count
