"""
Certificates for hackathon participants, sent from an exam.

The exam holds the certificate design (the uploaded artwork, where the name goes, the wording) and the
sending. To give the same certificate to the people of a hackathon, they are added to the exam as
"certificate-only" attendees: they get a certificate number and the certificate email, but are never
invited to the exam, scored, or counted in its statistics.

Admins first see exactly who would receive a certificate (a preview), then confirm.
"""

import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from modules.hackathons.participants_admin import ParticipantAdminService
from modules.hackathons.participation import ParticipationService
from modules.hackathons.service import HackathonService
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee
from modules.workshop_exams.service import WorkshopExamService

AUDIENCES = ("all", "teams", "scored", "top")
MAX_RECIPIENTS = 500

# What will happen to each person.
NEW = "new"  # added and sent a certificate
RESEND = "resend"  # added earlier, certificate not delivered yet: sent again
ALREADY_SENT = "already_sent"
ON_EXAM = "on_exam"  # is a normal attendee of this exam, who gets theirs through the exam
NO_EMAIL = "no_email"


@dataclass
class Recipient:
    name: str
    email: str | None
    team_name: str | None
    status: str


@dataclass
class Plan:
    hackathon_title: str
    recipients: list[Recipient]
    # attendee rows to create, and existing certificate-only attendees to send again
    to_create: list[Recipient]
    to_resend: list[WorkshopExamAttendee]

    def count(self, status: str) -> int:
        return sum(1 for r in self.recipients if r.status == status)

    @property
    def will_send(self) -> int:
        return len(self.to_create) + len(self.to_resend)


class HackathonCertificates:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.exams = WorkshopExamService(db)

    async def plan(
        self,
        exam: WorkshopExam,
        organization_id: uuid.UUID,
        hackathon_id: uuid.UUID,
        audience: str,
        top_n: int | None,
    ) -> Plan:
        hackathon = await HackathonService(self.db).get_hackathon(hackathon_id, organization_id)
        people = await ParticipantAdminService(self.db).participants(organization_id, hackathon_id)

        if audience == "teams":
            people = [p for p in people if p.team_id is not None]
        elif audience in ("scored", "top"):
            board = await ParticipationService(self.db).leaderboard(hackathon)
            if audience == "top":
                if not top_n:
                    raise ValidationError("Say how many top teams should get a certificate.")
                board = [row for row in board if row.rank <= top_n]
            wanted = {row.team_id for row in board}
            people = [p for p in people if p.team_id in wanted]
        elif audience != "all":
            raise ValidationError("Unknown audience.")

        existing = {
            a.email: a
            for a in (
                await self.db.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == exam.id))
            ).scalars()
        }
        recipients: list[Recipient] = []
        to_create: list[Recipient] = []
        to_resend: list[WorkshopExamAttendee] = []
        seen: set[str] = set()
        for person in people:
            email = (person.email or "").strip().lower()
            if not email:
                recipients.append(Recipient(person.full_name, None, person.team_name, NO_EMAIL))
                continue
            if email in seen:
                continue
            seen.add(email)
            attendee = existing.get(email)
            if attendee is None:
                recipient = Recipient(person.full_name, email, person.team_name, NEW)
                to_create.append(recipient)
            elif not attendee.certificate_only:
                recipient = Recipient(person.full_name, email, person.team_name, ON_EXAM)
            elif attendee.certificate_sent_at is not None:
                recipient = Recipient(person.full_name, email, person.team_name, ALREADY_SENT)
            else:
                recipient = Recipient(person.full_name, email, person.team_name, RESEND)
                to_resend.append(attendee)
            recipients.append(recipient)
        plan = Plan(hackathon.title, recipients, to_create, to_resend)
        if plan.will_send > MAX_RECIPIENTS:
            raise ValidationError(f"That is {plan.will_send} people; send at most {MAX_RECIPIENTS} at a time.")
        return plan

    async def issue(self, exam: WorkshopExam, plan: Plan) -> list[uuid.UUID]:
        """Create the attendee rows, give everyone a certificate number, and return the ids whose email must be sent."""
        ids: list[uuid.UUID] = []
        for recipient in plan.to_create:
            attendee = WorkshopExamAttendee(
                exam_id=exam.id,
                name=" ".join(recipient.name.split()),
                email=recipient.email,
                access_token=secrets.token_urlsafe(24),
                certificate_only=True,
            )
            self.db.add(attendee)
            await self.db.flush()
            attendee.certificate_number = await self.exams._new_certificate_number()
            await self.db.flush()
            ids.append(attendee.id)
        for attendee in plan.to_resend:
            if attendee.certificate_number is None:
                attendee.certificate_number = await self.exams._new_certificate_number()
            ids.append(attendee.id)
        await self.db.flush()
        return ids
