import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.lms.assignments.models import Assignment, AssignmentSubmission, SubmissionStatus
from modules.lms.assignments.repository import AssignmentRepository, SubmissionRepository
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class AssignmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AssignmentRepository(db)
        self.submission_repo = SubmissionRepository(db)
        self.course_repo = CourseRepository(db)
        self.student_repo = StudentRepository(db)

    async def create_assignment(
        self, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Assignment:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        assignment = await self.repo.create(course_id=course_id, **fields)
        logger.info("assignment_created", assignment_id=str(assignment.id), course_id=str(course_id))
        return assignment

    async def _get_owned_assignment(
        self, assignment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Assignment:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        assignment = await self.repo.get_by_id(assignment_id)
        if not assignment or assignment.course_id != course_id:
            raise NotFoundError("Assignment", assignment_id)
        return assignment

    async def list_assignments(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> list[Assignment]:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        return await self.repo.list_for_course(course_id)

    async def get_assignment(
        self, assignment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Assignment:
        return await self._get_owned_assignment(assignment_id, course_id, organization_id)

    async def update_assignment(
        self, assignment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Assignment:
        assignment = await self._get_owned_assignment(assignment_id, course_id, organization_id)
        updated = await self.repo.update(assignment, **fields)
        logger.info("assignment_updated", assignment_id=str(assignment_id))
        return updated

    async def delete_assignment(
        self, assignment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        assignment = await self._get_owned_assignment(assignment_id, course_id, organization_id)
        await self.repo.delete(assignment)
        logger.info("assignment_deleted", assignment_id=str(assignment_id))

    async def submit(
        self,
        assignment_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        student_id: uuid.UUID,
        content_url: str | None,
        content_text: str | None,
    ) -> AssignmentSubmission:
        assignment = await self._get_owned_assignment(assignment_id, course_id, organization_id)
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        existing = await self.submission_repo.get_by_assignment_and_student(assignment_id, student_id)
        if existing:
            raise ConflictError("This student has already submitted this assignment.")

        now = datetime.now(timezone.utc)
        status = SubmissionStatus.SUBMITTED
        if assignment.due_date and now > assignment.due_date:
            status = SubmissionStatus.LATE

        submission = await self.submission_repo.create(
            assignment_id=assignment_id,
            student_id=student_id,
            content_url=content_url,
            content_text=content_text,
            submitted_at=now,
            status=status,
        )
        logger.info(
            "assignment_submitted", submission_id=str(submission.id), assignment_id=str(assignment_id)
        )
        return submission

    async def list_submissions(
        self, assignment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[AssignmentSubmission]:
        await self._get_owned_assignment(assignment_id, course_id, organization_id)
        return await self.submission_repo.list_for_assignment(assignment_id)

    async def grade_submission(
        self,
        submission_id: uuid.UUID,
        assignment_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        score: int,
        feedback: str | None,
    ) -> AssignmentSubmission:
        assignment = await self._get_owned_assignment(assignment_id, course_id, organization_id)
        submission = await self.submission_repo.get_by_id(submission_id)
        if not submission or submission.assignment_id != assignment_id:
            raise NotFoundError("Submission", submission_id)
        if score > assignment.max_score:
            from app.core.exceptions import ValidationError

            raise ValidationError(
                f"Score cannot exceed the assignment's max score of {assignment.max_score}."
            )
        graded = await self.submission_repo.grade(submission, score, feedback)
        logger.info("submission_graded", submission_id=str(submission_id), score=score)
        return graded
