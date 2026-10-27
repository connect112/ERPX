"""
Managing the students of an internship's pool from the internship itself.

The pool is the registrations of the events in the internship's scope, so adding a student here means adding them to one of
those events (creating the student at the institution when they are new, reusing them by email when they are not).
Nothing here widens the scope: an internship tied to one institution or event only ever touches that.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.institutions.linked_people import AddResult, Candidates, LinkedPeople
from modules.institutions.models import EventRegistration, Institution, InstitutionEvent, InstitutionStudent
from modules.institutions.service import InstitutionService
from modules.our_internships.models import OurInternship
from modules.our_internships.service import OurInternshipService


class InternshipStudents:
    def __init__(self, db: AsyncSession, internship: OurInternship):
        self.db = db
        self.internship = internship
        self.institutions = InstitutionService(db)
        self.internships = OurInternshipService(db)

    def _scope(self) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        return self.internships.scope_filters(self.internship, None, None)

    async def event_in_scope(self, event_id: uuid.UUID) -> InstitutionEvent:
        event = await self.institutions.get_event(event_id, self.internship.organization_id)
        institution_id, scoped_event = self._scope()
        if institution_id is not None and event.institution_id != institution_id:
            raise ValidationError("That event is outside this internship's institution.")
        if scoped_event is not None and event.id != scoped_event:
            raise ValidationError("This internship is for one event only, so students can only be added to that event.")
        return event

    async def destinations(self) -> list[dict]:
        """The institutions and events students can be added to."""
        institution_id, event_id = self._scope()
        query = (
            select(InstitutionEvent, Institution)
            .join(Institution, Institution.id == InstitutionEvent.institution_id)
            .where(InstitutionEvent.organization_id == self.internship.organization_id)
            .order_by(Institution.name, InstitutionEvent.start_date.desc())
        )
        if institution_id is not None:
            query = query.where(InstitutionEvent.institution_id == institution_id)
        if event_id is not None:
            query = query.where(InstitutionEvent.id == event_id)
        grouped: dict[uuid.UUID, dict] = {}
        for event, institution in (await self.db.execute(query)).all():
            entry = grouped.setdefault(institution.id, {"institution_id": institution.id, "institution_name": institution.name, "events": []})
            entry["events"].append({"id": event.id, "name": event.name})
        return list(grouped.values())

    async def add(self, event_id: uuid.UUID, name: str, email: str, phone: str | None) -> tuple[InstitutionStudent, bool]:
        """Add a student to an event. Returns (student, created): False when they already were at the institution and are
        now just registered for the event."""
        event = await self.event_in_scope(event_id)
        institution = await self.institutions.get_institution(event.institution_id, self.internship.organization_id)
        email = email.strip().lower()
        existing = (await self.institutions._students_by_email(institution.id, {email})).get(email)
        if existing is None:
            return await self.institutions.add_student(institution, event, name, email, phone, {}), True
        registered = (
            await self.db.execute(
                select(EventRegistration.id).where(EventRegistration.event_id == event.id, EventRegistration.student_id == existing.id)
            )
        ).first()
        if registered:
            raise ConflictError("That student is already registered for this event.")
        await self.institutions.register(event, [existing.id])
        return existing, False

    async def update(self, event_id: uuid.UUID, student_id: uuid.UUID, fields: dict) -> None:
        event = await self.event_in_scope(event_id)
        registration = await self.institutions.get_registration(event.id, student_id)
        student = await self.institutions.get_student(student_id, self.internship.organization_id)
        person = {k: v for k, v in fields.items() if k in ("name", "email", "phone")}
        if person:
            await self.institutions.update_student(student, person)
        for key in ("individual_score", "remarks"):
            if key in fields:
                setattr(registration, key, fields[key])
        await self.db.flush()

    async def remove(self, event_id: uuid.UUID, student_id: uuid.UUID) -> None:
        event = await self.event_in_scope(event_id)
        if student_id in await self.internships.selected_ids(self.internship.id):
            raise ConflictError("This student is on the selected list. Remove them from it first.")
        await self.institutions.unregister(event, student_id)

    async def events_with_linked_data(self) -> list[InstitutionEvent]:
        """The events in scope that have an exam or hackathon linked, for the validation list."""
        from sqlalchemy import exists

        from modules.hackathons.models import Hackathon
        from modules.workshop_exams.models import WorkshopExam

        institution_id, scoped_event = self._scope()
        query = select(InstitutionEvent).where(
            InstitutionEvent.organization_id == self.internship.organization_id,
            exists().where(WorkshopExam.event_id == InstitutionEvent.id, WorkshopExam.hackathon_id.is_(None), WorkshopExam.award.is_(None))
            | exists().where(Hackathon.event_id == InstitutionEvent.id),
        )
        if institution_id is not None:
            query = query.where(InstitutionEvent.institution_id == institution_id)
        if scoped_event is not None:
            query = query.where(InstitutionEvent.id == scoped_event)
        return list((await self.db.execute(query.order_by(InstitutionEvent.start_date.desc()))).scalars().all())

    async def candidates(self, event_id: uuid.UUID) -> Candidates:
        """The people of one event's linked exams and hackathons, combined by email, for review."""
        return await LinkedPeople(self.db).candidates(await self.event_in_scope(event_id))

    async def add_candidates(self, event_id: uuid.UUID, items: list[dict]) -> AddResult:
        return await LinkedPeople(self.db).add(await self.event_in_scope(event_id), items)
