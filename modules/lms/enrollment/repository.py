import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.lms.enrollment.models import Enrollment, EnrollmentStatus


class EnrollmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Enrollment:
        enrollment = Enrollment(**fields)
        self.db.add(enrollment)
        await self.db.flush()
        await self.db.refresh(enrollment)
        return enrollment

    async def get_by_id(self, enrollment_id: uuid.UUID) -> Enrollment | None:
        result = await self.db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
        return result.scalar_one_or_none()

    async def get_by_student_and_course(
        self, student_id: uuid.UUID, course_id: uuid.UUID
    ) -> Enrollment | None:
        result = await self.db.execute(
            select(Enrollment).where(
                Enrollment.student_id == student_id, Enrollment.course_id == course_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_student(self, student_id: uuid.UUID) -> list[Enrollment]:
        result = await self.db.execute(
            select(Enrollment).where(Enrollment.student_id == student_id)
        )
        return list(result.scalars().all())

    async def list_for_course(self, course_id: uuid.UUID) -> list[Enrollment]:
        result = await self.db.execute(select(Enrollment).where(Enrollment.course_id == course_id))
        return list(result.scalars().all())

    async def set_status(self, enrollment: Enrollment, status: EnrollmentStatus) -> Enrollment:
        enrollment.status = status
        await self.db.flush()
        await self.db.refresh(enrollment)
        return enrollment
