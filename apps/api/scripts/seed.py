"""
Database seed script.

Run via `make seed` (docker) or `python -m scripts.seed` locally. Idempotent:
safe to run multiple times.

Seeds:
  1. Default permissions and system roles (Super Admin, Administrator, Staff,
     Student)
  2. An optional bootstrap superadmin user, if SEED_SUPERADMIN_EMAIL and
     SEED_SUPERADMIN_PASSWORD are set in the environment — this is the only
     way to get your first user into a fresh install, since registration
     requires email verification and no one can grant themselves a role. The
     superadmin is attached to a default "System" organization + user profile
     so the tenant-scoping dependency (get_current_user_organization_id) can
     resolve an organization for it and org-scoped endpoints work immediately.
  3. The fixed "GIR Technologies / Pentrix Program" organization + course
     that modules.provisioning resolves a Pentrix-share payment's
     `program_code` against — see modules/provisioning/service.py.
"""

import asyncio
import os

from app.core.config import settings
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
from modules.courses.repository import CourseRepository
from modules.organizations.repository import OrganizationRepository
from modules.provisioning.service import PENTRIX_ORG_SLUG
from modules.users.repository import UserProfileRepository

logger = get_logger(__name__)

# Fixed slug so the default org is looked up (never duplicated) on re-seed.
_SYSTEM_ORG_SLUG = "erpx-system"
_SYSTEM_ORG_NAME = "ERPX System"

# The org/course modules.provisioning provisions Pentrix-share students
# into — a single, deliberately fixed tenant, not one org per student.
_PENTRIX_ORG_NAME = "GIR Technologies / Pentrix Program"
_PENTRIX_COURSE_SLUG = "pentrix-program"
_PENTRIX_COURSE_TITLE = "Pentrix Cyber Range Program"

# Bootstrap-password hardening (mirrors config._refuse_default_jwt_secret_in_production).
# The docker-compose/.env scaffolding defaults SEED_SUPERADMIN_PASSWORD to a value
# that is publicly visible in this repo, and the api service runs this seed on every
# startup — so a production deploy that sets a real JWT_SECRET_KEY but forgets to
# override the seed password would silently create a superuser whose credentials
# anyone can read from source. Refuse that in production the same way the JWT guard
# does, rather than shipping a known-credential admin account.
_KNOWN_DEFAULT_SUPERADMIN_PASSWORDS = frozenset({"Admin@12345", "admin123", "changeme", "password"})
_MIN_SUPERADMIN_PASSWORD_LENGTH = 12


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

    if settings.is_production:
        if password in _KNOWN_DEFAULT_SUPERADMIN_PASSWORDS:
            raise ValueError(
                "SEED_SUPERADMIN_PASSWORD is still a publicly-known default value "
                "while ENVIRONMENT=production. Set a real, unique superadmin password "
                "before starting the application, or unset SEED_SUPERADMIN_PASSWORD to "
                "skip bootstrap seeding entirely."
            )
        if len(password) < _MIN_SUPERADMIN_PASSWORD_LENGTH:
            raise ValueError(
                f"SEED_SUPERADMIN_PASSWORD must be at least "
                f"{_MIN_SUPERADMIN_PASSWORD_LENGTH} characters in production "
                f"(got {len(password)})."
            )

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


async def seed_pentrix_program() -> None:
    """
    Idempotently seeds the fixed organization + course that
    modules.provisioning.ProvisioningService resolves an inbound Pentrix
    payment's `program_code` against (PENTRIX_ORG_SLUG,
    imported from that module so both sides share one source of truth for
    the slug). Kept separate from the "System" org above — Pentrix-share
    students are a distinct tenant from ERPX's own bootstrap/admin org, not
    a sub-part of it.
    """
    async with get_db_context() as db:
        org_repo = OrganizationRepository(db)
        course_repo = CourseRepository(db)

        org = await org_repo.get_by_slug(PENTRIX_ORG_SLUG)
        if not org:
            org = await org_repo.create(name=_PENTRIX_ORG_NAME, slug=PENTRIX_ORG_SLUG)
            await db.flush()
            logger.info("seed_pentrix_org_created", slug=PENTRIX_ORG_SLUG)

        course = await course_repo.get_by_slug(org.id, _PENTRIX_COURSE_SLUG)
        if not course:
            await course_repo.create(
                organization_id=org.id,
                title=_PENTRIX_COURSE_TITLE,
                slug=_PENTRIX_COURSE_SLUG,
                is_published=True,
            )
            logger.info("seed_pentrix_course_created", slug=_PENTRIX_COURSE_SLUG)


async def main() -> None:
    await seed_rbac()
    await seed_bootstrap_superadmin()
    await seed_pentrix_program()
    logger.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(main())
