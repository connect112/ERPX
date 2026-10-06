"""
What a hackathon participant does once they're on a team: work through the
tasks (problem statements) -- submitting a report and/or a repository or
registry URL for each -- and see where the team stands.

Each task has a maximum mark, optional sub-tasks (the parts of the task and
what each is worth) and a rubric (what staff mark a submission on). Each team
has its own submission per task, scored by staff against the rubric; the
leaderboard ranks teams by the sum of their task scores. Everything here is
ownership-gated by the caller (a member of the team, via get_current_student)
or staff-gated (hackathons.manage/view); nothing relies on a permission the
participant role doesn't hold.
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


def _with_ids(incoming: list[dict], existing: list[dict]) -> list[dict]:
    """Keep the id of an item that already existed (so marks awarded against it stay
    attached when the task is edited); give new items a fresh id."""
    known = {item["id"] for item in existing or []}
    out = []
    for item in incoming:
        item_id = item.get("id") if item.get("id") in known else uuid.uuid4().hex
        out.append({**{k: v for k, v in item.items() if k != "id"}, "id": item_id})
    return out


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TaskRow:
    task: ProblemStatement
    submission: TaskSubmission | None
    rank: int | None = None  # this team's place among teams scored on the task
    teams_scored: int = 0


@dataclass
class TasksView:
    team: Team | None
    rows: list[TaskRow]
    max_total: int
    team_rank: int | None = None
    team_total: int = 0
    teams_ranked: int = 0


@dataclass
class StaffSubmissionRow:
    submission: TaskSubmission
    team_name: str
    task: ProblemStatement
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

    async def add_problem_statement(
        self,
        hackathon_id: uuid.UUID,
        title: str,
        description: str | None,
        marks: int = 0,
        sub_tasks: list[dict] | None = None,
        rubric: list[dict] | None = None,
    ) -> ProblemStatement:
        next_index = (
            await self.db.execute(
                select(func.coalesce(func.max(ProblemStatement.order_index), -1)).where(
                    ProblemStatement.hackathon_id == hackathon_id
                )
            )
        ).scalar_one() + 1
        statement = ProblemStatement(
            hackathon_id=hackathon_id,
            title=title.strip(),
            description=(description or "").strip() or None,
            order_index=next_index,
            marks=marks,
            sub_tasks=_with_ids(sub_tasks or [], []),
            rubric=_with_ids(rubric or [], []),
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

    async def _has_scores(self, task_id: uuid.UUID) -> bool:
        count = (
            await self.db.execute(
                select(func.count()).select_from(TaskSubmission).where(
                    TaskSubmission.problem_statement_id == task_id, TaskSubmission.score.is_not(None)
                )
            )
        ).scalar_one()
        return count > 0

    async def update_problem_statement(
        self,
        hackathon_id: uuid.UUID,
        statement_id: uuid.UUID,
        title: str,
        description: str | None,
        marks: int = 0,
        sub_tasks: list[dict] | None = None,
        rubric: list[dict] | None = None,
    ) -> ProblemStatement:
        statement = await self._get_statement(hackathon_id, statement_id)
        new_rubric = _with_ids(rubric or [], statement.rubric or [])
        if await self._has_scores(statement.id):
            # Changing what the marks are out of, or what they were awarded for, would
            # silently change scores that teams have already been given.
            before = {r["id"]: r["points"] for r in statement.rubric or []}
            after = {r["id"]: r["points"] for r in new_rubric}
            if marks != statement.marks or before != after:
                raise ValidationError(
                    "Submissions for this task have already been scored, so its marks and rubric can't change. "
                    "You can still edit the title, description and sub-tasks."
                )
        statement.title = title.strip()
        statement.description = (description or "").strip() or None
        statement.marks = marks
        statement.sub_tasks = _with_ids(sub_tasks or [], statement.sub_tasks or [])
        statement.rubric = new_rubric
        await self.db.flush()
        await self.db.refresh(statement)
        return statement

    async def delete_problem_statement(self, hackathon_id: uuid.UUID, statement_id: uuid.UUID) -> None:
        # Submissions for the task go with it (ON DELETE CASCADE).
        await self.db.delete(await self._get_statement(hackathon_id, statement_id))
        await self.db.flush()

    async def max_total(self, hackathon_id: uuid.UUID) -> int:
        return int(
            (
                await self.db.execute(
                    select(func.coalesce(func.sum(ProblemStatement.marks), 0)).where(
                        ProblemStatement.hackathon_id == hackathon_id
                    )
                )
            ).scalar_one()
        )

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

    async def _task_places(self, hackathon_id: uuid.UUID, team_id: uuid.UUID) -> dict[uuid.UUID, tuple[int, int]]:
        """task id -> (this team's place, number of teams scored) for every task the team was scored on."""
        rows = (
            await self.db.execute(
                select(TaskSubmission.problem_statement_id, TaskSubmission.team_id, TaskSubmission.score)
                .join(Team, Team.id == TaskSubmission.team_id)
                .where(Team.hackathon_id == hackathon_id, TaskSubmission.score.is_not(None))
            )
        ).all()
        by_task: dict[uuid.UUID, list[tuple[uuid.UUID, int]]] = {}
        for task_id, tid, score in rows:
            by_task.setdefault(task_id, []).append((tid, score))
        places: dict[uuid.UUID, tuple[int, int]] = {}
        for task_id, entries in by_task.items():
            mine = next((score for tid, score in entries if tid == team_id), None)
            if mine is not None:
                places[task_id] = (1 + sum(1 for _, score in entries if score > mine), len(entries))
        return places

    async def tasks_for(self, hackathon: Hackathon, student: Student) -> TasksView:
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

        view = TasksView(
            team=team,
            rows=[TaskRow(task=t, submission=by_task.get(t.id)) for t in tasks],
            max_total=sum(t.marks for t in tasks),
        )
        # Places are only shown while the leaderboard is (so hiding it hides everyone's standing).
        if team is not None and hackathon.leaderboard_visible:
            places = await self._task_places(hackathon.id, team.id)
            for row in view.rows:
                if row.task.id in places:
                    row.rank, row.teams_scored = places[row.task.id]
            board = await self.leaderboard(hackathon)
            view.teams_ranked = len(board)
            mine = next((r for r in board if r.team_id == team.id), None)
            if mine is not None:
                view.team_rank, view.team_total = mine.rank, mine.score
        return view

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
                select(TaskSubmission, Team.name, ProblemStatement)
                .options(defer(TaskSubmission.report_data))
                .join(Team, Team.id == TaskSubmission.team_id)
                .join(ProblemStatement, ProblemStatement.id == TaskSubmission.problem_statement_id)
                .where(Team.hackathon_id == hackathon_id)
                .order_by(Team.name, ProblemStatement.order_index)
            )
        ).all()
        members = await self._members_by_team([s.team_id for s, *_ in rows])
        return [
            StaffSubmissionRow(submission=s, team_name=team_name, task=task, members=members.get(s.team_id, []))
            for s, team_name, task in rows
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
        self,
        hackathon_id: uuid.UUID,
        submission_id: uuid.UUID,
        score: int | None,
        rubric_scores: dict[str, int] | None,
        feedback: str | None,
    ) -> TaskSubmission:
        """Award marks. For a task with a rubric every rule must be marked (0..its points)
        and the score is their sum; for a task without one a single score (up to the
        task's marks, when it has any) is taken."""
        submission = await self._staff_submission(hackathon_id, submission_id)
        task = await self._get_statement(hackathon_id, submission.problem_statement_id)
        rubric = task.rubric or []
        if rubric:
            if rubric_scores is None:
                raise ValidationError("Enter marks for each rubric criterion.")
            ids = {rule["id"] for rule in rubric}
            if set(rubric_scores) - ids:
                raise ValidationError("That rubric has changed. Reload the page and mark again.")
            if ids - set(rubric_scores):
                raise ValidationError("Enter marks for every criterion (0 is fine).")
            for rule in rubric:
                value = rubric_scores[rule["id"]]
                if not 0 <= value <= rule["points"]:
                    raise ValidationError(f'"{rule["criterion"]}": marks must be between 0 and {rule["points"]}.')
            submission.rubric_scores = {rule["id"]: int(rubric_scores[rule["id"]]) for rule in rubric}
            submission.score = sum(submission.rubric_scores.values())
        else:
            if score is None:
                raise ValidationError("Enter the score.")
            if task.marks and score > task.marks:
                raise ValidationError(f"The score can't be more than the task's {task.marks} marks.")
            submission.rubric_scores = None
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
