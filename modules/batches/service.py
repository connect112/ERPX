import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.batches.models import Batch, BatchEnrollment
from modules.batches.repository import BatchEnrollmentRepository, BatchRepository
from modules.courses.repository import CourseRepository
from modules.trainers.repository import TrainerRepository

logger = get_logger(__name__)


class BatchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BatchRepository(db)
        self.enrollment_repo = BatchEnrollmentRepository(db)
        self.course_repo = CourseRepository(db)
        self.trainer_repo = TrainerRepository(db)

    async def create_batch(
        self,
        organization_id: uuid.UUID,
        course_id: uuid.UUID,
        code: str,
        trainer_id: uuid.UUID | None = None,
        **fields,
    ) -> Batch:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)

        if trainer_id is not None:
            trainer = await self.trainer_repo.get_by_id(trainer_id, organization_id)
            if not trainer:
                raise NotFoundError("Trainer", trainer_id)

        existing = await self.repo.get_by_org_and_code(organization_id, code)
        if existing:
            raise ConflictError(f"A batch with code '{code}' already exists for this organization.")

        batch = await self.repo.create(
            organization_id=organization_id,
            course_id=course_id,
            code=code,
            trainer_id=trainer_id,
            **fields,
        )
        logger.info("batch_created", batch_id=str(batch.id), course_id=str(course_id))
        return batch

    async def get_batch(self, batch_id: uuid.UUID, organization_id: uuid.UUID) -> Batch:
        batch = await self.repo.get_by_id(batch_id, organization_id)
        if not batch:
            raise NotFoundError("Batch", batch_id)
        return batch

    async def list_batches(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_batch(self, batch_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Batch:
        batch = await self.get_batch(batch_id, organization_id)

        trainer_id = fields.get("trainer_id")
        if trainer_id is not None:
            trainer = await self.trainer_repo.get_by_id(trainer_id, organization_id)
            if not trainer:
                raise NotFoundError("Trainer", trainer_id)

        updated = await self.repo.update(batch, **fields)
        logger.info("batch_updated", batch_id=str(batch_id))
        return updated

    async def delete_batch(self, batch_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        batch = await self.get_batch(batch_id, organization_id)
        await self.repo.delete(batch)
        logger.info("batch_deleted", batch_id=str(batch_id))

    # ---- Batch enrollment (student membership) ----

    async def enroll_student(
        self,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
        student_id: uuid.UUID,
        enrolled_at: date | None = None,
    ) -> BatchEnrollment:
        batch = await self.get_batch(batch_id, organization_id)
        existing = await self.enrollment_repo.get_by_batch_and_student(batch.id, student_id)
        if existing:
            raise ConflictError("This student is already a member of this batch.")
        enrollment = await self.enrollment_repo.create(
            organization_id=organization_id,
            batch_id=batch.id,
            student_id=student_id,
            enrolled_at=enrolled_at or date.today(),
        )
        logger.info("batch_enrollment_created", batch_id=str(batch.id), student_id=str(student_id))
        return enrollment

    async def list_my_batches(
        self, student_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[tuple[BatchEnrollment, Batch, str]]:
        """Returns (membership, batch, course_title) tuples for a student's own batches."""
        memberships = await self.enrollment_repo.list_for_student(student_id, organization_id)
        results = []
        course_titles: dict[uuid.UUID, str] = {}
        for membership in memberships:
            batch = await self.repo.get_by_id(membership.batch_id, organization_id)
            if not batch:
                continue
            if batch.course_id not in course_titles:
                course = await self.course_repo.get_by_id(batch.course_id, organization_id)
                course_titles[batch.course_id] = course.title if course else "Unknown course"
            results.append((membership, batch, course_titles[batch.course_id]))
        return results
