"""
The organiser's view of everyone invited to a hackathon: who they are, whether they have
signed in, which team they are in, and ways to remove or delete them.

"Invited" is recorded in `hackathon_participants` when a participant is bulk-added (or added
through a team). Anyone who is in one of the hackathon's teams also counts, so the list never
misses a team member.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.authentication.models import User, UserStatus
from modules.authentication.repository import AuthRepository
from modules.authorization.models import Role, UserRole
from modules.hackathons.models import HackathonParticipant, Team, TeamMember
from modules.hackathons.provisioning import PARTICIPANT_ROLE_SLUG, SET_PASSWORD_TOKEN_TTL_HOURS
from modules.students.models import Student

logger = get_logger(__name__)

MAX_LINKS_PER_REQUEST = 300


@dataclass
class ParticipantRow:
    student_id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    student_code: str
    invited_at: datetime | None
    has_logged_in: bool
    last_login_at: datetime | None
    team_id: uuid.UUID | None
    team_name: str | None
    is_creator: bool
    # Only accounts that exist purely for hackathons can be deleted outright;
    # anyone with other access (a course student, staff...) can only be taken out of the hackathon.
    can_delete_account: bool


async def record_participant(
    db: AsyncSession, hackathon_id: uuid.UUID, student_id: uuid.UUID, invited_by: uuid.UUID | None
) -> None:
    """Note that this student was invited to the hackathon (once)."""
    await db.execute(
        pg_insert(HackathonParticipant)
        .values(hackathon_id=hackathon_id, student_id=student_id, invited_by_user_id=invited_by)
        .on_conflict_do_nothing(constraint="uq_hackathon_participant")
    )


class ParticipantAdminService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_repo = AuthRepository(db)

    # ---------------- reading ----------------

    async def _ids(self, hackathon_id: uuid.UUID) -> set[uuid.UUID]:
        invited = (
            await self.db.execute(
                select(HackathonParticipant.student_id).where(HackathonParticipant.hackathon_id == hackathon_id)
            )
        ).scalars().all()
        in_teams = (
            await self.db.execute(
                select(TeamMember.student_id)
                .join(Team, Team.id == TeamMember.team_id)
                .where(Team.hackathon_id == hackathon_id)
            )
        ).scalars().all()
        return set(invited) | set(in_teams)

    async def is_participant(self, hackathon_id: uuid.UUID, student_id: uuid.UUID) -> bool:
        return student_id in await self._ids(hackathon_id)

    async def participants(self, organization_id: uuid.UUID, hackathon_id: uuid.UUID) -> list[ParticipantRow]:
        ids = await self._ids(hackathon_id)
        if not ids:
            return []
        rows = (
            await self.db.execute(
                select(Student, User, HackathonParticipant.created_at, Team.id, Team.name, Team.created_by_student_id)
                .outerjoin(User, User.id == Student.user_id)
                .outerjoin(
                    HackathonParticipant,
                    (HackathonParticipant.student_id == Student.id)
                    & (HackathonParticipant.hackathon_id == hackathon_id),
                )
                .outerjoin(TeamMember, TeamMember.student_id == Student.id)
                .outerjoin(Team, (Team.id == TeamMember.team_id) & (Team.hackathon_id == hackathon_id))
                .where(
                    Student.id.in_(ids),
                    Student.organization_id == organization_id,
                    Student.deleted_at.is_(None),
                )
                .order_by(Student.full_name)
            )
        ).all()
        # An outer join through TeamMember repeats a person once per team they are in (across hackathons);
        # keep only the row for this hackathon's team if there is one.
        best: dict[uuid.UUID, tuple] = {}
        for row in rows:
            student = row[0]
            if student.id not in best or (row[3] is not None and best[student.id][3] is None):
                best[student.id] = row
        deletable = await self._deletable_user_ids([r[1].id for r in best.values() if r[1] is not None])
        out = []
        for student, user, invited_at, team_id, team_name, creator_id in best.values():
            out.append(
                ParticipantRow(
                    student_id=student.id,
                    full_name=student.full_name,
                    email=student.email,
                    phone=student.phone,
                    student_code=student.student_code,
                    invited_at=invited_at,
                    has_logged_in=user is not None and user.last_login_at is not None,
                    last_login_at=user.last_login_at if user is not None else None,
                    team_id=team_id,
                    team_name=team_name,
                    is_creator=team_id is not None and creator_id == student.id,
                    can_delete_account=user is not None and user.id in deletable,
                )
            )
        return out

    async def _deletable_user_ids(self, user_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        """Users whose only role is the hackathon participant one (and who aren't administrators)."""
        if not user_ids:
            return set()
        slugs: dict[uuid.UUID, set[str]] = {uid: set() for uid in user_ids}
        for uid, slug in (
            await self.db.execute(
                select(UserRole.user_id, Role.slug).join(Role, Role.id == UserRole.role_id).where(UserRole.user_id.in_(user_ids))
            )
        ).all():
            slugs[uid].add(slug)
        supers = set(
            (await self.db.execute(select(User.id).where(User.id.in_(user_ids), User.is_superuser.is_(True)))).scalars().all()
        )
        return {uid for uid, s in slugs.items() if s == {PARTICIPANT_ROLE_SLUG} and uid not in supers}

    # ---------------- removing and deleting ----------------

    async def _student(self, organization_id: uuid.UUID, hackathon_id: uuid.UUID, student_id: uuid.UUID) -> Student:
        student = (
            await self.db.execute(
                select(Student).where(
                    Student.id == student_id, Student.organization_id == organization_id, Student.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if student is None or not await self.is_participant(hackathon_id, student_id):
            raise NotFoundError("Participant", student_id)
        return student

    async def remove_from_hackathon(
        self, organization_id: uuid.UUID, hackathon_id: uuid.UUID, student_id: uuid.UUID
    ) -> Student:
        """Take them out of this hackathon: out of their team and off the list. The login is kept."""
        student = await self._student(organization_id, hackathon_id, student_id)
        team_ids = select(Team.id).where(Team.hackathon_id == hackathon_id)
        await self.db.execute(
            delete(TeamMember).where(TeamMember.student_id == student_id, TeamMember.team_id.in_(team_ids))
        )
        await self.db.execute(
            delete(HackathonParticipant).where(
                HackathonParticipant.student_id == student_id, HackathonParticipant.hackathon_id == hackathon_id
            )
        )
        await self.db.flush()
        return student

    async def delete_account(
        self, organization_id: uuid.UUID, hackathon_id: uuid.UUID, student_id: uuid.UUID
    ) -> Student:
        """Delete the person's ERPX account: they can no longer sign in, they leave every hackathon, and
        their email address becomes free to invite again. Only for accounts that exist just for hackathons."""
        student = await self._student(organization_id, hackathon_id, student_id)
        user = await self.auth_repo.get_user_by_id(student.user_id) if student.user_id else None
        if user is not None and user.id not in await self._deletable_user_ids([user.id]):
            raise ValidationError(
                f"{student.full_name} has other access in ERPX (not only a hackathon login), "
                "so remove them from the hackathon instead, or delete the account from Students / Users."
            )
        now = datetime.now(timezone.utc)
        await self.db.execute(delete(TeamMember).where(TeamMember.student_id == student_id))
        await self.db.execute(delete(HackathonParticipant).where(HackathonParticipant.student_id == student_id))
        if user is not None:
            await self.auth_repo.revoke_all_refresh_tokens_for_user(user.id)
            user.status = UserStatus.DEACTIVATED
            user.deleted_at = now
            # The email column is unique even for deleted rows; rename it so the address can be used again.
            user.email = f"deleted-{secrets.token_hex(4)}.{user.email}"[:255]
        student.deleted_at = now
        await self.db.flush()
        logger.info("hackathon_participant_deleted", student_id=str(student_id), hackathon_id=str(hackathon_id))
        return student

    # ---------------- login links ----------------

    async def login_links(
        self, organization_id: uuid.UUID, hackathon_id: uuid.UUID, student_ids: list[uuid.UUID] | None
    ) -> list[tuple[str, str, str]]:
        """Fresh set-password links as (email, name, token): for the given people, or, with no list,
        for everyone who hasn't signed in yet."""
        people = await self.participants(organization_id, hackathon_id)
        wanted = set(student_ids) if student_ids is not None else None
        targets = [
            p
            for p in people
            if p.email and (p.student_id in wanted if wanted is not None else not p.has_logged_in)
        ]
        if len(targets) > MAX_LINKS_PER_REQUEST:
            raise ValidationError(f"Send at most {MAX_LINKS_PER_REQUEST} links at a time.")
        users = {
            s.id: s.user_id
            for s in (
                await self.db.execute(select(Student).where(Student.id.in_([p.student_id for p in targets])))
            ).scalars()
        }
        jobs: list[tuple[str, str, str]] = []
        for p in targets:
            user_id = users.get(p.student_id)
            if user_id is None or p.email is None:
                continue
            token = await self.auth_repo.create_password_reset_token(user_id, ttl_hours=SET_PASSWORD_TOKEN_TTL_HOURS)
            jobs.append((p.email, p.full_name, token.token))
        return jobs
