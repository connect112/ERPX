import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.placements.connectors.sources import SOURCES, is_configured
from modules.placements.job_feed import JobFeedService
from modules.placements.tasks import enqueue_job_feed_refresh
from modules.placements.models import JobFeedSettings, JobPostingStatus
from modules.placements.schemas import (
    ApplicationCreateRequest,
    ApplicationPublic,
    ApplicationStatusChangeRequest,
    CompanyCreateRequest,
    CompanyListResponse,
    CompanyPublic,
    CompanyUpdateRequest,
    ExternalJobListResponse,
    ExternalJobPublic,
    JobFeedRefreshResponse,
    JobFeedSettingsPublic,
    JobFeedSettingsUpdate,
    JobHiddenRequest,
    JobSourceStatus,
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


def _settings_public(row: JobFeedSettings) -> JobFeedSettingsPublic:
    state = row.source_state or {}
    return JobFeedSettingsPublic(
        keywords=row.keywords,
        india_only=row.india_only,
        boards=row.boards,
        refreshing=JobFeedService.is_refreshing(row),
        sources=[
            JobSourceStatus(
                name=name,
                label=label,
                enabled=bool(row.sources.get(name)),
                configured=is_configured(name),
                last_fetch_at=(state.get(name) or {}).get("last_fetch_at"),
                last_error=(state.get(name) or {}).get("error"),
                matched=(state.get(name) or {}).get("matched"),
            )
            for name, label in SOURCES.items()
        ],
    )


# ---- Job feed: jobs from outside job sites ----
# Fixed paths (/external/...) so they never collide with /postings/{id} below.


@router.get("/external/me", response_model=ExternalJobListResponse)
async def list_external_jobs_for_student(
    q: str | None = Query(default=None, max_length=100),
    source: str | None = Query(default=None, max_length=30),
    experience: str | None = Query(default=None, pattern=r"^(0-3|1-5|3-7|7\+|unknown)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Jobs found on outside job sites; the student opens `url` to apply on the original page."""
    rows, total = await JobFeedService(db).list_jobs(
        student.organization_id,
        include_hidden=False,
        q=q,
        source=source,
        skip=skip,
        limit=limit,
        experience=experience,
    )
    return ExternalJobListResponse(
        items=[ExternalJobPublic.model_validate(r) for r in rows], total=total, skip=skip, limit=limit
    )


@router.get("/external", response_model=ExternalJobListResponse)
async def list_external_jobs(
    q: str | None = Query(default=None, max_length=100),
    source: str | None = Query(default=None, max_length=30),
    include_hidden: bool = Query(default=True),
    experience: str | None = Query(default=None, pattern=r"^(0-3|1-5|3-7|7\+|unknown)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.view")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await JobFeedService(db).list_jobs(
        organization_id,
        include_hidden=include_hidden,
        q=q,
        source=source,
        skip=skip,
        limit=limit,
        experience=experience,
    )
    return ExternalJobListResponse(
        items=[ExternalJobPublic.model_validate(r) for r in rows], total=total, skip=skip, limit=limit
    )


@router.get("/external/settings", response_model=JobFeedSettingsPublic)
async def get_job_feed_settings(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.view")),
    db: AsyncSession = Depends(get_db),
):
    return _settings_public(await JobFeedService(db).get_settings(organization_id))


@router.put("/external/settings", response_model=JobFeedSettingsPublic)
async def update_job_feed_settings(
    payload: JobFeedSettingsUpdate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.manage")),
    db: AsyncSession = Depends(get_db),
):
    row = await JobFeedService(db).update_settings(
        organization_id, payload.keywords, payload.sources, payload.india_only, payload.boards
    )
    return _settings_public(row)


@router.post("/external/refresh", response_model=JobFeedRefreshResponse)
async def refresh_job_feed(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Start reading the enabled job sources in the background (it takes a minute or two). A source that was read
    recently is skipped (they limit how often they may be asked); the list also refreshes by itself every few hours."""
    service = JobFeedService(db)
    if not await service.start_refresh(organization_id):
        return JobFeedRefreshResponse(message="The job sites are already being checked. Give it a minute.", sources={})
    await db.commit()  # the "running" marker must be saved before the worker starts
    if not enqueue_job_feed_refresh(organization_id):
        row = await service.get_settings(organization_id)
        row.refresh_started_at = None
        await db.commit()
        raise ServiceUnavailableError("Couldn't start the refresh just now. Please try again.")
    return JobFeedRefreshResponse(message="Checking the job sites. New jobs appear in a minute or two.", sources={})


@router.post("/external/{job_id}/hidden", response_model=ExternalJobPublic)
async def set_external_job_hidden(
    job_id: uuid.UUID,
    payload: JobHiddenRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("placements.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Hide a job from students (or show it again)."""
    return ExternalJobPublic.model_validate(await JobFeedService(db).set_hidden(organization_id, job_id, payload.hidden))


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
