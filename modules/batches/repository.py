import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.batches.models import Batch, BatchEnrollment, BatchEnrollmentStatus, BatchStatus


class BatchRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Batch:
        batch = Batch(**fields)
        self.db.add(batch)
        await self.db.flush()
        await self.db.refresh(batch)
        return batch

    async def get_by_id(self, batch_id: uuid.UUID, organization_id: uuid.UUID) -> Batch | None:
        result = await self.db.execute(
            select(Batch).where(Batch.id == batch_id, Batch.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_org_and_code(self, organization_id: uuid.UUID, code: str) -> Batch | None:
        result = await self.db.execute(
            select(Batch).where(Batch.organization_id == organization_id, Batch.code == code)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        course_id: uuid.UUID | None = None,
        status: BatchStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Batch], int]:
        conditions = [Batch.organization_id == organization_id]
        if course_id is not None:
            conditions.append(Batch.course_id == course_id)
        if status is not None:
            conditions.append(Batch.status == status)

        count_result = await self.db.execute(select(func.count()).select_from(Batch).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Batch)
            .where(*conditions)
            .order_by(Batch.start_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_for_trainer(self, trainer_id: uuid.UUID, organization_id: uuid.UUID) -> list[Batch]:
        result = await self.db.execute(
            select(Batch)
            .where(Batch.trainer_id == trainer_id, Batch.organization_id == organization_id)
            .order_by(Batch.start_date.desc())
        )
        return list(result.scalars().all())

    async def trainer_teaches_course(self, trainer_id: uuid.UUID, course_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(func.count())
            .select_from(Batch)
            .where(Batch.trainer_id == trainer_id, Batch.course_id == course_id)
        )
        return result.scalar_one() > 0

    async def update(self, batch: Batch, **fields) -> Batch:
        for key, value in fields.items():
            if value is not None:
                setattr(batch, key, value)
        await self.db.flush()
        await self.db.refresh(batch)
        return batch

    async def delete(self, batch: Batch) -> None:
        await self.db.delete(batch)
        await self.db.flush()


class BatchEnrollmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
        student_id: uuid.UUID,
        enrolled_at: date,
    ) -> BatchEnrollment:
        enrollment = BatchEnrollment(
            organization_id=organization_id,
            batch_id=batch_id,
            student_id=student_id,
            enrolled_at=enrolled_at,
        )
        self.db.add(enrollment)
        await self.db.flush()
        await self.db.refresh(enrollment)
        return enrollment

    async def get_by_batch_and_student(
        self, batch_id: uuid.UUID, student_id: uuid.UUID
    ) -> BatchEnrollment | None:
        result = await self.db.execute(
            select(BatchEnrollment).where(
                BatchEnrollment.batch_id == batch_id, BatchEnrollment.student_id == student_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_student(
        self, student_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[BatchEnrollment]:
        result = await self.db.execute(
            select(BatchEnrollment)
            .where(
                BatchEnrollment.student_id == student_id,
                BatchEnrollment.organization_id == organization_id,
                BatchEnrollment.status == BatchEnrollmentStatus.ACTIVE,
            )
            .order_by(BatchEnrollment.enrolled_at.desc())
        )
        return list(result.scalars().all())

    async def list_batch_ids_for_student(
        self, student_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[uuid.UUID]:
        result = await self.db.execute(
            select(BatchEnrollment.batch_id).where(
                BatchEnrollment.student_id == student_id,
                BatchEnrollment.organization_id == organization_id,
                BatchEnrollment.status == BatchEnrollmentStatus.ACTIVE,
            )
        )
        return list(result.scalars().all())
