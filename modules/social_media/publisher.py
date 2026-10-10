"""
Publishing: scheduling, the worker that publishes, and the recovery that keeps it honest.

The database is the schedule. A post is "scheduled" with a time; once a minute the worker claims the posts that are due
with one atomic UPDATE (so two workers can never both take the same post) and publishes them. A restart, a crash or a
deployment loses nothing: whatever was waiting is still in the table, and whatever was half way is found by recovery.

The rule that prevents duplicate posts: creating Instagram containers can be repeated safely, but the one call that
creates the post is preceded by a committed note ("publish_started_at") on the attempt. After that point an unclear
result is never retried blindly. It is checked against Instagram (does the container say PUBLISHED? is the caption on the
profile?) and, if that can't settle it, the post is marked "publish_unknown" for a person to resolve.

A post is marked published only after Instagram has answered with the new media id (or the check proves it is there).
Nothing is ever silently dropped: every outcome is a status, an attempt record and, for problems, a notification.
"""

import asyncio
import io
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from PIL import Image
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.exceptions import ConflictError, ValidationError
from modules.social_media.safe_url import instagram_page
from app.core.logging_config import get_logger
from modules.social_media import instagram, render
from modules.social_media.checks import check_and_store
from modules.social_media.instagram import InstagramError
from modules.social_media.models import PostStatus, PublishAttempt, SocialAccount, SocialPost, SocialSettings, VerificationStatus
from modules.social_media.service import content_hash
from modules.social_media.token_crypto import TokenUnreadable, decrypt_token
from packages.storage.client import get_storage_client

logger = get_logger(__name__)

MIN_LEAD = timedelta(minutes=5)  # a schedule must be at least this far ahead
MAX_LEAD = timedelta(days=90)
GRACE = timedelta(minutes=60)  # a post that wakes up later than this was missed, and is not published stale
MAX_ATTEMPTS = 5
STUCK_AFTER = timedelta(minutes=10)  # a claim older than this with no result means a crash or restart
UNKNOWN_AFTER = timedelta(hours=1)  # recovery that can't settle a post for this long hands it to a person
CONTAINER_VALID = timedelta(hours=20)  # Instagram expires unused containers after 24 hours
BACKOFF_BASE = timedelta(minutes=1)
BACKOFF_CAP = timedelta(minutes=30)
POLL_TRIES = 6
POLL_DELAY = 5.0  # seconds between container status checks
CAPTION_LIMIT = 2200
MAX_JPEG_BYTES = 8 * 1024 * 1024
ACCOUNT_OK = ("connected", "expiring")
CLOSED_STATES = (PostStatus.PUBLISHED.value, PostStatus.CANCELLED.value)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def backoff(attempt: int, rng: random.Random | None = None) -> timedelta:
    """Wait before attempt number `attempt + 1`: 1, 2, 4, 8 ... minutes, capped, with +-20% jitter so retries spread out."""
    rng = rng or random
    base = min(BACKOFF_CAP, BACKOFF_BASE * (2 ** max(0, attempt - 1)))
    return base * rng.uniform(0.8, 1.2)


def compose_caption(post: SocialPost) -> str:
    """Exactly what is posted as the caption: the caption, the call to action, then the hashtags. Stories have none."""
    if post.format == "story":
        return ""
    content = post.content or {}
    parts = [str(content.get("caption") or "").strip(), str(content.get("cta") or "").strip()]
    tags = " ".join(f"#{t}" for t in content.get("hashtags") or [])
    if tags:
        parts.append(tags)
    return "\n\n".join(p for p in parts if p)


def local_to_utc(when: datetime, timezone_name: str) -> datetime:
    """A time typed without a zone is in the account timezone. A time that doesn't exist (the clocks jump forward) or
    happens twice (they go back) is refused rather than guessed."""
    if when.tzinfo is not None:
        return when.astimezone(timezone.utc)
    zone = ZoneInfo(timezone_name)
    local = when.replace(tzinfo=zone)
    if local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset():
        raise ValidationError(f"That time is ambiguous or doesn't exist in {timezone_name} (the clocks change then). Pick another time.")
    return local.astimezone(timezone.utc)


def to_jpeg(png: bytes) -> bytes:
    """Instagram only accepts JPEG images, so the PNG artwork is converted (flat colours, so quality 95 is lossless to the eye)."""
    image = Image.open(io.BytesIO(png)).convert("RGB")
    for quality in (95, 88, 80):
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=quality, optimize=True)
        if out.tell() <= MAX_JPEG_BYTES:
            return out.getvalue()
    raise ValidationError("The image is too large for Instagram even after compression.")


def absolute_url(url: str) -> str:
    return url if url.startswith("http") else app_settings.FRONTEND_URL.rstrip("/") + url


def notify_problem(post: SocialPost, problem: str, detail: str) -> None:
    """Tell the people who run the page (by email). Never raises: a notification problem must not hide the real one."""
    try:
        from modules.social_media.tasks import enqueue_problem_email

        enqueue_problem_email(post.id, problem, detail)
    except Exception:  # noqa: BLE001
        logger.warning("social_notify_failed", post_id=str(post.id), exc_info=True)


@dataclass
class Outcome:
    state: str  # published | not_published | unknown
    media_id: str | None = None
    permalink: str | None = None
    note: str = ""


class PublisherService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = get_storage_client()

    # ---------------- reading ----------------

    async def account(self, organization_id: uuid.UUID) -> SocialAccount | None:
        return (
            await self.db.execute(
                select(SocialAccount)
                .where(SocialAccount.organization_id == organization_id, SocialAccount.platform == "instagram")
                .order_by(SocialAccount.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def attempts(self, post_id: uuid.UUID, limit: int = 20) -> list[PublishAttempt]:
        rows = await self.db.execute(
            select(PublishAttempt).where(PublishAttempt.post_id == post_id).order_by(PublishAttempt.attempt_no.desc(), PublishAttempt.created_at.desc()).limit(limit)
        )
        return list(rows.scalars())

    async def _latest_attempt(self, post_id: uuid.UUID) -> PublishAttempt | None:
        return (
            await self.db.execute(
                select(PublishAttempt).where(PublishAttempt.post_id == post_id).order_by(PublishAttempt.attempt_no.desc(), PublishAttempt.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()

    # ---------------- is it publishable? ----------------

    def readiness(self, post: SocialPost, settings: SocialSettings, account: SocialAccount | None, now: datetime | None = None) -> list[str]:
        """Everything that stops this post from being published right now (empty = ready). Used when scheduling and
        again, with fresh data, just before publishing."""
        now = now or utcnow()
        problems: list[str] = []
        if not post.approved_content_hash or post.approved_content_hash != content_hash(post):
            problems.append("What is saved is not exactly what was approved. Approve it again.")
        if post.format == "reel":
            problems.append("Reels need a finished video, which can't be published yet. Only a script and cover exist.")
        art = post.artwork or {}
        files = art.get("files") or []
        if not files:
            problems.append("The post has no artwork. Make it first.")
        else:
            if not art.get("ok"):
                problems.append("The artwork doesn't meet the design rules.")
            content = post.content or {}
            pillar = next((p["label"] for p in settings.pillars or [] if p["key"] == post.pillar), None)
            current = render.current_fingerprint(post.format, content, post.design or {}, post.title, pillar, settings.brand or {})
            if current is None or current != art.get("fingerprint"):
                problems.append("The words or design changed after the artwork was made. Make the artwork again.")
            if post.format == "carousel":
                if not (2 <= len(files) <= 10) or len(files) != len(content.get("slides") or []):
                    problems.append("A carousel needs 2 to 10 pictures, one per slide.")
            elif len(files) != 1:
                problems.append("This format publishes exactly one picture.")
        caption = compose_caption(post)
        if len(caption) > CAPTION_LIMIT:
            problems.append(f"The caption with its call to action and hashtags is {len(caption)} characters; Instagram allows {CAPTION_LIMIT}.")
        if any(w.get("severity") == "blocking" for w in post.warnings or []):
            problems.append("The post has a blocking warning. Resolve it first.")
        if post.verification_status in (VerificationStatus.CONFLICTING.value, VerificationStatus.OUTDATED.value, VerificationStatus.UNVERIFIED.value):
            problems.append(f"The post's claims are marked {post.verification_status}.")
        problems.extend(self.account_problems(account, now))
        return problems

    @staticmethod
    def account_problems(account: SocialAccount | None, now: datetime) -> list[str]:
        if account is None:
            return ["Instagram isn't connected. Connect the account in Settings first."]
        problems = []
        if account.status not in ACCOUNT_OK:
            problems.append(f"The Instagram account needs attention (status: {account.status}). Reconnect it in Settings.")
        if not account.token_encrypted:
            problems.append("There is no Instagram access token. Reconnect the account.")
        elif account.token_expires_at and account.token_expires_at <= now:
            problems.append("The Instagram access token has expired. Reconnect the account.")
        if (account.capabilities or {}).get("publish") == "unavailable":
            problems.append("This Instagram account can't publish through the API (check it is a Professional account with publishing permission).")
        return problems

    # ---------------- people's actions ----------------

    def _check_time(self, settings: SocialSettings, when: datetime, now: datetime) -> datetime:
        at = local_to_utc(when, settings.timezone)
        if at < now + MIN_LEAD:
            raise ValidationError(f"Pick a time at least {int(MIN_LEAD.total_seconds() // 60)} minutes from now.")
        if at > now + MAX_LEAD:
            raise ValidationError("Pick a time within the next 90 days.")
        return at

    async def schedule(self, post: SocialPost, settings: SocialSettings, when: datetime, now: datetime | None = None) -> None:
        """approved (or already scheduled, to move it) -> scheduled for `when`."""
        now = now or utcnow()
        if settings.publish_mode != "scheduled":
            raise ValidationError("Scheduling is switched off: posts are published by hand. Change this under Settings > After a post is approved.")
        if post.status not in (PostStatus.APPROVED.value, PostStatus.SCHEDULED.value):
            raise ConflictError("Only an approved post can be scheduled.")
        at = self._check_time(settings, when, now)
        problems = self.readiness(post, settings, await self.account(post.organization_id), now)
        if problems:
            raise ValidationError("This post can't be scheduled yet: " + " ".join(problems))
        post.scheduled_at = at
        post.status = PostStatus.SCHEDULED.value
        post.attempt_count = 0
        post.next_attempt_at = None
        post.last_error = None
        await self.db.flush()

    async def unschedule(self, post: SocialPost) -> None:
        if post.status != PostStatus.SCHEDULED.value:
            raise ConflictError("Only a scheduled post that hasn't started publishing can be taken off the schedule.")
        post.status = PostStatus.APPROVED.value
        post.next_attempt_at = None
        await self.db.flush()

    async def publish_now(self, post: SocialPost, settings: SocialSettings, now: datetime | None = None) -> None:
        """An explicit click: publish this approved post as soon as the worker picks it up (within a minute)."""
        now = now or utcnow()
        if post.status not in (PostStatus.APPROVED.value, PostStatus.SCHEDULED.value):
            raise ConflictError("Only an approved post can be published.")
        problems = self.readiness(post, settings, await self.account(post.organization_id), now)
        if problems:
            raise ValidationError("This post can't be published yet: " + " ".join(problems))
        post.scheduled_at = now
        post.status = PostStatus.SCHEDULED.value
        post.attempt_count = 0
        post.next_attempt_at = None
        post.last_error = None
        await self.db.flush()

    async def retry(self, post: SocialPost, settings: SocialSettings, now: datetime | None = None) -> None:
        """A failed post (one that is certain not to be on Instagram) goes back in the queue, after a fresh readiness check."""
        now = now or utcnow()
        if post.status != PostStatus.FAILED.value:
            raise ConflictError("Only a failed post can be retried.")
        if not post.approved_content_hash:
            raise ValidationError("This post has to be approved again before it can be published.")
        problems = self.readiness(post, settings, await self.account(post.organization_id), now)
        if problems:
            raise ValidationError("This post can't be published yet: " + " ".join(problems))
        post.status = PostStatus.SCHEDULED.value
        post.scheduled_at = now
        post.attempt_count = 0
        post.next_attempt_at = None
        post.last_error = None
        await self.db.flush()

    async def resolve(self, post: SocialPost, published: bool, media_id: str | None, permalink: str | None, now: datetime | None = None) -> None:
        """A person looked at Instagram and says whether the post is there."""
        if post.status != PostStatus.PUBLISH_UNKNOWN.value:
            raise ConflictError("Only a post whose outcome is unclear needs to be resolved.")
        now = now or utcnow()
        attempt = await self._latest_attempt(post.id)
        if published:
            post.status = PostStatus.PUBLISHED.value
            post.published_at = now
            post.external_media_id = (media_id or None)
            post.external_permalink = instagram_page(permalink)
            post.last_error = None
            if attempt:
                attempt.status, attempt.finished_at, attempt.media_id = "published", now, media_id or None
        else:
            post.status = PostStatus.FAILED.value
            post.last_error = "A person confirmed the post is not on Instagram. It can be retried."
            if attempt:
                attempt.status, attempt.finished_at = "failed", now
        post.claimed_at = None
        await self.db.flush()

    async def reconcile(self, post: SocialPost) -> Outcome:
        """Ask Instagram what happened to a post with an unclear outcome and record the answer."""
        if post.status != PostStatus.PUBLISH_UNKNOWN.value:
            raise ConflictError("Only a post whose outcome is unclear can be reconciled.")
        attempt = await self._latest_attempt(post.id)
        client = await self._client(post.organization_id)
        outcome = await self._find_outcome(attempt, client)
        now = utcnow()
        if outcome.state == "published":
            await self._mark_published(post, attempt, outcome.media_id, outcome.permalink, now)
        elif outcome.state == "not_published":
            post.status = PostStatus.FAILED.value
            post.last_error = "Instagram confirms this post was not published. It can be retried."
            if attempt:
                attempt.status, attempt.finished_at = "failed", now
            post.claimed_at = None
        await self.db.flush()
        return outcome

    # ---------------- the worker ----------------

    async def due_post_ids(self, now: datetime | None = None, limit: int = 20) -> list[uuid.UUID]:
        now = now or utcnow()
        rows = await self.db.execute(
            select(SocialPost.id)
            .where(
                SocialPost.status == PostStatus.SCHEDULED.value,
                SocialPost.scheduled_at <= now,
                or_(SocialPost.next_attempt_at.is_(None), SocialPost.next_attempt_at <= now),
            )
            .order_by(SocialPost.scheduled_at)
            .limit(limit)
        )
        return list(rows.scalars())

    async def claim(self, post_id: uuid.UUID, now: datetime) -> SocialPost | None:
        """Take a due post for publishing with one atomic UPDATE: only one caller can ever win."""
        result = await self.db.execute(
            update(SocialPost)
            .where(
                SocialPost.id == post_id,
                SocialPost.status == PostStatus.SCHEDULED.value,
                SocialPost.scheduled_at <= now,
                or_(SocialPost.next_attempt_at.is_(None), SocialPost.next_attempt_at <= now),
            )
            .values(status=PostStatus.PUBLISHING.value, claimed_at=now, attempt_count=SocialPost.attempt_count + 1)
            .returning(SocialPost.id)
        )
        if result.first() is None:
            return None
        await self.db.commit()
        post = (await self.db.execute(select(SocialPost).where(SocialPost.id == post_id).execution_options(populate_existing=True))).scalar_one()
        return post

    async def run(self, post_id: uuid.UUID, now: datetime | None = None, user_id: uuid.UUID | None = None) -> str:
        """Claim one due post and publish it. Returns what happened (a short word, for logs and tests)."""
        now = now or utcnow()
        post = await self.claim(post_id, now)
        if post is None:
            return "skipped"
        settings = await self._settings(post.organization_id)
        # Numbered across the post's whole history (a retry by a person resets the counter that limits automatic retries,
        # but the record of what was tried keeps counting).
        previous = (await self._latest_attempt(post.id))
        attempt = PublishAttempt(
            organization_id=post.organization_id,
            post_id=post.id,
            triggered_by_user_id=user_id,
            attempt_no=(previous.attempt_no if previous else 0) + 1,
            status="started",
            idempotency_key=post.idempotency_key,
            caption=compose_caption(post),
        )
        self.db.add(attempt)
        await self.db.commit()

        if post.attempt_count == 1 and post.scheduled_at and now - post.scheduled_at > GRACE:
            minutes = int((now - post.scheduled_at).total_seconds() // 60)
            return await self._fail(post, attempt, "permanent", f"This post missed its time by {minutes} minutes (the server was down or busy), so it was not published late. Reschedule it.", "The post missed its time")

        account = await self.account(post.organization_id)
        problems = self.readiness(post, settings, account, now)
        if problems:
            return await self._fail(post, attempt, "permanent", "Not published: " + " ".join(problems), "The post could not be published")

        # Recheck the facts just before publishing: time-sensitive claims can go stale or be contradicted.
        await check_and_store(self.db, post.organization_id, post, settings)
        blocking = [w for w in post.warnings or [] if w.get("severity") == "blocking"]
        unreachable = [w for w in post.warnings or [] if w.get("code") == "chk_cve_unreachable"]
        if blocking or post.verification_status in (VerificationStatus.CONFLICTING.value, VerificationStatus.OUTDATED.value, VerificationStatus.UNVERIFIED.value):
            return await self._pause(post, attempt, blocking[0]["message"] if blocking else f"its claims are now marked {post.verification_status}")
        if unreachable and (post.time_sensitive or post.high_risk):
            return await self._retry_later(post, attempt, "The facts in this post couldn't be rechecked just before publishing (NVD was unreachable), so it was not published.", now)

        try:
            client = await self._client(post.organization_id, account)
        except (TokenUnreadable, InstagramError) as exc:
            return await self._token_failure(post, attempt, account, str(exc))
        try:
            return await self._publish(post, attempt, client, now)
        except InstagramError as exc:
            return await self._handle_error(post, attempt, account, exc, now)

    # ---- the publishing steps ----

    async def _publish(self, post: SocialPost, attempt: PublishAttempt, client: instagram.InstagramClient, now: datetime) -> str:
        art = post.artwork["files"]
        urls = []
        for index, file in enumerate(art):
            png = await self.storage.read_bytes(file["key"])
            jpg = to_jpeg(png)
            key = f"social/{post.organization_id}/posts/{post.id}/publish/{file['sha256'][:20]}.jpg"
            await self.storage.upload_bytes(key, jpg, "image/jpeg")
            url = absolute_url(self.storage.presigned_download_url(key))
            if any(host in url for host in ("localhost", "127.0.0.1")):
                raise InstagramError("permanent", "The picture's address isn't reachable from the internet (this is a local environment), so Instagram can't download it.")
            urls.append(url)

        container_ids = await self._containers(post, attempt, client, urls)
        parent = container_ids[-1]
        await self._wait_ready(client, container_ids)

        try:
            limit = await client.publishing_limit()
        except InstagramError as exc:
            if exc.kind == "token":
                raise
            limit = None  # the quota check is a courtesy; if it can't be read, publishing is still attempted
            logger.warning("social_limit_check_failed", post_id=str(post.id))
        if limit is not None and limit.exhausted:
            raise InstagramError("transient", f"Instagram's daily publishing limit has been reached ({limit.used} of {limit.total}). It will try again later.")

        # The point of no return, recorded BEFORE the call that creates the post.
        attempt.creation_id = parent
        attempt.publish_started_at = now
        await self.db.commit()

        media_id = await client.publish(parent)
        permalink = None
        try:
            permalink = await client.media_permalink(media_id)
        except InstagramError:
            logger.warning("social_permalink_failed", post_id=str(post.id))
        await self._mark_published(post, attempt, media_id, permalink, now)
        await self.db.commit()
        return "published"

    async def _containers(self, post: SocialPost, attempt: PublishAttempt, client: instagram.InstagramClient, urls: list[str]) -> list[str]:
        """Container ids for this post (children first, the one to publish last). A retry reuses the ones an earlier attempt
        made while Instagram still holds them, so a retry doesn't pile up orphans."""
        expected = len(urls) + (1 if post.format == "carousel" else 0)
        previous = await self._reusable_containers(post, client, expected)
        if previous:
            attempt.container_ids = previous
            await self.db.commit()
            return previous
        caption = attempt.caption or None
        alt = (post.content or {}).get("alt_text") or None
        ids: list[str] = []
        if post.format == "carousel":
            for url in urls:
                ids.append(await client.create_image_container(url, carousel_item=True))
                attempt.container_ids = list(ids)
                await self.db.commit()
            await self._wait_ready(client, ids)
            ids.append(await client.create_carousel_container(ids[:], caption or ""))
        else:
            ids.append(await client.create_image_container(urls[0], caption=caption, alt_text=alt, story=post.format == "story"))
        attempt.container_ids = list(ids)
        await self.db.commit()
        return ids

    async def _reusable_containers(self, post: SocialPost, client: instagram.InstagramClient, expected: int) -> list[str] | None:
        rows = await self.db.execute(
            select(PublishAttempt).where(PublishAttempt.post_id == post.id, PublishAttempt.status == "retry").order_by(PublishAttempt.attempt_no.desc()).limit(1)
        )
        previous = rows.scalar_one_or_none()
        if not previous or len(previous.container_ids or []) != expected or utcnow() - previous.created_at > CONTAINER_VALID:
            return None
        try:
            status = await client.container_status(previous.container_ids[-1])
        except InstagramError:
            return None
        return list(previous.container_ids) if status in (instagram.STATUS_FINISHED, instagram.STATUS_IN_PROGRESS) else None

    async def _wait_ready(self, client: instagram.InstagramClient, container_ids: list[str]) -> None:
        for container in container_ids:
            for attempt in range(POLL_TRIES):
                status = await client.container_status(container)
                if status == instagram.STATUS_FINISHED:
                    break
                if status in instagram.STATUS_FAILED:
                    raise InstagramError("permanent", f"Instagram couldn't process the picture (status {status}).")
                if status == instagram.STATUS_PUBLISHED:
                    break
                if attempt < POLL_TRIES - 1:
                    await asyncio.sleep(POLL_DELAY)
            else:
                raise InstagramError("transient", "Instagram is still processing the picture. It will try again shortly.")

    # ---- outcomes ----

    async def _handle_error(self, post: SocialPost, attempt: PublishAttempt, account: SocialAccount | None, exc: InstagramError, now: datetime) -> str:
        attempt.error_kind, attempt.error, attempt.http_status = exc.kind, exc.message[:600], exc.http_status
        if exc.kind == "token":
            return await self._token_failure(post, attempt, account, exc.message)
        if exc.kind == "permanent":
            return await self._fail(post, attempt, "permanent", exc.message, "Instagram rejected a post")
        if exc.kind == "ambiguous":
            return await self._ambiguous(post, attempt, account, exc, now)
        # transient: if the post-creating call was the one that failed, Instagram refused it outright, so it is safe to try again
        attempt.publish_started_at = None
        return await self._retry_later(post, attempt, exc.message, now)

    async def _ambiguous(self, post: SocialPost, attempt: PublishAttempt, account: SocialAccount | None, exc: InstagramError, now: datetime) -> str:
        """The publish call may or may not have worked. Check; never just try again."""
        try:
            client = await self._client(post.organization_id, account)
            outcome = await self._find_outcome(attempt, client)
        except (InstagramError, TokenUnreadable):
            outcome = Outcome("unknown")
        if outcome.state == "published":
            await self._mark_published(post, attempt, outcome.media_id, outcome.permalink, now)
            await self.db.commit()
            return "published"
        if outcome.state == "not_published":
            attempt.publish_started_at = None
            return await self._retry_later(post, attempt, "Instagram did not publish it the first time (checked). Trying again.", now)
        post.status = PostStatus.PUBLISH_UNKNOWN.value
        post.last_error = exc.message + " Check the Instagram profile, then resolve it in the queue."
        attempt.status, attempt.finished_at = "unknown", now
        post.claimed_at = None
        await self.db.commit()
        notify_problem(post, "A post's outcome can't be confirmed", post.last_error)
        return "unknown"

    async def _find_outcome(self, attempt: PublishAttempt | None, client: instagram.InstagramClient) -> Outcome:
        """Whether Instagram published this attempt's container, from what Instagram itself says."""
        if attempt is None or not attempt.creation_id:
            return Outcome("unknown", note="No publish attempt was recorded.")
        try:
            status = await client.container_status(attempt.creation_id)
        except InstagramError as exc:
            if exc.kind == "permanent" and exc.http_status in (400, 404):
                return Outcome("unknown", note="Instagram no longer knows the container.")
            return Outcome("unknown", note=exc.message)
        if status == instagram.STATUS_PUBLISHED:
            media_id, permalink = None, None
            try:
                wanted = (attempt.caption or "").strip()
                since = (attempt.publish_started_at or attempt.created_at) - timedelta(minutes=5)
                for item in await client.recent_media(25):
                    stamp = _parse_ts(item.get("timestamp"))
                    if stamp and stamp >= since and (not wanted or str(item.get("caption") or "").strip() == wanted):
                        media_id, permalink = str(item.get("id")), item.get("permalink")
                        break
            except InstagramError:
                pass
            return Outcome("published", media_id, permalink, "Instagram reports the container as published.")
        if status in (instagram.STATUS_FINISHED, instagram.STATUS_IN_PROGRESS) or status in instagram.STATUS_FAILED:
            return Outcome("not_published", note=f"The container is {status}, so it was not published.")
        return Outcome("unknown", note=f"Unexpected container status: {status or 'none'}.")

    async def _mark_published(self, post: SocialPost, attempt: PublishAttempt | None, media_id: str | None, permalink: str | None, now: datetime) -> None:
        post.status = PostStatus.PUBLISHED.value
        post.published_at = now
        post.external_media_id = media_id
        post.external_permalink = instagram_page(permalink)
        post.last_error = None
        post.next_attempt_at = None
        post.claimed_at = None
        if attempt:
            attempt.status, attempt.finished_at, attempt.media_id = "published", now, media_id

    async def _retry_later(self, post: SocialPost, attempt: PublishAttempt, message: str, now: datetime) -> str:
        attempt.error = message[:600]
        attempt.finished_at = now
        if post.attempt_count >= MAX_ATTEMPTS:
            return await self._fail(post, attempt, "transient", f"Gave up after {post.attempt_count} attempts. Last problem: {message}", "A post failed to publish")
        wait = backoff(post.attempt_count)
        attempt.status = "retry"
        post.status = PostStatus.SCHEDULED.value
        post.next_attempt_at = now + wait
        post.last_error = f"{message} Trying again at {(now + wait).strftime('%H:%M')} UTC (attempt {post.attempt_count} of {MAX_ATTEMPTS})."
        post.claimed_at = None
        await self.db.commit()
        return "retry"

    async def _fail(self, post: SocialPost, attempt: PublishAttempt | None, kind: str, message: str, problem: str) -> str:
        post.status = PostStatus.FAILED.value
        post.last_error = message[:500]
        post.claimed_at = None
        post.next_attempt_at = None
        if attempt:
            attempt.status, attempt.error_kind, attempt.error, attempt.finished_at = "failed", kind, message[:600], utcnow()
        await self.db.commit()
        notify_problem(post, problem, message)
        return "failed"

    async def _pause(self, post: SocialPost, attempt: PublishAttempt, reason: str) -> str:
        """Claims turned out to be wrong or out of date just before publishing: hold the post, don't publish it."""
        post.status = PostStatus.DRAFT.value
        post.approved_by_user_id = None
        post.approved_at = None
        post.approved_content_hash = None
        post.claimed_at = None
        post.next_attempt_at = None
        post.last_error = f"Paused before publishing: {reason}"[:500]
        post.warnings = [*post.warnings, {"severity": "warning", "code": "chk_paused_before_publish", "message": f"Paused before publishing: {reason}"[:590]}]
        attempt.status, attempt.finished_at, attempt.error = "paused", utcnow(), post.last_error
        await self.db.commit()
        notify_problem(post, "A scheduled post was paused", post.last_error)
        return "paused"

    async def _token_failure(self, post: SocialPost, attempt: PublishAttempt, account: SocialAccount | None, message: str) -> str:
        if account is not None:
            account.status = "expired"
            account.last_error = message[:500]
        return await self._fail(post, attempt, "token", f"{message} Reconnect the Instagram account, then retry the post.", "The Instagram connection needs attention")

    # ---------------- recovery ----------------

    async def recover(self, now: datetime | None = None) -> dict[str, int]:
        """Posts stuck in "publishing" (a crash, a restart, a deployment) are settled: put back if nothing was sent,
        checked against Instagram if the post-creating call may have been sent, and handed to a person if that can't be settled."""
        now = now or utcnow()
        result = {"requeued": 0, "published": 0, "unknown": 0, "waiting": 0}
        rows = await self.db.execute(select(SocialPost).where(SocialPost.status == PostStatus.PUBLISHING.value, SocialPost.claimed_at <= now - STUCK_AFTER))
        for post in rows.scalars().all():
            attempt = await self._latest_attempt(post.id)
            if attempt is None or attempt.publish_started_at is None:
                if post.attempt_count >= MAX_ATTEMPTS:
                    await self._fail(post, attempt, "transient", "The worker stopped while publishing too many times. Check the connection and retry.", "A post failed to publish")
                else:
                    post.status = PostStatus.SCHEDULED.value
                    post.next_attempt_at = now
                    post.claimed_at = None
                    if attempt:
                        attempt.status, attempt.error, attempt.finished_at = "retry", "Interrupted before anything was published.", now
                    await self.db.commit()
                result["requeued"] += 1
                continue
            try:
                client = await self._client(post.organization_id)
                outcome = await self._find_outcome(attempt, client)
            except (InstagramError, TokenUnreadable):
                outcome = Outcome("unknown")
            if outcome.state == "published":
                await self._mark_published(post, attempt, outcome.media_id, outcome.permalink, now)
                await self.db.commit()
                result["published"] += 1
            elif outcome.state == "not_published":
                post.status = PostStatus.SCHEDULED.value
                post.next_attempt_at = now
                post.claimed_at = None
                attempt.publish_started_at = None
                attempt.status, attempt.error, attempt.finished_at = "retry", "Interrupted; Instagram confirms it was not published.", now
                await self.db.commit()
                result["requeued"] += 1
            elif now - post.claimed_at >= UNKNOWN_AFTER:
                post.status = PostStatus.PUBLISH_UNKNOWN.value
                post.last_error = "The worker stopped while publishing and Instagram couldn't confirm the result. Check the profile, then resolve it in the queue."
                post.claimed_at = None
                attempt.status, attempt.finished_at = "unknown", now
                await self.db.commit()
                notify_problem(post, "A post's outcome can't be confirmed", post.last_error)
                result["unknown"] += 1
            else:
                result["waiting"] += 1
        return result

    # ---------------- helpers ----------------

    async def _settings(self, organization_id: uuid.UUID) -> SocialSettings:
        from modules.social_media.service import SettingsService

        return await SettingsService(self.db).get(organization_id)

    async def _client(self, organization_id: uuid.UUID, account: SocialAccount | None = None) -> instagram.InstagramClient:
        account = account or await self.account(organization_id)
        if account is None or not account.token_encrypted:
            raise InstagramError("token", "Instagram isn't connected.")
        return instagram.get_instagram_client(account.external_account_id, decrypt_token(account.token_encrypted))


def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00").replace("+0000", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
