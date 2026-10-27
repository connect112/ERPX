import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CertificateInfo(BaseModel):
    kind: str
    label: str
    exam_id: uuid.UUID
    has_design: bool
    review_required: bool
    eligible_count: int
    sent_count: int


class EligibilityRow(BaseModel):
    selection_id: uuid.UUID
    student_name: str
    student_email: str
    kind: str | None = None
    # not_selected | not_created | held_for_review | queued | sent
    delivery: str
    certificate_number: str | None = None
    sent_at: datetime | None = None
    locked: bool = False


class CertificatesOverview(BaseModel):
    certificates: list[CertificateInfo]
    rows: list[EligibilityRow]


class EligibilityRequest(BaseModel):
    selection_ids: list[uuid.UUID] = Field(min_length=1, max_length=2000)
    kind: str | None = None


class IssueRequest(BaseModel):
    kinds: list[str] = Field(default_factory=lambda: ["participation", "completion"])
    confirm: bool = False


class Recipient(BaseModel):
    name: str
    email: str | None = None
    status: str


class PlanOut(BaseModel):
    kind: str
    label: str
    exam_id: uuid.UUID
    recipients: list[Recipient]
    will_send: int
    already_sent: int
    no_email: int
    review_required: bool


class IssueResponse(BaseModel):
    plans: list[PlanOut]
    done: bool = False
    held_for_review: list[str] = []
    message: str = ""
