import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.corporate.tickets.models import TicketPriority, TicketStatus


class SupportTicketCreateRequest(BaseModel):
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None
    ticket_number: str = Field(..., min_length=1, max_length=50)
    subject: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=2)
    priority: TicketPriority = TicketPriority.MEDIUM
    assigned_to_employee_id: uuid.UUID | None = None
    raised_by_contact_name: str | None = None
    sla_due_at: datetime | None = None


class ClientTicketCreateRequest(BaseModel):
    project_id: uuid.UUID | None = None
    subject: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=2)
    priority: TicketPriority = TicketPriority.MEDIUM
    raised_by_contact_name: str | None = None


class ClientTicketCommentCreateRequest(BaseModel):
    comment_text: str = Field(..., min_length=1)


class SupportTicketUpdateRequest(BaseModel):
    priority: TicketPriority | None = None
    assigned_to_employee_id: uuid.UUID | None = None
    sla_due_at: datetime | None = None


class SupportTicketStatusChangeRequest(BaseModel):
    status: TicketStatus


class SupportTicketPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    client_id: uuid.UUID
    project_id: uuid.UUID | None
    assigned_to_employee_id: uuid.UUID | None
    ticket_number: str
    subject: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    raised_by_contact_name: str | None
    sla_due_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketCommentCreateRequest(BaseModel):
    comment_text: str = Field(..., min_length=1)
    is_internal: bool = False


class TicketCommentPublic(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    comment_text: str
    is_internal: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
