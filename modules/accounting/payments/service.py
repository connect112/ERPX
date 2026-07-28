import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.bank.models import BankTransactionSource
from modules.accounting.bank.repository import BankAccountRepository
from modules.accounting.bank.service import BankService
from modules.accounting.expenses.service import ExpenseService
from modules.accounting.journals.models import JournalSourceModule
from modules.accounting.journals.service import JournalService
from modules.accounting.payments.models import Payment, PaymentStatus
from modules.accounting.payments.repository import PaymentRepository
from modules.accounting.tds.service import TDSService
from modules.accounting.vendors.repository import VendorRepository

logger = get_logger(__name__)


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PaymentRepository(db)
        self.vendor_repo = VendorRepository(db)
        self.expense_service = ExpenseService(db)
        self.bank_account_repo = BankAccountRepository(db)
        self.bank_service = BankService(db)
        self.tds_service = TDSService(db)
        self.journal_service = JournalService(db)

    async def create_payment(
        self,
        organization_id: uuid.UUID,
        vendor_id: uuid.UUID,
        expense_id: uuid.UUID,
        payment_number: str,
        gross_amount: float,
        bank_account_id: uuid.UUID | None = None,
        payment_account_id: uuid.UUID | None = None,
        tds_section_id: uuid.UUID | None = None,
        tds_payable_account_id: uuid.UUID | None = None,
        created_by_user_id: uuid.UUID | None = None,
        **fields,
    ) -> Payment:
        vendor = await self.vendor_repo.get_by_id(vendor_id, organization_id)
        if not vendor:
            raise NotFoundError("Vendor", vendor_id)

        existing = await self.repo.get_by_number(organization_id, payment_number)
        if existing:
            raise ConflictError(f"A payment with number '{payment_number}' already exists.")

        expense = await self.expense_service.get_expense(expense_id, organization_id)
        if expense.vendor_id != vendor_id:
            raise ValidationError("This expense does not belong to the specified vendor.")
        if gross_amount > expense.outstanding_amount + 0.01:
            raise ValidationError("Payment amount exceeds the expense's outstanding balance.")

        if bank_account_id is not None:
            bank_account = await self.bank_account_repo.get_by_id(bank_account_id, organization_id)
            if not bank_account:
                raise NotFoundError("Bank account", bank_account_id)
            payment_account_id = bank_account.gl_account_id

        payment = await self.repo.create(
            organization_id=organization_id,
            vendor_id=vendor_id,
            expense_id=expense_id,
            payment_account_id=payment_account_id,
            bank_account_id=bank_account_id,
            tds_payable_account_id=tds_payable_account_id,
            tds_section_id=tds_section_id,
            payment_number=payment_number,
            gross_amount=gross_amount,
            tds_amount=0,
            net_amount=gross_amount,
            **fields,
        )

        tds_amount = 0.0
        net_amount = gross_amount
        tds_deduction_id = None
        if tds_section_id is not None:
            deduction = await self.tds_service.compute_and_record_deduction(
                organization_id=organization_id,
                vendor_id=vendor_id,
                tds_section_id=tds_section_id,
                gross_amount=gross_amount,
                deduction_date=fields["payment_date"],
                payment_id=payment.id,
            )
            tds_amount = float(deduction.tds_amount)
            net_amount = float(deduction.net_amount)
            tds_deduction_id = deduction.id

        journal_lines = [
            {"account_id": expense.payable_account_id, "debit": gross_amount, "credit": 0},
            {"account_id": payment_account_id, "debit": 0, "credit": net_amount},
        ]
        if tds_amount > 0:
            journal_lines.append({"account_id": tds_payable_account_id, "debit": 0, "credit": tds_amount})

        entry = await self.journal_service.post_transaction(
            organization_id=organization_id,
            entry_date=fields["payment_date"],
            memo=f"Payment {payment_number}",
            source_module=JournalSourceModule.PAYMENTS,
            source_id=payment.id,
            lines=journal_lines,
            branch_id=fields.get("branch_id"),
            created_by_user_id=created_by_user_id,
        )

        payment = await self.repo.update(
            payment,
            tds_amount=tds_amount,
            net_amount=net_amount,
            tds_deduction_id=tds_deduction_id,
            journal_entry_id=entry.id,
        )

        if bank_account_id is not None:
            await self.bank_service.record_linked_transaction(
                bank_account_id=bank_account_id,
                journal_entry_id=entry.id,
                transaction_date=fields["payment_date"],
                description=f"Payment {payment_number} to vendor",
                debit_amount=0,
                credit_amount=net_amount,
                source=BankTransactionSource.PAYMENT,
                source_id=payment.id,
                reference_number=fields.get("reference_number"),
            )

        await self.expense_service.apply_payment(expense_id, organization_id, gross_amount)

        logger.info("payment_created", payment_id=str(payment.id), net_amount=net_amount)
        return payment

    async def get_payment(self, payment_id: uuid.UUID, organization_id: uuid.UUID) -> Payment:
        payment = await self.repo.get_by_id(payment_id, organization_id)
        if not payment:
            raise NotFoundError("Payment", payment_id)
        return payment

    async def list_payments(self, organization_id: uuid.UUID, **filters) -> tuple[list[Payment], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def void_payment(self, payment_id: uuid.UUID, organization_id: uuid.UUID) -> Payment:
        payment = await self.get_payment(payment_id, organization_id)
        if payment.status == PaymentStatus.VOIDED:
            raise ValidationError("This payment is already voided.")

        if payment.journal_entry_id is not None:
            await self.journal_service.reverse_entry(
                payment.journal_entry_id, organization_id, memo=f"Void of payment {payment.payment_number}"
            )

        await self.expense_service.revert_payment(payment.expense_id, organization_id, float(payment.gross_amount))

        updated = await self.repo.update(payment, status=PaymentStatus.VOIDED)
        logger.info(
            "payment_voided",
            payment_id=str(payment_id),
            note="Associated TDSDeduction record (if any) is retained as a historical audit trail.",
        )
        return updated
