import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authentication.repository import AuthRepository
from modules.authorization.dependencies import require_permissions
from modules.hackathons.models import HackathonStatus
from modules.hackathons.participation import (
    MAX_REPORT_BYTES,
    ParticipationService,
    is_reviewed,
    resubmissions_left,
)
from modules.hackathons.schemas import (
    AwardPublic,
    CandidatePublic,
    HackathonCreateRequest,
    HackathonListResponse,
    HackathonPublic,
    HackathonStatusChangeRequest,
    HackathonUpdateRequest,
    LeaderboardBoard,
    LeaderboardEntry,
    MemberMoveRequest,
    MemberRef,
    MemberUpdateRequest,
    MessageResponse,
    ParticipantError,
    ParticipantsRequest,
    ParticipantsResponse,
    ProblemStatementInput,
    ProblemStatementPublic,
    ReportInfo,
    RosterMemberPublic,
    RosterTeamPublic,
    TaskGradeRequest,
    TaskPublic,
    TaskSubmissionAdmin,
    TaskSubmissionInfo,
    TasksResponse,
    TeamAdminCreateRequest,
    TeamCreateRequest,
    TeamMemberPublic,
    TeamPublic,
    TeamRenameRequest,
    TeamWithMembersPublic,
)
from modules.hackathons.provisioning import ParticipantProvisioner
from modules.hackathons.service import HackathonService, TeamService
from modules.hackathons.tasks import enqueue_welcome_emails
from modules.hackathons.team_admin import TeamAdminService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.students.repository import StudentRepository
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


def _report_response(submission) -> Response:
    from urllib.parse import quote

    return Response(
        content=submission.report_data,
        media_type=submission.report_content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(submission.report_filename or 'report')}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


async def _members_public(db: AsyncSession, members, organization_id: uuid.UUID) -> list[TeamMemberPublic]:
    student_repo = StudentRepository(db)
    results = []
    for member in members:
        student = await student_repo.get_by_id(member.student_id, organization_id)
        results.append(
            TeamMemberPublic(
                id=member.id,
                team_id=member.team_id,
                student_id=member.student_id,
                student_name=student.full_name if student else "Unknown student",
                joined_at=member.joined_at,
            )
        )
    return results


# ---- Student self-service ----


@router.get("/me", response_model=list[HackathonPublic])
async def list_open_hackathons(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = HackathonService(db)
    open_hackathons, _total = await service.list_hackathons(
        student.organization_id, status=HackathonStatus.REGISTRATION_OPEN, skip=0, limit=200
    )
    ongoing_hackathons, _total = await service.list_hackathons(
        student.organization_id, status=HackathonStatus.ONGOING, skip=0, limit=200
    )
    return [HackathonPublic.model_validate(h) for h in [*open_hackathons, *ongoing_hackathons]]


@router.get("/{hackathon_id}/teams/me", response_model=TeamWithMembersPublic | None)
async def get_my_team(
    hackathon_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = TeamService(db)
    result = await service.get_my_team(hackathon_id, student.id)
    if not result:
        return None
    team, members = result
    return TeamWithMembersPublic(
        team=TeamPublic.model_validate(team),
        members=await _members_public(db, members, student.organization_id),
    )


# ---- Participant features: tasks, leaderboard, achievements ----


async def _visible_hackathon(db: AsyncSession, hackathon_id: uuid.UUID, student: Student):
    hackathon = await HackathonService(db).get_hackathon(hackathon_id, student.organization_id)
    if hackathon.status in (HackathonStatus.DRAFT, HackathonStatus.CANCELLED):
        raise NotFoundError("Hackathon", hackathon_id)
    return hackathon


@router.get("/leaderboard/me", response_model=list[LeaderboardBoard])
async def my_leaderboards(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Team rankings for every running or finished hackathon in the org.
    Scores stay hidden until the organiser publishes them."""
    hackathons = []
    for status_value in (HackathonStatus.REGISTRATION_OPEN, HackathonStatus.ONGOING, HackathonStatus.COMPLETED):
        items, _total = await HackathonService(db).list_hackathons(
            student.organization_id, status=status_value, skip=0, limit=100
        )
        hackathons.extend(items)
    participation = ParticipationService(db)
    boards = []
    for hackathon in hackathons:
        entries = []
        if hackathon.leaderboard_visible:
            entries = [
                LeaderboardEntry(
                    rank=r.rank, team_name=r.team_name, score=r.score, tasks_scored=r.tasks_scored, members=r.members
                )
                for r in await participation.leaderboard(hackathon)
            ]
        boards.append(
            LeaderboardBoard(
                hackathon_id=hackathon.id,
                hackathon_title=hackathon.title,
                published=hackathon.leaderboard_visible,
                max_total=await participation.max_total(hackathon.id),
                entries=entries,
            )
        )
    return boards


@router.get("/achievements/me", response_model=list[AwardPublic])
async def my_achievements(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    awards = await ParticipationService(db).achievements_for(student)
    return [AwardPublic(**a.__dict__) for a in awards]


def _submission_info(submission) -> TaskSubmissionInfo:
    return TaskSubmissionInfo(
        id=submission.id,
        repo_url=submission.repo_url,
        report=ReportInfo(
            filename=submission.report_filename,
            size_bytes=submission.report_size_bytes or 0,
            uploaded_at=submission.updated_at,
        )
        if submission.report_filename
        else None,
        submitted_at=submission.submitted_at,
        score=submission.score,
        rubric_scores=submission.rubric_scores,
        feedback=submission.feedback,
        resubmission_count=submission.resubmission_count,
        reviewed=is_reviewed(submission),
    )


@router.get("/{hackathon_id}/tasks/me", response_model=TasksResponse)
async def list_my_tasks(
    hackathon_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Every task with its marks, sub-tasks and rubric, the team's submission for it
    (report and/or URL, marks per rubric rule, feedback) and the team's place."""
    hackathon = await _visible_hackathon(db, hackathon_id, student)
    view = await ParticipationService(db).tasks_for(hackathon, student)
    can_submit = view.team is not None and hackathon.status in (
        HackathonStatus.REGISTRATION_OPEN,
        HackathonStatus.ONGOING,
    )
    return TasksResponse(
        team_id=view.team.id if view.team else None,
        can_submit=can_submit,
        resubmission_enabled=hackathon.resubmission_enabled,
        max_resubmissions=hackathon.max_resubmissions,
        max_total=view.max_total,
        leaderboard_visible=hackathon.leaderboard_visible,
        team_rank=view.team_rank,
        team_total=view.team_total,
        teams_ranked=view.teams_ranked,
        tasks=[
            TaskPublic(
                id=row.task.id,
                title=row.task.title,
                description=row.task.description,
                order_index=row.task.order_index,
                marks=row.task.marks,
                sub_tasks=row.task.sub_tasks or [],
                rubric=row.task.rubric or [],
                submission=_submission_info(row.submission) if row.submission else None,
                task_rank=row.rank,
                task_teams_scored=row.teams_scored,
                can_resubmit=can_submit and resubmissions_left(hackathon, row.submission) > 0,
                resubmissions_left=resubmissions_left(hackathon, row.submission),
            )
            for row in view.rows
        ],
    )


@router.put("/{hackathon_id}/tasks/{task_id}/submission/me", response_model=TaskSubmissionInfo)
async def submit_my_task(
    hackathon_id: uuid.UUID,
    task_id: uuid.UUID,
    repo_url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Submit (or update) the team's work on one task: a report and/or a repository / registry URL."""
    hackathon = await _visible_hackathon(db, hackathon_id, student)
    data = await file.read(MAX_REPORT_BYTES + 1) if file is not None and file.filename else None
    submission = await ParticipationService(db).save_task_submission(
        hackathon, student, task_id, repo_url, file.filename if file is not None else None, data
    )
    return _submission_info(submission)


@router.get("/{hackathon_id}/tasks/{task_id}/submission/me/report")
async def download_my_task_report(
    hackathon_id: uuid.UUID,
    task_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    hackathon = await _visible_hackathon(db, hackathon_id, student)
    submission = await ParticipationService(db).my_task_report(hackathon, student, task_id)
    if submission is None:
        raise NotFoundError("Report")
    return _report_response(submission)


@router.post("/{hackathon_id}/teams/me", response_model=TeamPublic, status_code=status.HTTP_201_CREATED)
async def create_my_team(
    hackathon_id: uuid.UUID,
    payload: TeamCreateRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = TeamService(db)
    team = await service.create_team(student.organization_id, hackathon_id, student.id, payload.name)
    return TeamPublic.model_validate(team)


@router.get("/{hackathon_id}/teams/browse", response_model=list[TeamPublic])
async def browse_teams(
    hackathon_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = TeamService(db)
    teams = await service.list_teams(hackathon_id, student.organization_id)
    # Students see how full each team is (so they don't try a full one),
    # but not who is in other teams.
    names = await service.members_by_team(teams, student.organization_id)
    out = []
    for team in teams:
        item = TeamPublic.model_validate(team)
        item.member_count = len(names[team.id])
        out.append(item)
    return out


@router.post("/{hackathon_id}/teams/{team_id}/join/me", response_model=TeamMemberPublic)
async def join_team(
    hackathon_id: uuid.UUID,
    team_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = TeamService(db)
    member = await service.join_team(student.organization_id, hackathon_id, team_id, student.id)
    return TeamMemberPublic(
        id=member.id,
        team_id=member.team_id,
        student_id=member.student_id,
        student_name=student.full_name,
        joined_at=member.joined_at,
    )


# ---- Staff management ----


@router.post("", response_model=HackathonPublic, status_code=status.HTTP_201_CREATED)
async def create_hackathon(
    payload: HackathonCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = HackathonService(db)
    hackathon = await service.create_hackathon(organization_id, **payload.model_dump())
    return HackathonPublic.model_validate(hackathon)


@router.get("", response_model=HackathonListResponse)
async def list_hackathons(
    status_filter: HackathonStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    service = HackathonService(db)
    hackathons, total = await service.list_hackathons(
        organization_id, status=status_filter, skip=skip, limit=limit
    )
    return HackathonListResponse(
        items=[HackathonPublic.model_validate(h) for h in hackathons], total=total
    )


@router.get("/{hackathon_id}", response_model=HackathonPublic)
async def get_hackathon(
    hackathon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    service = HackathonService(db)
    hackathon = await service.get_hackathon(hackathon_id, organization_id)
    return HackathonPublic.model_validate(hackathon)


@router.patch("/{hackathon_id}", response_model=HackathonPublic)
async def update_hackathon(
    hackathon_id: uuid.UUID,
    payload: HackathonUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = HackathonService(db)
    hackathon = await service.update_hackathon(
        hackathon_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return HackathonPublic.model_validate(hackathon)


@router.post("/{hackathon_id}/status", response_model=HackathonPublic)
async def change_hackathon_status(
    hackathon_id: uuid.UUID,
    payload: HackathonStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = HackathonService(db)
    hackathon = await service.change_status(hackathon_id, organization_id, payload.status)
    return HackathonPublic.model_validate(hackathon)


@router.delete("/{hackathon_id}", response_model=MessageResponse)
async def delete_hackathon(
    hackathon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = HackathonService(db)
    await service.delete_hackathon(hackathon_id, organization_id)
    return MessageResponse(message="Hackathon deleted successfully.")


@router.get("/{hackathon_id}/teams", response_model=list[TeamPublic])
async def list_teams(
    hackathon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    service = TeamService(db)
    teams = await service.list_teams(hackathon_id, organization_id)
    names = await service.members_by_team(teams, organization_id)
    totals = await ParticipationService(db).team_totals([t.id for t in teams])
    out = []
    for team in teams:
        item = TeamPublic.model_validate(team)
        item.member_names = names[team.id]
        item.member_count = len(item.member_names)
        item.tasks_submitted, item.total_score = totals.get(team.id, (0, 0))
        out.append(item)
    return out


@router.get("/{hackathon_id}/task-submissions", response_model=list[TaskSubmissionAdmin])
async def list_task_submissions(
    hackathon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    rows = await ParticipationService(db).list_task_submissions(hackathon_id)
    return [
        TaskSubmissionAdmin(
            id=row.submission.id,
            team_id=row.submission.team_id,
            team_name=row.team_name,
            members=row.members,
            task_id=row.submission.problem_statement_id,
            task_title=row.task.title,
            task_order=row.task.order_index,
            task_marks=row.task.marks,
            rubric=row.task.rubric or [],
            repo_url=row.submission.repo_url,
            report_filename=row.submission.report_filename,
            report_size_bytes=row.submission.report_size_bytes,
            submitted_at=row.submission.submitted_at,
            score=row.submission.score,
            rubric_scores=row.submission.rubric_scores,
            reviewed=is_reviewed(row.submission),
            resubmission_count=row.submission.resubmission_count,
            feedback=row.submission.feedback,
        )
        for row in rows
    ]


@router.get("/{hackathon_id}/task-submissions/{submission_id}/report")
async def download_task_report(
    hackathon_id: uuid.UUID,
    submission_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    return _report_response(await ParticipationService(db).get_staff_report(hackathon_id, submission_id))


@router.post("/{hackathon_id}/task-submissions/{submission_id}/grade", response_model=TaskSubmissionInfo)
async def grade_task_submission(
    hackathon_id: uuid.UUID,
    submission_id: uuid.UUID,
    payload: TaskGradeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Award a score (and optional feedback) to one task submission; the leaderboard
    is computed live from these, so it updates as soon as this returns."""
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    submission = await ParticipationService(db).grade(
        hackathon_id, submission_id, payload.score, payload.rubric_scores, payload.feedback
    )
    return _submission_info(submission)


@router.delete("/{hackathon_id}/task-submissions/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_submission(
    hackathon_id: uuid.UUID,
    submission_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Delete one team's submission for a task (with its marks); the team can then submit it again."""
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    await ParticipationService(db).delete_task_submission(hackathon_id, submission_id)


@router.get("/{hackathon_id}/leaderboard", response_model=LeaderboardBoard)
async def staff_leaderboard(
    hackathon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    """The live ranking, whether or not it is published to participants."""
    hackathon = await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    rows = await ParticipationService(db).leaderboard(hackathon)
    return LeaderboardBoard(
        hackathon_id=hackathon.id,
        hackathon_title=hackathon.title,
        published=hackathon.leaderboard_visible,
        max_total=await ParticipationService(db).max_total(hackathon.id),
        entries=[
            LeaderboardEntry(rank=r.rank, team_name=r.team_name, score=r.score, tasks_scored=r.tasks_scored, members=r.members)
            for r in rows
        ],
    )


@router.get("/{hackathon_id}/problem-statements", response_model=list[ProblemStatementPublic])
async def list_problem_statements(
    hackathon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    items = await ParticipationService(db).list_problem_statements(hackathon_id)
    return [ProblemStatementPublic.model_validate(i) for i in items]


@router.post(
    "/{hackathon_id}/problem-statements", response_model=ProblemStatementPublic, status_code=status.HTTP_201_CREATED
)
async def add_problem_statement(
    hackathon_id: uuid.UUID,
    payload: ProblemStatementInput,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    item = await ParticipationService(db).add_problem_statement(
        hackathon_id,
        payload.title,
        payload.description,
        payload.marks,
        [t.model_dump() for t in payload.sub_tasks],
        [r.model_dump() for r in payload.rubric],
    )
    return ProblemStatementPublic.model_validate(item)


@router.put("/{hackathon_id}/problem-statements/{statement_id}", response_model=ProblemStatementPublic)
async def update_problem_statement(
    hackathon_id: uuid.UUID,
    statement_id: uuid.UUID,
    payload: ProblemStatementInput,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    item = await ParticipationService(db).update_problem_statement(
        hackathon_id,
        statement_id,
        payload.title,
        payload.description,
        payload.marks,
        [t.model_dump() for t in payload.sub_tasks],
        [r.model_dump() for r in payload.rubric],
    )
    return ProblemStatementPublic.model_validate(item)


@router.delete("/{hackathon_id}/problem-statements/{statement_id}", response_model=MessageResponse)
async def delete_problem_statement(
    hackathon_id: uuid.UUID,
    statement_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    await ParticipationService(db).delete_problem_statement(hackathon_id, statement_id)
    return MessageResponse(message="Task deleted.")


@router.post("/{hackathon_id}/participants", response_model=ParticipantsResponse)
async def add_participants(
    hackathon_id: uuid.UUID,
    payload: ParticipantsRequest,
    background: BackgroundTasks,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage", "students.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Create a student login for every pasted name+email and email each
    person a set-password link. Accounts that already exist as students are
    left alone (they can already take part)."""
    hackathon = await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    result = await ParticipantProvisioner(db).provision(
        organization_id,
        hackathon,
        [(p.name, str(p.email), p.phone) for p in payload.participants],
        created_by_user_id=user.id,
        resend_to_existing=payload.resend_to_existing,
    )
    # Commit first, then queue: a worker must never get (or a student an
    # email with) a token for a row that was rolled back. Queueing runs after
    # the response is sent, so a slow or unreachable broker can't hang the
    # request (the accounts are saved either way).
    await db.commit()
    background.add_task(
        enqueue_welcome_emails,
        [(c.email, c.full_name, c.reset_token) for c in [*result.created, *result.resent]],
        hackathon.title,
        settings.STUDENT_PORTAL_URL,
    )
    return ParticipantsResponse(
        created=len(result.created),
        resent=len(result.resent),
        already_have_login=len(result.already_ready),
        errors=[ParticipantError(email=e, reason=r) for e, r in result.errors],
    )


# ---------------- organiser team and member controls ----------------


async def _resolve_member(
    db: AsyncSession, organization_id: uuid.UUID, hackathon, ref: MemberRef, actor: User
) -> tuple[uuid.UUID, tuple[str, str, str] | None]:
    """The student a MemberRef points at. A new person gets a login (and a welcome email, returned
    for the caller to queue once the transaction is committed); someone who already has one is reused."""
    if ref.student_id is not None:
        return ref.student_id, None
    email = str(ref.email).strip().lower()
    result = await ParticipantProvisioner(db).provision(
        organization_id, hackathon, [(ref.name or "", email, ref.phone)], created_by_user_id=actor.id
    )
    if result.errors:
        raise ValidationError(result.errors[0][1])
    student_repo = StudentRepository(db)
    if result.created:
        login = result.created[0]
        student = await student_repo.get_by_user_id(login.user_id)
        email_job = (login.email, login.full_name, login.reset_token)
    else:  # they already had a login
        user = await AuthRepository(db).get_user_by_email(email)
        student = await student_repo.get_by_user_id(user.id) if user else None
        email_job = None
    if student is None:
        raise ValidationError("Could not find or create that participant.")
    return student.id, email_job


async def _commit_and_queue(db: AsyncSession, background: BackgroundTasks, hackathon, jobs) -> None:
    # Commit first so a link is never emailed for a change that was rolled back.
    await db.commit()
    jobs = [j for j in jobs if j is not None]
    if jobs:
        background.add_task(enqueue_welcome_emails, jobs, hackathon.title, settings.STUDENT_PORTAL_URL)


@router.get("/{hackathon_id}/roster", response_model=list[RosterTeamPublic])
async def team_roster(
    hackathon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    """Every team with its members' names, emails and phones, and whether each has signed in."""
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    teams = await TeamAdminService(db).roster(hackathon_id)
    totals = await ParticipationService(db).team_totals([t.team.id for t in teams])
    return [
        RosterTeamPublic(
            id=t.team.id,
            name=t.team.name,
            created_at=t.team.created_at,
            tasks_submitted=totals.get(t.team.id, (0, 0))[0],
            total_score=totals.get(t.team.id, (0, 0))[1],
            members=[RosterMemberPublic(**m.__dict__) for m in t.members],
        )
        for t in teams
    ]


@router.get("/{hackathon_id}/candidates", response_model=list[CandidatePublic])
async def team_candidates(
    hackathon_id: uuid.UUID,
    q: str = Query(default="", max_length=100),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    """People with a login who are not in any team of this hackathon yet."""
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    students = await TeamAdminService(db).candidates(organization_id, hackathon_id, q)
    return [
        CandidatePublic(student_id=s.id, full_name=s.full_name, email=s.email, student_code=s.student_code)
        for s in students
    ]


@router.post("/{hackathon_id}/teams", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_team_as_staff(
    hackathon_id: uuid.UUID,
    payload: TeamAdminCreateRequest,
    background: BackgroundTasks,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage", "students.manage")),
    db: AsyncSession = Depends(get_db),
):
    hackathon = await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    # One savepoint, so a refused team (say, a taken name) doesn't leave a freshly created login behind.
    async with db.begin_nested():
        student_id, job = await _resolve_member(db, organization_id, hackathon, payload.member, user)
        await TeamAdminService(db).create_team(organization_id, hackathon, payload.name, [student_id])
    await _commit_and_queue(db, background, hackathon, [job])
    return MessageResponse(message="Team created.")


@router.patch("/{hackathon_id}/teams/{team_id}", response_model=MessageResponse)
async def rename_team(
    hackathon_id: uuid.UUID,
    team_id: uuid.UUID,
    payload: TeamRenameRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    await TeamAdminService(db).rename_team(hackathon_id, team_id, payload.name)
    return MessageResponse(message="Team renamed.")


@router.delete("/{hackathon_id}/teams/{team_id}", response_model=MessageResponse)
async def delete_team(
    hackathon_id: uuid.UUID,
    team_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Delete a team, its members' places in it and its task submissions. Their logins are kept."""
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    await TeamAdminService(db).delete_team(hackathon_id, team_id)
    return MessageResponse(message="Team deleted.")


@router.post("/{hackathon_id}/teams/{team_id}/members", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def add_team_member(
    hackathon_id: uuid.UUID,
    team_id: uuid.UUID,
    payload: MemberRef,
    background: BackgroundTasks,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage", "students.manage")),
    db: AsyncSession = Depends(get_db),
):
    hackathon = await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    async with db.begin_nested():
        student_id, job = await _resolve_member(db, organization_id, hackathon, payload, user)
        await TeamAdminService(db).add_member(organization_id, hackathon, team_id, student_id)
    await _commit_and_queue(db, background, hackathon, [job])
    return MessageResponse(message="Member added.")


@router.delete("/{hackathon_id}/teams/{team_id}/members/{student_id}", response_model=MessageResponse)
async def remove_team_member(
    hackathon_id: uuid.UUID,
    team_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Take someone out of a team (their login is kept; they can join or be added to another team)."""
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    await TeamAdminService(db).remove_member(hackathon_id, team_id, student_id)
    return MessageResponse(message="Member removed.")


@router.post("/{hackathon_id}/members/{student_id}/move", response_model=MessageResponse)
async def move_team_member(
    hackathon_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: MemberMoveRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    hackathon = await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    team = await TeamAdminService(db).move_member(hackathon, student_id, payload.team_id)
    return MessageResponse(message=f'Moved to "{team.name}".')


@router.patch("/{hackathon_id}/members/{student_id}", response_model=MessageResponse)
async def update_team_member(
    hackathon_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: MemberUpdateRequest,
    background: BackgroundTasks,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage", "students.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Correct a participant's name, phone or login email."""
    hackathon = await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    result = await TeamAdminService(db).update_member(
        organization_id,
        hackathon_id,
        student_id,
        payload.full_name,
        str(payload.email) if payload.email else None,
        payload.phone,
        payload.send_login_link,
        phone_given="phone" in payload.model_fields_set,
    )
    await _commit_and_queue(db, background, hackathon, [result.login_link])
    if result.email_changed:
        message = "Saved. The login now uses the new email address."
        if result.login_link:
            message += " A set-password link was sent to it."
        return MessageResponse(message=message)
    return MessageResponse(message="Saved.")


@router.post("/{hackathon_id}/members/{student_id}/login-link", response_model=MessageResponse)
async def send_member_login_link(
    hackathon_id: uuid.UUID,
    student_id: uuid.UUID,
    background: BackgroundTasks,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage", "students.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Email the person a fresh set-password link."""
    hackathon = await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    job = await TeamAdminService(db).new_login_link(organization_id, hackathon_id, student_id)
    await _commit_and_queue(db, background, hackathon, [job])
    return MessageResponse(message=f"A set-password link was sent to {job[0]}.")
