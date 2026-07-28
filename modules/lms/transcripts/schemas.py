import uuid
from datetime import date

from pydantic import BaseModel

from modules.examinations.results.schemas import StudentCourseResultResponse


class CourseTranscriptEntry(BaseModel):
    course_id: uuid.UUID
    course_title: str
    enrollment_status: str
    enrolled_on: date
    percent_complete: float
    result: StudentCourseResultResponse | None
    certificate_number: str | None
    certificate_issued_at: str | None


class TranscriptResponse(BaseModel):
    student_id: uuid.UUID
    student_code: str
    student_name: str
    courses: list[CourseTranscriptEntry]
    total_courses: int
    completed_courses: int
    certificates_earned: int
