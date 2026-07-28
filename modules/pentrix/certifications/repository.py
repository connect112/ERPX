import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.pentrix.certifications.models import PentrixCertification


class CertificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> PentrixCertification:
        cert = PentrixCertification(**fields)
        self.db.add(cert)
        await self.db.flush()
        await self.db.refresh(cert)
        return cert

    async def get_by_student_and_track(
        self, student_id: uuid.UUID, track_name: str
    ) -> PentrixCertification | None:
        result = await self.db.execute(
            select(PentrixCertification).where(
                PentrixCertification.student_id == student_id,
                PentrixCertification.track_name == track_name,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, certificate_number: str) -> PentrixCertification | None:
        result = await self.db.execute(
            select(PentrixCertification).where(
                PentrixCertification.certificate_number == certificate_number
            )
        )
        return result.scalar_one_or_none()

    async def list_for_student(self, student_id: uuid.UUID) -> list[PentrixCertification]:
        result = await self.db.execute(
            select(PentrixCertification).where(PentrixCertification.student_id == student_id)
        )
        return list(result.scalars().all())
