import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SetFlagRequest(BaseModel):
    flag_value: str = Field(..., min_length=1, max_length=500)


class FlagPublic(BaseModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmitFlagRequest(BaseModel):
    student_id: uuid.UUID
    flag_value: str = Field(..., min_length=1, max_length=500)


class SubmissionResultResponse(BaseModel):
    correct: bool
    already_solved: bool = False
    points_awarded: int = 0


class SolvePublic(BaseModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    student_id: uuid.UUID
    points_awarded: int
    solved_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
