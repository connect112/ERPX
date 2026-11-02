"""
Synthetic data and self-checks for the Cashfree SANDBOX staging stack. Runs inside the staging api container only
(./staging.sh seed / ./staging.sh verify); it refuses to run anywhere that is not ENVIRONMENT=staging with Cashfree in
sandbox mode. No real people: every name is invented and every address is @example.com.

  bucket  create the staging storage bucket (a fresh MinIO has none, and uploads do not create it).
  seed    two organizations: "Staging Org A" (a plain Administrator, an institution, four students selected for an
          internship) and "Staging Org B" (one internship, only there to prove Org A cannot see it). Idempotent.
  verify  sandbox-only settings, migration head, the gateway's routes, a signed-link round trip through /_files, and
          organization scoping through the real API.
"""

import asyncio
import os
import sys
import uuid

import app.main  # noqa: F401  (loads every model)
import httpx
from sqlalchemy import select, text

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import get_db_context
from modules.authentication.models import User, UserStatus
from modules.authentication.repository import AuthRepository
from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.institutions.models import Institution, InstitutionStudent
from modules.organizations.models import Organization
from modules.organizations.repository import OrganizationRepository
from modules.our_internships.models import InternshipScope, InternshipSelection, OfferStatus, OurInternship
from modules.users.repository import UserProfileRepository
from packages.storage.client import get_storage_client

GATEWAY = "http://gateway"
ORG_A, ORG_B = "staging-org-a", "staging-org-b"
STUDENTS = ["Asha Test", "Ben Test", "Chitra Test", "Dev Test"]


def refuse_unless_staging() -> None:
    problems = []
    if settings.ENVIRONMENT != "staging":
        problems.append(f"ENVIRONMENT is {settings.ENVIRONMENT!r}, not 'staging'")
    if settings.CASHFREE_ENV != "sandbox" or settings.CASHFREE_ALLOW_PRODUCTION:
        problems.append("Cashfree is not sandbox-only")
    if not settings.DATABASE_URL.endswith("@postgres:5432/erpx_staging"):
        problems.append("the database is not the staging stack's own")
    if problems:
        sys.exit("refusing to run: " + "; ".join(problems))


async def organization(db, slug: str, name: str) -> Organization:
    found = (await db.execute(select(Organization).where(Organization.slug == slug))).scalar_one_or_none()
    return found or await OrganizationRepository(db).create(name=name, slug=slug)


async def bucket() -> None:
    await get_storage_client().ensure_bucket()
    print(f"storage bucket {settings.MINIO_BUCKET} ready")


async def seed() -> None:
    await bucket()
    email, password = os.environ["STAGING_ADMIN_EMAIL"], os.environ["STAGING_ADMIN_PASSWORD"]
    async with get_db_context() as db:
        org_a = await organization(db, ORG_A, "Staging Org A (synthetic)")
        org_b = await organization(db, ORG_B, "Staging Org B (synthetic)")
        await db.flush()
        if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none() is None:
            user = await AuthRepository(db).create_user(email=email, hashed_password=hash_password(password), full_name="Staging Administrator")
            user.status, user.is_email_verified = UserStatus.ACTIVE, True
            await db.flush()
            await UserProfileRepository(db).create(user_id=user.id, organization_id=org_a.id)
            role = await AuthorizationRepository(db).get_role_by_slug("administrator")  # a plain Administrator, not Super Admin
            await AuthorizationService(db).assign_role(user.id, role.id, org_a.id, assigned_by_user_id=None)
        for org, title in ((org_a, "Sandbox Internship (synthetic)"), (org_b, "Org B Internship (synthetic)")):
            exists = (await db.execute(select(OurInternship).where(OurInternship.organization_id == org.id, OurInternship.title == title))).scalar_one_or_none()
            if exists:
                continue
            internship = OurInternship(organization_id=org.id, title=title, scope=InternshipScope.ALL)
            institution = Institution(organization_id=org.id, name="Example College (synthetic)", location="Nowhere", faculty_name="Dr. Example")
            db.add_all([internship, institution])
            await db.flush()
            for i, name in enumerate(STUDENTS if org is org_a else STUDENTS[:1]):
                student = InstitutionStudent(
                    organization_id=org.id, institution_id=institution.id, name=name,
                    email=f"student{i + 1}-{uuid.uuid4().hex[:6]}@example.com", phone=f"900000000{i + 1}",
                    details={"Registration Number": f"SYN-{i + 1:03d}"},
                )  # fmt: skip
                db.add(student)
                await db.flush()
                db.add(InternshipSelection(organization_id=org.id, internship_id=internship.id, student_id=student.id, offer_status=OfferStatus.SENT))
        await db.commit()
    print("seeded: Staging Org A (administrator, 4 students, 1 internship) and Staging Org B (1 internship)")


def check(ok: bool, what: str, failures: list[str]) -> None:
    print(f"{'OK  ' if ok else 'FAIL'} {what}")
    if not ok:
        failures.append(what)


async def verify() -> None:
    failures: list[str] = []
    check(settings.CASHFREE_ENV == "sandbox" and not settings.CASHFREE_ALLOW_PRODUCTION, "Cashfree sandbox only, production not allowed", failures)
    check(settings.SMTP_HOST == "mailpit", "all email goes to Mailpit", failures)
    check(settings.MINIO_ENDPOINT == "minio:9000" and settings.MINIO_BUCKET == "erpx-staging", "own MinIO and bucket", failures)
    check(settings.REDIS_URL.startswith("redis://redis:6379/"), "own Redis", failures)
    async with get_db_context() as db:
        version = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        orgs = {o.slug: o for o in (await db.execute(select(Organization).where(Organization.slug.in_([ORG_A, ORG_B])))).scalars()}
        internships = {}
        for slug, org in orgs.items():
            internships[slug] = (await db.execute(select(OurInternship.id).where(OurInternship.organization_id == org.id))).scalars().first()
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    check(version == head, f"database migrated to head ({version})", failures)
    check(all(internships.get(s) for s in (ORG_A, ORG_B)), "synthetic organizations seeded (run ./staging.sh seed first)", failures)

    async with httpx.AsyncClient(base_url=GATEWAY, timeout=20, follow_redirects=False) as http:
        check((await http.get("/api/v1/health")).status_code == 200, "gateway -> API health", failures)
        page = await http.get("/internship-onboarding")
        check(page.status_code == 200 and "<div id=\"root\"" in page.text, "gateway -> web app (deep links served by the SPA)", failures)
        for blocked in ("/api/docs", "/api/redoc", "/api/openapi.json", "/metrics"):
            check((await http.get(blocked)).status_code == 404, f"gateway blocks {blocked}", failures)
        check((await http.post("/api/v1/public/payments/cashfree/webhook", content=b"{}")).status_code in (400, 401), "webhook route reachable and refusing unsigned calls", failures)
        # a signed download link, as the app hands them out, fetched through the gateway like a browser would
        storage, key, body = get_storage_client(), f"staging-verify/{uuid.uuid4().hex}.txt", b"synthetic staging check"
        try:
            await storage.upload_bytes(key, body, "text/plain")
            link = storage.presigned_download_url(key)
            fetched = await http.get(link)
            check(link.startswith("/_files/") and fetched.status_code == 200 and fetched.content == body, "signed file link works through /_files", failures)
        except Exception as exc:  # noqa: BLE001  (reported as a failed check)
            check(False, f"signed file link works through /_files ({type(exc).__name__}; run ./staging.sh up again)", failures)
        finally:
            await storage.delete_object(key)
        if all(internships.get(s) for s in (ORG_A, ORG_B)):
            login = await http.post("/api/v1/auth/login", json={"email": os.environ["STAGING_ADMIN_EMAIL"], "password": os.environ["STAGING_ADMIN_PASSWORD"]})
            check(login.status_code == 200, "Org A administrator signs in", failures)
            if login.status_code == 200:
                headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
                own = await http.get(f"/api/v1/our-internships/{internships[ORG_A]}", headers=headers)
                other = await http.get(f"/api/v1/our-internships/{internships[ORG_B]}", headers=headers)
                check(own.status_code == 200, "Org A sees its own internship", failures)
                check(other.status_code == 404, "Org A cannot see Org B's internship (organization scoping)", failures)
    async with get_db_context() as db:
        admin = (await db.execute(select(User).where(User.email == os.environ["STAGING_ADMIN_EMAIL"]))).scalar_one_or_none()
        check(admin is not None and admin.is_superuser is False, "the test administrator is not a Super Admin", failures)
    sys.exit(f"{len(failures)} check(s) failed" if failures else 0)


if __name__ == "__main__":
    refuse_unless_staging()
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "bucket":
        asyncio.run(bucket())
    elif command == "seed":
        asyncio.run(seed())
    elif command == "verify":
        asyncio.run(verify())
    else:
        sys.exit("usage: bucket | seed | verify")
