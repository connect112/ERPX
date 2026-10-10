"""
Social media: background tasks.

The database is the schedule, so none of this holds state. Every minute `social.publish_due` finds the posts whose time has
come and queues one `social.publish_post` each; the publisher's atomic claim guarantees a post is only ever published by one
of them, even if it is queued twice. Every five minutes `social.recover_publishing` settles posts that were left half way
by a crash or a restart. Problems are emailed to the addresses set in Settings.
"""

import uuid

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.config import settings as app_settings
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.email_templates.render import render_email_sync
from app.core.exceptions import ConflictError
from modules.social_media import health, retention
from modules.social_media.analytics import AnalyticsService
from modules.social_media.connection import ConnectionService
from modules.social_media.inbox import InboxService
from modules.social_media.models import SocialAccount, SocialPost, SocialSettings
from modules.social_media.publisher import PublisherService
from modules.social_media.reports import ReportService
from packages.email.service import email_service

logger = get_logger(__name__)


async def _tracked(job: str, work):
    """Run a scheduled job and leave a heartbeat: when it finished, whether it worked and, if not, a short reason."""
    try:
        result = await work
    except Exception as exc:  # noqa: BLE001 - recorded, then raised so the worker logs it too
        try:
            async with get_db_context() as db:
                await health.record(db, job, False, f"{type(exc).__name__}: {str(exc)[:200]}")
        except Exception:  # noqa: BLE001 - never hide the original failure behind a failed heartbeat
            logger.warning("social_heartbeat_failed", job=job, exc_info=True)
        raise
    try:
        async with get_db_context() as db:
            await health.record(db, job, True, count=result if isinstance(result, int) and not isinstance(result, bool) else None, detail=result if isinstance(result, dict) else None)
    except Exception:  # noqa: BLE001
        logger.warning("social_heartbeat_failed", job=job, exc_info=True)
    return result


async def _queue_due() -> int:
    async with get_db_context() as db:
        ids = await PublisherService(db).due_post_ids()
    queued = 0
    for post_id in ids:
        try:
            publish_post_task.apply_async(args=[str(post_id)], ignore_result=True, retry=False)
            queued += 1
        except Exception:  # noqa: BLE001 - the broker is down; the post stays scheduled and the next minute tries again
            logger.warning("social_enqueue_failed", post_id=str(post_id), exc_info=True)
    return queued


async def _publish(post_id: uuid.UUID, user_id: uuid.UUID | None) -> str:
    async with get_db_context() as db:
        return await PublisherService(db).run(post_id, user_id=user_id)


async def _recover() -> dict:
    async with get_db_context() as db:
        return await PublisherService(db).recover()


@celery_app.task(name="social.publish_due", ignore_result=True)
def publish_due_task() -> int:
    return run_async(_tracked("publish_due", _queue_due()))


@celery_app.task(name="social.publish_post", ignore_result=True)
def publish_post_task(post_id: str, user_id: str | None = None) -> str:
    outcome = run_async(_publish(uuid.UUID(post_id), uuid.UUID(user_id) if user_id else None))
    logger.info("social_publish_finished", post_id=post_id, outcome=outcome)
    return outcome


@celery_app.task(name="social.recover_publishing", ignore_result=True)
def recover_publishing_task() -> dict:
    result = run_async(_tracked("recover_publishing", _recover()))
    if any(result.values()):
        logger.info("social_recovery", **result)
    return result


def enqueue_publish(post_id: uuid.UUID, user_id: uuid.UUID | None = None) -> bool:
    """Queue a publish right away (an explicit click). If the broker is down the every-minute task still finds the post."""
    try:
        publish_post_task.apply_async(args=[str(post_id), str(user_id) if user_id else None], ignore_result=True, retry=False)
    except Exception:  # noqa: BLE001
        logger.warning("social_enqueue_failed", post_id=str(post_id), exc_info=True)
        return False
    return True


async def _problem_details(post_id: uuid.UUID) -> tuple[str, str, list[str]] | None:
    async with get_db_context() as db:
        post = (await db.execute(select(SocialPost).where(SocialPost.id == post_id))).scalar_one_or_none()
        if post is None:
            return None
        settings = (await db.execute(select(SocialSettings).where(SocialSettings.organization_id == post.organization_id))).scalar_one_or_none()
        notifications = (settings.notifications if settings else {}) or {}
        if not notifications.get("notify_on_failure", True):
            return None
        return str(post.organization_id), post.title, list(notifications.get("emails") or [])


@celery_app.task(name="social.send_problem_email", bind=True, max_retries=3)
def send_problem_email_task(self, post_id: str, problem: str, detail: str) -> None:
    found = run_async(_problem_details(uuid.UUID(post_id)))
    if not found:
        return
    organization_id, title, recipients = found
    if not recipients:
        logger.info("social_problem_not_emailed", post_id=post_id, reason="no notification address is set")
        return
    failed = []
    for address in recipients:
        subject, text, html = render_email_sync(
            "social_publish_problem",
            {
                "problem": problem[:120],
                "post_title": title[:120],
                "detail": detail[:500],
                "queue_url": f"{app_settings.FRONTEND_URL.rstrip('/')}/social-media?tab=queue",
            },
            organization_id=organization_id,
            recipient_email=address,
        )
        if not run_async(email_service.send(address, subject, text, html)):
            failed.append(address)
    if failed:
        logger.warning("social_problem_email_retry", attempt=self.request.retries)
        raise self.retry(countdown=60 * (self.request.retries + 1))


def enqueue_problem_email(post_id: uuid.UUID, problem: str, detail: str) -> None:
    send_problem_email_task.apply_async(args=[str(post_id), problem, detail], ignore_result=True, retry=False)


# ---------------- the Instagram connection ----------------


async def _refresh_tokens() -> dict:
    async with get_db_context() as db:
        return await ConnectionService(db).refresh_due()


@celery_app.task(name="social.refresh_tokens", ignore_result=True)
def refresh_tokens_task() -> dict:
    """Daily: refresh access tokens that are within 20 days of expiring, and warn when one can't be kept alive."""
    result = run_async(_tracked("refresh_tokens", _refresh_tokens()))
    if any(result.values()):
        logger.info("social_tokens_refreshed", **result)
    return result


async def _account_details(account_id: uuid.UUID) -> tuple[str, str, list[str]] | None:
    async with get_db_context() as db:
        account = (await db.execute(select(SocialAccount).where(SocialAccount.id == account_id))).scalar_one_or_none()
        if account is None:
            return None
        settings = (await db.execute(select(SocialSettings).where(SocialSettings.organization_id == account.organization_id))).scalar_one_or_none()
        notifications = (settings.notifications if settings else {}) or {}
        if not notifications.get("notify_on_token_expiry", True):
            return None
        return str(account.organization_id), f"@{account.username}" if account.username else "the Instagram account", list(notifications.get("emails") or [])


@celery_app.task(name="social.send_account_problem_email", bind=True, max_retries=3)
def send_account_problem_email_task(self, account_id: str, problem: str, detail: str) -> None:
    found = run_async(_account_details(uuid.UUID(account_id)))
    if not found:
        return
    organization_id, name, recipients = found
    if not recipients:
        logger.info("social_account_problem_not_emailed", reason="no notification address is set")
        return
    failed = []
    for address in recipients:
        subject, text, html = render_email_sync(
            "social_account_problem",
            {
                "problem": problem[:120],
                "account_name": name[:120],
                "detail": detail[:500],
                "settings_url": f"{app_settings.FRONTEND_URL.rstrip('/')}/social-media?tab=settings",
            },
            organization_id=organization_id,
            recipient_email=address,
        )
        if not run_async(email_service.send(address, subject, text, html)):
            failed.append(address)
    if failed:
        raise self.retry(countdown=60 * (self.request.retries + 1))


def enqueue_account_problem_email(account_id: uuid.UUID, problem: str, detail: str) -> None:
    send_account_problem_email_task.apply_async(args=[str(account_id), problem, detail], ignore_result=True, retry=False)


# ---------------- reading comments and messages ----------------


async def _sync_one(organization_id: uuid.UUID) -> str:
    try:
        async with get_db_context() as db:
            result = await InboxService(db).sync(organization_id)
    except ConflictError as exc:
        return str(exc)
    return "skipped" if result["skipped"] else "read"


async def _sync_all() -> int:
    async with get_db_context() as db:
        organizations = list(
            (await db.execute(select(SocialAccount.organization_id).where(SocialAccount.token_encrypted.is_not(None), SocialAccount.status.in_(("connected", "expiring"))))).scalars()
        )
    for organization_id in organizations:
        try:
            await _sync_one(organization_id)
        except Exception:  # noqa: BLE001 - one organisation's trouble must not stop the others
            logger.warning("social_inbox_sync_failed", organization_id=str(organization_id), exc_info=True)
    return len(organizations)


@celery_app.task(name="social.sync_account", ignore_result=True)
def sync_account_task(organization_id: str) -> str:
    """Read one organisation's new comments and messages (woken by a webhook notification)."""
    return run_async(_sync_one(uuid.UUID(organization_id)))


@celery_app.task(name="social.sync_inbox", ignore_result=True)
def sync_inbox_task() -> int:
    """Every half hour, a safety net in case a notification was missed. Cheap: unchanged conversations aren't re-read."""
    return run_async(_tracked("sync_inbox", _sync_all()))


def enqueue_sync(organization_id: uuid.UUID) -> bool:
    try:
        sync_account_task.apply_async(args=[str(organization_id)], ignore_result=True, retry=False)
    except Exception:  # noqa: BLE001
        logger.warning("social_sync_enqueue_failed", organization_id=str(organization_id), exc_info=True)
        return False
    return True


# ---------------- insights and reports ----------------


async def _connected_organizations() -> list[uuid.UUID]:
    async with get_db_context() as db:
        return list(
            (await db.execute(select(SocialAccount.organization_id).where(SocialAccount.token_encrypted.is_not(None), SocialAccount.status.in_(("connected", "expiring"))))).scalars()
        )


async def _read_insights() -> int:
    done = 0
    for organization_id in await _connected_organizations():
        try:
            async with get_db_context() as db:
                result = await AnalyticsService(db).sync(organization_id)
            done += 0 if result["skipped"] else 1
        except ConflictError:
            continue
        except Exception:  # noqa: BLE001 - one organisation's trouble must not stop the others
            logger.warning("social_insights_sync_failed", organization_id=str(organization_id), exc_info=True)
    return done


async def _make_reports() -> int:
    made = 0
    for organization_id in await _connected_organizations():
        for kind in ("weekly", "monthly"):
            try:
                async with get_db_context() as db:
                    if await ReportService(db).ensure_latest(organization_id, kind) is not None:
                        made += 1
            except Exception:  # noqa: BLE001
                logger.warning("social_report_failed", organization_id=str(organization_id), kind=kind, exc_info=True)
    return made


@celery_app.task(name="social.sync_insights", ignore_result=True)
def sync_insights_task() -> int:
    """Once a day: read the profile's figures and each recent post's insights (at most 14 days and 40 posts per run)."""
    return run_async(_tracked("sync_insights", _read_insights()))


@celery_app.task(name="social.make_reports", ignore_result=True)
def make_reports_task() -> int:
    """Once a day, after the read: write the report for the last complete week and month if it doesn't exist yet."""
    return run_async(_tracked("make_reports", _make_reports()))


# ---------------- housekeeping and monitoring ----------------


async def _apply_retention() -> dict:
    async with get_db_context() as db:
        return await retention.apply_all(db)


@celery_app.task(name="social.apply_retention", ignore_result=True)
def apply_retention_task() -> dict:
    """Once a day: remove comments, messages and other personal data that are past the retention period set in Settings."""
    result = run_async(_tracked("apply_retention", _apply_retention()))
    if any(result.values()):
        logger.info("social_retention_applied", **result)
    return result


async def _problems_and_recipients() -> list[tuple[str, list[str], list[dict]]]:
    async with get_db_context() as db:
        problems = await health.due_alerts(db)
        if not problems:
            return []
        out = []
        for settings in (await db.execute(select(SocialSettings))).scalars():
            notifications = settings.notifications or {}
            emails = list(notifications.get("emails") or [])
            if emails and notifications.get("notify_on_failure", True):
                out.append((str(settings.organization_id), emails, problems))
        return out


@celery_app.task(name="social.check_health", ignore_result=True)
def check_health_task() -> int:
    """Every 15 minutes: email once a day about a scheduled job that has failed or stopped running."""
    sent = 0
    for organization_id, recipients, problems in run_async(_problems_and_recipients()):
        for problem in problems:
            for address in recipients:
                subject, text, html = render_email_sync(
                    "social_job_problem",
                    {
                        "job": problem["label"][:120],
                        "state": "has failed" if problem["state"] == "failed" else "has stopped running",
                        "detail": problem["detail"][:500],
                        "overview_url": f"{app_settings.FRONTEND_URL.rstrip('/')}/social-media",
                    },
                    organization_id=organization_id,
                    recipient_email=address,
                )
                if run_async(email_service.send(address, subject, text, html)):
                    sent += 1
    return sent
