import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.placements.models import Application, ApplicationStatus, Company, JobPosting, JobPostingStatus


class CompanyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Company:
        company = Company(**fields)
        self.db.add(company)
        await self.db.flush()
        await self.db.refresh(company)
        return company

    async def get_by_id(self, company_id: uuid.UUID, organization_id: uuid.UUID) -> Company | None:
        result = await self.db.execute(
            select(Company).where(
                Company.id == company_id,
                Company.organization_id == organization_id,
                Company.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[Company], int]:
        conditions = [Company.organization_id == organization_id, Company.deleted_at.is_(None)]
        count_result = await self.db.execute(select(func.count()).select_from(Company).where(*conditions))
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(Company).where(*conditions).order_by(Company.name.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, company: Company, **fields) -> Company:
        for key, value in fields.items():
            if value is not None:
                setattr(company, key, value)
        await self.db.flush()
        await self.db.refresh(company)
        return company

    async def soft_delete(self, company: Company) -> None:
        from datetime import datetime, timezone

        company.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()


class JobPostingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> JobPosting:
        posting = JobPosting(**fields)
        self.db.add(posting)
        await self.db.flush()
        await self.db.refresh(posting)
        return posting

    async def get_by_id(self, posting_id: uuid.UUID, organization_id: uuid.UUID) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting).where(
                JobPosting.id == posting_id, JobPosting.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: JobPostingStatus | None = None,
        company_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[JobPosting], int]:
        conditions = [JobPosting.organization_id == organization_id]
        if status is not None:
            conditions.append(JobPosting.status == status)
        if company_id is not None:
            conditions.append(JobPosting.company_id == company_id)

        count_result = await self.db.execute(
            select(func.count()).select_from(JobPosting).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(JobPosting)
            .where(*conditions)
            .order_by(JobPosting.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, posting: JobPosting, **fields) -> JobPosting:
        for key, value in fields.items():
            if value is not None:
                setattr(posting, key, value)
        await self.db.flush()
        await self.db.refresh(posting)
        return posting

    async def delete(self, posting: JobPosting) -> None:
        await self.db.delete(posting)
        await self.db.flush()


class ApplicationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Application:
        application = Application(**fields)
        self.db.add(application)
        await self.db.flush()
        await self.db.refresh(application)
        return application

    async def get_by_id(self, application_id: uuid.UUID) -> Application | None:
        result = await self.db.execute(select(Application).where(Application.id == application_id))
        return result.scalar_one_or_none()

    async def get_by_posting_and_student(
        self, job_posting_id: uuid.UUID, student_id: uuid.UUID
    ) -> Application | None:
        result = await self.db.execute(
            select(Application).where(
                Application.job_posting_id == job_posting_id, Application.student_id == student_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_posting(self, job_posting_id: uuid.UUID) -> list[Application]:
        result = await self.db.execute(
            select(Application)
            .where(Application.job_posting_id == job_posting_id)
            .order_by(Application.applied_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_student(self, student_id: uuid.UUID) -> list[Application]:
        result = await self.db.execute(
            select(Application)
            .where(Application.student_id == student_id)
            .order_by(Application.applied_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, application: Application, **fields) -> Application:
        for key, value in fields.items():
            if value is not None:
                setattr(application, key, value)
        await self.db.flush()
        await self.db.refresh(application)
        return application
