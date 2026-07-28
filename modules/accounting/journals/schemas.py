import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from modules.accounting.journals.models import JournalEntryStatus, JournalSourceModule


class JournalLineRequest(BaseModel):
    account_id: uuid.UUID
    description: str | None = Field(default=None, max_length=500)
    debit: float = Field(default=0, ge=0)
    credit: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _single_sided(self):
        if self.debit > 0 and self.credit > 0:
            raise ValueError("A journal line cannot have both a debit and a credit amount.")
        if self.debit == 0 and self.credit == 0:
            raise ValueError("A journal line must have either a debit or a credit amount.")
        return self


class JournalEntryCreateRequest(BaseModel):
    entry_date: datetime
    memo: str | None = None
    branch_id: uuid.UUID | None = None
    lines: list[JournalLineRequest] = Field(..., min_length=2)


class JournalLinePublic(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    description: str | None
    debit: float
    credit: float
    line_order: int

    model_config = {"from_attributes": True}


class JournalEntryPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    entry_number: str
    entry_date: datetime
    memo: str | None
    source_module: JournalSourceModule
    source_id: uuid.UUID | None
    status: JournalEntryStatus
    reversed_by_entry_id: uuid.UUID | None
    posted_at: datetime | None
    created_at: datetime
    lines: list[JournalLinePublic] = []

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
