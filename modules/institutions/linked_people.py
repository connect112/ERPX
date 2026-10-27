"""
Reviewing the people of an event's linked exams and hackathons before they become the event's students.

An exam or hackathon that already has its own people (attendees, participants and team members) can be linked to an event.
Marks and team scores are matched to the event's registered students by email, so those people must be on the event's list
for their scores to show anywhere. They are not added blindly: they are first gathered into a review list that

- combines everyone who appears more than once (in several exams, in an exam and a hackathon, twice in one list) into ONE
  entry per email, keeping the most used spelling of the name and listing the other spellings, and leaves everyone else as
  they are;
- says what would happen to each (new to the institution, already at the institution, already on the event) and flags
  problems (an email that is not an email, a name that differs from the one the institution already has);
- lists separately the people who have no email, who cannot be matched or added.

Only the people someone verifies and confirms are added: each becomes a student of the event's institution (an existing
student with the same email is reused, never duplicated or renamed) and is registered for the event. Capacity is not
applied: these people already took part.
"""

import re
import uuid
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from modules.hackathons.models import Hackathon
from modules.hackathons.participants_admin import ParticipantAdminService
from modules.institutions.models import EventRegistration, InstitutionEvent, InstitutionStudent
from modules.institutions.service import InstitutionService
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_ADD = 2000

NEW = "new"  # not at the institution yet
AT_INSTITUTION = "at_institution"  # a student there already, not on this event
REGISTERED = "registered"  # already on this event


@dataclass
class Source:
    kind: str  # exam | hackathon
    title: str


@dataclass
class Candidate:
    email: str
    name: str
    phone: str | None
    name_variants: list[str]
    sources: list[Source]
    entries: int
    status: str
    existing_name: str | None
    issues: list[str]

    @property
    def addable(self) -> bool:
        return self.status != REGISTERED and "invalid_email" not in self.issues


@dataclass
class NoEmail:
    name: str
    source: Source


@dataclass
class Candidates:
    exams: int = 0
    hackathons: int = 0
    candidates: list[Candidate] = field(default_factory=list)
    without_email: list[NoEmail] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(1 for c in self.candidates if c.status == status)

    def summary(self) -> str:
        if self.exams + self.hackathons == 0:
            return "This event has no exams or hackathons linked yet."
        if not self.candidates and not self.without_email:
            return "The linked exams and hackathons have no people yet."
        bits = [
            f"{n} {label}"
            for n, label in (
                (self.count(NEW), "new"),
                (self.count(AT_INSTITUTION), "already at the institution"),
                (self.count(REGISTERED), "already on the event"),
            )
            if n
        ]
        text = f"{len(self.candidates)} {'person' if len(self.candidates) == 1 else 'people'} found" + (f" ({', '.join(bits)})" if bits else "")
        if self.without_email:
            text += f", {len(self.without_email)} without an email"
        return text + ". Open Validate students to review them and add the ones you verify."


@dataclass
class AddResult:
    new_students: int = 0
    registered: int = 0
    skipped: int = 0

    def message(self) -> str:
        if self.registered == 0:
            return "Nobody was added." + (f" {self.skipped} could not be added." if self.skipped else "")
        text = f"{self.registered} added to the event ({self.new_students} new to the institution)."
        return text + (f" {self.skipped} skipped." if self.skipped else "")


def _clean_name(name: str | None) -> str:
    return " ".join((name or "").split())


class LinkedPeople:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.institutions = InstitutionService(db)

    async def _entries(self, event: InstitutionEvent) -> tuple[int, int, list[tuple[Source, str, str | None, str | None]]]:
        """Every (source, name, email, phone) entry of the event's linked exams and hackathons, in the order they came."""
        entries: list[tuple[Source, str, str | None, str | None]] = []
        exams = (
            await self.db.execute(
                select(WorkshopExam.id, WorkshopExam.title)
                .where(WorkshopExam.event_id == event.id, WorkshopExam.hackathon_id.is_(None), WorkshopExam.award.is_(None))
                .order_by(WorkshopExam.created_at)
            )
        ).all()
        for exam_id, title in exams:
            rows = await self.db.execute(
                select(WorkshopExamAttendee.name, WorkshopExamAttendee.email, WorkshopExamAttendee.info)
                .where(WorkshopExamAttendee.exam_id == exam_id, WorkshopExamAttendee.certificate_only.is_(False))
                .order_by(WorkshopExamAttendee.created_at)
            )
            source = Source("exam", title)
            entries.extend((source, name, email, (info or {}).get("phone")) for name, email, info in rows.all())
        hackathons = (
            await self.db.execute(select(Hackathon.id, Hackathon.title).where(Hackathon.event_id == event.id).order_by(Hackathon.start_date))
        ).all()
        admin = ParticipantAdminService(self.db)
        for hackathon_id, title in hackathons:
            source = Source("hackathon", title)
            for p in await admin.participants(event.organization_id, hackathon_id):
                entries.append((source, p.full_name, p.email, p.phone))
        return len(exams), len(hackathons), entries

    async def candidates(self, event: InstitutionEvent) -> Candidates:
        result = Candidates()
        result.exams, result.hackathons, entries = await self._entries(event)

        groups: dict[str, list[tuple[Source, str, str | None]]] = {}
        for source, name, email, phone in entries:
            email = (email or "").strip().lower()
            if not email:
                result.without_email.append(NoEmail(_clean_name(name) or "(no name)", source))
                continue
            groups.setdefault(email, []).append((source, _clean_name(name), (phone or "").strip() or None))
        if not groups:
            return result

        existing = await self.institutions._students_by_email(event.institution_id, set(groups))
        registered = {
            sid
            for (sid,) in (await self.db.execute(select(EventRegistration.student_id).where(EventRegistration.event_id == event.id))).all()
        }
        for email, rows in groups.items():
            names = Counter(n.lower() for _, n, _ in rows if n)
            spellings: dict[str, str] = {}
            for _, n, _ in rows:
                if n:
                    spellings.setdefault(n.lower(), n)
            # the most used spelling wins; a tie goes to the fuller one ("Asha Rao" over "Asha R"), then the one seen first
            order = [key for key, _ in sorted(names.items(), key=lambda kv: (-kv[1], -len(spellings[kv[0]]), list(spellings).index(kv[0])))]
            name = spellings[order[0]] if order else email.split("@")[0]
            variants = [spellings[k] for k in order[1:]]
            sources: list[Source] = []
            for source, _, _ in rows:
                if not any(s.kind == source.kind and s.title == source.title for s in sources):
                    sources.append(source)
            student = existing.get(email)
            status = NEW if student is None else (REGISTERED if student.id in registered else AT_INSTITUTION)
            issues = []
            if not _EMAIL.match(email):
                issues.append("invalid_email")
            if variants:
                issues.append("name_variants")
            if student is not None and student.name.strip().lower() != name.lower():
                issues.append("name_differs")
            result.candidates.append(
                Candidate(
                    email=email,
                    name=name,
                    phone=next((p for _, _, p in rows if p), None),
                    name_variants=variants,
                    sources=sources,
                    entries=len(rows),
                    status=status,
                    existing_name=student.name if student else None,
                    issues=issues,
                )
            )
        result.candidates.sort(key=lambda c: (c.status == REGISTERED, c.name.lower()))
        return result

    async def add(self, event: InstitutionEvent, items: list[dict]) -> AddResult:
        """Add the verified people. Only emails that are in the current review list can be added (nothing else is trusted),
        each once however many times it is sent; a corrected name or phone is used for a student who is new."""
        if len(items) > MAX_ADD:
            raise ValidationError(f"Add at most {MAX_ADD} people at a time.")
        review = {c.email: c for c in (await self.candidates(event)).candidates}
        wanted: dict[str, dict] = {}
        result = AddResult()
        for item in items:
            email = (item.get("email") or "").strip().lower()
            if email in wanted:
                continue  # the same person sent twice is one person
            candidate = review.get(email)
            if candidate is None or not candidate.addable:
                result.skipped += 1
                continue
            wanted[email] = item
        if not wanted:
            return result

        existing = await self.institutions._students_by_email(event.institution_id, set(wanted))
        for email, item in wanted.items():
            candidate = review[email]
            student = existing.get(email)
            if student is None:
                name = _clean_name(item.get("name")) or candidate.name
                phone = (item.get("phone") or "").strip() or candidate.phone
                student = InstitutionStudent(
                    organization_id=event.organization_id,
                    institution_id=event.institution_id,
                    name=name,
                    email=email,
                    phone=phone,
                    details={},
                )
                self.db.add(student)
                existing[email] = student
                result.new_students += 1
            elif not student.phone and (candidate.phone or (item.get("phone") or "").strip()):
                student.phone = (item.get("phone") or "").strip() or candidate.phone  # only a blank phone is filled; name and email never change
        await self.db.flush()
        for email in wanted:
            self.db.add(EventRegistration(organization_id=event.organization_id, event_id=event.id, student_id=existing[email].id))
            result.registered += 1
        await self.db.flush()
        return result
