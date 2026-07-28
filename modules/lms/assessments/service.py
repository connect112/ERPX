import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.lms.assessments.models import Assessment, AssessmentAttempt
from modules.lms.assessments.repository import AssessmentRepository, AttemptRepository
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class AssessmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AssessmentRepository(db)
        self.attempt_repo = AttemptRepository(db)
        self.course_repo = CourseRepository(db)
        self.student_repo = StudentRepository(db)

    async def create_assessment(
        self, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Assessment:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        assessment = await self.repo.create(course_id=course_id, **fields)
        logger.info("assessment_created", assessment_id=str(assessment.id))
        return assessment

    async def _get_owned_assessment(
        self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Assessment:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        assessment = await self.repo.get_by_id(assessment_id)
        if not assessment or assessment.course_id != course_id:
            raise NotFoundError("Assessment", assessment_id)
        return assessment

    async def list_assessments(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> list[Assessment]:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        return await self.repo.list_for_course(course_id)

    async def get_assessment(
        self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Assessment:
        return await self._get_owned_assessment(assessment_id, course_id, organization_id)

    async def update_assessment(
        self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Assessment:
        assessment = await self._get_owned_assessment(assessment_id, course_id, organization_id)
        updated = await self.repo.update(assessment, **fields)
        logger.info("assessment_updated", assessment_id=str(assessment_id))
        return updated

    async def delete_assessment(
        self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        assessment = await self._get_owned_assessment(assessment_id, course_id, organization_id)
        await self.repo.delete(assessment)
        logger.info("assessment_deleted", assessment_id=str(assessment_id))

    async def start_attempt(
        self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, student_id: uuid.UUID
    ) -> AssessmentAttempt:
        assessment = await self._get_owned_assessment(assessment_id, course_id, organization_id)
        if not assessment.is_published:
            raise ValidationError("This assessment is not yet published.")

        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        existing = await self.attempt_repo.get_by_assessment_and_student(assessment_id, student_id)
        if existing:
            raise ConflictError("This student has already attempted this assessment.")

        attempt = await self.attempt_repo.create(
            assessment_id=assessment_id,
            student_id=student_id,
            started_at=datetime.now(timezone.utc),
        )
        logger.info("assessment_attempt_started", attempt_id=str(attempt.id))
        return attempt

    async def submit_attempt(
        self,
        attempt_id: uuid.UUID,
        assessment_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        score: int,
    ) -> AssessmentAttempt:
        assessment = await self._get_owned_assessment(assessment_id, course_id, organization_id)
        attempt = await self.attempt_repo.get_by_id(attempt_id)
        if not attempt or attempt.assessment_id != assessment_id:
            raise NotFoundError("Attempt", attempt_id)
        if score > assessment.total_marks:
            raise ValidationError(f"Score cannot exceed the total marks of {assessment.total_marks}.")

        submitted = await self.attempt_repo.submit(attempt, score)
        logger.info("assessment_attempt_submitted", attempt_id=str(attempt_id), score=score)
        return submitted

    async def list_attempts(
        self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[AssessmentAttempt]:
        await self._get_owned_assessment(assessment_id, course_id, organization_id)
        return await self.attempt_repo.list_for_assessment(assessment_id)
