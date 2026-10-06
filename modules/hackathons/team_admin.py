"""
Organiser controls over a hackathon's teams and members.

Students form teams themselves, but on the day the organiser has to fix
things: rename a team, put someone in (or take them out of, or move them to)
another team, delete a team, and correct a participant's name or login email.
Unlike the student-facing actions these are not limited to the registration
window or the deadline; they only respect the hackathon's maximum team size.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.authentication.models import PasswordResetToken, User
from modules.authentication.repository import AuthRepository
from modules.authorization.repository import AuthorizationRepository
from modules.hackathons.models import Hackathon, Team, TeamMember
from modules.hackathons.provisioning import (
    PARTICIPANT_ROLE_SLUG,
    SET_PASSWORD_TOKEN_TTL_HOURS,
)
from modules.hackathons.repository import TeamMemberRepository, TeamRepository
from modules.students.models import Student

logger = get_logger(__name__)

# A login with any role beyond these belongs to someone else's job (staff, trainer...),
# so it can't be renamed or re-addressed from a hackathon page.
_EDITABLE_ROLE_SLUGS = {PARTICIPANT_ROLE_SLUG, "student"}
MAX_SEARCH_RESULTS = 20


@dataclass
class RosterMember:
    student_id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    joined_at: datetime
    has_logged_in: bool
    is_creator: bool


@dataclass
class RosterTeam:
    team: Team
    members: list[RosterMember] = field(default_factory=list)


@dataclass
class MemberEditResult:
    student: Student
    email_changed: bool
    # Set when a fresh set-password link should be emailed to the (new) address.
    login_link: tuple[str, str, str] | None = None  # (email, full_name, token)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TeamAdminService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.teams = TeamRepository(db)
        self.members = TeamMemberRepository(db)
        self.auth_repo = AuthRepository(db)
        self.authz_repo = AuthorizationRepository(db)

    # ---------------- reading ----------------

    async def roster(self, hackathon_id: uuid.UUID) -> list[RosterTeam]:
        """Every team with its members' contact details and whether they have signed in."""
        teams = await self.teams.list_for_hackathon(hackathon_id)
        by_team = {t.id: RosterTeam(team=t) for t in teams}
        if not by_team:
            return []
        rows = (
            await self.db.execute(
                select(TeamMember, Student, User.last_login_at)
                .join(Student, Student.id == TeamMember.student_id)
                .outerjoin(User, User.id == Student.user_id)
                .where(TeamMember.team_id.in_(list(by_team)))
                .order_by(TeamMember.joined_at)
            )
        ).all()
        for member, student, last_login in rows:
            by_team[member.team_id].members.append(
                RosterMember(
                    student_id=student.id,
                    full_name=student.full_name,
                    email=student.email,
                    phone=student.phone,
                    joined_at=member.joined_at,
                    has_logged_in=last_login is not None,
                    is_creator=student.id == by_team[member.team_id].team.created_by_student_id,
                )
            )
        return list(by_team.values())

    async def candidates(self, organization_id: uuid.UUID, hackathon_id: uuid.UUID, query: str) -> list[Student]:
        """Students with a login who are not in any team of this hackathon yet (matching name, email or code)."""
        in_a_team = (
            select(TeamMember.student_id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(Team.hackathon_id == hackathon_id)
        )
        stmt = select(Student).where(
            Student.organization_id == organization_id,
            Student.deleted_at.is_(None),
            Student.user_id.is_not(None),
            Student.id.not_in(in_a_team),
        )
        text = query.strip()
        if text:
            like = f"%{text.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Student.full_name).like(like),
                    func.lower(Student.email).like(like),
                    func.lower(Student.student_code).like(like),
                )
            )
        stmt = stmt.order_by(Student.full_name).limit(MAX_SEARCH_RESULTS)
        return list((await self.db.execute(stmt)).scalars().all())

    # ---------------- helpers ----------------

    async def _team(self, hackathon_id: uuid.UUID, team_id: uuid.UUID, lock: bool = False) -> Team:
        team = await (self.teams.get_by_id_for_update(team_id) if lock else self.teams.get_by_id(team_id))
        if team is None or team.hackathon_id != hackathon_id:
            raise NotFoundError("Team", team_id)
        return team

    async def _student(self, organization_id: uuid.UUID, student_id: uuid.UUID) -> Student:
        student = (
            await self.db.execute(
                select(Student).where(
                    Student.id == student_id,
                    Student.organization_id == organization_id,
                    Student.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if student is None:
            raise NotFoundError("Student", student_id)
        return student

    async def _current_team(self, hackathon_id: uuid.UUID, student_id: uuid.UUID) -> Team | None:
        return await self.teams.get_for_student_in_hackathon(hackathon_id, student_id)

    async def _assert_room(self, hackathon: Hackathon, team_id: uuid.UUID) -> None:
        if await self.members.count_for_team(team_id) >= hackathon.max_team_size:
            raise ValidationError(
                f"This team already has {hackathon.max_team_size} members, the most this hackathon allows. "
                "Raise the maximum team size under Edit if you need a bigger team."
            )

    async def _addable_student(
        self, organization_id: uuid.UUID, hackathon_id: uuid.UUID, student_id: uuid.UUID
    ) -> Student:
        student = await self._student(organization_id, student_id)
        if student.user_id is None:
            raise ValidationError(f"{student.full_name} has no login yet. Add them as a new person with their email.")
        existing = await self._current_team(hackathon_id, student.id)
        if existing is not None:
            raise ConflictError(f'{student.full_name} is already in team "{existing.name}". Move them instead.')
        return student

    # ---------------- teams ----------------

    async def create_team(
        self,
        organization_id: uuid.UUID,
        hackathon: Hackathon,
        name: str,
        student_ids: list[uuid.UUID],
    ) -> Team:
        """A team made by the organiser. It needs at least one member (its first becomes the creator)."""
        clean = " ".join(name.split())
        if not clean:
            raise ValidationError("Give the team a name.")
        ids = list(dict.fromkeys(student_ids))
        if not ids:
            raise ValidationError("Pick at least one member for the new team.")
        if len(ids) > hackathon.max_team_size:
            raise ValidationError(f"A team can have at most {hackathon.max_team_size} members.")
        students = [await self._addable_student(organization_id, hackathon.id, sid) for sid in ids]
        try:
            async with self.db.begin_nested():
                team = await self.teams.create(
                    hackathon_id=hackathon.id, created_by_student_id=students[0].id, name=clean
                )
        except IntegrityError:
            raise ConflictError(f'A team named "{clean}" already exists.') from None
        for student in students:
            await self.members.create(team_id=team.id, student_id=student.id, joined_at=_now())
        logger.info("hackathon_team_created_by_staff", team_id=str(team.id), hackathon_id=str(hackathon.id))
        return team

    async def rename_team(self, hackathon_id: uuid.UUID, team_id: uuid.UUID, name: str) -> Team:
        clean = " ".join(name.split())
        if not clean:
            raise ValidationError("Give the team a name.")
        team = await self._team(hackathon_id, team_id, lock=True)
        if team.name == clean:
            return team
        try:
            async with self.db.begin_nested():
                team.name = clean
                await self.db.flush()
        except IntegrityError:
            raise ConflictError(f'A team named "{clean}" already exists.') from None
        return team

    async def delete_team(self, hackathon_id: uuid.UUID, team_id: uuid.UUID) -> None:
        """Remove a team with its members' places and its task submissions (their logins stay)."""
        team = await self._team(hackathon_id, team_id, lock=True)
        await self.db.delete(team)
        await self.db.flush()
        logger.info("hackathon_team_deleted", team_id=str(team_id), hackathon_id=str(hackathon_id))

    # ---------------- members ----------------

    async def add_member(
        self, organization_id: uuid.UUID, hackathon: Hackathon, team_id: uuid.UUID, student_id: uuid.UUID
    ) -> Student:
        team = await self._team(hackathon.id, team_id, lock=True)
        student = await self._addable_student(organization_id, hackathon.id, student_id)
        await self._assert_room(hackathon, team.id)
        await self.members.create(team_id=team.id, student_id=student.id, joined_at=_now())
        return student

    async def remove_member(self, hackathon_id: uuid.UUID, team_id: uuid.UUID, student_id: uuid.UUID) -> None:
        await self._team(hackathon_id, team_id, lock=True)
        member = await self.members.get(team_id, student_id)
        if member is None:
            raise NotFoundError("Team member", student_id)
        await self.db.delete(member)
        await self.db.flush()

    async def move_member(
        self, hackathon: Hackathon, student_id: uuid.UUID, to_team_id: uuid.UUID
    ) -> Team:
        target = await self._team(hackathon.id, to_team_id, lock=True)
        current = await self._current_team(hackathon.id, student_id)
        if current is None:
            raise NotFoundError("Team member", student_id)
        if current.id == target.id:
            raise ValidationError("They are already in that team.")
        await self._assert_room(hackathon, target.id)
        member = await self.members.get(current.id, student_id)
        assert member is not None
        member.team_id = target.id
        await self.db.flush()
        return target

    async def update_member(
        self,
        organization_id: uuid.UUID,
        hackathon_id: uuid.UUID,
        student_id: uuid.UUID,
        full_name: str | None,
        email: str | None,
        phone: str | None,
        send_login_link: bool,
        phone_given: bool,
    ) -> MemberEditResult:
        """Correct a participant's name, phone or login email. Changing the email moves the
        login to the new address (the old address stops working), signs the person out
        everywhere, cancels any unused set-password links, and (by default) emails a
        fresh one to the new address."""
        student = await self._student(organization_id, student_id)
        if await self._current_team(hackathon_id, student_id) is None:
            raise NotFoundError("Team member", student_id)
        user = await self.auth_repo.get_user_by_id(student.user_id) if student.user_id else None
        if user is not None:
            if user.is_superuser:
                raise ValidationError("This is an administrator's account. Change it from Users.")
            slugs = {r.slug for r in await self.authz_repo.get_roles_for_user(user.id)}
            if slugs - _EDITABLE_ROLE_SLUGS:
                raise ValidationError("This account has staff or trainer access, so change it from Users.")

        if full_name is not None:
            name = " ".join(full_name.split())
            if not name:
                raise ValidationError("The name can't be empty.")
            student.full_name = name
            if user is not None:
                user.full_name = name
        if phone_given:
            student.phone = (phone or "").strip() or None
            if user is not None:
                user.phone_number = student.phone

        new_email = email.strip().lower() if email else None
        changed = new_email is not None and new_email != (user.email if user is not None else (student.email or "").lower())
        login_link: tuple[str, str, str] | None = None
        if changed and new_email is not None:
            clash = await self.auth_repo.get_user_by_email(new_email)
            if clash is not None and (user is None or clash.id != user.id):
                raise ConflictError("Another account already uses that email address.")
            student.email = new_email
            if user is not None:
                user.email = new_email
                user.is_email_verified = True  # the organiser vouches for the new address
                await self.auth_repo.revoke_all_refresh_tokens_for_user(user.id)
                await self.db.execute(
                    update(PasswordResetToken)
                    .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
                    .values(used_at=_now())
                )
        await self.db.flush()
        if changed and send_login_link and user is not None and new_email is not None:
            token = await self.auth_repo.create_password_reset_token(user.id, ttl_hours=SET_PASSWORD_TOKEN_TTL_HOURS)
            login_link = (new_email, student.full_name, token.token)
        return MemberEditResult(student=student, email_changed=changed, login_link=login_link)

    async def new_login_link(
        self, organization_id: uuid.UUID, hackathon_id: uuid.UUID, student_id: uuid.UUID
    ) -> tuple[str, str, str]:
        """A fresh set-password link for someone who lost (or never got) the first email."""
        student = await self._student(organization_id, student_id)
        if await self._current_team(hackathon_id, student_id) is None:
            raise NotFoundError("Team member", student_id)
        if student.user_id is None or not student.email:
            raise ValidationError("This person has no login to send a link for.")
        token = await self.auth_repo.create_password_reset_token(
            student.user_id, ttl_hours=SET_PASSWORD_TOKEN_TTL_HOURS
        )
        return student.email, student.full_name, token.token
