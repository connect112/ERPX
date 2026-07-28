import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TrainerCreateRequest(BaseModel):
    employee_id: uuid.UUID
    specializations: str | None = None
    bio: str | None = None
    max_weekly_hours: int | None = Field(default=None, ge=1, le=168)


class TrainerUpdateRequest(BaseModel):
    specializations: str | None = None
    bio: str | None = None
    max_weekly_hours: int | None = Field(default=None, ge=1, le=168)
    is_active: bool | None = None


class TrainerPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    employee_email: str | None
    specializations: str | None
    bio: str | None
    max_weekly_hours: int | None
    is_active: bool
    created_at: datetime


class TrainerListResponse(BaseModel):
    items: list[TrainerPublic]
    total: int


class MessageResponse(BaseModel):
    message: str
