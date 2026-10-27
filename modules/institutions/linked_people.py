"""
Fetching the people of an event's linked exams and hackathons into the event's student list.

An exam or hackathon that already has its own people (attendees, participants and team members) can be linked to an event.
Marks and team scores are matched to the event's registered students by email, so those people must be on the event's list
for their scores to show anywhere. This brings them in: each person becomes a student of the event's institution (an
existing student with the same email is reused, never duplicated or renamed) and is registered for the event.

Capacity is not applied here: these people already took part, so they are registered regardless of the event's limit.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.hackathons.models import Hackathon
from modules.hackathons.participants_admin import ParticipantAdminService
from modules.institutions.models import EventRegistration, InstitutionEvent, InstitutionStudent
from modules.institutions.service import InstitutionService
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee


@dataclass
class Person:
    name: str
    email: str
    phone: str | None = None


@dataclass
class SyncResult:
    exams: int = 0
    hackathons: int = 0
    people: int = 0  # distinct people with an email
    new_students: int = 0  # not yet at the institution
    newly_registered: int = 0  # added to the event's list
    already_registered: int = 0
    without_email: int = 0  # cannot be matched, so skipped

    def add(self, other: "SyncResult") -> None:
        for key in self.__dataclass_fields__:
            setattr(self, key, getattr(self, key) + getattr(other, key))

    def summary(self) -> str:
        if self.exams + self.hackathons == 0:
            return "This event has no exams or hackathons linked yet."
        if self.people == 0 and self.without_email == 0:
            return "The linked exams and hackathons have no people yet."
        parts = [f"{self.people} {'person' if self.people == 1 else 'people'} found"]
        if self.newly_registered:
            parts.append(f"{self.newly_registered} added to the event ({self.new_students} new to the institution)")
        if self.already_registered:
            parts.append(f"{self.already_registered} already on the event")
        if self.without_email:
            parts.append(f"{self.without_email} skipped for having no email")
        return ", ".join(parts) + "."


class LinkedPeople:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.institutions = InstitutionService(db)

    async def _exam_people(self, event: InstitutionEvent) -> tuple[int, list[tuple[str, str | None, str | None]]]:
        exams = (
            await self.db.execute(
                select(WorkshopExam.id).where(
                    WorkshopExam.event_id == event.id, WorkshopExam.hackathon_id.is_(None), WorkshopExam.award.is_(None)
                )
            )
        ).scalars().all()
        if not exams:
            return 0, []
        rows = await self.db.execute(
            select(WorkshopExamAttendee.name, WorkshopExamAttendee.email, WorkshopExamAttendee.info)
            .where(WorkshopExamAttendee.exam_id.in_(list(exams)), WorkshopExamAttendee.certificate_only.is_(False))
            .order_by(WorkshopExamAttendee.created_at)
        )
        return len(exams), [(name, email, (info or {}).get("phone")) for name, email, info in rows.all()]

    async def _hackathon_people(self, event: InstitutionEvent) -> tuple[int, list[tuple[str, str | None, str | None]]]:
        hackathons = (await self.db.execute(select(Hackathon.id).where(Hackathon.event_id == event.id))).scalars().all()
        people: list[tuple[str, str | None, str | None]] = []
        admin = ParticipantAdminService(self.db)
        for hackathon_id in hackathons:
            for p in await admin.participants(event.organization_id, hackathon_id):
                people.append((p.full_name, p.email, p.phone))
        return len(hackathons), people

    async def sync(self, event: InstitutionEvent) -> SyncResult:
        result = SyncResult()
        result.exams, from_exams = await self._exam_people(event)
        result.hackathons, from_hackathons = await self._hackathon_people(event)

        wanted: dict[str, Person] = {}
        for name, email, phone in [*from_exams, *from_hackathons]:
            email = (email or "").strip().lower()
            if not email:
                result.without_email += 1
                continue
            name = " ".join((name or "").split()) or email.split("@")[0]
            known = wanted.get(email)
            if known is None:
                wanted[email] = Person(name, email, (phone or "").strip() or None)
            elif not known.phone and phone:
                known.phone = phone.strip() or None
        result.people = len(wanted)
        if not wanted:
            return result

        existing = await self.institutions._students_by_email(event.institution_id, set(wanted))
        for email, person in wanted.items():
            student = existing.get(email)
            if student is None:
                student = InstitutionStudent(
                    organization_id=event.organization_id,
                    institution_id=event.institution_id,
                    name=person.name,
                    email=email,
                    phone=person.phone,
                    details={},
                )
                self.db.add(student)
                existing[email] = student
                result.new_students += 1
            elif not student.phone and person.phone:
                student.phone = person.phone  # only a blank phone is filled; name and email are never overwritten
        await self.db.flush()

        registered: set[uuid.UUID] = {
            sid
            for (sid,) in (
                await self.db.execute(select(EventRegistration.student_id).where(EventRegistration.event_id == event.id))
            ).all()
        }
        for email in wanted:
            student = existing[email]
            if student.id in registered:
                result.already_registered += 1
                continue
            self.db.add(EventRegistration(organization_id=event.organization_id, event_id=event.id, student_id=student.id))
            registered.add(student.id)
            result.newly_registered += 1
        await self.db.flush()
        return result
