"""
What a hackathon participant does once they're on a team: work through the
tasks (problem statements) -- submitting a report and/or a repository or
registry URL for each -- and see where the team stands.

Each task has its own submission per team, scored by staff; the leaderboard
ranks teams by the sum of their task scores. Everything here is ownership-gated
by the caller (a member of the team, via get_current_student) or staff-gated
(hackathons.manage/view); nothing relies on a permission the participant role
doesn't hold.
"""

import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.core.exceptions import NotFoundError, ValidationError
from modules.hackathons.models import (
    Hackathon,
    HackathonStatus,
    ProblemStatement,
    TaskSubmission,
    Team,
    TeamMember,
)
from modules.students.models import Student

MAX_REPORT_BYTES = 20 * 1024 * 1024
MAX_URL_LENGTH = 512

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


def clean_url(value: str | None) -> str | None:
    """A http(s) URL, or None for an empty value; anything else is rejected with a message."""
    url = (value or "").strip()
    if not url:
        return None
    if len(url) > MAX_URL_LENGTH:
        raise ValidationError("That URL is too long.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValidationError("Enter the full URL, starting with http:// or https://")
    return url


@dataclass
class TaskRow:
    task: ProblemStatement
    submission: TaskSubmission | None


@dataclass
class StaffSubmissionRow:
    submission: TaskSubmission
    team_name: str
    task_title: str
    task_order: int
    members: list[str]


@dataclass
class LeaderboardRow:
    rank: int
    team_id: uuid.UUID
    team_name: str
    score: int
    tasks_scored: int
    members: list[str]


@dataclass
class Award:
    hackathon_id: uuid.UUID
    hackathon_title: str
    team_name: str
    code: str  # participant | submitted | winner | runner_up | third_place
    label: str
    detail: str


class ParticipationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- tasks (problem statements) ----------------

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
            raise NotFoundError("Task", statement_id)
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
        # Submissions for the task go with it (ON DELETE CASCADE).
        await self.db.delete(await self._get_statement(hackathon_id, statement_id))
        await self.db.flush()

    # ---------------- a participant's own team ----------------

    async def my_team(self, hackathon: Hackathon, student: Student) -> Team | None:
        return (
            await self.db.execute(
                select(Team)
                .join(TeamMember, TeamMember.team_id == Team.id)
                .where(Team.hackathon_id == hackathon.id, TeamMember.student_id == student.id)
            )
        ).scalar_one_or_none()

    @staticmethod
    def _assert_active(hackathon: Hackathon) -> None:
        if hackathon.status not in _ACTIVE:
            raise ValidationError("Task submission is closed for this hackathon.")

    async def tasks_for(self, hackathon: Hackathon, student: Student) -> tuple[Team | None, list[TaskRow]]:
        """Every task, each with this student's team's submission (if any). The
        report bytes are not loaded -- only what the list needs."""
        team = await self.my_team(hackathon, student)
        tasks = await self.list_problem_statements(hackathon.id)
        by_task: dict[uuid.UUID, TaskSubmission] = {}
        if team is not None:
            rows = (
                await self.db.execute(
                    select(TaskSubmission)
                    .options(defer(TaskSubmission.report_data))
                    .where(TaskSubmission.team_id == team.id)
                )
            ).scalars().all()
            by_task = {s.problem_statement_id: s for s in rows}
        return team, [TaskRow(task=t, submission=by_task.get(t.id)) for t in tasks]

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

    async def save_task_submission(
        self,
        hackathon: Hackathon,
        student: Student,
        task_id: uuid.UUID,
        repo_url: str | None,
        filename: str | None,
        data: bytes | None,
    ) -> TaskSubmission:
        """Create or update this team's submission for one task.

        `repo_url` None leaves the saved URL alone, "" clears it; `data` None
        keeps the saved report, otherwise replaces it. A submission must hold a
        report or a URL.
        """
        self._assert_active(hackathon)
        team = await self.my_team(hackathon, student)
        if team is None:
            raise ValidationError("Create or join a team first.")
        await self._get_statement(hackathon.id, task_id)

        url = clean_url(repo_url) if repo_url is not None else None
        report = self.validate_report(filename or "report", data) if data is not None else None

        submission = (
            await self.db.execute(
                select(TaskSubmission)
                .options(defer(TaskSubmission.report_data))
                .where(TaskSubmission.team_id == team.id, TaskSubmission.problem_statement_id == task_id)
            )
        ).scalar_one_or_none()
        if submission is None:
            if url is None and report is None:
                raise ValidationError("Add a report or a repository / registry URL to submit this task.")
            submission = TaskSubmission(team_id=team.id, problem_statement_id=task_id, submitted_at=_now())
            self.db.add(submission)
        if repo_url is not None:
            submission.repo_url = url
        if report is not None and data is not None:
            submission.report_filename, submission.report_content_type = report
            submission.report_size_bytes, submission.report_data = len(data), data
        if submission.repo_url is None and submission.report_filename is None:
            raise ValidationError("A submission needs a report or a repository / registry URL.")
        submission.submitted_by_student_id = student.id
        submission.submitted_at = _now()
        await self.db.flush()
        await self.db.refresh(submission, attribute_names=["id", "updated_at", "created_at"])
        return submission

    async def my_task_report(
        self, hackathon: Hackathon, student: Student, task_id: uuid.UUID
    ) -> TaskSubmission | None:
        team = await self.my_team(hackathon, student)
        if team is None:
            return None
        submission = (
            await self.db.execute(
                select(TaskSubmission).where(
                    TaskSubmission.team_id == team.id, TaskSubmission.problem_statement_id == task_id
                )
            )
        ).scalar_one_or_none()
        return submission if submission and submission.report_data is not None else None

    # ---------------- staff: review and score ----------------

    async def list_task_submissions(self, hackathon_id: uuid.UUID) -> list[StaffSubmissionRow]:
        rows = (
            await self.db.execute(
                select(TaskSubmission, Team.name, ProblemStatement.title, ProblemStatement.order_index)
                .options(defer(TaskSubmission.report_data))
                .join(Team, Team.id == TaskSubmission.team_id)
                .join(ProblemStatement, ProblemStatement.id == TaskSubmission.problem_statement_id)
                .where(Team.hackathon_id == hackathon_id)
                .order_by(ProblemStatement.order_index, Team.name)
            )
        ).all()
        members = await self._members_by_team([s.team_id for s, *_ in rows])
        return [
            StaffSubmissionRow(
                submission=s,
                team_name=team_name,
                task_title=task_title,
                task_order=task_order,
                members=members.get(s.team_id, []),
            )
            for s, team_name, task_title, task_order in rows
        ]

    async def _staff_submission(
        self, hackathon_id: uuid.UUID, submission_id: uuid.UUID, with_report: bool = False
    ) -> TaskSubmission:
        query = (
            select(TaskSubmission)
            .join(Team, Team.id == TaskSubmission.team_id)
            .where(TaskSubmission.id == submission_id, Team.hackathon_id == hackathon_id)
        )
        if not with_report:
            query = query.options(defer(TaskSubmission.report_data))
        submission = (await self.db.execute(query)).scalar_one_or_none()
        if submission is None:
            raise NotFoundError("Submission", submission_id)
        return submission

    async def get_staff_report(self, hackathon_id: uuid.UUID, submission_id: uuid.UUID) -> TaskSubmission:
        submission = await self._staff_submission(hackathon_id, submission_id, with_report=True)
        if submission.report_data is None:
            raise NotFoundError("Report")
        return submission

    async def grade(
        self, hackathon_id: uuid.UUID, submission_id: uuid.UUID, score: int, feedback: str | None
    ) -> TaskSubmission:
        submission = await self._staff_submission(hackathon_id, submission_id)
        submission.score = score
        submission.feedback = (feedback or "").strip() or None
        await self.db.flush()
        await self.db.refresh(submission, attribute_names=["updated_at"])
        return submission

    async def team_totals(self, team_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
        """(tasks submitted, total score) per team."""
        if not team_ids:
            return {}
        rows = await self.db.execute(
            select(
                TaskSubmission.team_id,
                func.count(TaskSubmission.id),
                func.coalesce(func.sum(TaskSubmission.score), 0),
            )
            .where(TaskSubmission.team_id.in_(team_ids))
            .group_by(TaskSubmission.team_id)
        )
        return {team_id: (int(count), int(total)) for team_id, count, total in rows.all()}

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
        """Teams with at least one scored task, best total first. Equal totals
        share a rank (1, 1, 3); the team that reached the total first wins the
        order within a tie."""
        totals = (
            await self.db.execute(
                select(
                    Team.id,
                    Team.name,
                    func.sum(TaskSubmission.score),
                    func.count(TaskSubmission.id),
                    func.max(TaskSubmission.updated_at),
                )
                .join(TaskSubmission, TaskSubmission.team_id == Team.id)
                .where(Team.hackathon_id == hackathon.id, TaskSubmission.score.is_not(None))
                .group_by(Team.id, Team.name)
                .order_by(func.sum(TaskSubmission.score).desc(), func.max(TaskSubmission.updated_at).asc())
            )
        ).all()
        members = await self._members_by_team([row[0] for row in totals])
        rows: list[LeaderboardRow] = []
        previous_score: int | None = None
        previous_rank = 0
        for position, (team_id, team_name, total, scored, _last) in enumerate(totals, start=1):
            total = int(total)
            rank = previous_rank if total == previous_score else position
            previous_score, previous_rank = total, rank
            rows.append(
                LeaderboardRow(
                    rank=rank,
                    team_id=team_id,
                    team_name=team_name,
                    score=total,
                    tasks_scored=int(scored),
                    members=members.get(team_id, []),
                )
            )
        return rows

    async def achievements_for(self, student: Student) -> list[Award]:
        """What this participant has earned so far, derived (never stored):
        taking part, submitting tasks and, once scores exist, a podium finish."""
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

            def award(code: str, label: str, detail: str, *, _team=team, _hackathon=hackathon) -> None:
                awards.append(Award(_hackathon.id, _hackathon.title, _team.name, code, label, detail))

            award("participant", "Hackathon participant", f"Took part with team {team.name}.")
            submitted = (await self.team_totals([team.id])).get(team.id, (0, 0))[0]
            if submitted:
                task_count = (
                    await self.db.execute(
                        select(func.count()).select_from(ProblemStatement).where(
                            ProblemStatement.hackathon_id == hackathon.id
                        )
                    )
                ).scalar_one()
                award("submitted", "Tasks submitted", f"Your team has submitted {submitted} of {task_count} tasks.")
            if hackathon.leaderboard_visible:
                podium = {1: ("winner", "Winner"), 2: ("runner_up", "Runner-up"), 3: ("third_place", "Third place")}
                for row in await self.leaderboard(hackathon):
                    if row.team_id == team.id and row.rank in podium:
                        code, label = podium[row.rank]
                        award(code, label, f"Ranked #{row.rank} with {row.score} points.")
        return awards


def _now() -> datetime:
    return datetime.now(timezone.utc)
