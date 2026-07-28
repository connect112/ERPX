import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class HintCreateRequest(BaseModel):
    hint_text: str = Field(..., min_length=1)
    point_cost: int = Field(default=10, ge=0)
    order_index: int = Field(..., ge=0)


class HintPublic(BaseModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    hint_text: str
    point_cost: int
    order_index: int

    model_config = {"from_attributes": True}


class HintLocked(BaseModel):
    """What a student sees for a hint they haven't unlocked yet — no text."""

    id: uuid.UUID
    challenge_id: uuid.UUID
    point_cost: int
    order_index: int
    unlocked: bool = False


class UnlockHintRequest(BaseModel):
    student_id: uuid.UUID


class HintUnlockResponse(BaseModel):
    hint_id: uuid.UUID
    hint_text: str
    point_cost: int


class MessageResponse(BaseModel):
    message: str
