import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.internships.models import InternshipPostingStatus
from modules.internships.schemas import (
    InternshipApplicationCreateRequest,
    InternshipApplicationPublic,
    InternshipApplicationStatusChangeRequest,
    InternshipListResponse,
    InternshipPostingCreateRequest,
    InternshipPostingListResponse,
    InternshipPostingPublic,
    InternshipPostingStatusChangeRequest,
    InternshipPostingUpdateRequest,
    InternshipPublic,
    InternshipStatusChangeRequest,
    InternshipUpdateRequest,
    MessageResponse,
)
from modules.internships.service import (
    InternshipApplicationService,
    InternshipPostingService,
    InternshipService,
)
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Student self-service ----


@router.get("/postings/me", response_model=list[InternshipPostingPublic])
async def list_open_postings(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipPostingService(db)
    postings, _total = await service.list_postings(
        student.organization_id, status=InternshipPostingStatus.OPEN, skip=0, limit=200
    )
    return [InternshipPostingPublic.model_validate(p) for p in postings]


@router.post(
    "/postings/{posting_id}/apply/me",
    response_model=InternshipApplicationPublic,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_posting(
    posting_id: uuid.UUID,
    payload: InternshipApplicationCreateRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipApplicationService(db)
    application = await service.apply(
        student.organization_id, posting_id, student.id, cover_letter=payload.cover_letter
    )
    return InternshipApplicationPublic.model_validate(application)


@router.get("/applications/me", response_model=list[InternshipApplicationPublic])
async def list_my_applications(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipApplicationService(db)
    applications = await service.list_for_student(student.id)
    return [InternshipApplicationPublic.model_validate(a) for a in applications]


@router.post("/applications/{application_id}/withdraw/me", response_model=InternshipApplicationPublic)
async def withdraw_application(
    application_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipApplicationService(db)
    application = await service.withdraw(application_id, student.id)
    return InternshipApplicationPublic.model_validate(application)


@router.get("/me", response_model=list[InternshipPublic])
async def list_my_internships(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipService(db)
    internships = await service.list_for_student(student.id)
    return [InternshipPublic.model_validate(i) for i in internships]


# ---- Staff: postings ----


@router.post("/postings", response_model=InternshipPostingPublic, status_code=status.HTTP_201_CREATED)
async def create_posting(
    payload: InternshipPostingCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipPostingService(db)
    posting = await service.create_posting(organization_id, **payload.model_dump())
    return InternshipPostingPublic.model_validate(posting)


@router.get("/postings", response_model=InternshipPostingListResponse)
async def list_postings(
    status_filter: InternshipPostingStatus | None = Query(default=None, alias="status"),
    company_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipPostingService(db)
    postings, total = await service.list_postings(
        organization_id, status=status_filter, company_id=company_id, skip=skip, limit=limit
    )
    return InternshipPostingListResponse(
        items=[InternshipPostingPublic.model_validate(p) for p in postings], total=total
    )


@router.get("/postings/{posting_id}", response_model=InternshipPostingPublic)
async def get_posting(
    posting_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipPostingService(db)
    posting = await service.get_posting(posting_id, organization_id)
    return InternshipPostingPublic.model_validate(posting)


@router.patch("/postings/{posting_id}", response_model=InternshipPostingPublic)
async def update_posting(
    posting_id: uuid.UUID,
    payload: InternshipPostingUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipPostingService(db)
    posting = await service.update_posting(
        posting_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return InternshipPostingPublic.model_validate(posting)


@router.post("/postings/{posting_id}/status", response_model=InternshipPostingPublic)
async def change_posting_status(
    posting_id: uuid.UUID,
    payload: InternshipPostingStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipPostingService(db)
    posting = await service.change_status(posting_id, organization_id, payload.status)
    return InternshipPostingPublic.model_validate(posting)


@router.delete("/postings/{posting_id}", response_model=MessageResponse)
async def delete_posting(
    posting_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipPostingService(db)
    await service.delete_posting(posting_id, organization_id)
    return MessageResponse(message="Internship posting deleted successfully.")


@router.get("/postings/{posting_id}/applications", response_model=list[InternshipApplicationPublic])
async def list_posting_applications(
    posting_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipApplicationService(db)
    applications = await service.list_for_posting(posting_id, organization_id)
    return [InternshipApplicationPublic.model_validate(a) for a in applications]


@router.post("/applications/{application_id}/status", response_model=InternshipApplicationPublic)
async def change_application_status(
    application_id: uuid.UUID,
    payload: InternshipApplicationStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipApplicationService(db)
    application = await service.change_status(
        application_id, organization_id, payload.status, payload.notes
    )
    return InternshipApplicationPublic.model_validate(application)


# ---- Staff: active internships ----


@router.get("/internships", response_model=InternshipListResponse)
async def list_internships(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipService(db)
    internships, total = await service.list_internships(organization_id, skip=skip, limit=limit)
    return InternshipListResponse(items=[InternshipPublic.model_validate(i) for i in internships], total=total)


@router.get("/internships/{internship_id}", response_model=InternshipPublic)
async def get_internship(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipService(db)
    internship = await service.get_internship(internship_id, organization_id)
    return InternshipPublic.model_validate(internship)


@router.patch("/internships/{internship_id}", response_model=InternshipPublic)
async def update_internship(
    internship_id: uuid.UUID,
    payload: InternshipUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipService(db)
    internship = await service.update_internship(
        internship_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return InternshipPublic.model_validate(internship)


@router.post("/internships/{internship_id}/status", response_model=InternshipPublic)
async def change_internship_status(
    internship_id: uuid.UUID,
    payload: InternshipStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipService(db)
    internship = await service.change_status(internship_id, organization_id, payload.status)
    return InternshipPublic.model_validate(internship)
