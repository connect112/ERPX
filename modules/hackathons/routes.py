import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.hackathons.models import HackathonStatus
from modules.hackathons.participation import MAX_REPORT_BYTES, ParticipationService
from modules.hackathons.schemas import (
    AwardPublic,
    ChooseProblemRequest,
    HackathonCreateRequest,
    HackathonListResponse,
    HackathonPublic,
    HackathonStatusChangeRequest,
    HackathonUpdateRequest,
    LeaderboardBoard,
    LeaderboardEntry,
    MessageResponse,
    ParticipantError,
    ParticipantsRequest,
    ParticipantsResponse,
    ProblemStatementInput,
    ProblemStatementPublic,
    ReportInfo,
    SubmissionCreateRequest,
    SubmissionGradeRequest,
    SubmissionPublic,
    TeamCreateRequest,
    TeamMemberPublic,
    TeamPublic,
    TeamWithMembersPublic,
)
from modules.hackathons.provisioning import ParticipantProvisioner
from modules.hackathons.repository import TeamRepository
from modules.hackathons.service import HackathonService, SubmissionService, TeamService
from modules.hackathons.tasks import enqueue_welcome_emails
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.students.repository import StudentRepository
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


def _report_response(report) -> Response:
    from urllib.parse import quote

    return Response(
        content=report.data,
        media_type=report.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(report.filename)}",
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
    participation = ParticipationService(db)
    team_public = TeamPublic.model_validate(team)
    team_public.problem_statement_title = (await participation.problem_titles_by_team([team])).get(team.id)
    report = await participation.get_report(team.id)
    return TeamWithMembersPublic(
        team=team_public,
        members=await _members_public(db, members, student.organization_id),
        report=ReportInfo(filename=report.filename, size_bytes=report.size_bytes, uploaded_at=report.updated_at)
        if report
        else None,
    )


# ---- Participant features: problem statements, report, leaderboard, achievements ----


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
                    rank=r.rank, team_name=r.team_name, score=r.score, project_title=r.project_title, members=r.members
                )
                for r in await participation.leaderboard(hackathon)
            ]
        boards.append(
            LeaderboardBoard(
                hackathon_id=hackathon.id,
                hackathon_title=hackathon.title,
                published=hackathon.leaderboard_visible,
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


@router.get("/{hackathon_id}/problem-statements/me", response_model=list[ProblemStatementPublic])
async def list_problem_statements_for_me(
    hackathon_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    await _visible_hackathon(db, hackathon_id, student)
    items = await ParticipationService(db).list_problem_statements(hackathon_id)
    return [ProblemStatementPublic.model_validate(i) for i in items]


@router.put("/{hackathon_id}/teams/me/problem-statement", response_model=TeamPublic)
async def choose_my_problem_statement(
    hackathon_id: uuid.UUID,
    payload: ChooseProblemRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    hackathon = await _visible_hackathon(db, hackathon_id, student)
    participation = ParticipationService(db)
    team = await participation.choose_problem(hackathon, student, payload.problem_statement_id)
    out = TeamPublic.model_validate(team)
    out.problem_statement_title = (await participation.problem_titles_by_team([team])).get(team.id)
    return out


@router.put("/{hackathon_id}/teams/me/report", response_model=ReportInfo)
async def upload_my_team_report(
    hackathon_id: uuid.UUID,
    file: UploadFile = File(...),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    hackathon = await _visible_hackathon(db, hackathon_id, student)
    data = await file.read(MAX_REPORT_BYTES + 1)
    report = await ParticipationService(db).save_report(hackathon, student, file.filename or "report", data)
    return ReportInfo(filename=report.filename, size_bytes=report.size_bytes, uploaded_at=report.updated_at)


@router.get("/{hackathon_id}/teams/me/report/download")
async def download_my_team_report(
    hackathon_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    hackathon = await _visible_hackathon(db, hackathon_id, student)
    _team, report = await ParticipationService(db).my_report(hackathon, student)
    if report is None:
        raise NotFoundError("Report")
    return _report_response(report)


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


@router.post(
    "/{hackathon_id}/teams/{team_id}/submissions/me",
    response_model=SubmissionPublic,
    status_code=status.HTTP_201_CREATED,
)
async def submit_my_project(
    hackathon_id: uuid.UUID,
    team_id: uuid.UUID,
    payload: SubmissionCreateRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = SubmissionService(db)
    submission = await service.submit_project(
        student.organization_id, hackathon_id, team_id, student.id, **payload.model_dump()
    )
    return SubmissionPublic.model_validate(submission)


@router.get("/{hackathon_id}/teams/{team_id}/submissions/me", response_model=SubmissionPublic | None)
async def get_my_team_submission(
    hackathon_id: uuid.UUID,
    team_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = SubmissionService(db)
    submission = await service.get_for_team(team_id)
    return SubmissionPublic.model_validate(submission) if submission else None


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
    participation = ParticipationService(db)
    reports = await participation.report_info_by_team([t.id for t in teams])
    problems = await participation.problem_titles_by_team(teams)
    out = []
    for team in teams:
        item = TeamPublic.model_validate(team)
        item.member_names = names[team.id]
        item.member_count = len(item.member_names)
        item.problem_statement_title = problems.get(team.id)
        if team.id in reports:
            item.has_report, item.report_filename = True, reports[team.id][0]
        out.append(item)
    return out


@router.get("/{hackathon_id}/teams/{team_id}/report")
async def download_team_report(
    hackathon_id: uuid.UUID,
    team_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)
    team = await TeamRepository(db).get_by_id(team_id)
    if not team or team.hackathon_id != hackathon_id:
        raise NotFoundError("Team", team_id)
    report = await ParticipationService(db).get_report(team_id)
    if report is None:
        raise NotFoundError("Report")
    return _report_response(report)


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
    item = await ParticipationService(db).add_problem_statement(hackathon_id, payload.title, payload.description)
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
        hackathon_id, statement_id, payload.title, payload.description
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
    return MessageResponse(message="Problem statement deleted.")


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


@router.get("/{hackathon_id}/submissions", response_model=list[SubmissionPublic])
async def list_submissions(
    hackathon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    service = SubmissionService(db)
    submissions = await service.list_for_hackathon(hackathon_id, organization_id)
    return [SubmissionPublic.model_validate(s) for s in submissions]


@router.post("/submissions/{submission_id}/grade", response_model=SubmissionPublic)
async def grade_submission(
    submission_id: uuid.UUID,
    payload: SubmissionGradeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SubmissionService(db)
    submission = await service.grade_submission(
        submission_id, organization_id, payload.score, payload.feedback
    )
    return SubmissionPublic.model_validate(submission)
