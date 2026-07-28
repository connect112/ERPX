"""
Database-backed fixtures, shared by `tests/api` and `tests/integration`
(each pulls these in via its own `conftest.py`) — never imported by
`tests/unit`, which must be runnable with no live database at all.

Every test gets an isolated transaction (`db_session`) that is rolled
back at the end of the test — services call `flush()`, never `commit()`,
throughout the app (see `app/db/session.py`), so the whole request
lifecycle works identically whether or not the outer transaction is
ever actually committed. `client` overrides FastAPI's `get_db`
dependency to hand every request in a test the *same* transactional
session, so setup done directly via repositories and assertions made
via HTTP responses see the same data.

Requires a real PostgreSQL test database with migrations already
applied (`alembic upgrade head` against `erpx_test`) — the same
database CI provisions before running pytest. See `tests/README.md`.
"""

import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://erpx:erpx_secret@localhost:5432/erpx_test")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_at_least_32_characters_long")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.db.session import engine, get_db
from app.main import app
from modules.authentication.models import User, UserStatus
from modules.authentication.repository import AuthRepository
from modules.authentication.tasks import send_password_reset_email_task, send_verification_email_task
from modules.authorization.service import AuthorizationService
from modules.crm.followups.tasks import send_followup_sms_task, send_followup_whatsapp_task
from modules.organizations.models import Organization
from modules.organizations.repository import OrganizationRepository
from modules.users.repository import UserProfileRepository


@pytest_asyncio.fixture(autouse=True)
def _no_background_email(monkeypatch):
    """Prevent tests from dispatching real Celery tasks / SMTP, SMS, or WhatsApp sends."""
    monkeypatch.setattr(send_verification_email_task, "delay", lambda *a, **kw: None)
    monkeypatch.setattr(send_password_reset_email_task, "delay", lambda *a, **kw: None)
    monkeypatch.setattr(send_followup_whatsapp_task, "delay", lambda *a, **kw: None)
    monkeypatch.setattr(send_followup_sms_task, "delay", lambda *a, **kw: None)


@pytest_asyncio.fixture
async def db_session():
    # `engine` (app/db/session.py) is a module-level singleton whose pooled
    # asyncpg connections are bound to whichever event loop was running
    # when they were opened. pytest-asyncio hands each test function its
    # own fresh loop, so a connection pooled by an earlier test is invalid
    # here — dispose the pool first so this test opens its connection
    # against the loop it's actually running on.
    await engine.dispose()
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def organization(db_session: AsyncSession) -> Organization:
    repo = OrganizationRepository(db_session)
    unique = uuid.uuid4().hex[:8]
    org = await repo.create(name=f"Test Org {unique}", slug=f"test-org-{unique}")
    await db_session.flush()
    return org


async def _make_user(
    db_session: AsyncSession, organization: Organization, *, is_superuser: bool, email: str
) -> tuple[User, str]:
    auth_repo = AuthRepository(db_session)
    user = await auth_repo.create_user(
        email=email, hashed_password=hash_password("Test1234!"), full_name="Test User"
    )
    user.status = UserStatus.ACTIVE
    user.is_email_verified = True
    user.is_superuser = is_superuser
    await db_session.flush()

    profile_repo = UserProfileRepository(db_session)
    await profile_repo.create(user_id=user.id, organization_id=organization.id)
    await db_session.flush()

    token = create_access_token(str(user.id))
    return user, token


@pytest_asyncio.fixture
async def superuser(db_session: AsyncSession, organization: Organization) -> tuple[User, str]:
    return await _make_user(db_session, organization, is_superuser=True, email=f"admin-{uuid.uuid4().hex[:8]}@erpx.example.com")


@pytest_asyncio.fixture
async def staff_user(db_session: AsyncSession, organization: Organization) -> tuple[User, str]:
    """A regular (non-superuser) user with no roles/permissions assigned — for RBAC-denial tests."""
    return await _make_user(db_session, organization, is_superuser=False, email=f"staff-{uuid.uuid4().hex[:8]}@erpx.example.com")


@pytest_asyncio.fixture
async def auth_headers(superuser) -> dict:
    _, token = superuser
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def staff_headers(staff_user) -> dict:
    _, token = staff_user
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def rbac_seeded(db_session: AsyncSession) -> None:
    """Seeds the platform-wide default permissions/roles (idempotent) for tests that need real RBAC, not just is_superuser bypass."""
    await AuthorizationService(db_session).seed_default_rbac()
