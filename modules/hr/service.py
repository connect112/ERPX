import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.authorization.repository import AuthorizationRepository
from modules.hr.models import Department, Designation
from modules.hr.repository import DepartmentRepository, DesignationRepository

logger = get_logger(__name__)

# Deliberately excluded from what a designation's linked_role_id can point
# at: "student" makes no sense for an employee, and auto-granting
# "super_admin" to every future employee who happens to get this job
# title is a real footgun a UUID typo or a copy-pasted designation could
# trigger silently — that grant should stay an explicit, individual
# decision on the Roles page, not something a designation can hand out in
# bulk. "administrator"/"staff"/any future custom role are unaffected.
_DESIGNATION_LINKABLE_ROLE_BLOCKLIST = {"student", "super_admin"}


class DepartmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DepartmentRepository(db)

    async def create_department(self, organization_id: uuid.UUID, code: str, **fields) -> Department:
        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"A department with code '{code}' already exists.")
        if fields.get("parent_department_id") is not None:
            parent = await self.repo.get_by_id(fields["parent_department_id"], organization_id)
            if not parent:
                raise NotFoundError("Parent department", fields["parent_department_id"])
        department = await self.repo.create(organization_id=organization_id, code=code, **fields)
        logger.info("department_created", department_id=str(department.id))
        return department

    async def get_department(self, department_id: uuid.UUID, organization_id: uuid.UUID) -> Department:
        department = await self.repo.get_by_id(department_id, organization_id)
        if not department:
            raise NotFoundError("Department", department_id)
        return department

    async def list_departments(self, organization_id: uuid.UUID, is_active: bool | None = None) -> list[Department]:
        return await self.repo.list_for_organization(organization_id, is_active)

    async def update_department(
        self, department_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Department:
        department = await self.get_department(department_id, organization_id)
        updated = await self.repo.update(department, **fields)
        logger.info("department_updated", department_id=str(department_id))
        return updated


class DesignationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DesignationRepository(db)
        self.authz_repo = AuthorizationRepository(db)

    async def _validate_linked_role(self, linked_role_id: uuid.UUID | None) -> None:
        if linked_role_id is None:
            return
        role = await self.authz_repo.get_role_by_id(linked_role_id)
        if not role:
            raise NotFoundError("Role", linked_role_id)
        if role.slug in _DESIGNATION_LINKABLE_ROLE_BLOCKLIST:
            raise ValidationError(
                f"The '{role.slug}' role can't be linked to a designation — "
                "assign it to individual users directly from the Roles page instead."
            )

    async def create_designation(self, organization_id: uuid.UUID, code: str, **fields) -> Designation:
        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"A designation with code '{code}' already exists.")
        await self._validate_linked_role(fields.get("linked_role_id"))
        designation = await self.repo.create(organization_id=organization_id, code=code, **fields)
        logger.info("designation_created", designation_id=str(designation.id))
        return designation

    async def get_designation(self, designation_id: uuid.UUID, organization_id: uuid.UUID) -> Designation:
        designation = await self.repo.get_by_id(designation_id, organization_id)
        if not designation:
            raise NotFoundError("Designation", designation_id)
        return designation

    async def list_designations(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[Designation]:
        return await self.repo.list_for_organization(organization_id, is_active)

    async def update_designation(
        self, designation_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Designation:
        designation = await self.get_designation(designation_id, organization_id)
        if "linked_role_id" in fields:
            await self._validate_linked_role(fields["linked_role_id"])
        updated = await self.repo.update(designation, **fields)
        logger.info("designation_updated", designation_id=str(designation_id))
        return updated
