import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.hackathons.models import HackathonStatus
from modules.hackathons.schemas import (
    HackathonCreateRequest,
    HackathonListResponse,
    HackathonPublic,
    HackathonStatusChangeRequest,
    HackathonUpdateRequest,
    MessageResponse,
    SubmissionCreateRequest,
    SubmissionGradeRequest,
    SubmissionPublic,
    TeamCreateRequest,
    TeamMemberPublic,
    TeamPublic,
    TeamWithMembersPublic,
)
from modules.hackathons.service import HackathonService, SubmissionService, TeamService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.students.repository import StudentRepository
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


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
    return [TeamPublic.model_validate(t) for t in teams]


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
    return [TeamPublic.model_validate(t) for t in teams]


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
