"""
Certificates for a hackathon's winners (1st, 2nd and 3rd place) and, optionally, its other participants.

Each award is a certificate-only workshop exam that belongs to the hackathon (`hackathon_id` + `award`), created on first
use. That is what lets the winners' certificates have everything the exam certificates have: an uploaded design per
place with the name (and ID) positioned on it, the ID format, review before sending, per-person fixes, preview and test
emails, and sending. Every member of a winning team gets their own certificate; a team of one gets one.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from modules.hackathons.models import Hackathon
from modules.hackathons.participants_admin import ParticipantAdminService
from modules.hackathons.participation import ParticipationService
from modules.workshop_exams.certificate_template import CertificateLayout
from modules.workshop_exams.hackathon_certificates import HackathonCertificates, Plan
from modules.workshop_exams.models import WorkshopExam, WorkshopExamStatus
from modules.workshop_exams.service import WorkshopExamService

# award key -> (what the certificate is for, the rank that wins it)
PLACES = {"first": ("1st place", 1), "second": ("2nd place", 2), "third": ("3rd place", 3)}
PARTICIPATION = "participation"
AWARDS = (*PLACES, PARTICIPATION)
LABELS = {**{key: label for key, (label, _rank) in PLACES.items()}, PARTICIPATION: "Participation"}
PARTICIPATION_AUDIENCES = ("teams", "all")


@dataclass
class Person:
    full_name: str
    email: str | None
    team_name: str | None


@dataclass
class TeamGroup:
    rank: int
    team_name: str
    score: int
    members: list[Person]


@dataclass
class AwardGroup:
    award: str
    label: str
    exam: WorkshopExam
    teams: list[TeamGroup] = field(default_factory=list)

    @property
    def people(self) -> list[Person]:
        return [member for team in self.teams for member in team.members]


class HackathonAwards:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.exams = WorkshopExamService(db)
        self.certificates = HackathonCertificates(db)

    # ---------------- the four award exams ----------------

    async def ensure_exams(self, organization_id: uuid.UUID, hackathon: Hackathon) -> dict[str, WorkshopExam]:
        existing = {
            exam.award: exam
            for exam in (
                await self.db.execute(select(WorkshopExam).where(WorkshopExam.hackathon_id == hackathon.id))
            ).scalars()
            if exam.award
        }
        for award in AWARDS:
            if award in existing:
                continue
            label = LABELS[award]
            winning = award != PARTICIPATION
            existing[award] = await self.exams.create_exam(
                organization_id,
                title=f"{hackathon.title}: {label} certificate"[:255],
                duration_minutes=30,
                status=WorkshopExamStatus.DRAFT,
                hackathon_id=hackathon.id,
                award=award,
                certificate_heading="Certificate of Achievement" if winning else "Certificate of Participation",
                certificate_text=(
                    f'has secured {label} in the hackathon "{hackathon.title}".'
                    if winning
                    else f'has participated in the hackathon "{hackathon.title}".'
                ),
                certificate_layout=CertificateLayout().model_dump(),
            )
        return existing

    # ---------------- who gets what ----------------

    async def groups(
        self, organization_id: uuid.UUID, hackathon: Hackathon, exams: dict[str, WorkshopExam]
    ) -> tuple[dict[str, AwardGroup], list]:
        """The winning teams per place (ranks 1-3 of the leaderboard; a tie shares a place) and every participant."""
        participants = await ParticipantAdminService(self.db).participants(organization_id, hackathon.id)
        by_team: dict[uuid.UUID, list[Person]] = {}
        for person in participants:
            if person.team_id is not None:
                by_team.setdefault(person.team_id, []).append(Person(person.full_name, person.email, person.team_name))
        groups = {key: AwardGroup(key, LABELS[key], exams[key]) for key in PLACES}
        for row in await ParticipationService(self.db).leaderboard(hackathon):
            for key, (_label, rank) in PLACES.items():
                if row.rank == rank:
                    groups[key].teams.append(TeamGroup(row.rank, row.team_name, row.score, by_team.get(row.team_id, [])))
        return groups, participants

    @staticmethod
    def participation_people(winners: dict[str, AwardGroup], participants: list, audience: str) -> list[Person]:
        """Everyone else who took part: those in a team ("teams") or every invited participant ("all"). Anyone who is
        on a winning team already gets that certificate, not this one."""
        if audience not in PARTICIPATION_AUDIENCES:
            raise ValidationError("Choose who gets a participation certificate: people in a team, or everyone invited.")
        winning_emails = {(p.email or "").lower() for group in winners.values() for p in group.people if p.email}
        out: list[Person] = []
        seen: set[str] = set()
        for person in participants:
            if audience == "teams" and person.team_id is None:
                continue
            email = (person.email or "").strip().lower()
            if email and (email in winning_emails or email in seen):
                continue
            if email:
                seen.add(email)
            out.append(Person(person.full_name, person.email, person.team_name))
        return out

    @staticmethod
    def label(award: str) -> str:
        return LABELS[award]

    # ---------------- preview and issue ----------------

    async def plan(self, exam: WorkshopExam, hackathon: Hackathon, people: list[Person]) -> Plan:
        return await self.certificates.plan_for(exam, hackathon.title, people)

    async def issue(self, exam: WorkshopExam, plan: Plan) -> list[uuid.UUID]:
        return await self.certificates.issue(exam, plan)
