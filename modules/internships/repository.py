import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.internships.models import (
    Internship,
    InternshipApplication,
    InternshipApplicationStatus,
    InternshipPosting,
    InternshipPostingStatus,
)


class InternshipPostingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> InternshipPosting:
        posting = InternshipPosting(**fields)
        self.db.add(posting)
        await self.db.flush()
        await self.db.refresh(posting)
        return posting

    async def get_by_id(
        self, posting_id: uuid.UUID, organization_id: uuid.UUID
    ) -> InternshipPosting | None:
        result = await self.db.execute(
            select(InternshipPosting).where(
                InternshipPosting.id == posting_id, InternshipPosting.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: InternshipPostingStatus | None = None,
        company_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[InternshipPosting], int]:
        conditions = [InternshipPosting.organization_id == organization_id]
        if status is not None:
            conditions.append(InternshipPosting.status == status)
        if company_id is not None:
            conditions.append(InternshipPosting.company_id == company_id)

        count_result = await self.db.execute(
            select(func.count()).select_from(InternshipPosting).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(InternshipPosting)
            .where(*conditions)
            .order_by(InternshipPosting.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, posting: InternshipPosting, **fields) -> InternshipPosting:
        for key, value in fields.items():
            if value is not None:
                setattr(posting, key, value)
        await self.db.flush()
        await self.db.refresh(posting)
        return posting

    async def delete(self, posting: InternshipPosting) -> None:
        await self.db.delete(posting)
        await self.db.flush()


class InternshipApplicationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> InternshipApplication:
        application = InternshipApplication(**fields)
        self.db.add(application)
        await self.db.flush()
        await self.db.refresh(application)
        return application

    async def get_by_id(self, application_id: uuid.UUID) -> InternshipApplication | None:
        result = await self.db.execute(
            select(InternshipApplication).where(InternshipApplication.id == application_id)
        )
        return result.scalar_one_or_none()

    async def get_by_posting_and_student(
        self, internship_posting_id: uuid.UUID, student_id: uuid.UUID
    ) -> InternshipApplication | None:
        result = await self.db.execute(
            select(InternshipApplication).where(
                InternshipApplication.internship_posting_id == internship_posting_id,
                InternshipApplication.student_id == student_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_posting(self, internship_posting_id: uuid.UUID) -> list[InternshipApplication]:
        result = await self.db.execute(
            select(InternshipApplication)
            .where(InternshipApplication.internship_posting_id == internship_posting_id)
            .order_by(InternshipApplication.applied_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_student(self, student_id: uuid.UUID) -> list[InternshipApplication]:
        result = await self.db.execute(
            select(InternshipApplication)
            .where(InternshipApplication.student_id == student_id)
            .order_by(InternshipApplication.applied_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, application: InternshipApplication, **fields) -> InternshipApplication:
        for key, value in fields.items():
            if value is not None:
                setattr(application, key, value)
        await self.db.flush()
        await self.db.refresh(application)
        return application


class InternshipRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Internship:
        internship = Internship(**fields)
        self.db.add(internship)
        await self.db.flush()
        await self.db.refresh(internship)
        return internship

    async def get_by_id(self, internship_id: uuid.UUID, organization_id: uuid.UUID) -> Internship | None:
        result = await self.db.execute(
            select(Internship).where(
                Internship.id == internship_id, Internship.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_application_id(self, application_id: uuid.UUID) -> Internship | None:
        result = await self.db.execute(
            select(Internship).where(Internship.application_id == application_id)
        )
        return result.scalar_one_or_none()

    async def list_for_student(self, student_id: uuid.UUID) -> list[Internship]:
        result = await self.db.execute(
            select(Internship)
            .where(Internship.student_id == student_id)
            .order_by(Internship.start_date.desc())
        )
        return list(result.scalars().all())

    async def list_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[Internship], int]:
        conditions = [Internship.organization_id == organization_id]
        count_result = await self.db.execute(
            select(func.count()).select_from(Internship).where(*conditions)
        )
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(Internship)
            .where(*conditions)
            .order_by(Internship.start_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, internship: Internship, **fields) -> Internship:
        for key, value in fields.items():
            if value is not None:
                setattr(internship, key, value)
        await self.db.flush()
        await self.db.refresh(internship)
        return internship
