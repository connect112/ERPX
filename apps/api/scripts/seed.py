"""
Database seed script.

Run via `make seed` (docker) or `python -m scripts.seed` locally. Idempotent:
safe to run multiple times.

Seeds:
  1. Default permissions and system roles (Super Admin, Administrator, Staff)
  2. An optional bootstrap superadmin user, if SEED_SUPERADMIN_EMAIL and
     SEED_SUPERADMIN_PASSWORD are set in the environment — this is the only
     way to get your first user into a fresh install, since registration
     requires email verification and no one can grant themselves a role.
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

logger = get_logger(__name__)


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

        super_admin_role = await authz_repo.get_role_by_slug("super_admin")
        if super_admin_role:
            await authz_repo.assign_role(user.id, super_admin_role.id, assigned_by_user_id=None)


async def main() -> None:
    await seed_rbac()
    await seed_bootstrap_superadmin()
    logger.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(main())
