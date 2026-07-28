import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.internships.models import (
    Internship,
    InternshipApplication,
    InternshipApplicationStatus,
    InternshipPosting,
    InternshipPostingStatus,
    InternshipStatus,
)
from modules.internships.repository import (
    InternshipApplicationRepository,
    InternshipPostingRepository,
    InternshipRepository,
)
from modules.placements.repository import CompanyRepository

logger = get_logger(__name__)


class InternshipPostingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = InternshipPostingRepository(db)
        self.company_repo = CompanyRepository(db)

    async def create_posting(self, organization_id: uuid.UUID, company_id: uuid.UUID, **fields) -> InternshipPosting:
        company = await self.company_repo.get_by_id(company_id, organization_id)
        if not company:
            raise NotFoundError("Company", company_id)
        posting = await self.repo.create(organization_id=organization_id, company_id=company_id, **fields)
        logger.info("internship_posting_created", posting_id=str(posting.id))
        return posting

    async def get_posting(self, posting_id: uuid.UUID, organization_id: uuid.UUID) -> InternshipPosting:
        posting = await self.repo.get_by_id(posting_id, organization_id)
        if not posting:
            raise NotFoundError("Internship posting", posting_id)
        return posting

    async def list_postings(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_posting(
        self, posting_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> InternshipPosting:
        posting = await self.get_posting(posting_id, organization_id)
        updated = await self.repo.update(posting, **fields)
        logger.info("internship_posting_updated", posting_id=str(posting_id))
        return updated

    async def change_status(
        self, posting_id: uuid.UUID, organization_id: uuid.UUID, status: InternshipPostingStatus
    ) -> InternshipPosting:
        posting = await self.get_posting(posting_id, organization_id)
        updated = await self.repo.update(posting, status=status)
        logger.info("internship_posting_status_changed", posting_id=str(posting_id), status=status.value)
        return updated

    async def delete_posting(self, posting_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        posting = await self.get_posting(posting_id, organization_id)
        await self.repo.delete(posting)
        logger.info("internship_posting_deleted", posting_id=str(posting_id))


class InternshipApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = InternshipApplicationRepository(db)
        self.posting_repo = InternshipPostingRepository(db)
        self.internship_repo = InternshipRepository(db)

    async def apply(
        self,
        organization_id: uuid.UUID,
        internship_posting_id: uuid.UUID,
        student_id: uuid.UUID,
        cover_letter: str | None = None,
    ) -> InternshipApplication:
        posting = await self.posting_repo.get_by_id(internship_posting_id, organization_id)
        if not posting:
            raise NotFoundError("Internship posting", internship_posting_id)
        if posting.status != InternshipPostingStatus.OPEN:
            raise ValidationError("This internship posting is not currently accepting applications.")
        if posting.application_deadline and date.today() > posting.application_deadline:
            raise ValidationError("The application deadline for this posting has passed.")

        existing = await self.repo.get_by_posting_and_student(internship_posting_id, student_id)
        if existing:
            raise ConflictError("You have already applied to this internship posting.")

        application = await self.repo.create(
            internship_posting_id=internship_posting_id,
            student_id=student_id,
            applied_at=datetime.now(timezone.utc),
            cover_letter=cover_letter,
        )
        logger.info("internship_application_created", application_id=str(application.id))
        return application

    async def list_for_posting(
        self, posting_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[InternshipApplication]:
        posting = await self.posting_repo.get_by_id(posting_id, organization_id)
        if not posting:
            raise NotFoundError("Internship posting", posting_id)
        return await self.repo.list_for_posting(posting_id)

    async def list_for_student(self, student_id: uuid.UUID) -> list[InternshipApplication]:
        return await self.repo.list_for_student(student_id)

    async def change_status(
        self,
        application_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: InternshipApplicationStatus,
        notes: str | None = None,
    ) -> InternshipApplication:
        application = await self.repo.get_by_id(application_id)
        if not application:
            raise NotFoundError("Application", application_id)
        posting = await self.posting_repo.get_by_id(application.internship_posting_id, organization_id)
        if not posting:
            raise NotFoundError("Internship posting", application.internship_posting_id)

        updated = await self.repo.update(application, status=status, notes=notes)
        logger.info(
            "internship_application_status_changed", application_id=str(application_id), status=status.value
        )

        if status == InternshipApplicationStatus.SELECTED:
            existing_internship = await self.internship_repo.get_by_application_id(application_id)
            if not existing_internship:
                await self.internship_repo.create(
                    organization_id=organization_id,
                    application_id=application_id,
                    internship_posting_id=posting.id,
                    student_id=application.student_id,
                    start_date=date.today(),
                    stipend=posting.stipend,
                )
                logger.info("internship_created_from_selection", application_id=str(application_id))

        return updated

    async def withdraw(self, application_id: uuid.UUID, student_id: uuid.UUID) -> InternshipApplication:
        application = await self.repo.get_by_id(application_id)
        if not application or application.student_id != student_id:
            raise NotFoundError("Application", application_id)
        updated = await self.repo.update(application, status=InternshipApplicationStatus.WITHDRAWN)
        logger.info("internship_application_withdrawn", application_id=str(application_id))
        return updated


class InternshipService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = InternshipRepository(db)

    async def get_internship(self, internship_id: uuid.UUID, organization_id: uuid.UUID) -> Internship:
        internship = await self.repo.get_by_id(internship_id, organization_id)
        if not internship:
            raise NotFoundError("Internship", internship_id)
        return internship

    async def list_internships(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def list_for_student(self, student_id: uuid.UUID) -> list[Internship]:
        return await self.repo.list_for_student(student_id)

    async def update_internship(
        self,
        internship_id: uuid.UUID,
        organization_id: uuid.UUID,
        mentor_employee_id: uuid.UUID | None = None,
        end_date: date | None = None,
        stipend: float | None = None,
        feedback: str | None = None,
    ) -> Internship:
        internship = await self.get_internship(internship_id, organization_id)
        updated = await self.repo.update(
            internship,
            mentor_employee_id=mentor_employee_id,
            end_date=end_date,
            stipend=stipend,
            feedback=feedback,
        )
        logger.info("internship_updated", internship_id=str(internship_id))
        return updated

    async def change_status(
        self, internship_id: uuid.UUID, organization_id: uuid.UUID, status: InternshipStatus
    ) -> Internship:
        internship = await self.get_internship(internship_id, organization_id)
        fields = {"status": status}
        if status in (InternshipStatus.COMPLETED, InternshipStatus.TERMINATED) and not internship.end_date:
            fields["end_date"] = date.today()
        updated = await self.repo.update(internship, **fields)
        logger.info("internship_status_changed", internship_id=str(internship_id), status=status.value)
        return updated
