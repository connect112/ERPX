"""
What a hackathon participant does once they're on a team: pick a problem
statement, upload their report, and see where they stand.

Everything here is ownership-gated by the caller (a member of the team, via
get_current_student) or staff-gated (hackathons.manage/view); nothing relies
on a permission the participant role doesn't hold.
"""

import os
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from modules.hackathons.models import (
    Hackathon,
    HackathonStatus,
    ProblemStatement,
    Submission,
    Team,
    TeamMember,
    TeamReport,
)
from modules.students.models import Student

MAX_REPORT_BYTES = 20 * 1024 * 1024

# extension -> (content type served back, leading bytes the real file must start with)
_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy .doc / .ppt
_ZIP = b"PK\x03\x04"  # .docx / .pptx / .zip
_REPORT_TYPES: dict[str, tuple[str, tuple[bytes, ...]]] = {
    "pdf": ("application/pdf", (b"%PDF",)),
    "doc": ("application/msword", (_OLE,)),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (_ZIP,)),
    "ppt": ("application/vnd.ms-powerpoint", (_OLE,)),
    "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", (_ZIP,)),
    "zip": ("application/zip", (_ZIP,)),
}
ALLOWED_REPORT_EXTENSIONS = ", ".join(f".{e}" for e in _REPORT_TYPES)

_ACTIVE = (HackathonStatus.REGISTRATION_OPEN, HackathonStatus.ONGOING)


def clean_filename(name: str) -> str:
    base = os.path.basename((name or "").replace("\\", "/"))
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip().strip(".")
    return base[:200] or "report"


@dataclass
class LeaderboardRow:
    rank: int
    team_id: uuid.UUID
    team_name: str
    score: int
    project_title: str
    members: list[str]


@dataclass
class Award:
    hackathon_id: uuid.UUID
    hackathon_title: str
    team_name: str
    code: str  # participant | submitted | report | winner | runner_up | third_place
    label: str
    detail: str


class ParticipationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- problem statements ----------------

    async def list_problem_statements(self, hackathon_id: uuid.UUID) -> list[ProblemStatement]:
        result = await self.db.execute(
            select(ProblemStatement)
            .where(ProblemStatement.hackathon_id == hackathon_id)
            .order_by(ProblemStatement.order_index, ProblemStatement.created_at)
        )
        return list(result.scalars().all())

    async def add_problem_statement(self, hackathon_id: uuid.UUID, title: str, description: str) -> ProblemStatement:
        next_index = (
            await self.db.execute(
                select(func.coalesce(func.max(ProblemStatement.order_index), -1)).where(
                    ProblemStatement.hackathon_id == hackathon_id
                )
            )
        ).scalar_one() + 1
        statement = ProblemStatement(
            hackathon_id=hackathon_id, title=title.strip(), description=description.strip(), order_index=next_index
        )
        self.db.add(statement)
        await self.db.flush()
        await self.db.refresh(statement)
        return statement

    async def _get_statement(self, hackathon_id: uuid.UUID, statement_id: uuid.UUID) -> ProblemStatement:
        statement = (
            await self.db.execute(
                select(ProblemStatement).where(
                    ProblemStatement.id == statement_id, ProblemStatement.hackathon_id == hackathon_id
                )
            )
        ).scalar_one_or_none()
        if not statement:
            raise NotFoundError("Problem statement", statement_id)
        return statement

    async def update_problem_statement(
        self, hackathon_id: uuid.UUID, statement_id: uuid.UUID, title: str, description: str
    ) -> ProblemStatement:
        statement = await self._get_statement(hackathon_id, statement_id)
        statement.title, statement.description = title.strip(), description.strip()
        await self.db.flush()
        await self.db.refresh(statement)
        return statement

    async def delete_problem_statement(self, hackathon_id: uuid.UUID, statement_id: uuid.UUID) -> None:
        # Teams that had picked it simply go back to "no problem chosen"
        # (the foreign key is ON DELETE SET NULL).
        await self.db.delete(await self._get_statement(hackathon_id, statement_id))
        await self.db.flush()

    # ---------------- a participant's own team ----------------

    async def _my_team(self, hackathon: Hackathon, student: Student) -> Team:
        team = (
            await self.db.execute(
                select(Team)
                .join(TeamMember, TeamMember.team_id == Team.id)
                .where(Team.hackathon_id == hackathon.id, TeamMember.student_id == student.id)
            )
        ).scalar_one_or_none()
        if not team:
            raise ValidationError("Create or join a team first.")
        return team

    @staticmethod
    def _assert_active(hackathon: Hackathon, what: str) -> None:
        if hackathon.status not in _ACTIVE:
            raise ValidationError(f"{what} is closed for this hackathon.")

    async def choose_problem(
        self, hackathon: Hackathon, student: Student, statement_id: uuid.UUID | None
    ) -> Team:
        self._assert_active(hackathon, "Choosing a problem statement")
        team = await self._my_team(hackathon, student)
        if statement_id is not None:
            await self._get_statement(hackathon.id, statement_id)
        team.problem_statement_id = statement_id
        await self.db.flush()
        await self.db.refresh(team)
        return team

    # ---------------- reports ----------------

    def validate_report(self, filename: str, data: bytes) -> tuple[str, str]:
        """Return (clean filename, content type) or raise a message for the student."""
        if not data:
            raise ValidationError("The file is empty.")
        if len(data) > MAX_REPORT_BYTES:
            raise ValidationError("The report is larger than 20 MB. Compress it or remove large images.")
        name = clean_filename(filename)
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        spec = _REPORT_TYPES.get(extension)
        if spec is None:
            raise ValidationError(f"Upload your report as one of: {ALLOWED_REPORT_EXTENSIONS}.")
        content_type, signatures = spec
        if not any(data.startswith(sig) for sig in signatures):
            raise ValidationError(f"That file doesn't look like a real .{extension} file.")
        return name, content_type

    async def save_report(
        self, hackathon: Hackathon, student: Student, filename: str, data: bytes
    ) -> TeamReport:
        self._assert_active(hackathon, "Report upload")
        team = await self._my_team(hackathon, student)
        name, content_type = self.validate_report(filename, data)
        report = await self.get_report(team.id)
        if report is None:
            report = TeamReport(team_id=team.id)
            self.db.add(report)
        report.filename, report.content_type = name, content_type
        report.size_bytes, report.data = len(data), data
        report.uploaded_by_student_id = student.id
        await self.db.flush()
        await self.db.refresh(report)
        return report

    async def get_report(self, team_id: uuid.UUID) -> TeamReport | None:
        return (
            await self.db.execute(select(TeamReport).where(TeamReport.team_id == team_id))
        ).scalar_one_or_none()

    async def my_report(self, hackathon: Hackathon, student: Student) -> tuple[Team | None, TeamReport | None]:
        team = (
            await self.db.execute(
                select(Team)
                .join(TeamMember, TeamMember.team_id == Team.id)
                .where(Team.hackathon_id == hackathon.id, TeamMember.student_id == student.id)
            )
        ).scalar_one_or_none()
        return team, (await self.get_report(team.id) if team else None)

    async def report_info_by_team(self, team_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[str, int]]:
        """filename + size per team without loading the file bytes."""
        if not team_ids:
            return {}
        rows = await self.db.execute(
            select(TeamReport.team_id, TeamReport.filename, TeamReport.size_bytes).where(
                TeamReport.team_id.in_(team_ids)
            )
        )
        return {team_id: (filename, size) for team_id, filename, size in rows.all()}

    async def problem_titles_by_team(self, teams: list[Team]) -> dict[uuid.UUID, str]:
        ids = {t.problem_statement_id for t in teams if t.problem_statement_id}
        if not ids:
            return {}
        rows = await self.db.execute(select(ProblemStatement.id, ProblemStatement.title).where(ProblemStatement.id.in_(ids)))
        by_id = {i: title for i, title in rows.all()}
        return {t.id: by_id[t.problem_statement_id] for t in teams if t.problem_statement_id in by_id}

    # ---------------- leaderboard & achievements ----------------

    async def _members_by_team(self, team_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
        if not team_ids:
            return {}
        rows = await self.db.execute(
            select(TeamMember.team_id, Student.full_name)
            .join(Student, Student.id == TeamMember.student_id)
            .where(TeamMember.team_id.in_(team_ids))
            .order_by(TeamMember.joined_at)
        )
        out: dict[uuid.UUID, list[str]] = {}
        for team_id, name in rows.all():
            out.setdefault(team_id, []).append(name)
        return out

    async def leaderboard(self, hackathon: Hackathon) -> list[LeaderboardRow]:
        """Graded teams, best first. Equal scores share a rank (1, 1, 3)."""
        graded = (
            await self.db.execute(
                select(Team, Submission)
                .join(Submission, Submission.team_id == Team.id)
                .where(Team.hackathon_id == hackathon.id, Submission.score.is_not(None))
                .order_by(Submission.score.desc(), Submission.submitted_at.asc())
            )
        ).all()
        members = await self._members_by_team([team.id for team, _ in graded])
        rows: list[LeaderboardRow] = []
        previous_score: int | None = None
        previous_rank = 0
        for position, (team, submission) in enumerate(graded, start=1):
            rank = previous_rank if submission.score == previous_score else position
            previous_score, previous_rank = submission.score, rank
            rows.append(
                LeaderboardRow(
                    rank=rank,
                    team_id=team.id,
                    team_name=team.name,
                    score=submission.score,
                    project_title=submission.title,
                    members=members.get(team.id, []),
                )
            )
        return rows

    async def achievements_for(self, student: Student) -> list[Award]:
        """What this participant has earned so far, derived (never stored):
        taking part, submitting, uploading a report and, once the organiser has
        published the leaderboard, a podium finish."""
        teams = (
            await self.db.execute(
                select(Team, Hackathon)
                .join(TeamMember, TeamMember.team_id == Team.id)
                .join(Hackathon, Hackathon.id == Team.hackathon_id)
                .where(TeamMember.student_id == student.id, Hackathon.organization_id == student.organization_id)
                .order_by(Hackathon.start_date.desc())
            )
        ).all()
        awards: list[Award] = []
        for team, hackathon in teams:
            def award(code: str, label: str, detail: str) -> None:
                awards.append(Award(hackathon.id, hackathon.title, team.name, code, label, detail))

            award("participant", "Hackathon participant", f"Took part with team {team.name}.")
            if await self.db.scalar(select(func.count()).select_from(Submission).where(Submission.team_id == team.id)):
                award("submitted", "Project submitted", "Your team submitted a project.")
            if await self.get_report(team.id):
                award("report", "Report submitted", "Your team uploaded its report.")
            if hackathon.leaderboard_visible:
                for row in await self.leaderboard(hackathon):
                    if row.team_id != team.id:
                        continue
                    podium = {1: ("winner", "Winner"), 2: ("runner_up", "Runner-up"), 3: ("third_place", "Third place")}
                    if row.rank in podium:
                        code, label = podium[row.rank]
                        award(code, label, f"Ranked #{row.rank} with {row.score} points.")
        return awards
