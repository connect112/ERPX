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
from modules.social_media.models import SocialPost, SocialSettings
from modules.social_media.publisher import PublisherService
from packages.email.service import email_service

logger = get_logger(__name__)


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
    return run_async(_queue_due())


@celery_app.task(name="social.publish_post", ignore_result=True)
def publish_post_task(post_id: str, user_id: str | None = None) -> str:
    outcome = run_async(_publish(uuid.UUID(post_id), uuid.UUID(user_id) if user_id else None))
    logger.info("social_publish_finished", post_id=post_id, outcome=outcome)
    return outcome


@celery_app.task(name="social.recover_publishing", ignore_result=True)
def recover_publishing_task() -> dict:
    result = run_async(_recover())
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
