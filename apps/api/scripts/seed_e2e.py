"""
End-to-end test fixture seed script.

Unlike `scripts/seed.py` (production bootstrap: RBAC + an optional
superadmin with no organization), this creates a *complete* login-ready
identity for Playwright's e2e suite: RBAC, an organization, a verified
superuser, and a `UserProfile` linking the two — since almost every
business-module endpoint requires the caller to have an organization via
`get_current_user_organization_id`, not just a valid token.

Idempotent: safe to run before every e2e run. Reads its target database
from `DATABASE_URL` like every other entry point in this app.

Run via `python -m scripts.seed_e2e` from `apps/api/` (see
`apps/web/e2e/global-setup.ts`, which invokes this before the suite).
"""

import asyncio

# Importing the app (rather than hand-picking model modules) pulls in
# every module's routers -> services -> models transitively, so
# SQLAlchemy's mapper configuration sees the full schema (e.g. the FK
# from user_profiles.branch_id to branches) no matter which repositories
# this script touches directly.
from app.main import app  # noqa: F401

from app.core.logging_config import get_logger
from app.core.security import hash_password
from app.db.session import get_db_context
from modules.authentication.models import UserStatus
from modules.authentication.repository import AuthRepository
from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.organizations.repository import OrganizationRepository
from modules.users.repository import UserProfileRepository

logger = get_logger(__name__)

E2E_ORG_SLUG = "e2e-test-org"
E2E_ORG_NAME = "E2E Test Org"
E2E_EMAIL = "e2e@erpx.example.com"
E2E_PASSWORD = "E2ePass123!"
E2E_FULL_NAME = "E2E Test User"


async def main() -> None:
    async with get_db_context() as db:
        await AuthorizationService(db).seed_default_rbac()

        org_repo = OrganizationRepository(db)
        org = await org_repo.get_by_slug(E2E_ORG_SLUG)
        if not org:
            org = await org_repo.create(name=E2E_ORG_NAME, slug=E2E_ORG_SLUG)
            await db.flush()
            logger.info("seed_e2e_org_created", org_id=str(org.id))
        else:
            logger.info("seed_e2e_org_already_exists", org_id=str(org.id))

        auth_repo = AuthRepository(db)
        user = await auth_repo.get_user_by_email(E2E_EMAIL)
        if not user:
            user = await auth_repo.create_user(
                email=E2E_EMAIL,
                hashed_password=hash_password(E2E_PASSWORD),
                full_name=E2E_FULL_NAME,
            )
            user.is_superuser = True
            user.is_email_verified = True
            user.status = UserStatus.ACTIVE
            await db.flush()
            logger.info("seed_e2e_user_created", user_id=str(user.id))
        else:
            logger.info("seed_e2e_user_already_exists", user_id=str(user.id))

        authz_repo = AuthorizationRepository(db)
        super_admin_role = await authz_repo.get_role_by_slug("super_admin")
        if super_admin_role:
            await authz_repo.assign_role(user.id, super_admin_role.id, assigned_by_user_id=None)

        profile_repo = UserProfileRepository(db)
        profile = await profile_repo.get_by_user_id(user.id)
        if not profile:
            await profile_repo.create(user_id=user.id, organization_id=org.id)
            logger.info("seed_e2e_profile_created", user_id=str(user.id), org_id=str(org.id))
        else:
            logger.info("seed_e2e_profile_already_exists", user_id=str(user.id))

        logger.info(
            "seed_e2e_complete",
            email=E2E_EMAIL,
            org_id=str(org.id),
            org_slug=E2E_ORG_SLUG,
        )


if __name__ == "__main__":
    asyncio.run(main())
