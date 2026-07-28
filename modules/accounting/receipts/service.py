import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.bank.models import BankTransactionSource
from modules.accounting.bank.repository import BankAccountRepository
from modules.accounting.bank.service import BankService
from modules.accounting.customers.repository import CustomerRepository
from modules.accounting.invoices.repository import InvoiceRepository
from modules.accounting.invoices.service import InvoiceService
from modules.accounting.journals.models import JournalSourceModule
from modules.accounting.journals.service import JournalService
from modules.accounting.receipts.models import Receipt, ReceiptStatus
from modules.accounting.receipts.repository import ReceiptRepository

logger = get_logger(__name__)


class ReceiptService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ReceiptRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.invoice_service = InvoiceService(db)
        self.bank_account_repo = BankAccountRepository(db)
        self.bank_service = BankService(db)
        self.journal_service = JournalService(db)

    async def create_receipt(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        receipt_number: str,
        amount: float,
        invoice_id: uuid.UUID | None = None,
        receivable_account_id: uuid.UUID | None = None,
        bank_account_id: uuid.UUID | None = None,
        deposit_account_id: uuid.UUID | None = None,
        created_by_user_id: uuid.UUID | None = None,
        **fields,
    ) -> Receipt:
        customer = await self.customer_repo.get_by_id(customer_id, organization_id)
        if not customer:
            raise NotFoundError("Customer", customer_id)

        existing = await self.repo.get_by_number(organization_id, receipt_number)
        if existing:
            raise ConflictError(f"A receipt with number '{receipt_number}' already exists.")

        invoice = None
        if invoice_id is not None:
            invoice = await self.invoice_service.get_invoice(invoice_id, organization_id)
            if invoice.customer_id != customer_id:
                raise ValidationError("This invoice does not belong to the specified customer.")
            if amount > invoice.outstanding_amount + 0.01:
                raise ValidationError("Receipt amount exceeds the invoice's outstanding balance.")
            receivable_account_id = invoice.receivable_account_id

        if bank_account_id is not None:
            bank_account = await self.bank_account_repo.get_by_id(bank_account_id, organization_id)
            if not bank_account:
                raise NotFoundError("Bank account", bank_account_id)
            deposit_account_id = bank_account.gl_account_id

        entry = await self.journal_service.post_transaction(
            organization_id=organization_id,
            entry_date=fields["receipt_date"],
            memo=f"Receipt {receipt_number}",
            source_module=JournalSourceModule.RECEIPTS,
            lines=[
                {"account_id": deposit_account_id, "debit": amount, "credit": 0},
                {"account_id": receivable_account_id, "debit": 0, "credit": amount},
            ],
            branch_id=fields.get("branch_id"),
            created_by_user_id=created_by_user_id,
        )

        receipt = await self.repo.create(
            organization_id=organization_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            deposit_account_id=deposit_account_id,
            bank_account_id=bank_account_id,
            journal_entry_id=entry.id,
            receipt_number=receipt_number,
            amount=amount,
            **fields,
        )

        if bank_account_id is not None:
            await self.bank_service.record_linked_transaction(
                bank_account_id=bank_account_id,
                journal_entry_id=entry.id,
                transaction_date=fields["receipt_date"],
                description=f"Receipt {receipt_number} from customer",
                debit_amount=amount,
                credit_amount=0,
                source=BankTransactionSource.RECEIPT,
                source_id=receipt.id,
                reference_number=fields.get("reference_number"),
            )

        if invoice is not None:
            await self.invoice_service.apply_payment(invoice_id, organization_id, amount)

        logger.info("receipt_created", receipt_id=str(receipt.id), amount=amount)
        return receipt

    async def get_receipt(self, receipt_id: uuid.UUID, organization_id: uuid.UUID) -> Receipt:
        receipt = await self.repo.get_by_id(receipt_id, organization_id)
        if not receipt:
            raise NotFoundError("Receipt", receipt_id)
        return receipt

    async def list_receipts(self, organization_id: uuid.UUID, **filters) -> tuple[list[Receipt], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def void_receipt(self, receipt_id: uuid.UUID, organization_id: uuid.UUID) -> Receipt:
        receipt = await self.get_receipt(receipt_id, organization_id)
        if receipt.status == ReceiptStatus.VOIDED:
            raise ValidationError("This receipt is already voided.")

        if receipt.journal_entry_id is not None:
            await self.journal_service.reverse_entry(
                receipt.journal_entry_id, organization_id, memo=f"Void of receipt {receipt.receipt_number}"
            )

        if receipt.invoice_id is not None:
            await self.invoice_service.revert_payment(receipt.invoice_id, organization_id, float(receipt.amount))

        updated = await self.repo.update(receipt, status=ReceiptStatus.VOIDED)
        logger.info("receipt_voided", receipt_id=str(receipt_id))
        return updated
