import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from modules.accounting.receipts.models import PaymentMode, ReceiptStatus


class ReceiptCreateRequest(BaseModel):
    customer_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    receivable_account_id: uuid.UUID | None = Field(
        default=None,
        description="Required for on-account/advance receipts (no invoice_id); "
        "derived from the invoice's receivable account otherwise.",
    )
    receipt_number: str = Field(..., min_length=1, max_length=50)
    receipt_date: datetime
    amount: float = Field(..., gt=0)
    payment_mode: PaymentMode
    bank_account_id: uuid.UUID | None = None
    deposit_account_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    reference_number: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _deposit_target_required(self):
        if self.bank_account_id is None and self.deposit_account_id is None:
            raise ValueError("Either bank_account_id or deposit_account_id must be provided.")
        if self.invoice_id is None and self.receivable_account_id is None:
            raise ValueError("receivable_account_id is required for an on-account receipt (no invoice_id).")
        return self


class ReceiptPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    customer_id: uuid.UUID
    invoice_id: uuid.UUID | None
    deposit_account_id: uuid.UUID
    bank_account_id: uuid.UUID | None
    journal_entry_id: uuid.UUID | None
    receipt_number: str
    receipt_date: datetime
    amount: float
    payment_mode: PaymentMode
    reference_number: str | None
    status: ReceiptStatus
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
