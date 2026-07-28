import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.placements.models import JobPostingStatus
from modules.placements.schemas import (
    ApplicationCreateRequest,
    ApplicationPublic,
    ApplicationStatusChangeRequest,
    CompanyCreateRequest,
    CompanyListResponse,
    CompanyPublic,
    CompanyUpdateRequest,
    JobPostingCreateRequest,
    JobPostingListResponse,
    JobPostingPublic,
    JobPostingStatusChangeRequest,
    JobPostingUpdateRequest,
    MessageResponse,
)
from modules.placements.service import ApplicationService, CompanyService, JobPostingService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Student self-service ----


@router.get("/postings/me", response_model=list[JobPostingPublic])
async def list_open_postings(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = JobPostingService(db)
    postings, _total = await service.list_postings(
        student.organization_id, status=JobPostingStatus.OPEN, skip=0, limit=200
    )
    return [JobPostingPublic.model_validate(p) for p in postings]


@router.post(
    "/postings/{posting_id}/apply/me", response_model=ApplicationPublic, status_code=status.HTTP_201_CREATED
)
async def apply_to_posting(
    posting_id: uuid.UUID,
    payload: ApplicationCreateRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = ApplicationService(db)
    application = await service.apply(
        student.organization_id, posting_id, student.id, cover_letter=payload.cover_letter
    )
    return ApplicationPublic.model_validate(application)


@router.get("/applications/me", response_model=list[ApplicationPublic])
async def list_my_applications(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = ApplicationService(db)
    applications = await service.list_for_student(student.id)
    return [ApplicationPublic.model_validate(a) for a in applications]


@router.post("/applications/{application_id}/withdraw/me", response_model=ApplicationPublic)
async def withdraw_application(
    application_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = ApplicationService(db)
    application = await service.withdraw(application_id, student.id)
    return ApplicationPublic.model_validate(application)


# ---- Staff: companies ----


@router.post("/companies", response_model=CompanyPublic, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CompanyService(db)
    company = await service.create_company(organization_id, **payload.model_dump())
    return CompanyPublic.model_validate(company)


@router.get("/companies", response_model=CompanyListResponse)
async def list_companies(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CompanyService(db)
    companies, total = await service.list_companies(organization_id, skip=skip, limit=limit)
    return CompanyListResponse(items=[CompanyPublic.model_validate(c) for c in companies], total=total)


@router.get("/companies/{company_id}", response_model=CompanyPublic)
async def get_company(
    company_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CompanyService(db)
    company = await service.get_company(company_id, organization_id)
    return CompanyPublic.model_validate(company)


@router.patch("/companies/{company_id}", response_model=CompanyPublic)
async def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CompanyService(db)
    company = await service.update_company(
        company_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return CompanyPublic.model_validate(company)


@router.delete("/companies/{company_id}", response_model=MessageResponse)
async def delete_company(
    company_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CompanyService(db)
    await service.delete_company(company_id, organization_id)
    return MessageResponse(message="Company deleted successfully.")


# ---- Staff: job postings ----


@router.post("/postings", response_model=JobPostingPublic, status_code=status.HTTP_201_CREATED)
async def create_posting(
    payload: JobPostingCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = JobPostingService(db)
    posting = await service.create_posting(organization_id, **payload.model_dump())
    return JobPostingPublic.model_validate(posting)


@router.get("/postings", response_model=JobPostingListResponse)
async def list_postings(
    status_filter: JobPostingStatus | None = Query(default=None, alias="status"),
    company_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.view")),
    db: AsyncSession = Depends(get_db),
):
    service = JobPostingService(db)
    postings, total = await service.list_postings(
        organization_id, status=status_filter, company_id=company_id, skip=skip, limit=limit
    )
    return JobPostingListResponse(
        items=[JobPostingPublic.model_validate(p) for p in postings], total=total
    )


@router.get("/postings/{posting_id}", response_model=JobPostingPublic)
async def get_posting(
    posting_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.view")),
    db: AsyncSession = Depends(get_db),
):
    service = JobPostingService(db)
    posting = await service.get_posting(posting_id, organization_id)
    return JobPostingPublic.model_validate(posting)


@router.patch("/postings/{posting_id}", response_model=JobPostingPublic)
async def update_posting(
    posting_id: uuid.UUID,
    payload: JobPostingUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = JobPostingService(db)
    posting = await service.update_posting(
        posting_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return JobPostingPublic.model_validate(posting)


@router.post("/postings/{posting_id}/status", response_model=JobPostingPublic)
async def change_posting_status(
    posting_id: uuid.UUID,
    payload: JobPostingStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = JobPostingService(db)
    posting = await service.change_status(posting_id, organization_id, payload.status)
    return JobPostingPublic.model_validate(posting)


@router.delete("/postings/{posting_id}", response_model=MessageResponse)
async def delete_posting(
    posting_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = JobPostingService(db)
    await service.delete_posting(posting_id, organization_id)
    return MessageResponse(message="Job posting deleted successfully.")


@router.get("/postings/{posting_id}/applications", response_model=list[ApplicationPublic])
async def list_posting_applications(
    posting_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ApplicationService(db)
    applications = await service.list_for_posting(posting_id, organization_id)
    return [ApplicationPublic.model_validate(a) for a in applications]


@router.post("/applications/{application_id}/status", response_model=ApplicationPublic)
async def change_application_status(
    application_id: uuid.UUID,
    payload: ApplicationStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ApplicationService(db)
    application = await service.change_status(
        application_id, organization_id, payload.status, payload.notes
    )
    return ApplicationPublic.model_validate(application)
