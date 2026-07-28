import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.students.models import Student, StudentStatus


class StudentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _next_student_code(self, organization_id: uuid.UUID) -> str:
        result = await self.db.execute(
            select(func.count()).select_from(Student).where(Student.organization_id == organization_id)
        )
        count = result.scalar_one()
        return f"STU-{count + 1:05d}"

    async def create(self, organization_id: uuid.UUID, **fields) -> Student:
        """
        Generates the next sequential student code and retries on a rare
        concurrent-insert collision (two enrollments in the same org at
        the exact same moment), rather than trusting a single count query
        under concurrency.
        """
        last_error: Exception | None = None
        for _ in range(5):
            code = await self._next_student_code(organization_id)
            student = Student(organization_id=organization_id, student_code=code, **fields)
            self.db.add(student)
            try:
                await self.db.flush()
                await self.db.refresh(student)
                return student
            except IntegrityError as exc:
                await self.db.rollback()
                last_error = exc
                continue
        raise last_error or RuntimeError("Failed to allocate a unique student code.")

    async def get_by_id(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> Student | None:
        result = await self.db.execute(
            select(Student).where(
                Student.id == student_id,
                Student.organization_id == organization_id,
                Student.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> Student | None:
        result = await self.db.execute(
            select(Student).where(Student.user_id == user_id, Student.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_admission_id(self, admission_id: uuid.UUID) -> Student | None:
        result = await self.db.execute(select(Student).where(Student.admission_id == admission_id))
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: StudentStatus | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Student], int]:
        conditions = [Student.organization_id == organization_id, Student.deleted_at.is_(None)]
        if status is not None:
            conditions.append(Student.status == status)
        if search:
            like_pattern = f"%{search}%"
            conditions.append(
                (Student.full_name.ilike(like_pattern))
                | (Student.email.ilike(like_pattern))
                | (Student.student_code.ilike(like_pattern))
            )

        count_result = await self.db.execute(
            select(func.count()).select_from(Student).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Student)
            .where(*conditions)
            .order_by(Student.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, student: Student, **fields) -> Student:
        for key, value in fields.items():
            if value is not None:
                setattr(student, key, value)
        await self.db.flush()
        await self.db.refresh(student)
        return student

    async def set_status(
        self, student: Student, status: StudentStatus, notes: str | None = None
    ) -> Student:
        student.status = status
        if notes is not None:
            student.notes = notes
        await self.db.flush()
        await self.db.refresh(student)
        return student

    async def soft_delete(self, student: Student) -> None:
        from datetime import datetime, timezone

        student.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
