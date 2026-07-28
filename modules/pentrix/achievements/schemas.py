import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.pentrix.achievements.models import AchievementCriteriaType


class AchievementCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None
    criteria_type: AchievementCriteriaType
    criteria_value: int = Field(..., ge=1)


class AchievementPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    criteria_type: AchievementCriteriaType
    criteria_value: int
    created_at: datetime

    model_config = {"from_attributes": True}


class StudentAchievementPublic(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    achievement_id: uuid.UUID
    awarded_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
