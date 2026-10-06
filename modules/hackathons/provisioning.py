"""
Bulk account creation for hackathon participants.

A hackathon's student-facing side (create/join a team, submit a project)
runs on Student records that are linked to a login, so before an event
the organiser needs ~40-200 of them at once. This creates, for every
pasted "name, email" row: a Student, a User (email pre-verified, the
unguessable placeholder password is never revealed -- the student sets
their own through the emailed link), the profile, and the `student` role.

Each row runs in its own savepoint so one bad row (an email that already
belongs to staff, a database hiccup) is reported and skipped instead of
discarding the rows that worked. Emails are queued by the caller *after*
the commit, so a link is never sent for a row that was rolled back.
"""

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.core.logging_config import get_logger
from app.core.security import hash_password
from modules.authentication.models import UserStatus
from modules.authentication.repository import AuthRepository
from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.hackathons.models import Hackathon
from modules.students.models import Student
from modules.students.repository import StudentRepository
from modules.users.repository import UserProfileRepository

logger = get_logger(__name__)

# Long enough for a student who opens the email a day or two later.
SET_PASSWORD_TOKEN_TTL_HOURS = 72
MAX_ROWS_PER_REQUEST = 300
# Participants get the restricted role, not the full course-student one.
PARTICIPANT_ROLE_SLUG = "hackathon_participant"


@dataclass
class ProvisionedLogin:
    user_id: uuid.UUID
    email: str
    full_name: str
    reset_token: str


@dataclass
class ProvisionResult:
    created: list[ProvisionedLogin] = field(default_factory=list)
    resent: list[ProvisionedLogin] = field(default_factory=list)
    already_ready: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)  # (email, reason)


class ParticipantProvisioner:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_repo = AuthRepository(db)
        self.student_repo = StudentRepository(db)
        self.profile_repo = UserProfileRepository(db)
        self.authz_repo = AuthorizationRepository(db)

    async def _find_unlinked_student(self, organization_id: uuid.UUID, email: str) -> Student | None:
        return (
            await self.db.execute(
                select(Student).where(
                    Student.organization_id == organization_id,
                    func.lower(Student.email) == email,
                    Student.deleted_at.is_(None),
                    Student.user_id.is_(None),
                )
            )
        ).scalars().first()

    async def provision(
        self,
        organization_id: uuid.UUID,
        hackathon: Hackathon,
        rows: list[tuple[str, str, str | None]],
        created_by_user_id: uuid.UUID,
        resend_to_existing: bool = False,
    ) -> ProvisionResult:
        if len(rows) > MAX_ROWS_PER_REQUEST:
            raise ValidationError(f"Add at most {MAX_ROWS_PER_REQUEST} participants at a time.")
        student_role = await self.authz_repo.get_role_by_slug(PARTICIPANT_ROLE_SLUG)
        if not student_role:
            raise ValidationError(
                f"The '{PARTICIPANT_ROLE_SLUG}' system role is not seeded on this ERPX instance. "
                "Run apps/api/scripts/seed.py (seed_default_rbac) first."
            )

        # One placeholder password hash shared by the batch: bcrypt costs
        # ~0.25 s a call, which 200 times in one request would stall the
        # event loop for most of a minute. Nobody knows the secret it was
        # made from, and every account sets its own password before use.
        placeholder_hash = hash_password(secrets.token_urlsafe(32))
        authz = AuthorizationService(self.db)
        result = ProvisionResult()
        seen: set[str] = set()

        for raw_name, raw_email, phone in rows:
            email = raw_email.strip().lower()
            name = " ".join(raw_name.split())
            if email in seen:
                continue
            seen.add(email)
            try:
                async with self.db.begin_nested():
                    login = await self._provision_one(
                        organization_id, hackathon, name, email, phone, placeholder_hash,
                        student_role.id, authz, created_by_user_id, result, resend_to_existing,
                    )
                if login is not None:
                    result.created.append(login)
            except _RowError as exc:
                result.errors.append((email, str(exc)))
            except IntegrityError:
                result.errors.append((email, "Could not be saved (it may have just been added elsewhere)."))
            except Exception:  # noqa: BLE001 - one bad row must not sink the batch
                logger.exception("hackathon_participant_row_failed", email=email)
                result.errors.append((email, "Something went wrong creating this account."))
        return result

    async def _provision_one(
        self,
        organization_id: uuid.UUID,
        hackathon: Hackathon,
        name: str,
        email: str,
        phone: str | None,
        placeholder_hash: str,
        student_role_id: uuid.UUID,
        authz: AuthorizationService,
        created_by_user_id: uuid.UUID,
        result: ProvisionResult,
        resend_to_existing: bool,
    ) -> ProvisionedLogin | None:
        existing_user = await self.auth_repo.get_user_by_email(email)
        if existing_user is not None:
            linked = await self.student_repo.get_by_user_id(existing_user.id)
            if linked is not None and linked.organization_id == organization_id:
                if resend_to_existing:
                    # A fresh link for someone who lost the first email.
                    token = await self.auth_repo.create_password_reset_token(
                        existing_user.id, ttl_hours=SET_PASSWORD_TOKEN_TTL_HOURS
                    )
                    result.resent.append(
                        ProvisionedLogin(existing_user.id, email, linked.full_name, token.token)
                    )
                else:
                    result.already_ready.append(email)
                return None
            raise _RowError("An ERPX account already exists for this email and it isn't a student account.")

        student = await self._find_unlinked_student(organization_id, email)
        if student is None:
            student = Student(
                organization_id=organization_id,
                student_code=await self.student_repo._next_student_code(organization_id),
                full_name=name,
                email=email,
                phone=phone,
                course_name=hackathon.title[:255],
                enrollment_date=date.today(),
            )
            self.db.add(student)
            await self.db.flush()

        user = await self.auth_repo.create_user(
            email=email, hashed_password=placeholder_hash, full_name=student.full_name, phone_number=student.phone
        )
        # An admin is vouching for this address; the account only becomes
        # usable once the student follows the set-password link.
        user.is_email_verified = True
        user.status = UserStatus.ACTIVE
        await self.db.flush()
        await self.profile_repo.create(user_id=user.id, organization_id=organization_id)
        await authz.assign_role(user.id, student_role_id, organization_id, assigned_by_user_id=created_by_user_id)
        student.user_id = user.id
        await self.db.flush()

        token = await self.auth_repo.create_password_reset_token(user.id, ttl_hours=SET_PASSWORD_TOKEN_TTL_HOURS)
        return ProvisionedLogin(user_id=user.id, email=email, full_name=student.full_name, reset_token=token.token)


class _RowError(Exception):
    """A row that can't be created, with a message safe to show the admin."""
