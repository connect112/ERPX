import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.lms.assessments.models import Assessment, AssessmentAttempt, AttemptStatus


class AssessmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Assessment:
        assessment = Assessment(**fields)
        self.db.add(assessment)
        await self.db.flush()
        await self.db.refresh(assessment)
        return assessment

    async def get_by_id(self, assessment_id: uuid.UUID) -> Assessment | None:
        result = await self.db.execute(select(Assessment).where(Assessment.id == assessment_id))
        return result.scalar_one_or_none()

    async def list_for_course(self, course_id: uuid.UUID) -> list[Assessment]:
        result = await self.db.execute(select(Assessment).where(Assessment.course_id == course_id))
        return list(result.scalars().all())

    async def update(self, assessment: Assessment, **fields) -> Assessment:
        for key, value in fields.items():
            if value is not None:
                setattr(assessment, key, value)
        await self.db.flush()
        await self.db.refresh(assessment)
        return assessment

    async def delete(self, assessment: Assessment) -> None:
        await self.db.delete(assessment)
        await self.db.flush()


class AttemptRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AssessmentAttempt:
        attempt = AssessmentAttempt(**fields)
        self.db.add(attempt)
        await self.db.flush()
        await self.db.refresh(attempt)
        return attempt

    async def get_by_id(self, attempt_id: uuid.UUID) -> AssessmentAttempt | None:
        result = await self.db.execute(
            select(AssessmentAttempt).where(AssessmentAttempt.id == attempt_id)
        )
        return result.scalar_one_or_none()

    async def get_by_assessment_and_student(
        self, assessment_id: uuid.UUID, student_id: uuid.UUID
    ) -> AssessmentAttempt | None:
        result = await self.db.execute(
            select(AssessmentAttempt).where(
                AssessmentAttempt.assessment_id == assessment_id,
                AssessmentAttempt.student_id == student_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_assessment(self, assessment_id: uuid.UUID) -> list[AssessmentAttempt]:
        result = await self.db.execute(
            select(AssessmentAttempt).where(AssessmentAttempt.assessment_id == assessment_id)
        )
        return list(result.scalars().all())

    async def submit(self, attempt: AssessmentAttempt, score: int) -> AssessmentAttempt:
        from datetime import datetime, timezone

        attempt.score = score
        attempt.status = AttemptStatus.EVALUATED
        attempt.submitted_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(attempt)
        return attempt
