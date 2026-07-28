import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.pentrix.labs.models import LabDifficulty


class ChallengeCreateRequest(BaseModel):
    lab_id: uuid.UUID | None = None
    title: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=2)
    category: str = Field(..., min_length=2, max_length=100)
    difficulty: LabDifficulty = LabDifficulty.EASY
    points: int = Field(default=100, ge=1)


class ChallengeUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    difficulty: LabDifficulty | None = None
    points: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class ChallengePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    lab_id: uuid.UUID | None
    title: str
    description: str
    category: str
    difficulty: LabDifficulty
    points: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
