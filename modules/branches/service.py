import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.branches.models import Branch
from modules.branches.repository import BranchRepository
from modules.organizations.repository import OrganizationRepository

logger = get_logger(__name__)


class BranchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BranchRepository(db)
        self.org_repo = OrganizationRepository(db)

    async def create_branch(self, **fields) -> Branch:
        org = await self.org_repo.get_by_id(fields["organization_id"])
        if not org:
            raise NotFoundError("Organization", fields["organization_id"])

        existing = await self.repo.get_by_org_and_code(fields["organization_id"], fields["code"])
        if existing:
            raise ConflictError(
                f"A branch with code '{fields['code']}' already exists for this organization."
            )

        branch = await self.repo.create(**fields)
        logger.info("branch_created", branch_id=str(branch.id), org_id=str(org.id))
        return branch

    async def get_branch(self, branch_id: uuid.UUID) -> Branch:
        branch = await self.repo.get_by_id(branch_id)
        if not branch:
            raise NotFoundError("Branch", branch_id)
        return branch

    async def list_branches(self, organization_id: uuid.UUID) -> list[Branch]:
        return await self.repo.list_for_organization(organization_id)

    async def update_branch(self, branch_id: uuid.UUID, **fields) -> Branch:
        branch = await self.repo.get_by_id(branch_id)
        if not branch:
            raise NotFoundError("Branch", branch_id)
        updated = await self.repo.update(branch, **fields)
        logger.info("branch_updated", branch_id=str(branch_id))
        return updated

    async def delete_branch(self, branch_id: uuid.UUID) -> None:
        branch = await self.repo.get_by_id(branch_id)
        if not branch:
            raise NotFoundError("Branch", branch_id)
        if branch.is_head_office:
            from app.core.exceptions import ValidationError

            raise ValidationError("The head office branch cannot be deleted.")
        await self.repo.delete(branch)
        logger.info("branch_deleted", branch_id=str(branch_id))
