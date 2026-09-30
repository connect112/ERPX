import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.expense_claims.models import ExpenseClaimStatus


class ReceiptUploadRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=255)


class ReceiptUploadResponse(BaseModel):
    document_id: uuid.UUID
    upload_url: str


class ExpenseClaimSelfCreateRequest(BaseModel):
    description: str = Field(..., min_length=2)
    amount: float = Field(..., gt=0)
    receipt_document_id: uuid.UUID | None = None


class ExpenseClaimRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=2)


class ExpenseClaimPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    receipt_document_id: uuid.UUID | None
    reviewed_by_user_id: uuid.UUID | None
    period_year: int
    period_month: int
    applied_payroll_run_id: uuid.UUID | None
    description: str
    amount: float
    status: ExpenseClaimStatus
    rejection_reason: str | None
    reviewed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
