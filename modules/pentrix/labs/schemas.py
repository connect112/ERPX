import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.pentrix.labs.models import LabDifficulty


class LabCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    category: str = Field(..., min_length=2, max_length=100)
    difficulty: LabDifficulty = LabDifficulty.EASY
    environment_image: str = Field(..., min_length=1, max_length=255)
    points: int = Field(default=100, ge=1)
    default_duration_minutes: int = Field(default=60, ge=5)


class LabUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    difficulty: LabDifficulty | None = None
    environment_image: str | None = None
    points: int | None = Field(default=None, ge=1)
    default_duration_minutes: int | None = Field(default=None, ge=5)
    is_active: bool | None = None


class LabPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    slug: str
    description: str | None
    category: str
    difficulty: LabDifficulty
    environment_image: str
    points: int
    default_duration_minutes: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
