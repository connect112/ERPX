import uuid
from datetime import datetime

from pydantic import BaseModel

from modules.audit.models import AuditAction


class AuditLogPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    user_id: uuid.UUID | None
    user_email: str | None = None
    user_full_name: str | None = None
    action: AuditAction
    entity_type: str
    entity_id: uuid.UUID | None
    changes: dict
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogPublic]
    total: int
