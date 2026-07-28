"""
Results sub-module — service layer.

Deliberately has no dedicated table: a student's overall result for a
course is always computed live from Exam attempts (Evaluation),
Practical results, and Viva results, which are each the single source
of truth for their own component. Storing a fourth "results" table
alongside them would just be a cache that could drift out of sync.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from modules.courses.repository import CourseRepository
from modules.examinations.evaluation.models import AttemptStatus
from modules.examinations.evaluation.repository import ExamAttemptRepository
from modules.examinations.exams.repository import ExamRepository
from modules.examinations.practicals.repository import PracticalRepository
from modules.examinations.results.schemas import ComponentResult, StudentCourseResultResponse
from modules.examinations.viva.repository import VivaRepository
from modules.students.repository import StudentRepository


class ResultsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.course_repo = CourseRepository(db)
        self.student_repo = StudentRepository(db)
        self.exam_repo = ExamRepository(db)
        self.attempt_repo = ExamAttemptRepository(db)
        self.practical_repo = PracticalRepository(db)
        self.viva_repo = VivaRepository(db)

    async def get_student_course_result(
        self, student_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> StudentCourseResultResponse:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)

        components: list[ComponentResult] = []

        for exam in await self.exam_repo.list_for_course(course_id):
            attempt = await self.attempt_repo.get_by_exam_and_student(exam.id, student_id)
            total_marks = await self.exam_repo.total_marks(exam.id)
            score = attempt.total_score if attempt and attempt.status == AttemptStatus.EVALUATED else None
            components.append(
                ComponentResult(
                    component_type="exam",
                    component_id=exam.id,
                    title=exam.title,
                    score=score,
                    total_marks=total_marks,
                    passing_marks=exam.passing_marks,
                    passed=(score >= exam.passing_marks) if score is not None else None,
                )
            )

        for practical in await self.practical_repo.list_for_course(course_id):
            result_row = await self.practical_repo.get_result(practical.id, student_id)
            score = result_row.score if result_row else None
            components.append(
                ComponentResult(
                    component_type="practical",
                    component_id=practical.id,
                    title=practical.title,
                    score=score,
                    total_marks=practical.total_marks,
                    passing_marks=practical.passing_marks,
                    passed=(score >= practical.passing_marks) if score is not None else None,
                )
            )

        for viva in await self.viva_repo.list_for_course(course_id):
            result_row = await self.viva_repo.get_result(viva.id, student_id)
            score = result_row.score if result_row else None
            components.append(
                ComponentResult(
                    component_type="viva",
                    component_id=viva.id,
                    title=viva.title,
                    score=score,
                    total_marks=viva.total_marks,
                    passing_marks=viva.passing_marks,
                    passed=(score >= viva.passing_marks) if score is not None else None,
                )
            )

        overall_total = sum(c.total_marks for c in components)
        overall_score = sum(c.score or 0 for c in components)
        overall_percentage = (
            round((overall_score / overall_total) * 100, 2) if overall_total > 0 else 0.0
        )

        if not components:
            overall_status = "incomplete"
        elif any(c.passed is None for c in components):
            overall_status = "incomplete"
        elif all(c.passed for c in components):
            overall_status = "pass"
        else:
            overall_status = "fail"

        return StudentCourseResultResponse(
            student_id=student_id,
            course_id=course_id,
            components=components,
            overall_score=overall_score,
            overall_total=overall_total,
            overall_percentage=overall_percentage,
            overall_status=overall_status,
        )
