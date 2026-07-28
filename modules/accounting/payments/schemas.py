import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from modules.accounting.payments.models import ApPaymentMode, PaymentStatus


class PaymentCreateRequest(BaseModel):
    vendor_id: uuid.UUID
    expense_id: uuid.UUID
    payment_number: str = Field(..., min_length=1, max_length=50)
    payment_date: datetime
    gross_amount: float = Field(..., gt=0)
    payment_mode: ApPaymentMode
    bank_account_id: uuid.UUID | None = None
    payment_account_id: uuid.UUID | None = None
    tds_section_id: uuid.UUID | None = None
    tds_payable_account_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    reference_number: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _validate_targets(self):
        if self.bank_account_id is None and self.payment_account_id is None:
            raise ValueError("Either bank_account_id or payment_account_id must be provided.")
        if self.tds_section_id is not None and self.tds_payable_account_id is None:
            raise ValueError("tds_payable_account_id is required when tds_section_id is set.")
        return self


class PaymentPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    vendor_id: uuid.UUID
    expense_id: uuid.UUID
    payment_account_id: uuid.UUID
    bank_account_id: uuid.UUID | None
    tds_payable_account_id: uuid.UUID | None
    tds_section_id: uuid.UUID | None
    tds_deduction_id: uuid.UUID | None
    journal_entry_id: uuid.UUID | None
    payment_number: str
    payment_date: datetime
    gross_amount: float
    tds_amount: float
    net_amount: float
    payment_mode: ApPaymentMode
    reference_number: str | None
    status: PaymentStatus
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
