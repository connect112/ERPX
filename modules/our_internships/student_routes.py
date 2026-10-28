"""Routes for managing an internship's students (our_internships.view / our_internships.manage)."""

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.our_internships.access import internship_access
from modules.institutions.routes import _read_list
from modules.institutions.routes import candidates_out
from modules.institutions.schemas import CandidatesAddOut, CandidatesAddRequest, CandidatesOut, ImportResult
from modules.our_internships.schemas import MessageResponse
from modules.our_internships.service import OurInternshipService
from modules.our_internships.students import InternshipStudents
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


class EventRef(BaseModel):
    id: uuid.UUID
    name: str


class Destination(BaseModel):
    institution_id: uuid.UUID
    institution_name: str
    events: list[EventRef]


class StudentAddRequest(BaseModel):
    event_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)

    @field_validator("name", "phone", mode="before")
    @classmethod
    def _trim(cls, value):
        return " ".join(value.split()) if isinstance(value, str) else value


class StudentAddOut(BaseModel):
    student_id: uuid.UUID
    created: bool
    message: str


class StudentUpdateRequest(BaseModel):
    event_id: uuid.UUID
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    individual_score: float | None = Field(default=None, ge=0, le=9999)
    remarks: str | None = Field(default=None, max_length=5000)


async def _students(db: AsyncSession, internship_id: uuid.UUID, organization_id: uuid.UUID) -> InternshipStudents:
    return InternshipStudents(db, await OurInternshipService(db).get(internship_id, organization_id))


@router.get("/{internship_id}/students/destinations", response_model=list[Destination])
async def destinations(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The institutions and events students can be added to for this internship."""
    return await (await _students(db, internship_id, organization_id)).destinations()


@router.post("/{internship_id}/students", response_model=StudentAddOut, status_code=status.HTTP_201_CREATED)
async def add_student(
    internship_id: uuid.UUID,
    payload: StudentAddRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Add one student to an event of this internship. Someone already at the institution is reused, not duplicated."""
    student, created = await (await _students(db, internship_id, organization_id)).add(
        payload.event_id, payload.name, payload.email, payload.phone
    )
    return StudentAddOut(
        student_id=student.id,
        created=created,
        message="Student added." if created else f"{student.name} was already at the institution and is now registered for the event.",
    )


@router.post("/{internship_id}/students/import", response_model=ImportResult)
async def import_students(
    internship_id: uuid.UUID,
    event_id: uuid.UUID = Form(...),
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    dry_run: bool = Form(default=False),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Import a list (name, email, phone) into an event of this internship. With dry_run nothing is written."""
    students = await _students(db, internship_id, organization_id)
    event = await students.event_in_scope(event_id)
    institution = await students.institutions.get_institution(event.institution_id, organization_id)
    parsed = await _read_list(file, text)
    return ImportResult(**await students.institutions.import_students(institution, event, parsed, dry_run))


class ValidationEvent(BaseModel):
    event_id: uuid.UUID
    event_name: str
    institution_name: str


@router.get("/{internship_id}/students/validation-events", response_model=list[ValidationEvent])
async def validation_events(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The events in this internship's scope that have exams or hackathons linked, whose people can be validated."""
    students = await _students(db, internship_id, organization_id)
    events = await students.events_with_linked_data()
    names = {d["institution_id"]: d["institution_name"] for d in await students.destinations()}
    return [ValidationEvent(event_id=e.id, event_name=e.name, institution_name=names.get(e.institution_id, "")) for e in events]


@router.get("/{internship_id}/students/candidates", response_model=CandidatesOut)
async def student_candidates(
    internship_id: uuid.UUID,
    event_id: uuid.UUID = Query(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The people of one event's linked exams and hackathons, combined by email into one entry each, to validate."""
    return candidates_out(await (await _students(db, internship_id, organization_id)).candidates(event_id))


@router.post("/{internship_id}/students/candidates/add", response_model=CandidatesAddOut)
async def add_student_candidates(
    internship_id: uuid.UUID,
    payload: CandidatesAddRequest,
    event_id: uuid.UUID = Query(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Add the verified people to the institution and register them for the event."""
    result = await (await _students(db, internship_id, organization_id)).add_candidates(event_id, [i.model_dump() for i in payload.items])
    return CandidatesAddOut(new_students=result.new_students, registered=result.registered, skipped=result.skipped, message=result.message())


@router.patch("/{internship_id}/students/{student_id}", response_model=MessageResponse)
async def update_student(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: StudentUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Edit a student's details, and their individual score and remarks for the given event."""
    fields = payload.model_dump(exclude_unset=True, exclude={"event_id"})
    if not fields:
        raise ValidationError("Nothing to change.")
    await (await _students(db, internship_id, organization_id)).update(payload.event_id, student_id, fields)
    return MessageResponse(message="Saved.")


@router.delete("/{internship_id}/students/{student_id}", response_model=MessageResponse)
async def remove_student(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    event_id: uuid.UUID = Query(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Take a student off the event. They stay at the institution and in their other events."""
    await (await _students(db, internship_id, organization_id)).remove(event_id, student_id)
    return MessageResponse(message="Removed from the event.")
