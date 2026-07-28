import uuid
from datetime import datetime

from pydantic import BaseModel

from modules.pentrix.lab_instances.models import LabInstanceStatus


class LaunchLabRequest(BaseModel):
    student_id: uuid.UUID


class LabInstancePublic(BaseModel):
    id: uuid.UUID
    lab_id: uuid.UUID
    student_id: uuid.UUID
    environment_ref: str | None
    access_endpoint: str | None
    status: LabInstanceStatus
    started_at: datetime
    expires_at: datetime
    stopped_at: datetime | None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
