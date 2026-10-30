"""
Who may work on an internship: people holding the organization-wide Our Internships permissions, and instructors.

An instructor is a trainer an administrator has assigned to one internship for a period (see ``InternshipInstructor``).
While the period lasts they can do everything on that internship and on the exams that belong to it -- view, add, edit,
validate, mark, release -- except delete: every DELETE request is refused to them, so nothing can be removed, whatever the
screen. Outside the period, or on any other internship, they get nothing, and the internship is missing from their list.

Two dependencies carry this: ``internship_access`` for the internship's own endpoints and ``exam_access`` for the workshop
exam endpoints (an internship's exams, and its certificate exams, are workshop exams).
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.repository import AuthorizationRepository
from modules.employees.models import Employee
from modules.employees.repository import EmployeeRepository
from modules.our_internships.instructor_models import InternshipInstructor
from modules.our_internships.models import OurInternship
from modules.trainers.models import Trainer
from modules.workshop_exams.models import WorkshopExam

Level = Literal["view", "manage"]

NO_DELETE = "Instructors cannot delete anything. Ask an administrator."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def window_status(access_from: datetime | None, access_until: datetime | None, now: datetime | None = None) -> str:
    """upcoming (not started), active, or expired (ended)."""
    now = now or _now()
    if access_from is not None and now < access_from:
        return "upcoming"
    if access_until is not None and now > access_until:
        return "expired"
    return "active"


def _active_clause(now: datetime):
    return (
        or_(InternshipInstructor.access_from.is_(None), InternshipInstructor.access_from <= now),
        or_(InternshipInstructor.access_until.is_(None), InternshipInstructor.access_until >= now),
    )


class InstructorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- who the caller is ----------------

    async def trainer_of(self, user: User) -> Trainer | None:
        """The active trainer profile behind a login, if there is one."""
        employee = await EmployeeRepository(self.db).get_by_user_id(user.id)
        if employee is None:
            return None
        return (
            await self.db.execute(
                select(Trainer).where(
                    Trainer.employee_id == employee.id,
                    Trainer.organization_id == employee.organization_id,
                    Trainer.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    async def has_global(self, user: User, level: Level) -> bool:
        if user.is_superuser:
            return True
        codes = await AuthorizationRepository(self.db).get_permission_codes_for_user(user.id)
        return f"our_internships.{level}" in codes

    async def active_assignments(self, user: User) -> list[InternshipInstructor]:
        trainer = await self.trainer_of(user)
        if trainer is None:
            return []
        rows = await self.db.execute(
            select(InternshipInstructor).where(InternshipInstructor.trainer_id == trainer.id, *_active_clause(_now()))
        )
        return list(rows.scalars().all())

    async def active_internship_ids(self, user: User) -> set[uuid.UUID]:
        return {a.internship_id for a in await self.active_assignments(user)}

    async def is_instructor(self, user: User) -> bool:
        return bool(await self.active_assignments(user))

    async def assignment_for(self, user: User, internship_id: uuid.UUID) -> InternshipInstructor | None:
        return next((a for a in await self.active_assignments(user) if a.internship_id == internship_id), None)

    async def restricted_ids(self, user: User) -> set[uuid.UUID] | None:
        """None for someone who may see every internship; otherwise the ones they instruct right now."""
        if await self.has_global(user, "view"):
            return None
        return await self.active_internship_ids(user)

    # ---------------- managing assignments (administrators) ----------------

    async def _get(self, internship_id: uuid.UUID, instructor_id: uuid.UUID) -> InternshipInstructor:
        row = (
            await self.db.execute(
                select(InternshipInstructor).where(
                    InternshipInstructor.id == instructor_id, InternshipInstructor.internship_id == internship_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Instructor", instructor_id)
        return row

    async def listing(self, internship: OurInternship) -> list[dict]:
        rows = await self.db.execute(
            select(InternshipInstructor, Trainer, Employee)
            .join(Trainer, Trainer.id == InternshipInstructor.trainer_id)
            .join(Employee, Employee.id == Trainer.employee_id)
            .where(InternshipInstructor.internship_id == internship.id)
            .order_by(Employee.full_name)
        )
        return [self.out(i, e) for i, _, e in rows.all()]

    @staticmethod
    def out(instructor: InternshipInstructor, employee: Employee) -> dict:
        return {
            "id": instructor.id,
            "trainer_id": instructor.trainer_id,
            "name": employee.full_name,
            "email": employee.email,
            "access_from": instructor.access_from,
            "access_until": instructor.access_until,
            "status": window_status(instructor.access_from, instructor.access_until),
            "note": instructor.note,
            "created_at": instructor.created_at,
        }

    async def options(self, internship: OurInternship) -> list[dict]:
        """Active trainers with a login who are not assigned to this internship yet."""
        assigned = select(InternshipInstructor.trainer_id).where(InternshipInstructor.internship_id == internship.id)
        rows = await self.db.execute(
            select(Trainer, Employee)
            .join(Employee, Employee.id == Trainer.employee_id)
            .where(
                Trainer.organization_id == internship.organization_id,
                Trainer.is_active.is_(True),
                Employee.deleted_at.is_(None),
                Employee.user_id.is_not(None),
                Trainer.id.not_in(assigned),
            )
            .order_by(Employee.full_name)
        )
        return [{"trainer_id": t.id, "name": e.full_name, "email": e.email} for t, e in rows.all()]

    @staticmethod
    def _check_window(access_from: datetime | None, access_until: datetime | None) -> None:
        if access_from and access_until and access_until <= access_from:
            raise ValidationError("The access must end after it starts.")

    async def add(
        self,
        internship: OurInternship,
        trainer_id: uuid.UUID,
        access_from: datetime | None,
        access_until: datetime | None,
        note: str | None,
        user_id: uuid.UUID,
    ) -> dict:
        self._check_window(access_from, access_until)
        row = (
            await self.db.execute(
                select(Trainer, Employee)
                .join(Employee, Employee.id == Trainer.employee_id)
                .where(Trainer.id == trainer_id, Trainer.organization_id == internship.organization_id)
            )
        ).first()
        if row is None or not row[0].is_active:
            raise NotFoundError("Trainer", trainer_id)
        trainer, employee = row
        if employee.user_id is None:
            raise ValidationError("This trainer has no login yet, so they cannot be given access.")
        taken = (
            await self.db.execute(
                select(InternshipInstructor.id).where(
                    InternshipInstructor.internship_id == internship.id, InternshipInstructor.trainer_id == trainer.id
                )
            )
        ).first()
        if taken:
            raise ConflictError("That trainer is already an instructor on this internship. Change their dates instead.")
        instructor = InternshipInstructor(
            organization_id=internship.organization_id,
            internship_id=internship.id,
            trainer_id=trainer.id,
            access_from=access_from,
            access_until=access_until,
            note=(note or "").strip() or None,
            granted_by_user_id=user_id,
        )
        self.db.add(instructor)
        await self.db.flush()
        return self.out(instructor, employee)

    async def update(self, internship: OurInternship, instructor_id: uuid.UUID, fields: dict) -> dict:
        instructor = await self._get(internship.id, instructor_id)
        start = fields.get("access_from", instructor.access_from)
        end = fields.get("access_until", instructor.access_until)
        self._check_window(start, end)
        for key in ("access_from", "access_until"):
            if key in fields:
                setattr(instructor, key, fields[key])
        if "note" in fields:
            instructor.note = (fields["note"] or "").strip() or None
        await self.db.flush()
        employee = (
            await self.db.execute(
                select(Employee).join(Trainer, Trainer.employee_id == Employee.id).where(Trainer.id == instructor.trainer_id)
            )
        ).scalar_one()
        return self.out(instructor, employee)

    async def remove(self, internship: OurInternship, instructor_id: uuid.UUID) -> None:
        await self.db.delete(await self._get(internship.id, instructor_id))
        await self.db.flush()

    async def assigned_to(self, user: User) -> list[dict]:
        """The internships a trainer instructs right now, with when their access ends (for their own portal)."""
        assignments = {a.internship_id: a for a in await self.active_assignments(user)}
        if not assignments:
            return []
        rows = await self.db.execute(select(OurInternship).where(OurInternship.id.in_(list(assignments))).order_by(OurInternship.title))
        return [
            {
                "id": i.id,
                "title": i.title,
                "description": i.description,
                "status": i.status.value,
                "access_from": assignments[i.id].access_from,
                "access_until": assignments[i.id].access_until,
            }
            for i in rows.scalars().all()
        ]


def _path_uuid(request: Request, name: str) -> uuid.UUID | None:
    raw = request.path_params.get(name)
    try:
        return uuid.UUID(str(raw)) if raw is not None else None
    except ValueError:
        return None


def internship_access(level: Level):
    """Allow the organization-wide permission (``our_internships.view`` / ``.manage``), or an instructor of the internship in
    the path. Without an internship in the path (the list, creating one) only the list is open to instructors, and only
    to see their own. Instructors are refused every DELETE."""

    async def dependency(
        request: Request,
        user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        service = InstructorService(db)
        if await service.has_global(user, level):
            return user
        internship_id = _path_uuid(request, "internship_id")
        if internship_id is None:
            # the internship list: instructors may open it (it shows only their own); nothing else without an internship
            if level == "view" and request.method == "GET" and await service.is_instructor(user):
                return user
            raise AuthorizationError(f"This action requires the permission: our_internships.{level}")
        if request.method == "DELETE" and await service.assignment_for(user, internship_id):
            raise AuthorizationError(NO_DELETE)
        if await service.assignment_for(user, internship_id) is None:
            raise AuthorizationError(f"This action requires the permission: our_internships.{level}")
        return user

    return dependency


def exam_access(level: Level):
    """Allow the workshops permission, or an instructor of the internship the exam belongs to. Instructors are refused
    every DELETE. Without an exam in the path only the workshops permission opens it."""

    async def dependency(
        request: Request,
        user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        await assert_exam_access(db, user, _path_uuid(request, "exam_id"), level, deleting=request.method == "DELETE")
        return user

    return dependency


async def assert_exam_access(
    db: AsyncSession, user: User, exam_id: uuid.UUID | None, level: Level, *, deleting: bool = False
) -> None:
    """The rule behind ``exam_access``, for callers that are not an exam endpoint (bulk downloads)."""
    if user.is_superuser:
        return
    permission = f"workshops.{level}"
    codes = await AuthorizationRepository(db).get_permission_codes_for_user(user.id)
    if permission in codes:
        return
    internship_id = None
    if exam_id is not None:
        internship_id = (await db.execute(select(WorkshopExam.internship_id).where(WorkshopExam.id == exam_id))).scalar_one_or_none()
    assignment = await InstructorService(db).assignment_for(user, internship_id) if internship_id else None
    if assignment is None:
        raise AuthorizationError(f"This action requires the following permission(s): {permission}")
    if deleting:
        raise AuthorizationError(NO_DELETE)


async def assert_internship_access(db: AsyncSession, user: User, internship_id: uuid.UUID, level: Level) -> None:
    """The rule behind ``internship_access`` for one internship, for callers that are not an internship endpoint."""
    service = InstructorService(db)
    if await service.has_global(user, level):
        return
    if await service.assignment_for(user, internship_id) is None:
        raise AuthorizationError(f"This action requires the permission: our_internships.{level}")


async def assert_can_create_exam(user: User, db: AsyncSession, internship_id: uuid.UUID | None) -> None:
    """Creating an exam needs the workshops permission, or being an instructor of the internship it is created for."""
    if user.is_superuser:
        return
    codes = await AuthorizationRepository(db).get_permission_codes_for_user(user.id)
    if "workshops.manage" in codes:
        return
    if internship_id is not None and await InstructorService(db).assignment_for(user, internship_id):
        return
    raise AuthorizationError("This action requires the following permission(s): workshops.manage")
