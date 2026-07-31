"""
Database seed script.

Run via `make seed` (docker) or `python -m scripts.seed` locally. Idempotent:
safe to run multiple times.

Seeds:
  1. Default permissions and system roles (Super Admin, Administrator, Staff)
  2. An optional bootstrap superadmin user, if SEED_SUPERADMIN_EMAIL and
     SEED_SUPERADMIN_PASSWORD are set in the environment — this is the only
     way to get your first user into a fresh install, since registration
     requires email verification and no one can grant themselves a role. The
     superadmin is attached to a default "System" organization + user profile
     so the tenant-scoping dependency (get_current_user_organization_id) can
     resolve an organization for it and org-scoped endpoints work immediately.
"""

import asyncio
import os

from app.core.logging_config import get_logger
from app.core.security import hash_password
from app.db.session import get_db_context
from modules.authentication.models import UserStatus
from modules.authentication.repository import AuthRepository
from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService

# Registers the `branches` table in the mapper metadata. UserProfile.branch_id
# FKs to it, so inserting a profile below triggers table-dependency sorting that
# fails with NoReferencedTableError unless Branch is imported (app.main pulls in
# every model transitively; this standalone script must register it explicitly).
from modules.branches.models import Branch  # noqa: F401
from modules.organizations.repository import OrganizationRepository
from modules.users.repository import UserProfileRepository

logger = get_logger(__name__)

# Fixed slug so the default org is looked up (never duplicated) on re-seed.
_SYSTEM_ORG_SLUG = "erpx-system"
_SYSTEM_ORG_NAME = "ERPX System"


async def seed_rbac() -> None:
    async with get_db_context() as db:
        service = AuthorizationService(db)
        await service.seed_default_rbac()


async def seed_bootstrap_superadmin() -> None:
    email = os.getenv("SEED_SUPERADMIN_EMAIL")
    password = os.getenv("SEED_SUPERADMIN_PASSWORD")
    if not email or not password:
        logger.info("seed_superadmin_skipped", reason="SEED_SUPERADMIN_EMAIL/PASSWORD not set")
        return

    async with get_db_context() as db:
        auth_repo = AuthRepository(db)
        authz_repo = AuthorizationRepository(db)
        org_repo = OrganizationRepository(db)
        profile_repo = UserProfileRepository(db)

        # Default "System" organization (idempotent by slug) — the tenant the
        # bootstrap superadmin operates in so org-scoped endpoints resolve.
        org = await org_repo.get_by_slug(_SYSTEM_ORG_SLUG)
        if not org:
            org = await org_repo.create(name=_SYSTEM_ORG_NAME, slug=_SYSTEM_ORG_SLUG)
            await db.flush()
            logger.info("seed_system_org_created", slug=_SYSTEM_ORG_SLUG)

        user = await auth_repo.get_user_by_email(email)
        if not user:
            user = await auth_repo.create_user(
                email=email,
                hashed_password=hash_password(password),
                full_name="Super Admin",
            )
            user.is_superuser = True
            user.is_email_verified = True
            user.status = UserStatus.ACTIVE
            await db.flush()
            logger.info("seed_superadmin_created", email=email)
        else:
            logger.info("seed_superadmin_already_exists", email=email)

        # User profile linking the superadmin to the System org (idempotent by
        # user_id) — get_current_user_organization_id reads this to scope
        # requests; without it every org-scoped endpoint returns 422.
        profile = await profile_repo.get_by_user_id(user.id)
        if not profile:
            await profile_repo.create(user_id=user.id, organization_id=org.id)
            logger.info("seed_superadmin_profile_created", email=email, org=_SYSTEM_ORG_SLUG)

        super_admin_role = await authz_repo.get_role_by_slug("super_admin")
        if super_admin_role:
            await authz_repo.assign_role(user.id, super_admin_role.id, assigned_by_user_id=None)


async def main() -> None:
    await seed_rbac()
    await seed_bootstrap_superadmin()
    logger.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(main())
