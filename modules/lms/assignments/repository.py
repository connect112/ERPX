import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.lms.assignments.models import Assignment, AssignmentSubmission, SubmissionStatus


class AssignmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Assignment:
        assignment = Assignment(**fields)
        self.db.add(assignment)
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment

    async def get_by_id(self, assignment_id: uuid.UUID) -> Assignment | None:
        result = await self.db.execute(select(Assignment).where(Assignment.id == assignment_id))
        return result.scalar_one_or_none()

    async def list_for_course(self, course_id: uuid.UUID) -> list[Assignment]:
        result = await self.db.execute(
            select(Assignment).where(Assignment.course_id == course_id).order_by(Assignment.due_date)
        )
        return list(result.scalars().all())

    async def update(self, assignment: Assignment, **fields) -> Assignment:
        for key, value in fields.items():
            if value is not None:
                setattr(assignment, key, value)
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment

    async def delete(self, assignment: Assignment) -> None:
        await self.db.delete(assignment)
        await self.db.flush()


class SubmissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AssignmentSubmission:
        submission = AssignmentSubmission(**fields)
        self.db.add(submission)
        await self.db.flush()
        await self.db.refresh(submission)
        return submission

    async def get_by_id(self, submission_id: uuid.UUID) -> AssignmentSubmission | None:
        result = await self.db.execute(
            select(AssignmentSubmission).where(AssignmentSubmission.id == submission_id)
        )
        return result.scalar_one_or_none()

    async def get_by_assignment_and_student(
        self, assignment_id: uuid.UUID, student_id: uuid.UUID
    ) -> AssignmentSubmission | None:
        result = await self.db.execute(
            select(AssignmentSubmission).where(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.student_id == student_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_assignment(self, assignment_id: uuid.UUID) -> list[AssignmentSubmission]:
        result = await self.db.execute(
            select(AssignmentSubmission).where(AssignmentSubmission.assignment_id == assignment_id)
        )
        return list(result.scalars().all())

    async def grade(
        self, submission: AssignmentSubmission, score: int, feedback: str | None
    ) -> AssignmentSubmission:
        submission.score = score
        submission.feedback = feedback
        submission.status = SubmissionStatus.GRADED
        await self.db.flush()
        await self.db.refresh(submission)
        return submission
