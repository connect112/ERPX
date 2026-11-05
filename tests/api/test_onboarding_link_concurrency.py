"""
Staff-issued, revoked and cancelled onboarding links against an email's pending link, with REAL concurrency.

The ordinary test fixtures run everything inside one rolled-back transaction, which cannot show two database connections racing.
These tests therefore use their own engine and committed rows (with foreign-key checks switched off for those sessions, so a bare
application row is enough) and remove everything afterwards. The database is the throwaway test database.

The rule being checked: a link an email is still carrying (pending) can only ever be promoted if it is still the newest thing the
application knows. A staff-issued link, a revocation or a cancellation that comes later always wins, in whatever order the database
happens to serialise them.
"""

import asyncio
import random
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.exceptions import ValidationError
from modules.internship_onboarding.config import OnboardingConfig
from modules.internship_onboarding.models import OnboardingApplication, OnboardingEvent
from modules.internship_onboarding.service import ApplicationService, hash_token

pytestmark = pytest.mark.api

ROUNDS = 12


@pytest_asyncio.fixture
async def rig():
    """Its own connections, committed rows, and a clean-up afterwards."""
    engine = create_async_engine(settings.DATABASE_URL, connect_args={"server_settings": {"session_replication_role": "replica"}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    made: list[uuid.UUID] = []
    org = uuid.uuid4()

    async def application(*, active: str | None, pending: str | None = None, ref: str | None = "ol:test:batch") -> uuid.UUID:
        application_id = uuid.uuid4()
        async with sessions() as db, db.begin():
            await db.execute(
                OnboardingApplication.__table__.insert().values(
                    id=application_id, organization_id=org, internship_id=uuid.uuid4(), selection_id=uuid.uuid4(), reference=f"T-{application_id.hex[:12]}",
                    token_hash=hash_token(active) if active else None, token_issued_at=datetime.now(timezone.utc) if active else None,
                    pending_token_hash=hash_token(pending) if pending else None, pending_token_issued_at=datetime.now(timezone.utc) if pending else None,
                    pending_token_ref=ref if pending else None,
                )
            )
        made.append(application_id)
        return application_id

    async def state(application_id: uuid.UUID) -> OnboardingApplication:
        async with sessions() as db:
            return (await db.execute(select(OnboardingApplication).where(OnboardingApplication.id == application_id).execution_options(populate_existing=True))).scalar_one()

    async def run(operation, *args):
        """One operation in its own session and transaction, started after a small random delay so interleavings differ."""
        await asyncio.sleep(random.random() * 0.01)
        async with sessions() as db, db.begin():
            return await operation(ApplicationService(db), db, *args)

    yield SimpleNamespace(sessions=sessions, application=application, state=state, run=run, org=org)
    async with sessions() as db, db.begin():
        await db.execute(delete(OnboardingEvent).where(OnboardingEvent.application_id.in_(made)))
        await db.execute(delete(OnboardingApplication).where(OnboardingApplication.id.in_(made)))
    await engine.dispose()


def token() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


# operations, as (service, db, ...) -> result
async def install(service, db, application_id, new_token):
    return (await service.install_link(application_id, hash_token(new_token))).id


async def promote(service, db, application_id, pending_token):
    return await service.promote_pending(application_id, hash_token(pending_token))


async def revoke(service, db, application_id):
    application = await db.get(OnboardingApplication, application_id)
    await service.revoke_link(application, None)


async def cancel(service, db, application_id):
    return (await service.cancel_link_state(application_id, "withdrawn")).id


async def issue_pending(service, db, application_id, new_token, ref):
    # what an email about to be sent does: it asks for a pending link (the raw token is made inside; the hash is what we compare)
    application = await db.get(OnboardingApplication, application_id)
    internship = SimpleNamespace(id=application.internship_id, organization_id=application.organization_id)
    selection = SimpleNamespace(id=application.selection_id)
    return await service.issue_pending(internship, selection, ref, OnboardingConfig())


# ------------------------------------------------------------ the races


async def test_a_staff_issued_link_always_beats_a_pending_link_being_promoted(rig):
    for _ in range(ROUNDS):
        old, pending, staff = token(), token(), token()
        application_id = await rig.application(active=old, pending=pending)
        promoted, _ = await asyncio.gather(rig.run(promote, application_id, pending), rig.run(install, application_id, staff))
        now = await rig.state(application_id)
        assert now.token_hash == hash_token(staff), "an older pending link overwrote the staff-issued link"
        assert now.pending_token_hash is None and now.pending_token_ref is None and now.token_revoked_at is None
        assert isinstance(promoted, bool)  # either it won first (then the staff link replaced it) or it found the slot cleared


async def test_a_revoked_application_never_ends_up_with_a_working_link(rig):
    for _ in range(ROUNDS):
        pending = token()
        application_id = await rig.application(active=token(), pending=pending)
        await asyncio.gather(rig.run(promote, application_id, pending), rig.run(revoke, application_id))
        now = await rig.state(application_id)
        assert now.token_hash is None and now.token_revoked_at is not None and now.pending_token_hash is None


async def test_a_cancelled_application_never_ends_up_with_a_working_link(rig):
    for _ in range(ROUNDS):
        pending = token()
        application_id = await rig.application(active=token(), pending=pending)
        await asyncio.gather(rig.run(promote, application_id, pending), rig.run(cancel, application_id))
        now = await rig.state(application_id)
        assert now.cancelled_at is not None and now.token_hash is None and now.pending_token_hash is None


async def test_staff_issuing_and_an_email_asking_for_a_pending_link_leave_a_consistent_state(rig):
    """Whichever comes first: if the email's pending link was made first the staff link clears it; if it was made after, it is newer
    than the staff link and may legitimately replace it once its email is accepted. A pending link is never OLDER than the active one."""
    cleared = kept = 0
    for _ in range(ROUNDS * 2):
        staff = token()
        application_id = await rig.application(active=token())
        await asyncio.gather(rig.run(install, application_id, staff), rig.run(issue_pending, application_id, token(), "ol:test:2"))
        now = await rig.state(application_id)
        assert now.token_hash == hash_token(staff)
        if now.pending_token_hash is None:
            cleared += 1
        else:
            kept += 1
            assert now.pending_token_issued_at >= now.token_issued_at
    assert cleared + kept == ROUNDS * 2


async def test_a_staff_issue_after_a_pending_link_was_made_by_someone_else_still_clears_it(rig):
    """The old defect: the staff action held a stale copy of the row (no pending link on it) and wrote back without clearing one that
    another connection had just committed."""
    application_id = await rig.application(active=token())
    async with rig.sessions() as stale, stale.begin():
        copy = await stale.get(OnboardingApplication, application_id)
        assert copy.pending_token_hash is None  # what the staff action believes
        async with rig.sessions() as other, other.begin():  # an email's worker commits a pending link meanwhile
            await issue_pending(ApplicationService(other), other, application_id, token(), "ol:test:3")
        staff = token()
        issued = await ApplicationService(stale).install_link(application_id, hash_token(staff))
        assert issued.pending_token_hash is None and issued.token_hash == hash_token(staff)
    now = await rig.state(application_id)
    assert now.pending_token_hash is None and now.token_hash == hash_token(staff)


async def test_a_stale_revoke_or_cancel_clears_a_pending_link_committed_meanwhile(rig):
    for action in ("revoke", "cancel"):
        application_id = await rig.application(active=token())
        async with rig.sessions() as stale, stale.begin():
            copy = await stale.get(OnboardingApplication, application_id)
            async with rig.sessions() as other, other.begin():
                await issue_pending(ApplicationService(other), other, application_id, token(), "ol:test:4")
            if action == "revoke":
                await ApplicationService(stale).revoke_link(copy, None)
            else:
                await ApplicationService(stale).cancel_link_state(application_id, "withdrawn")
        now = await rig.state(application_id)
        assert now.pending_token_hash is None and now.token_hash is None and now.token_revoked_at is not None


async def test_after_a_staff_issue_the_old_pending_link_can_no_longer_be_promoted(rig):
    pending, staff = token(), token()
    application_id = await rig.application(active=token(), pending=pending)
    await rig.run(install, application_id, staff)
    assert await rig.run(promote, application_id, pending) is False
    now = await rig.state(application_id)
    assert now.token_hash == hash_token(staff)


# ------------------------------------------------------------ the lock is really taken


async def test_the_application_row_is_locked_while_a_link_changes(rig):
    """A second connection that wants to change the same application's links waits for the first to finish."""
    pending, staff = token(), token()
    application_id = await rig.application(active=token(), pending=pending)
    async with rig.sessions() as first, first.begin():
        await ApplicationService(first).install_link(application_id, hash_token(staff))  # holds the row until this block ends
        waiting = asyncio.create_task(rig.run(promote, application_id, pending))
        await asyncio.sleep(0.4)
        assert not waiting.done(), "a second change went through while the first still held the application"
    assert await asyncio.wait_for(waiting, 5) is False  # and when it ran, the pending link had been superseded
    assert (await rig.state(application_id)).token_hash == hash_token(staff)


async def test_a_cancelled_application_refuses_a_new_link(rig):
    application_id = await rig.application(active=token())
    await rig.run(cancel, application_id)
    with pytest.raises(ValidationError):
        await rig.run(install, application_id, token())
    assert (await rig.state(application_id)).token_hash is None
