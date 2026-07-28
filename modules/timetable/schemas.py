import uuid
from datetime import datetime, time

from pydantic import BaseModel

from modules.timetable.models import DayOfWeek


class TimetableEntryCreateRequest(BaseModel):
    batch_id: uuid.UUID
    classroom_id: uuid.UUID | None = None
    trainer_id: uuid.UUID | None = None
    day_of_week: DayOfWeek
    start_time: time
    end_time: time
    subject: str | None = None


class TimetableEntryUpdateRequest(BaseModel):
    classroom_id: uuid.UUID | None = None
    trainer_id: uuid.UUID | None = None
    day_of_week: DayOfWeek | None = None
    start_time: time | None = None
    end_time: time | None = None
    subject: str | None = None


class TimetableEntryPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    batch_id: uuid.UUID
    classroom_id: uuid.UUID | None
    trainer_id: uuid.UUID | None
    day_of_week: DayOfWeek
    start_time: time
    end_time: time
    subject: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
