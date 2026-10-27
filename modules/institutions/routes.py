"""
Admin routes for institutions, their events and the students registered for them (institutions.view /
institutions.manage). Three routers share one service:

* ``router``           /institutions            the institution itself, its MOU, its events and its student directory
* ``events_router``    /institution-events      one event: its details, registered students, exams and hackathons
* ``students_router``  /institution-students    one student's profile
"""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.institutions.models import Institution, InstitutionEvent, InstitutionStudent
from modules.institutions.schemas import (
    EventCreateRequest,
    EventOut,
    EventStudentListResponse,
    EventStudentOut,
    EventUpdateRequest,
    ImportResult,
    ImportTextRequest,
    InstitutionCreateRequest,
    InstitutionListResponse,
    InstitutionOut,
    InstitutionUpdateRequest,
    LinkedExam,
    LinkedHackathon,
    SyncResultOut,
    MessageResponse,
    RegisterStudentsRequest,
    RegistrationUpdateRequest,
    StudentCreateRequest,
    StudentEventRef,
    StudentListResponse,
    StudentOut,
    StudentUpdateRequest,
)
from modules.institutions.linked_people import LinkedPeople, SyncResult
from modules.institutions.service import InstitutionService
from modules.institutions.student_import import StudentListError, parse_students
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
events_router = APIRouter()
students_router = APIRouter()


# ---------------------------------------------------------------- output helpers


def _institution_out(institution: Institution, events: int, students: int) -> InstitutionOut:
    out = InstitutionOut.model_validate(institution)
    out.event_count = events
    out.student_count = students
    return out


def _event_out(event: InstitutionEvent, institution_name: str, counts: tuple[int, int, int]) -> EventOut:
    out = EventOut.model_validate(event)
    out.institution_name = institution_name
    out.student_count, out.exam_count, out.hackathon_count = counts
    return out


async def _event_response(service: InstitutionService, event: InstitutionEvent) -> EventOut:
    institution = await service.get_institution(event.institution_id, event.organization_id)
    counts = (await service.event_counts([event.id]))[event.id]
    return _event_out(event, institution.name, counts)


def _student_out(student: InstitutionStudent, institution_name: str, events: list[InstitutionEvent]) -> StudentOut:
    out = StudentOut.model_validate(student)
    out.institution_name = institution_name
    out.events = [
        StudentEventRef(event_id=e.id, event_name=e.name, event_type=e.event_type, status=e.status) for e in events
    ]
    return out


async def _read_list(file: UploadFile | None, text: str | None):
    try:
        if file is not None:
            data = await file.read()
            return parse_students(filename=file.filename, data=data)
        return parse_students(text=text)
    except StudentListError as exc:
        raise ValidationError(str(exc)) from exc


# ================================================================ institutions


@router.get("", response_model=InstitutionListResponse)
async def list_institutions(
    q: str | None = Query(default=None, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await InstitutionService(db).list_institutions(organization_id, q, skip, limit)
    return InstitutionListResponse(items=[_institution_out(i, e, s) for i, e, s in rows], total=total)


@router.post("", response_model=InstitutionOut, status_code=status.HTTP_201_CREATED)
async def create_institution(
    payload: InstitutionCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    institution = await InstitutionService(db).create_institution(organization_id, user.id, **payload.model_dump())
    return _institution_out(institution, 0, 0)


@router.get("/{institution_id}", response_model=InstitutionOut)
async def get_institution(
    institution_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    institution = await service.get_institution(institution_id, organization_id)
    return _institution_out(institution, *await service.institution_counts(institution.id))


@router.patch("/{institution_id}", response_model=InstitutionOut)
async def update_institution(
    institution_id: uuid.UUID,
    payload: InstitutionUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    institution = await service.get_institution(institution_id, organization_id)
    fields = payload.model_dump(exclude_unset=True)
    for required in ("name", "location", "faculty_name"):
        if required in fields and fields[required] is None:
            raise ValidationError(f"{required.replace('_', ' ').capitalize()} cannot be empty.")
    institution = await service.update_institution(institution, **fields)
    return _institution_out(institution, *await service.institution_counts(institution.id))


@router.delete("/{institution_id}", response_model=MessageResponse)
async def delete_institution(
    institution_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    await service.delete_institution(await service.get_institution(institution_id, organization_id))
    return MessageResponse(message="Institution deleted.")


@router.put("/{institution_id}/mou", response_model=InstitutionOut)
async def upload_mou(
    institution_id: uuid.UUID,
    file: UploadFile = File(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    institution = await service.get_institution(institution_id, organization_id)
    data = await file.read()
    await service.set_mou_file(institution, file.filename or "mou", file.content_type or "", data)
    return _institution_out(institution, *await service.institution_counts(institution.id))


@router.delete("/{institution_id}/mou", response_model=InstitutionOut)
async def remove_mou(
    institution_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    institution = await service.get_institution(institution_id, organization_id)
    await service.clear_mou_file(institution)
    return _institution_out(institution, *await service.institution_counts(institution.id))


@router.get("/{institution_id}/mou")
async def download_mou(
    institution_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    institution = await InstitutionService(db).get_mou(institution_id, organization_id)
    if not institution.mou_data:
        raise NotFoundError("MOU document")
    return Response(
        content=institution.mou_data,
        media_type=institution.mou_content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(institution.mou_filename or 'mou')}",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ---------------------------------------------------------------- events of an institution


@router.get("/{institution_id}/events", response_model=list[EventOut])
async def list_institution_events(
    institution_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    institution = await service.get_institution(institution_id, organization_id)
    events = await service.list_events(institution.id)
    counts = await service.event_counts([e.id for e in events])
    return [_event_out(e, institution.name, counts[e.id]) for e in events]


@router.post("/{institution_id}/events", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_institution_event(
    institution_id: uuid.UUID,
    payload: EventCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    institution = await service.get_institution(institution_id, organization_id)
    event = await service.create_event(institution, user.id, **payload.model_dump())
    return _event_out(event, institution.name, (0, 0, 0))


# ---------------------------------------------------------------- students of an institution


@router.get("/{institution_id}/students", response_model=StudentListResponse)
async def list_institution_students(
    institution_id: uuid.UUID,
    q: str | None = Query(default=None, max_length=100),
    event_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    institution = await service.get_institution(institution_id, organization_id)
    students, total = await service.list_students(organization_id, institution.id, q, event_id, skip, limit)
    events = await service.events_of_students([s.id for s in students])
    return StudentListResponse(
        items=[_student_out(s, institution.name, events.get(s.id, [])) for s in students], total=total
    )


@router.post("/{institution_id}/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
async def add_institution_student(
    institution_id: uuid.UUID,
    payload: StudentCreateRequest,
    event_id: uuid.UUID | None = Query(default=None, description="Also register the student for this event."),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    institution = await service.get_institution(institution_id, organization_id)
    event = None
    if event_id is not None:
        event = await service.get_event(event_id, organization_id)
        if event.institution_id != institution.id:
            raise ValidationError("That event belongs to a different institution.")
    student = await service.add_student(
        institution, event, payload.name, payload.email, payload.phone, payload.details
    )
    events = await service.events_of_students([student.id])
    return _student_out(student, institution.name, events.get(student.id, []))


async def _import(
    service: InstitutionService,
    institution: Institution,
    event: InstitutionEvent | None,
    file: UploadFile | None,
    text: str | None,
    dry_run: bool,
) -> ImportResult:
    parsed = await _read_list(file, text)
    return ImportResult(**await service.import_students(institution, event, parsed, dry_run))


@router.post("/{institution_id}/students/import", response_model=ImportResult)
async def import_institution_students(
    institution_id: uuid.UUID,
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    dry_run: bool = Form(default=False),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Add students to the institution only (not to any event)."""
    service = InstitutionService(db)
    institution = await service.get_institution(institution_id, organization_id)
    return await _import(service, institution, None, file, text, dry_run)


# ================================================================ one event


@events_router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    return await _event_response(service, await service.get_event(event_id, organization_id))


@events_router.patch("/{event_id}", response_model=EventOut)
async def update_event(
    event_id: uuid.UUID,
    payload: EventUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    event = await service.get_event(event_id, organization_id)
    event = await service.update_event(event, payload.model_dump(exclude_unset=True))
    return await _event_response(service, event)


@events_router.delete("/{event_id}", response_model=MessageResponse)
async def delete_event(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    await service.delete_event(await service.get_event(event_id, organization_id))
    return MessageResponse(message="Event deleted. Its exams and hackathons were kept and are no longer linked to it.")


# ---------------------------------------------------------------- the event's students


@events_router.get("/{event_id}/students", response_model=EventStudentListResponse)
async def list_event_students(
    event_id: uuid.UUID,
    q: str | None = Query(default=None, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    event = await service.get_event(event_id, organization_id)
    institution = await service.get_institution(event.institution_id, organization_id)
    rows, total = await service.event_students(event, q, skip, limit)
    return EventStudentListResponse(
        items=[
            EventStudentOut(
                student_id=s.id,
                institution_id=institution.id,
                institution_name=institution.name,
                event_id=event.id,
                event_name=event.name,
                name=s.name,
                email=s.email,
                phone=s.phone,
                details=s.details or {},
                individual_score=float(r.individual_score) if r.individual_score is not None else None,
                remarks=r.remarks,
                registered_at=r.created_at,
            )
            for r, s in rows
        ],
        total=total,
    )


@events_router.post("/{event_id}/students/import", response_model=ImportResult)
async def import_event_students(
    event_id: uuid.UUID,
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    dry_run: bool = Form(default=False),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Add students to this event's institution and register them for this event, and no other."""
    service = InstitutionService(db)
    event = await service.get_event(event_id, organization_id)
    institution = await service.get_institution(event.institution_id, organization_id)
    return await _import(service, institution, event, file, text, dry_run)


@events_router.post("/{event_id}/students", response_model=MessageResponse)
async def register_existing_students(
    event_id: uuid.UUID,
    payload: RegisterStudentsRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Register students who are already at the institution (from another event or an earlier list) for this event."""
    service = InstitutionService(db)
    event = await service.get_event(event_id, organization_id)
    added, already = await service.register(event, payload.student_ids)
    return MessageResponse(message=f"{added} registered" + (f", {already} already registered." if already else "."))


@events_router.patch("/{event_id}/students/{student_id}", response_model=MessageResponse)
async def update_registration(
    event_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: RegistrationUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Set this student's individual score and remarks for this event."""
    service = InstitutionService(db)
    event = await service.get_event(event_id, organization_id)
    registration = await service.get_registration(event.id, student_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(registration, key, value)
    await db.flush()
    return MessageResponse(message="Saved.")


@events_router.delete("/{event_id}/students/{student_id}", response_model=MessageResponse)
async def unregister_student(
    event_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Take a student off this event. They stay at the institution and in their other events."""
    service = InstitutionService(db)
    await service.unregister(await service.get_event(event_id, organization_id), student_id)
    return MessageResponse(message="Removed from the event.")


# ---------------------------------------------------------------- the event's exams and hackathons


def _sync_out(result: SyncResult) -> SyncResultOut:
    return SyncResultOut(**{k: getattr(result, k) for k in result.__dataclass_fields__}, message=result.summary())


def _exam_out(exam, attendees: int, questions: int) -> LinkedExam:
    return LinkedExam(
        id=exam.id,
        title=exam.title,
        status=exam.status.value if hasattr(exam.status, "value") else str(exam.status),
        attendee_count=attendees,
        question_count=questions,
        event_id=exam.event_id,
    )


def _hackathon_out(hackathon) -> LinkedHackathon:
    return LinkedHackathon(
        id=hackathon.id,
        code=hackathon.code,
        title=hackathon.title,
        status=hackathon.status.value if hasattr(hackathon.status, "value") else str(hackathon.status),
        start_date=hackathon.start_date,
        end_date=hackathon.end_date,
        event_id=hackathon.event_id,
    )


@events_router.get("/{event_id}/exams", response_model=list[LinkedExam])
async def list_event_exams(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    event = await service.get_event(event_id, organization_id)
    return [_exam_out(*row) for row in await service.event_exams(event.id)]


@events_router.get("/{event_id}/exam-candidates", response_model=list[LinkedExam])
async def list_exam_candidates(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    """Existing workshop exams that are not part of any event yet, so they can be linked here."""
    service = InstitutionService(db)
    await service.get_event(event_id, organization_id)
    return [_exam_out(*row) for row in await service.unlinked_exams(organization_id)]


@events_router.put("/{event_id}/exams/{exam_id}", response_model=MessageResponse)
async def link_exam(
    event_id: uuid.UUID,
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    event = await service.get_event(event_id, organization_id)
    await service.link_exam(event, exam_id)
    # the exam's own attendees become the event's students, so their marks show against them
    fetched = await LinkedPeople(db).sync(event)
    return MessageResponse(message=f"Exam linked to the event. {fetched.summary()}")


@events_router.post("/{event_id}/sync-students", response_model=SyncResultOut)
async def sync_linked_students(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the people of this event's linked exams and hackathons into its student list (again, for people who
    registered for them after they were linked). Existing students are reused by email, never duplicated or renamed."""
    service = InstitutionService(db)
    result = await LinkedPeople(db).sync(await service.get_event(event_id, organization_id))
    return _sync_out(result)


@events_router.delete("/{event_id}/exams/{exam_id}", response_model=MessageResponse)
async def unlink_exam(
    event_id: uuid.UUID,
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Take the exam off this event. The exam itself is kept."""
    service = InstitutionService(db)
    await service.unlink_exam(await service.get_event(event_id, organization_id), exam_id)
    return MessageResponse(message="Exam removed from the event.")


@events_router.get("/{event_id}/hackathons", response_model=list[LinkedHackathon])
async def list_event_hackathons(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    event = await service.get_event(event_id, organization_id)
    return [_hackathon_out(h) for h in await service.event_hackathons(event.id)]


@events_router.get("/{event_id}/hackathon-candidates", response_model=list[LinkedHackathon])
async def list_hackathon_candidates(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    """Existing hackathons that are not part of any event yet, so they can be linked here."""
    service = InstitutionService(db)
    await service.get_event(event_id, organization_id)
    return [_hackathon_out(h) for h in await service.unlinked_hackathons(organization_id)]


@events_router.put("/{event_id}/hackathons/{hackathon_id}", response_model=MessageResponse)
async def link_hackathon(
    event_id: uuid.UUID,
    hackathon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    event = await service.get_event(event_id, organization_id)
    await service.link_hackathon(event, hackathon_id)
    # the hackathon's participants and team members become the event's students, so their scores show against them
    fetched = await LinkedPeople(db).sync(event)
    return MessageResponse(message=f"Hackathon linked to the event. {fetched.summary()}")


@events_router.delete("/{event_id}/hackathons/{hackathon_id}", response_model=MessageResponse)
async def unlink_hackathon(
    event_id: uuid.UUID,
    hackathon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Take the hackathon off this event. The hackathon itself is kept."""
    service = InstitutionService(db)
    await service.unlink_hackathon(await service.get_event(event_id, organization_id), hackathon_id)
    return MessageResponse(message="Hackathon removed from the event.")


# ================================================================ one student


@students_router.get("/{student_id}", response_model=StudentOut)
async def get_student(
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    student = await service.get_student(student_id, organization_id)
    institution = await service.get_institution(student.institution_id, organization_id)
    events = await service.events_of_students([student.id])
    return _student_out(student, institution.name, events.get(student.id, []))


@students_router.patch("/{student_id}", response_model=StudentOut)
async def update_student(
    student_id: uuid.UUID,
    payload: StudentUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InstitutionService(db)
    student = await service.get_student(student_id, organization_id)
    student = await service.update_student(student, payload.model_dump(exclude_unset=True))
    institution = await service.get_institution(student.institution_id, organization_id)
    events = await service.events_of_students([student.id])
    return _student_out(student, institution.name, events.get(student.id, []))


@students_router.delete("/{student_id}", response_model=MessageResponse)
async def delete_student(
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("institutions.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Remove the student from the institution and from every event they were registered for."""
    service = InstitutionService(db)
    await service.delete_student(await service.get_student(student_id, organization_id))
    return MessageResponse(message="Student removed.")
