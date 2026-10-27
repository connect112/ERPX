"""
Admin routes for Our Internships (our_internships.view / our_internships.manage): create an internship, look at how the
students of its institution or event performed, and keep the shortlist of selected students.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.our_internships.models import OurInternship
from modules.our_internships.schemas import (
    InternshipCreateRequest,
    InternshipOut,
    InternshipUpdateRequest,
    MessageResponse,
    PerformanceResponse,
    SelectedListResponse,
    SelectionNoteRequest,
    SelectRequest,
)
from modules.our_internships.service import OurInternshipService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


async def _out(service: OurInternshipService, internships: list[OurInternship]) -> list[InternshipOut]:
    institutions, events, counts = await service.names(internships)
    out = []
    for i in internships:
        item = InternshipOut.model_validate(i)
        item.institution_name = institutions.get(i.institution_id)
        item.event_name = events.get(i.event_id)
        item.selected_count = counts.get(i.id, 0)
        out.append(item)
    return out


@router.get("", response_model=list[InternshipOut])
async def list_internships(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    return await _out(service, await service.list_all(organization_id))


@router.post("", response_model=InternshipOut, status_code=status.HTTP_201_CREATED)
async def create_internship(
    payload: InternshipCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    internship = await service.create(organization_id, user.id, **payload.model_dump())
    return (await _out(service, [internship]))[0]


@router.get("/{internship_id}", response_model=InternshipOut)
async def get_internship(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    return (await _out(service, [await service.get(internship_id, organization_id)]))[0]


@router.patch("/{internship_id}", response_model=InternshipOut)
async def update_internship(
    internship_id: uuid.UUID,
    payload: InternshipUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    internship = await service.update(await service.get(internship_id, organization_id), payload.model_dump(exclude_unset=True))
    return (await _out(service, [internship]))[0]


@router.delete("/{internship_id}", response_model=MessageResponse)
async def delete_internship(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    await service.delete(await service.get(internship_id, organization_id))
    return MessageResponse(message="Internship deleted.")


@router.get("/{internship_id}/performance", response_model=PerformanceResponse)
async def performance(
    internship_id: uuid.UUID,
    institution_id: uuid.UUID | None = Query(default=None, description="Narrow an all-students internship to one institution."),
    event_id: uuid.UUID | None = Query(default=None, description="Narrow to one event."),
    q: str | None = Query(default=None, max_length=100),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    """The students (and, grouped by hackathon team, the teams) this internship can select from, with their workshop exam
    marks, hackathon team score and individual score. Read live from the events' exams and hackathons."""
    service = OurInternshipService(db)
    internship = await service.get(internship_id, organization_id)
    return await service.performance(internship, institution_id, event_id, q)


@router.get("/{internship_id}/selected", response_model=SelectedListResponse)
async def selected_students(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    items = await service.selected(await service.get(internship_id, organization_id))
    return SelectedListResponse(items=items, total=len(items))


@router.post("/{internship_id}/selected", response_model=MessageResponse)
async def select_students(
    internship_id: uuid.UUID,
    payload: SelectRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    internship = await service.get(internship_id, organization_id)
    added, already = await service.select(internship, payload.student_ids, user.id, payload.note)
    return MessageResponse(message=f"{added} added to the selected list" + (f", {already} already on it." if already else "."))


@router.patch("/{internship_id}/selected/{student_id}", response_model=MessageResponse)
async def update_selection_note(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: SelectionNoteRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    await service.set_note(await service.get(internship_id, organization_id), student_id, payload.note)
    return MessageResponse(message="Saved.")


@router.delete("/{internship_id}/selected/{student_id}", response_model=MessageResponse)
async def unselect_student(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    await service.unselect(await service.get(internship_id, organization_id), student_id)
    return MessageResponse(message="Removed from the selected list.")
