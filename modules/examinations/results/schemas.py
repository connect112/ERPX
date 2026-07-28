import uuid

from pydantic import BaseModel


class ComponentResult(BaseModel):
    component_type: str  # "exam" | "practical" | "viva"
    component_id: uuid.UUID
    title: str
    score: int | None
    total_marks: int
    passing_marks: int
    passed: bool | None  # None if not yet evaluated


class StudentCourseResultResponse(BaseModel):
    student_id: uuid.UUID
    course_id: uuid.UUID
    components: list[ComponentResult]
    overall_score: int
    overall_total: int
    overall_percentage: float
    overall_status: str  # "pass" | "fail" | "incomplete"
