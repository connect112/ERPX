import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.classrooms.models import ClassroomType


class ClassroomCreateRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    classroom_type: ClassroomType = ClassroomType.PHYSICAL
    capacity: int | None = Field(default=None, ge=1)
    location: str | None = None
    meeting_link: str | None = None


class ClassroomUpdateRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=255)
    classroom_type: ClassroomType | None = None
    capacity: int | None = Field(default=None, ge=1)
    location: str | None = None
    meeting_link: str | None = None
    is_active: bool | None = None


class ClassroomPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    name: str
    code: str
    classroom_type: ClassroomType
    capacity: int | None
    location: str | None
    meeting_link: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ClassroomListResponse(BaseModel):
    items: list[ClassroomPublic]
    total: int


class MessageResponse(BaseModel):
    message: str
