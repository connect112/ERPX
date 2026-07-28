"""
Transcripts — read-only aggregator, no dedicated table.

A student's transcript is always assembled live from the modules that
already own each piece of data: Enrollment (which courses), Progress
(completion %), Results (Examinations — exam/practical/viva scores,
itself already computed live rather than cached), and Certificates
(LMS). Storing a transcript snapshot would just be a copy that could
drift from the source records the moment any of them changes.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from modules.courses.repository import CourseRepository
from modules.examinations.evaluation.repository import ExamAttemptRepository
from modules.examinations.exams.repository import ExamRepository
from modules.examinations.practicals.repository import PracticalRepository
from modules.examinations.results.service import ResultsService
from modules.examinations.viva.repository import VivaRepository
from modules.lms.certificates.repository import CertificateRepository
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.lms.progress.service import ProgressService
from modules.lms.transcripts.schemas import CourseTranscriptEntry, TranscriptResponse
from modules.students.repository import StudentRepository


class TranscriptService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.student_repo = StudentRepository(db)
        self.course_repo = CourseRepository(db)
        self.enrollment_repo = EnrollmentRepository(db)
        self.certificate_repo = CertificateRepository(db)
        self.progress_service = ProgressService(db)
        self.results_service = ResultsService(db)
        self.exam_repo = ExamRepository(db)
        self.practical_repo = PracticalRepository(db)
        self.viva_repo = VivaRepository(db)

    async def _course_has_result_components(self, course_id: uuid.UUID) -> bool:
        if await self.exam_repo.list_for_course(course_id):
            return True
        if await self.practical_repo.list_for_course(course_id):
            return True
        if await self.viva_repo.list_for_course(course_id):
            return True
        return False

    async def get_student_transcript(
        self, organization_id: uuid.UUID, student_id: uuid.UUID
    ) -> TranscriptResponse:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        enrollments = await self.enrollment_repo.list_for_student(student_id)
        certificates = await self.certificate_repo.list_for_student(student_id)
        certificates_by_course = {c.course_id: c for c in certificates}

        entries: list[CourseTranscriptEntry] = []
        for enrollment in enrollments:
            course = await self.course_repo.get_by_id(enrollment.course_id, organization_id)
            if not course:
                continue

            progress = await self.progress_service.get_course_progress(
                organization_id, student_id, course.id
            )

            result = None
            if await self._course_has_result_components(course.id):
                result = await self.results_service.get_student_course_result(
                    student_id, course.id, organization_id
                )

            certificate = certificates_by_course.get(course.id)

            entries.append(
                CourseTranscriptEntry(
                    course_id=course.id,
                    course_title=course.title,
                    enrollment_status=enrollment.status.value,
                    enrolled_on=enrollment.enrolled_on,
                    percent_complete=progress.percent_complete,
                    result=result,
                    certificate_number=certificate.certificate_number if certificate else None,
                    certificate_issued_at=(
                        certificate.issued_at.isoformat() if certificate else None
                    ),
                )
            )

        completed_courses = sum(1 for e in enrollments if e.status.value == "completed")

        return TranscriptResponse(
            student_id=student.id,
            student_code=student.student_code,
            student_name=student.full_name,
            courses=entries,
            total_courses=len(enrollments),
            completed_courses=completed_courses,
            certificates_earned=len(certificates),
        )
