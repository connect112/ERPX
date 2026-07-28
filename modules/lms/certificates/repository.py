import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.lms.certificates.models import Certificate


class CertificateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Certificate:
        certificate = Certificate(**fields)
        self.db.add(certificate)
        await self.db.flush()
        await self.db.refresh(certificate)
        return certificate

    async def get_by_student_and_course(
        self, student_id: uuid.UUID, course_id: uuid.UUID
    ) -> Certificate | None:
        result = await self.db.execute(
            select(Certificate).where(
                Certificate.student_id == student_id, Certificate.course_id == course_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, certificate_number: str) -> Certificate | None:
        result = await self.db.execute(
            select(Certificate).where(Certificate.certificate_number == certificate_number)
        )
        return result.scalar_one_or_none()

    async def list_for_student(self, student_id: uuid.UUID) -> list[Certificate]:
        result = await self.db.execute(select(Certificate).where(Certificate.student_id == student_id))
        return list(result.scalars().all())
