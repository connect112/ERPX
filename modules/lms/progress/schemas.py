import uuid
from datetime import datetime

from pydantic import BaseModel


class MarkLessonCompleteRequest(BaseModel):
    student_id: uuid.UUID
    lesson_id: uuid.UUID


class LessonProgressPublic(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    lesson_id: uuid.UUID
    completed_at: datetime

    model_config = {"from_attributes": True}


class CourseProgressResponse(BaseModel):
    student_id: uuid.UUID
    course_id: uuid.UUID
    total_lessons: int
    completed_lessons: int
    percent_complete: float
    completed_lesson_ids: list[uuid.UUID]


class MessageResponse(BaseModel):
    message: str
