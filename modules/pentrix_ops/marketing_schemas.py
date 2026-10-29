import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FiltersIn(BaseModel):
    """The Registrations filters, the same ones the list uses."""

    q: str | None = Field(default=None, max_length=100)
    assessment: list[str] = []
    qualification: list[str] = []
    booking: list[str] = []
    payment: list[str] = []
    marketing: list[str] = []
    registered_from: datetime | None = None
    registered_to: datetime | None = None


class SelectionIn(BaseModel):
    """Who is chosen: candidates picked one by one, or everyone matching the filters (less any taken out)."""

    mode: Literal["ids", "filter"]
    ids: list[uuid.UUID] = Field(default=[], max_length=20000)
    filters: FiltersIn = FiltersIn()
    exclude_ids: list[uuid.UUID] = Field(default=[], max_length=20000)

    def as_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "ids": self.ids, "filters": self.filters.model_dump(), "exclude_ids": self.exclude_ids}


class TemplateAssign(BaseModel):
    template_id: uuid.UUID
    campaign_name: str = Field(min_length=1, max_length=200)
    available_from: date | None = None
    available_until: date | None = None


class TemplateUpdate(BaseModel):
    campaign_name: str | None = Field(default=None, min_length=1, max_length=200)
    available_from: date | None = None
    available_until: date | None = None
    enabled: bool | None = None


class MarketingTemplateOut(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    name: str
    campaign_name: str
    category: str
    available_from: date | None = None
    available_until: date | None = None
    enabled: bool
    published: bool
    usable: bool
    problem: str | None = None
    subject: str = ""
    source_type: str
    last_updated: datetime | None = None


class AssignableOut(BaseModel):
    template_id: uuid.UUID
    name: str
    category: str
    subject: str = ""
    source_type: str


class OptionOut(BaseModel):
    id: uuid.UUID
    name: str
    is_default: bool = False


class OptionsOut(BaseModel):
    brands: list[OptionOut]
    signatures: list[OptionOut]


class RecipientsPreviewIn(BaseModel):
    selection: SelectionIn
    assignment_id: uuid.UUID | None = None  # lets "already received this template" be counted


class ExcludedOut(BaseModel):
    reason: str
    label: str
    count: int


class PersonOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str


class RecipientsPreviewOut(BaseModel):
    selected: int
    eligible: int
    excluded: list[ExcludedOut]
    people: list[PersonOut]  # the first few who would receive it
    people_shown: int


class CampaignPreviewIn(BaseModel):
    assignment_id: uuid.UUID
    selection: SelectionIn | None = None
    candidate_id: uuid.UUID | None = None  # preview as this candidate; default is the first recipient, or a sample
    brand_profile_id: uuid.UUID | None = None
    signature_id: uuid.UUID | None = None


class AttachmentOut(BaseModel):
    name: str
    size_bytes: int


class CandidateRef(BaseModel):
    id: uuid.UUID
    name: str
    email: str


class EmailPreviewOut(BaseModel):
    assignment_id: uuid.UUID
    campaign_name: str
    template_name: str
    subject: str
    html: str
    text: str
    brand: str | None = None
    brand_profile_id: uuid.UUID | None = None
    signature: str | None = None
    signature_id: uuid.UUID | None = None
    attachments: list[AttachmentOut] = []
    missing: list[str] = []
    warnings: list[str] = []
    candidate: CandidateRef | None = None
    sample: bool = True
    recipients: RecipientsPreviewOut | None = None


class CampaignCreate(BaseModel):
    assignment_id: uuid.UUID
    selection: SelectionIn
    brand_profile_id: uuid.UUID | None = None
    signature_id: uuid.UUID | None = None
    expected_count: int = Field(ge=1)
    confirm: Literal[True]  # an explicit confirmation, not an inference
    idempotency_key: str = Field(min_length=8, max_length=80)


class CampaignOut(BaseModel):
    id: uuid.UUID
    campaign_name: str
    subject: str
    status: str
    recipient_count: int
    counts: dict[str, int]
    excluded: dict[str, int]
    confirmed_at: datetime
    completed_at: datetime | None = None
    template_id: uuid.UUID | None = None


class CampaignPage(BaseModel):
    items: list[CampaignOut]
    total: int
    page: int
    page_size: int


class RecipientOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    status: str
    error: str | None = None
    attempts: int
    sent_at: datetime | None = None


class RecipientPage(BaseModel):
    items: list[RecipientOut]
    total: int
    page: int
    page_size: int


class UnsubscribeInfo(BaseModel):
    email: str
    unsubscribed: bool = False
