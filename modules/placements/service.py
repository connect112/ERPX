import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.placements.models import (
    Application,
    ApplicationStatus,
    Company,
    JobPosting,
    JobPostingStatus,
)
from modules.placements.repository import ApplicationRepository, CompanyRepository, JobPostingRepository

logger = get_logger(__name__)


class CompanyService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CompanyRepository(db)

    async def create_company(self, organization_id: uuid.UUID, **fields) -> Company:
        company = await self.repo.create(organization_id=organization_id, **fields)
        logger.info("placement_company_created", company_id=str(company.id))
        return company

    async def get_company(self, company_id: uuid.UUID, organization_id: uuid.UUID) -> Company:
        company = await self.repo.get_by_id(company_id, organization_id)
        if not company:
            raise NotFoundError("Company", company_id)
        return company

    async def list_companies(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_company(self, company_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Company:
        company = await self.get_company(company_id, organization_id)
        updated = await self.repo.update(company, **fields)
        logger.info("placement_company_updated", company_id=str(company_id))
        return updated

    async def delete_company(self, company_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        company = await self.get_company(company_id, organization_id)
        await self.repo.soft_delete(company)
        logger.info("placement_company_deleted", company_id=str(company_id))


class JobPostingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = JobPostingRepository(db)
        self.company_repo = CompanyRepository(db)

    async def create_posting(
        self, organization_id: uuid.UUID, company_id: uuid.UUID, **fields
    ) -> JobPosting:
        company = await self.company_repo.get_by_id(company_id, organization_id)
        if not company:
            raise NotFoundError("Company", company_id)
        posting = await self.repo.create(organization_id=organization_id, company_id=company_id, **fields)
        logger.info("job_posting_created", posting_id=str(posting.id))
        return posting

    async def get_posting(self, posting_id: uuid.UUID, organization_id: uuid.UUID) -> JobPosting:
        posting = await self.repo.get_by_id(posting_id, organization_id)
        if not posting:
            raise NotFoundError("Job posting", posting_id)
        return posting

    async def list_postings(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_posting(
        self, posting_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> JobPosting:
        posting = await self.get_posting(posting_id, organization_id)
        updated = await self.repo.update(posting, **fields)
        logger.info("job_posting_updated", posting_id=str(posting_id))
        return updated

    async def change_status(
        self, posting_id: uuid.UUID, organization_id: uuid.UUID, status: JobPostingStatus
    ) -> JobPosting:
        posting = await self.get_posting(posting_id, organization_id)
        updated = await self.repo.update(posting, status=status)
        logger.info("job_posting_status_changed", posting_id=str(posting_id), status=status.value)
        return updated

    async def delete_posting(self, posting_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        posting = await self.get_posting(posting_id, organization_id)
        await self.repo.delete(posting)
        logger.info("job_posting_deleted", posting_id=str(posting_id))


class ApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ApplicationRepository(db)
        self.posting_repo = JobPostingRepository(db)

    async def apply(
        self,
        organization_id: uuid.UUID,
        job_posting_id: uuid.UUID,
        student_id: uuid.UUID,
        cover_letter: str | None = None,
    ) -> Application:
        posting = await self.posting_repo.get_by_id(job_posting_id, organization_id)
        if not posting:
            raise NotFoundError("Job posting", job_posting_id)
        if posting.status != JobPostingStatus.OPEN:
            raise ValidationError("This job posting is not currently accepting applications.")
        if posting.application_deadline and date.today() > posting.application_deadline:
            raise ValidationError("The application deadline for this posting has passed.")

        existing = await self.repo.get_by_posting_and_student(job_posting_id, student_id)
        if existing:
            raise ConflictError("You have already applied to this job posting.")

        application = await self.repo.create(
            job_posting_id=job_posting_id,
            student_id=student_id,
            applied_at=datetime.now(timezone.utc),
            cover_letter=cover_letter,
        )
        logger.info("placement_application_created", application_id=str(application.id))
        return application

    async def list_for_posting(self, posting_id: uuid.UUID, organization_id: uuid.UUID) -> list[Application]:
        posting = await self.posting_repo.get_by_id(posting_id, organization_id)
        if not posting:
            raise NotFoundError("Job posting", posting_id)
        return await self.repo.list_for_posting(posting_id)

    async def list_for_student(self, student_id: uuid.UUID) -> list[Application]:
        return await self.repo.list_for_student(student_id)

    async def change_status(
        self,
        application_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: ApplicationStatus,
        notes: str | None = None,
    ) -> Application:
        application = await self.repo.get_by_id(application_id)
        if not application:
            raise NotFoundError("Application", application_id)
        posting = await self.posting_repo.get_by_id(application.job_posting_id, organization_id)
        if not posting:
            raise NotFoundError("Job posting", application.job_posting_id)

        updated = await self.repo.update(application, status=status, notes=notes)
        logger.info(
            "placement_application_status_changed", application_id=str(application_id), status=status.value
        )
        return updated

    async def withdraw(self, application_id: uuid.UUID, student_id: uuid.UUID) -> Application:
        application = await self.repo.get_by_id(application_id)
        if not application or application.student_id != student_id:
            raise NotFoundError("Application", application_id)
        updated = await self.repo.update(application, status=ApplicationStatus.WITHDRAWN)
        logger.info("placement_application_withdrawn", application_id=str(application_id))
        return updated
