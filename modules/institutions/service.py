import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.hackathons.models import Hackathon
from modules.institutions.models import (
    EventRegistration,
    Institution,
    InstitutionEvent,
    InstitutionStudent,
)
from modules.institutions.student_import import ParsedList
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee, WorkshopExamQuestion

MAX_MOU_BYTES = 10 * 1024 * 1024
MOU_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def _like(term: str) -> str:
    escaped = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class InstitutionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ institutions

    async def get_institution(self, institution_id: uuid.UUID, organization_id: uuid.UUID) -> Institution:
        institution = (
            await self.db.execute(
                select(Institution).where(Institution.id == institution_id, Institution.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if institution is None:
            raise NotFoundError("Institution", institution_id)
        return institution

    async def get_mou(self, institution_id: uuid.UUID, organization_id: uuid.UUID) -> Institution:
        """The institution with its MOU document loaded (the bytes are not fetched with ordinary reads)."""
        institution = (
            await self.db.execute(
                select(Institution)
                .options(undefer(Institution.mou_data))
                .where(Institution.id == institution_id, Institution.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if institution is None:
            raise NotFoundError("Institution", institution_id)
        return institution

    async def _name_taken(
        self, organization_id: uuid.UUID, name: str, location: str, except_id: uuid.UUID | None = None
    ) -> bool:
        query = select(Institution.id).where(
            Institution.organization_id == organization_id,
            func.lower(Institution.name) == name.lower(),
            func.lower(Institution.location) == location.lower(),
        )
        if except_id:
            query = query.where(Institution.id != except_id)
        return (await self.db.execute(query.limit(1))).first() is not None

    async def create_institution(self, organization_id: uuid.UUID, user_id: uuid.UUID, **fields) -> Institution:
        if await self._name_taken(organization_id, fields["name"], fields["location"]):
            raise ConflictError("An institution with that name and location already exists.")
        institution = Institution(organization_id=organization_id, created_by_user_id=user_id, **fields)
        self.db.add(institution)
        await self.db.flush()
        await self.db.refresh(institution)
        return institution

    async def update_institution(self, institution: Institution, **fields) -> Institution:
        name = fields.get("name", institution.name)
        location = fields.get("location", institution.location)
        if ("name" in fields or "location" in fields) and await self._name_taken(
            institution.organization_id, name, location, except_id=institution.id
        ):
            raise ConflictError("An institution with that name and location already exists.")
        for key, value in fields.items():
            setattr(institution, key, value)
        await self.db.flush()
        return institution

    async def delete_institution(self, institution: Institution) -> None:
        # Its events, students and registrations go with it (database cascade); exams and hackathons that were linked to
        # its events stay, just no longer linked.
        await self.db.delete(institution)
        await self.db.flush()

    async def list_institutions(
        self, organization_id: uuid.UUID, q: str | None, skip: int, limit: int
    ) -> tuple[list[tuple[Institution, int, int]], int]:
        conditions = [Institution.organization_id == organization_id]
        if q and q.strip():
            like = _like(q)
            conditions.append(
                or_(Institution.name.ilike(like, escape="\\"), Institution.location.ilike(like, escape="\\"),
                    Institution.faculty_name.ilike(like, escape="\\"))
            )
        total = (await self.db.execute(select(func.count()).select_from(Institution).where(*conditions))).scalar_one()
        rows = list(
            (
                await self.db.execute(
                    select(Institution).where(*conditions).order_by(Institution.name).offset(skip).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        ids = [i.id for i in rows]
        events = await self._count_by(InstitutionEvent.institution_id, ids)
        students = await self._count_by(InstitutionStudent.institution_id, ids)
        return [(i, events.get(i.id, 0), students.get(i.id, 0)) for i in rows], total

    async def _count_by(self, column, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not ids:
            return {}
        rows = await self.db.execute(select(column, func.count()).where(column.in_(ids)).group_by(column))
        return {key: count for key, count in rows.all()}

    async def institution_counts(self, institution_id: uuid.UUID) -> tuple[int, int]:
        events = (await self._count_by(InstitutionEvent.institution_id, [institution_id])).get(institution_id, 0)
        students = (await self._count_by(InstitutionStudent.institution_id, [institution_id])).get(institution_id, 0)
        return events, students

    async def set_mou_file(self, institution: Institution, filename: str, content_type: str, data: bytes) -> None:
        if content_type not in MOU_TYPES:
            raise ValidationError("Please upload the MOU as a PDF, Word document or image.")
        if not data:
            raise ValidationError("That file is empty.")
        if len(data) > MAX_MOU_BYTES:
            raise ValidationError("That file is too large (the limit is 10 MB).")
        institution.mou_filename = " ".join(filename.split())[:255] or f"mou{MOU_TYPES[content_type]}"
        institution.mou_content_type = content_type
        institution.mou_size_bytes = len(data)
        institution.mou_data = data
        await self.db.flush()

    async def clear_mou_file(self, institution: Institution) -> None:
        institution.mou_filename = None
        institution.mou_content_type = None
        institution.mou_size_bytes = None
        institution.mou_data = None
        await self.db.flush()

    # ------------------------------------------------------------------ events

    async def get_event(self, event_id: uuid.UUID, organization_id: uuid.UUID) -> InstitutionEvent:
        event = (
            await self.db.execute(
                select(InstitutionEvent).where(
                    InstitutionEvent.id == event_id, InstitutionEvent.organization_id == organization_id
                )
            )
        ).scalar_one_or_none()
        if event is None:
            raise NotFoundError("Event", event_id)
        return event

    async def create_event(
        self, institution: Institution, user_id: uuid.UUID, **fields
    ) -> InstitutionEvent:
        event = InstitutionEvent(
            organization_id=institution.organization_id,
            institution_id=institution.id,
            created_by_user_id=user_id,
            **fields,
        )
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def update_event(self, event: InstitutionEvent, fields: dict) -> InstitutionEvent:
        start = fields.get("start_date", event.start_date)
        end = fields.get("end_date", event.end_date)
        if end < start:
            raise ValidationError("The end date cannot be before the start date.")
        for required in ("name", "event_type", "start_date", "end_date", "status"):
            if required in fields and fields[required] is None:
                raise ValidationError(f"{required.replace('_', ' ').capitalize()} cannot be empty.")
        if "max_capacity" in fields and fields["max_capacity"] is not None:
            registered = await self.registration_count(event.id)
            if fields["max_capacity"] < registered:
                raise ValidationError(
                    f"{registered} students are already registered, so the limit cannot be lower than that."
                )
        for key, value in fields.items():
            setattr(event, key, value)
        await self.db.flush()
        return event

    async def delete_event(self, event: InstitutionEvent) -> None:
        await self.db.delete(event)
        await self.db.flush()

    async def list_events(self, institution_id: uuid.UUID) -> list[InstitutionEvent]:
        return list(
            (
                await self.db.execute(
                    select(InstitutionEvent)
                    .where(InstitutionEvent.institution_id == institution_id)
                    .order_by(InstitutionEvent.start_date.desc(), InstitutionEvent.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def event_counts(self, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int, int]]:
        """(registered students, exams, hackathons) for each event."""
        students = await self._count_by(EventRegistration.event_id, event_ids)
        exams = await self._count_by(WorkshopExam.event_id, event_ids)
        hackathons = await self._count_by(Hackathon.event_id, event_ids)
        return {e: (students.get(e, 0), exams.get(e, 0), hackathons.get(e, 0)) for e in event_ids}

    async def registration_count(self, event_id: uuid.UUID) -> int:
        return (
            await self.db.execute(
                select(func.count()).select_from(EventRegistration).where(EventRegistration.event_id == event_id)
            )
        ).scalar_one()

    # ------------------------------------------------------------------ students

    async def get_student(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> InstitutionStudent:
        student = (
            await self.db.execute(
                select(InstitutionStudent).where(
                    InstitutionStudent.id == student_id, InstitutionStudent.organization_id == organization_id
                )
            )
        ).scalar_one_or_none()
        if student is None:
            raise NotFoundError("Student", student_id)
        return student

    async def _students_by_email(self, institution_id: uuid.UUID, emails: set[str]) -> dict[str, InstitutionStudent]:
        found: dict[str, InstitutionStudent] = {}
        pool = list(emails)
        for start in range(0, len(pool), 1000):
            chunk = pool[start : start + 1000]
            rows = await self.db.execute(
                select(InstitutionStudent).where(
                    InstitutionStudent.institution_id == institution_id, InstitutionStudent.email.in_(chunk)
                )
            )
            for student in rows.scalars().all():
                found[student.email] = student
        return found

    async def import_students(
        self,
        institution: Institution,
        event: InstitutionEvent | None,
        parsed: ParsedList,
        dry_run: bool,
    ) -> dict:
        """Add the people in ``parsed`` to the institution and, when ``event`` is given, register them for that event only.

        Someone already at the institution (same email) is reused, never duplicated; only blank phone/details are filled
        in from the list, their name and email are never overwritten by an import. With ``dry_run`` nothing is written
        and the result says what would happen.
        """
        problems = [{"row": p.row, "reason": p.reason, "raw": p.raw} for p in parsed.problems]
        first_seen: dict[str, int] = {}
        rows = []
        for student in parsed.students:
            if student.email in first_seen:
                problems.append(
                    {
                        "row": student.row,
                        "reason": f"Same email as row {first_seen[student.email]}; the first one is used.",
                        "raw": f"{student.name}, {student.email}",
                    }
                )
                continue
            first_seen[student.email] = student.row
            rows.append(student)

        existing = await self._students_by_email(institution.id, set(first_seen))
        registered_ids: set[uuid.UUID] = set()
        if event is not None and existing:
            registered_ids = {
                sid
                for (sid,) in (
                    await self.db.execute(
                        select(EventRegistration.student_id).where(
                            EventRegistration.event_id == event.id,
                            EventRegistration.student_id.in_([s.id for s in existing.values()]),
                        )
                    )
                ).all()
            }
        room = None
        if event is not None and event.max_capacity is not None:
            room = max(event.max_capacity - await self.registration_count(event.id), 0)

        new_students = existing_students = registered = already_registered = over_capacity = 0
        for parsed_student in rows:
            current = existing.get(parsed_student.email)
            will_register = event is not None
            if current is not None and current.id in registered_ids:
                already_registered += 1
                existing_students += 1
                will_register = False
            elif will_register and room is not None and room <= 0:
                over_capacity += 1
                problems.append(
                    {
                        "row": parsed_student.row,
                        "reason": "The event is full, so this student was not added.",
                        "raw": f"{parsed_student.name}, {parsed_student.email}",
                    }
                )
                continue
            elif current is not None:
                existing_students += 1
            else:
                new_students += 1

            if will_register:
                registered += 1
                if room is not None:
                    room -= 1
            if dry_run:
                continue

            if current is None:
                current = InstitutionStudent(
                    organization_id=institution.organization_id,
                    institution_id=institution.id,
                    name=parsed_student.name,
                    email=parsed_student.email,
                    phone=parsed_student.phone,
                    details=parsed_student.details,
                )
                self.db.add(current)
                await self.db.flush()
                existing[current.email] = current
            else:
                if not current.phone and parsed_student.phone:
                    current.phone = parsed_student.phone
                merged = {**parsed_student.details, **(current.details or {})}
                if merged != (current.details or {}):
                    current.details = merged
            if will_register:
                self.db.add(
                    EventRegistration(organization_id=institution.organization_id, event_id=event.id, student_id=current.id)
                )
        if not dry_run:
            await self.db.flush()
        problems.sort(key=lambda p: p["row"])
        return {
            "dry_run": dry_run,
            "total_rows": len(parsed.students) + len(parsed.problems),
            "new_students": new_students,
            "existing_students": existing_students,
            "registered": registered,
            "already_registered": already_registered,
            "over_capacity": over_capacity,
            "problems": problems,
        }

    async def add_student(
        self, institution: Institution, event: InstitutionEvent | None, name: str, email: str, phone, details: dict
    ) -> InstitutionStudent:
        email = email.strip().lower()
        existing = (await self._students_by_email(institution.id, {email})).get(email)
        if existing is not None:
            raise ConflictError("A student with that email address is already at this institution.")
        student = InstitutionStudent(
            organization_id=institution.organization_id,
            institution_id=institution.id,
            name=" ".join(name.split()),
            email=email,
            phone=phone or None,
            details=details or {},
        )
        self.db.add(student)
        await self.db.flush()
        if event is not None:
            await self.register(event, [student.id])
        return student

    async def update_student(self, student: InstitutionStudent, fields: dict) -> InstitutionStudent:
        if fields.get("name") is not None:
            student.name = " ".join(fields["name"].split())
        if fields.get("email") is not None:
            email = fields["email"].strip().lower()
            if email != student.email:
                other = (await self._students_by_email(student.institution_id, {email})).get(email)
                if other is not None:
                    raise ConflictError("Another student at this institution already has that email address.")
                student.email = email
        if "phone" in fields:
            student.phone = fields["phone"] or None
        if fields.get("details") is not None:
            student.details = fields["details"]
        await self.db.flush()
        return student

    async def delete_student(self, student: InstitutionStudent) -> None:
        await self.db.delete(student)
        await self.db.flush()

    async def list_students(
        self,
        organization_id: uuid.UUID,
        institution_id: uuid.UUID,
        q: str | None,
        event_id: uuid.UUID | None,
        skip: int,
        limit: int,
    ) -> tuple[list[InstitutionStudent], int]:
        conditions = [InstitutionStudent.organization_id == organization_id, InstitutionStudent.institution_id == institution_id]
        if q and q.strip():
            like = _like(q)
            conditions.append(
                or_(
                    InstitutionStudent.name.ilike(like, escape="\\"),
                    InstitutionStudent.email.ilike(like, escape="\\"),
                    InstitutionStudent.phone.ilike(like, escape="\\"),
                )
            )
        if event_id is not None:
            conditions.append(
                InstitutionStudent.id.in_(select(EventRegistration.student_id).where(EventRegistration.event_id == event_id))
            )
        total = (await self.db.execute(select(func.count()).select_from(InstitutionStudent).where(*conditions))).scalar_one()
        rows = (
            await self.db.execute(
                select(InstitutionStudent)
                .where(*conditions)
                .order_by(func.lower(InstitutionStudent.name), InstitutionStudent.email)
                .offset(skip)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def events_of_students(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[InstitutionEvent]]:
        if not student_ids:
            return {}
        rows = await self.db.execute(
            select(EventRegistration.student_id, InstitutionEvent)
            .join(InstitutionEvent, InstitutionEvent.id == EventRegistration.event_id)
            .where(EventRegistration.student_id.in_(student_ids))
            .order_by(InstitutionEvent.start_date.desc())
        )
        out: dict[uuid.UUID, list[InstitutionEvent]] = {}
        for student_id, event in rows.all():
            out.setdefault(student_id, []).append(event)
        return out

    # ------------------------------------------------------------------ registrations

    async def register(self, event: InstitutionEvent, student_ids: list[uuid.UUID]) -> tuple[int, int]:
        """Register existing students of the event's own institution. Returns (registered, already registered)."""
        wanted = list(dict.fromkeys(student_ids))
        valid = {
            sid
            for (sid,) in (
                await self.db.execute(
                    select(InstitutionStudent.id).where(
                        InstitutionStudent.id.in_(wanted), InstitutionStudent.institution_id == event.institution_id
                    )
                )
            ).all()
        }
        if len(valid) != len(wanted):
            raise ValidationError("Only students of this institution can be registered for its events.")
        already = {
            sid
            for (sid,) in (
                await self.db.execute(
                    select(EventRegistration.student_id).where(
                        EventRegistration.event_id == event.id, EventRegistration.student_id.in_(wanted)
                    )
                )
            ).all()
        }
        fresh = [sid for sid in wanted if sid not in already]
        if event.max_capacity is not None:
            room = event.max_capacity - await self.registration_count(event.id)
            if len(fresh) > room:
                raise ValidationError(f"This event has room for {max(room, 0)} more students (its limit is {event.max_capacity}).")
        for sid in fresh:
            self.db.add(EventRegistration(organization_id=event.organization_id, event_id=event.id, student_id=sid))
        await self.db.flush()
        return len(fresh), len(already)

    async def unregister(self, event: InstitutionEvent, student_id: uuid.UUID) -> None:
        result = await self.db.execute(
            delete(EventRegistration).where(
                EventRegistration.event_id == event.id, EventRegistration.student_id == student_id
            )
        )
        if result.rowcount == 0:
            raise NotFoundError("Registration", student_id)

    async def get_registration(self, event_id: uuid.UUID, student_id: uuid.UUID) -> EventRegistration:
        registration = (
            await self.db.execute(
                select(EventRegistration).where(
                    EventRegistration.event_id == event_id, EventRegistration.student_id == student_id
                )
            )
        ).scalar_one_or_none()
        if registration is None:
            raise NotFoundError("Registration", student_id)
        return registration

    async def event_students(
        self, event: InstitutionEvent, q: str | None, skip: int, limit: int
    ) -> tuple[list[tuple[EventRegistration, InstitutionStudent]], int]:
        conditions = [EventRegistration.event_id == event.id]
        if q and q.strip():
            like = _like(q)
            conditions.append(
                or_(
                    InstitutionStudent.name.ilike(like, escape="\\"),
                    InstitutionStudent.email.ilike(like, escape="\\"),
                    InstitutionStudent.phone.ilike(like, escape="\\"),
                )
            )
        base = (
            select(EventRegistration, InstitutionStudent)
            .join(InstitutionStudent, InstitutionStudent.id == EventRegistration.student_id)
            .where(*conditions)
        )
        total = (
            await self.db.execute(
                select(func.count())
                .select_from(EventRegistration)
                .join(InstitutionStudent, InstitutionStudent.id == EventRegistration.student_id)
                .where(*conditions)
            )
        ).scalar_one()
        rows = (
            await self.db.execute(base.order_by(func.lower(InstitutionStudent.name)).offset(skip).limit(limit))
        ).all()
        return [(r, s) for r, s in rows], total

    # ------------------------------------------------------------------ exams and hackathons of an event

    async def event_exams(self, event_id: uuid.UUID) -> list[tuple[WorkshopExam, int, int]]:
        exams = list(
            (
                await self.db.execute(
                    select(WorkshopExam).where(WorkshopExam.event_id == event_id).order_by(WorkshopExam.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return await self._with_exam_counts(exams)

    async def _with_exam_counts(self, exams: list[WorkshopExam]) -> list[tuple[WorkshopExam, int, int]]:
        ids = [e.id for e in exams]
        attendees = await self._count_by(WorkshopExamAttendee.exam_id, ids)
        questions = await self._count_by(WorkshopExamQuestion.exam_id, ids)
        return [(e, attendees.get(e.id, 0), questions.get(e.id, 0)) for e in exams]

    async def unlinked_exams(self, organization_id: uuid.UUID) -> list[tuple[WorkshopExam, int, int]]:
        exams = list(
            (
                await self.db.execute(
                    select(WorkshopExam)
                    .where(
                        WorkshopExam.organization_id == organization_id,
                        WorkshopExam.event_id.is_(None),
                        # a hackathon's award-certificate exams are managed from the hackathon, never linked by hand
                        WorkshopExam.hackathon_id.is_(None),
                    )
                    .order_by(WorkshopExam.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return await self._with_exam_counts(exams)

    async def link_exam(self, event: InstitutionEvent, exam_id: uuid.UUID) -> WorkshopExam:
        exam = (
            await self.db.execute(
                select(WorkshopExam).where(
                    WorkshopExam.id == exam_id,
                    WorkshopExam.organization_id == event.organization_id,
                    WorkshopExam.hackathon_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        if exam is None:
            raise NotFoundError("Workshop exam", exam_id)
        if exam.event_id not in (None, event.id):
            raise ConflictError("That exam already belongs to another event. Remove it from there first.")
        exam.event_id = event.id
        await self.db.flush()
        return exam

    async def unlink_exam(self, event: InstitutionEvent, exam_id: uuid.UUID) -> None:
        exam = (
            await self.db.execute(select(WorkshopExam).where(WorkshopExam.id == exam_id, WorkshopExam.event_id == event.id))
        ).scalar_one_or_none()
        if exam is None:
            raise NotFoundError("Workshop exam", exam_id)
        exam.event_id = None
        await self.db.flush()

    async def event_hackathons(self, event_id: uuid.UUID) -> list[Hackathon]:
        return list(
            (
                await self.db.execute(
                    select(Hackathon).where(Hackathon.event_id == event_id).order_by(Hackathon.start_date.desc())
                )
            )
            .scalars()
            .all()
        )

    async def unlinked_hackathons(self, organization_id: uuid.UUID) -> list[Hackathon]:
        return list(
            (
                await self.db.execute(
                    select(Hackathon)
                    .where(Hackathon.organization_id == organization_id, Hackathon.event_id.is_(None))
                    .order_by(Hackathon.start_date.desc())
                )
            )
            .scalars()
            .all()
        )

    async def link_hackathon(self, event: InstitutionEvent, hackathon_id: uuid.UUID) -> Hackathon:
        hackathon = (
            await self.db.execute(
                select(Hackathon).where(Hackathon.id == hackathon_id, Hackathon.organization_id == event.organization_id)
            )
        ).scalar_one_or_none()
        if hackathon is None:
            raise NotFoundError("Hackathon", hackathon_id)
        if hackathon.event_id not in (None, event.id):
            raise ConflictError("That hackathon already belongs to another event. Remove it from there first.")
        hackathon.event_id = event.id
        await self.db.flush()
        return hackathon

    async def unlink_hackathon(self, event: InstitutionEvent, hackathon_id: uuid.UUID) -> None:
        hackathon = (
            await self.db.execute(select(Hackathon).where(Hackathon.id == hackathon_id, Hackathon.event_id == event.id))
        ).scalar_one_or_none()
        if hackathon is None:
            raise NotFoundError("Hackathon", hackathon_id)
        hackathon.event_id = None
        await self.db.flush()

    async def assert_event_in_org(self, event_id: uuid.UUID | None, organization_id: uuid.UUID) -> None:
        """Used when an exam or hackathon is created from an event page: the event must be this organization's."""
        if event_id is not None:
            await self.get_event(event_id, organization_id)

