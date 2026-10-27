"""
Routes for an internship's instructors.

Administrators (our_internships.manage) assign trainers to an internship, one or many, each for a period, and can change or
end that access. Instructors themselves can only read what access they have (``my-access``) and list their own internships.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.our_internships.access import InstructorService, internship_access, window_status
from modules.our_internships.schemas import MessageResponse
from modules.our_internships.service import OurInternshipService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
my_instructing_router = APIRouter()


class InstructorOut(BaseModel):
    id: uuid.UUID
    trainer_id: uuid.UUID
    name: str
    email: str | None = None
    access_from: datetime | None = None
    access_until: datetime | None = None
    status: str  # upcoming | active | expired
    note: str | None = None
    created_at: datetime


class InstructorOption(BaseModel):
    trainer_id: uuid.UUID
    name: str
    email: str | None = None


class InstructorAddRequest(BaseModel):
    trainer_id: uuid.UUID
    access_from: datetime | None = None
    access_until: datetime | None = None
    note: str | None = Field(default=None, max_length=255)


class InstructorUpdateRequest(BaseModel):
    access_from: datetime | None = None
    access_until: datetime | None = None
    note: str | None = Field(default=None, max_length=255)


class MyAccess(BaseModel):
    role: str  # admin | instructor
    can_delete: bool
    access_from: datetime | None = None
    access_until: datetime | None = None
    status: str | None = None


class AssignedInternship(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    status: str
    access_from: datetime | None = None
    access_until: datetime | None = None


@router.get("/{internship_id}/instructors", response_model=list[InstructorOut])
async def list_instructors(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await OurInternshipService(db).get(internship_id, organization_id)
    return await InstructorService(db).listing(internship)


@router.get("/{internship_id}/instructors/options", response_model=list[InstructorOption])
async def instructor_options(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Trainers who can still be given access: active, with a login, not assigned to this internship yet."""
    internship = await OurInternshipService(db).get(internship_id, organization_id)
    return await InstructorService(db).options(internship)


@router.post("/{internship_id}/instructors", response_model=InstructorOut, status_code=status.HTTP_201_CREATED)
async def add_instructor(
    internship_id: uuid.UUID,
    payload: InstructorAddRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await OurInternshipService(db).get(internship_id, organization_id)
    return await InstructorService(db).add(internship, payload.trainer_id, payload.access_from, payload.access_until, payload.note, user.id)


@router.patch("/{internship_id}/instructors/{instructor_id}", response_model=InstructorOut)
async def update_instructor(
    internship_id: uuid.UUID,
    instructor_id: uuid.UUID,
    payload: InstructorUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Extend, shorten or open up an instructor's access by changing its dates."""
    internship = await OurInternshipService(db).get(internship_id, organization_id)
    return await InstructorService(db).update(internship, instructor_id, payload.model_dump(exclude_unset=True))


@router.delete("/{internship_id}/instructors/{instructor_id}", response_model=MessageResponse)
async def remove_instructor(
    internship_id: uuid.UUID,
    instructor_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await OurInternshipService(db).get(internship_id, organization_id)
    await InstructorService(db).remove(internship, instructor_id)
    return MessageResponse(message="The instructor no longer has access to this internship.")


@router.get("/{internship_id}/my-access", response_model=MyAccess)
async def my_access(
    internship_id: uuid.UUID,
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """What the caller may do on this internship: an administrator may do everything; an instructor everything but delete,
    until their access ends."""
    service = InstructorService(db)
    if await service.has_global(user, "view"):
        return MyAccess(role="admin", can_delete=await service.has_global(user, "manage"))
    assignment = await service.assignment_for(user, internship_id)
    return MyAccess(
        role="instructor",
        can_delete=False,
        access_from=assignment.access_from if assignment else None,
        access_until=assignment.access_until if assignment else None,
        status=window_status(assignment.access_from, assignment.access_until) if assignment else None,
    )


@my_instructing_router.get("", response_model=list[AssignedInternship])
async def my_instructing(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """The internships the caller instructs right now (for the trainer portal). Empty when they instruct none."""
    return await InstructorService(db).assigned_to(user)
