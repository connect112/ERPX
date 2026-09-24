import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from app.core.security import hash_password
from modules.authentication.models import UserStatus
from modules.authentication.repository import AuthRepository
from modules.authentication.tasks import send_password_reset_email_task
from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.organizations.models import Organization
from modules.organizations.repository import OrganizationRepository
from modules.settings.service import SettingsService
from modules.users.repository import UserProfileRepository

logger = get_logger(__name__)

# A first login shouldn't expire before the invited admin has opened the
# email — mirrors modules/employees/service.py's identical
# _INVITE_TOKEN_TTL_HOURS and modules/provisioning/service.py's
# SET_PASSWORD_TOKEN_TTL_HOURS for the same reason.
_ADMIN_INVITE_TOKEN_TTL_HOURS = 72

# The bootstrap organization apps/api/scripts/seed.py creates purely to
# give the SEED_SUPERADMIN account a profile/organization_id to resolve
# (see get_current_user_organization_id) — it holds no real customer data
# and was never meant to be a selectable tenant. Without this filter it
# shows up as a second, confusing entry in Super Admin's Organizations
# list alongside actual customer organizations.
SYSTEM_ORG_SLUG = "erpx-system"


class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = OrganizationRepository(db)
        self.auth_repo = AuthRepository(db)
        self.profile_repo = UserProfileRepository(db)
        self.authz_repo = AuthorizationRepository(db)

    async def create_organization(self, admin_full_name: str, admin_email: str, **fields) -> Organization:
        existing = await self.repo.get_by_slug(fields["slug"])
        if existing:
            raise ConflictError(f"An organization with slug '{fields['slug']}' already exists.")

        existing_user = await self.auth_repo.get_user_by_email(admin_email)
        if existing_user:
            raise ConflictError(f"An account already exists for {admin_email}.")

        org = await self.repo.create(**fields)
        await SettingsService(self.db).seed_defaults_for_organization(org.id)
        await self._invite_organization_admin(org, admin_full_name, admin_email)
        logger.info("organization_created", org_id=str(org.id), slug=org.slug)
        return org

    async def _invite_organization_admin(
        self, org: Organization, admin_full_name: str, admin_email: str
    ) -> None:
        """Onboarding a customer means handing them a working admin
        account, not a database row they can't log into — mirrors
        modules/employees/service.py's invite_employee and
        modules/provisioning/service.py's student provisioning: a
        random, never-communicated password (the account is unusable
        until the admin sets their own via the emailed link), an
        immediately-active status (internally vouched for, same as an
        employee invite), and the "administrator" system role."""
        admin_user = await self.auth_repo.create_user(
            email=admin_email,
            hashed_password=hash_password(uuid.uuid4().hex),
            full_name=admin_full_name,
        )
        admin_user.is_email_verified = True
        admin_user.status = UserStatus.ACTIVE
        await self.db.flush()

        await self.profile_repo.create(user_id=admin_user.id, organization_id=org.id)

        admin_role = await self.authz_repo.get_role_by_slug("administrator")
        if admin_role:
            await AuthorizationService(self.db).assign_role(
                admin_user.id, admin_role.id, org.id, assigned_by_user_id=None
            )

        reset_token = await self.auth_repo.create_password_reset_token(
            admin_user.id, ttl_hours=_ADMIN_INVITE_TOKEN_TTL_HOURS
        )
        set_password_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token.token}"
        send_password_reset_email_task.delay(admin_user.email, admin_user.full_name, set_password_url)

        logger.info("organization_admin_invited", org_id=str(org.id), user_id=str(admin_user.id))

    async def get_organization(self, org_id: uuid.UUID) -> Organization:
        org = await self.repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("Organization", org_id)
        return org

    async def list_organizations(self, skip: int, limit: int) -> list[Organization]:
        return await self.repo.list_all(skip, limit, exclude_slug=SYSTEM_ORG_SLUG)

    async def update_organization(self, org_id: uuid.UUID, **fields) -> Organization:
        org = await self.repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("Organization", org_id)
        updated = await self.repo.update(org, **fields)
        logger.info("organization_updated", org_id=str(org_id))
        return updated

    async def delete_organization(self, org_id: uuid.UUID) -> None:
        org = await self.repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("Organization", org_id)
        await self.repo.soft_delete(org)
        logger.info("organization_deleted", org_id=str(org_id))
