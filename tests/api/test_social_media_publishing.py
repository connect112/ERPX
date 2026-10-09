"""
Social Media phase 3: scheduling, the publishing worker, recovery and the calendar.

Instagram is a scripted fake, so none of this proves the real API accepts these calls; it proves what ERPX does with every
kind of answer: a post is published once or not at all, an unclear result is checked and never retried blindly, nothing is
dropped silently, and every problem is a status and a notification.
"""

import io
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from PIL import Image
from sqlalchemy import select

from modules.social_media import instagram, publisher, tasks
from modules.social_media.instagram import InstagramError, PublishLimit
from modules.social_media.models import PublishAttempt, SocialAccount, SocialPost
from modules.social_media.publisher import PublisherService, backoff, compose_caption, local_to_utc, to_jpeg
from modules.social_media.token_crypto import TokenUnreadable, decrypt_token, encrypt_token
from packages.storage import client as storage_client
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"
NOW = datetime.now(timezone.utc).replace(microsecond=0)


# ---------------- fakes ----------------


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    async def upload_bytes(self, key, data, content_type="application/octet-stream"):
        self.objects[key] = data

    async def read_bytes(self, key, max_bytes=20 * 1024 * 1024):
        return self.objects[key]

    async def delete_object(self, key):
        self.objects.pop(key, None)

    def presigned_download_url(self, key):
        return f"https://files.test/{key}"


class FakeInstagram:
    """A scripted Instagram. `errors[method]` is a list consumed in order (None = succeed this time)."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.statuses: dict[str, str] = {}
        self.errors: dict[str, list] = {}
        self.media: list[dict] = []
        self.limit = PublishLimit(0, 100)
        self.counter = 0

    def _fail(self, method):
        queue = self.errors.get(method)
        if queue:
            error = queue.pop(0)
            if error:
                raise error

    def called(self, name):
        return [kwargs for method, kwargs in self.calls if method == name]

    async def create_image_container(self, image_url, caption=None, alt_text=None, story=False, carousel_item=False):
        self.calls.append(("create_image_container", {"image_url": image_url, "caption": caption, "alt_text": alt_text, "story": story, "carousel_item": carousel_item}))
        self._fail("create_image_container")
        self.counter += 1
        return f"c{self.counter}"

    async def create_carousel_container(self, children, caption):
        self.calls.append(("create_carousel_container", {"children": list(children), "caption": caption}))
        self._fail("create_carousel_container")
        self.counter += 1
        return f"c{self.counter}"

    async def container_status(self, container_id):
        self.calls.append(("container_status", {"id": container_id}))
        self._fail("container_status")
        return self.statuses.get(container_id, "FINISHED")

    async def publish(self, creation_id):
        self.calls.append(("publish", {"creation_id": creation_id}))
        self._fail("publish")
        self.statuses[creation_id] = "PUBLISHED"
        return "m1"

    async def media_permalink(self, media_id):
        self.calls.append(("media_permalink", {"id": media_id}))
        self._fail("media_permalink")
        return "https://www.instagram.com/p/abc123/"

    async def recent_media(self, limit=20):
        self.calls.append(("recent_media", {}))
        self._fail("recent_media")
        return self.media

    async def publishing_limit(self):
        self.calls.append(("publishing_limit", {}))
        self._fail("publishing_limit")
        return self.limit


@pytest.fixture
def storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(storage_client, "_client", fake)
    return fake


@pytest.fixture
def ig(monkeypatch):
    fake = FakeInstagram()
    monkeypatch.setattr(instagram, "get_instagram_client", lambda ig_user_id, token: fake)
    monkeypatch.setattr(publisher, "POLL_DELAY", 0)
    return fake


@pytest.fixture
def notified(monkeypatch):
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(publisher, "notify_problem", lambda post, problem, detail: sent.append((str(post.id), problem, detail)))
    enqueued: list[uuid.UUID] = []
    monkeypatch.setattr("modules.social_media.publish_routes.enqueue_publish", lambda post_id, user_id=None: enqueued.append(post_id) or True)
    sent_enqueued = type("Box", (), {"problems": sent, "enqueued": enqueued})
    return sent_enqueued


# ---------------- helpers ----------------


async def _account(db_session, organization, **kw):
    values = dict(
        organization_id=organization.id,
        external_account_id="17841400000000000",
        username="pentrix",
        status="connected",
        token_encrypted=encrypt_token("test-token"),
        token_expires_at=NOW + timedelta(days=30),
        connected_at=NOW,
        capabilities={},
    )
    values.update(kw)
    existing = (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == organization.id))).scalar_one_or_none()
    if existing is not None:  # a test that makes several posts shares one connected account
        return existing
    account = SocialAccount(**values)
    db_session.add(account)
    await db_session.flush()
    return account


async def _settings(client, headers, **kw):
    response = await client.put(f"{_BASE}/settings", json=kw, headers=headers)
    assert response.status_code == 200, response.text


async def _approved(client, headers, fmt="image", extra=None, mode="scheduled"):
    await _settings(client, headers, publish_mode=mode)
    content = {"headline": "Why logs matter", "caption": "Logs tell the story of an attack.", "cta": "Save this.", "hashtags": ["SIEM", "SOC"], "alt_text": "Text on a plain background."}
    if fmt == "carousel":
        content["slides"] = [{"heading": "One", "body": "First point."}, {"heading": "Two", "body": "Second point."}]
    body = {"title": "t", "format": fmt, "pillar": "soc", "content": content}
    body.update(extra or {})
    post = (await client.post(f"{_BASE}/posts", json=body, headers=headers)).json()
    rendered = await client.post(f"{_BASE}/posts/{post['id']}/render", headers=headers)
    assert rendered.status_code == 200, rendered.text
    await client.post(f"{_BASE}/posts/{post['id']}/check", headers=headers)
    await client.post(f"{_BASE}/posts/{post['id']}/transition", json={"action": "submit"}, headers=headers)
    approved = await client.post(f"{_BASE}/posts/{post['id']}/transition", json={"action": "approve", "acknowledge_warnings": True}, headers=headers)
    assert approved.status_code == 200, approved.text
    return approved.json()


async def _schedule(client, headers, post_id, when=None):
    when = when or NOW + timedelta(hours=2)
    return await client.post(f"{_BASE}/posts/{post_id}/schedule", json={"scheduled_at": when.isoformat()}, headers=headers)


async def _row(db_session, post_id):
    row = (await db_session.execute(select(SocialPost).where(SocialPost.id == uuid.UUID(post_id)))).scalar_one()
    await db_session.refresh(row)
    return row


async def _attempts(db_session, post_id):
    rows = await db_session.execute(select(PublishAttempt).where(PublishAttempt.post_id == uuid.UUID(post_id)).order_by(PublishAttempt.attempt_no, PublishAttempt.created_at))
    result = list(rows.scalars())
    for r in result:
        await db_session.refresh(r)
    return result


async def _ready(client, headers, db_session, organization, fmt="image", scheduled_for=None):
    """An approved, scheduled post and an account that can publish it. Returns (post_id, the time to run the worker at)."""
    await _account(db_session, organization)
    post = await _approved(client, headers, fmt)
    when = scheduled_for or NOW + timedelta(hours=2)
    response = await _schedule(client, headers, post["id"], when)
    assert response.status_code == 200, response.text
    return post["id"], when + timedelta(minutes=1)


async def _run(db_session, post_id, at):
    return await PublisherService(db_session).run(uuid.UUID(post_id), now=at)


def _transient(message="Instagram is busy."):
    return InstagramError("transient", message, http_status=503)


def _ambiguous():
    return InstagramError("ambiguous", "Instagram didn't answer in time, so it isn't known whether the post was created.")


# ---------------- small pieces ----------------


def test_the_caption_is_exactly_what_will_be_posted():
    class P:
        format = "image"
        content = {"caption": " A caption. ", "cta": "Save it.", "hashtags": ["SIEM", "SOC"]}

    assert compose_caption(P) == "A caption.\n\nSave it.\n\n#SIEM #SOC"
    P.content = {"caption": "Only this."}
    assert compose_caption(P) == "Only this."
    P.format = "story"
    assert compose_caption(P) == ""


def test_backoff_doubles_is_capped_and_is_jittered():
    rng = random.Random(1)
    waits = [backoff(n, rng) for n in range(1, 9)]
    assert all(timedelta(minutes=0.8) <= w <= timedelta(minutes=36) for w in waits)
    assert waits[0] < timedelta(minutes=1.3) and waits[2] > timedelta(minutes=3) and max(waits) <= timedelta(minutes=36)
    assert len({round(backoff(3, rng).total_seconds()) for _ in range(20)}) > 5, "retries are spread out"


def test_times_are_read_in_the_account_timezone_and_clock_changes_are_refused():
    assert local_to_utc(datetime(2026, 12, 1, 9, 0), "Asia/Kolkata") == datetime(2026, 12, 1, 3, 30, tzinfo=timezone.utc)
    assert local_to_utc(datetime(2026, 12, 1, 9, 0, tzinfo=timezone(timedelta(hours=2))), "Asia/Kolkata") == datetime(2026, 12, 1, 7, 0, tzinfo=timezone.utc)
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="ambiguous"):
        local_to_utc(datetime(2026, 11, 1, 1, 30), "America/New_York")  # the clocks go back: 1:30 happens twice
    with pytest.raises(ValidationError, match="doesn't exist"):
        local_to_utc(datetime(2027, 3, 14, 2, 30), "America/New_York")  # the clocks jump forward


def test_pictures_are_converted_to_jpeg_because_instagram_accepts_nothing_else():
    out = io.BytesIO()
    Image.new("RGBA", (400, 500), (10, 20, 30, 255)).save(out, format="PNG")
    jpg = to_jpeg(out.getvalue())
    assert jpg[:3] == b"\xff\xd8\xff" and Image.open(io.BytesIO(jpg)).format == "JPEG"


def test_a_relative_storage_address_becomes_a_public_one(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "FRONTEND_URL", "https://erp.example.com/")
    assert publisher.absolute_url("/_files/erpx/x.jpg?sig=1") == "https://erp.example.com/_files/erpx/x.jpg?sig=1"
    assert publisher.absolute_url("https://cdn.example.com/x.jpg") == "https://cdn.example.com/x.jpg"


def test_tokens_are_encrypted_and_a_changed_key_makes_them_unreadable(monkeypatch):
    from app.core.config import settings

    stored = encrypt_token("secret-access-token")
    assert "secret-access-token" not in stored and decrypt_token(stored) == "secret-access-token"
    with pytest.raises(TokenUnreadable):
        decrypt_token(stored[:-4] + "AAAA")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "another-secret-another-secret-another!")
    with pytest.raises(TokenUnreadable):
        decrypt_token(stored)


@pytest.mark.parametrize(
    "status, body, kind",
    [
        (400, {"error": {"code": 190, "message": "token"}}, "token"),
        (401, None, "token"),
        (400, {"error": {"code": 9004, "message": "Only photo or video can be accepted as media type."}}, "permanent"),
        (400, {"error": {"code": 36003, "message": "aspect ratio"}}, "permanent"),
        (403, {"error": {"code": 10, "message": "no permission"}}, "permanent"),
        (400, {"error": {"code": 4, "message": "rate"}}, "transient"),
        (400, {"error": {"code": 100, "message": "x", "is_transient": True}}, "transient"),
        (429, None, "transient"),
        (502, None, "transient"),
    ],
)
def test_instagram_errors_are_sorted_by_what_to_do_about_them(status, body, kind):
    assert instagram.classify(status, body)[0] == kind


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._payload = status, payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _http(monkeypatch, behaviour):
    seen = {}

    class Http:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, method, url, data=None, params=None, headers=None):
            seen.update(method=method, url=url, data=data, params=params, headers=headers)
            result = behaviour()
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr(instagram.httpx, "AsyncClient", Http)
    return seen


async def test_a_timeout_while_creating_is_transient_but_while_publishing_it_is_ambiguous(monkeypatch):
    client = instagram.InstagramClient("123", "tok")
    _http(monkeypatch, lambda: httpx.ReadTimeout("slow"))
    with pytest.raises(InstagramError) as creating:
        await client.create_image_container("https://x/y.jpg")
    assert creating.value.kind == "transient"
    with pytest.raises(InstagramError) as publishing:
        await client.publish("c1")
    assert publishing.value.kind == "ambiguous"
    _http(monkeypatch, lambda: httpx.ConnectError("broken"))
    with pytest.raises(InstagramError) as broken:
        await client.publish("c1")
    assert broken.value.kind == "ambiguous"
    _http(monkeypatch, lambda: _Resp(500, {"error": {"message": "oops"}}))
    with pytest.raises(InstagramError) as server:
        await client.publish("c1")
    assert server.value.kind == "ambiguous", "a server error while publishing doesn't prove nothing was created"
    with pytest.raises(InstagramError) as read:
        await client.container_status("c1")
    assert read.value.kind == "transient"
    _http(monkeypatch, lambda: _Resp(200, {"unexpected": True}))
    with pytest.raises(InstagramError) as noid:
        await client.publish("c1")
    assert noid.value.kind == "ambiguous"


async def test_the_token_goes_in_a_header_never_in_the_url_or_the_error(monkeypatch):
    client = instagram.InstagramClient("123", "super-secret-token")
    seen = _http(monkeypatch, lambda: _Resp(200, {"id": "c9"}))
    assert await client.create_image_container("https://x/y.jpg", caption="hi", alt_text="alt") == "c9"
    assert seen["headers"]["Authorization"] == "Bearer super-secret-token"
    assert "super-secret-token" not in seen["url"] and "super-secret-token" not in str(seen["params"]) and "super-secret-token" not in str(seen["data"])
    assert seen["data"] == {"image_url": "https://x/y.jpg", "caption": "hi", "alt_text": "alt"} and seen["url"].endswith("/123/media")
    _http(monkeypatch, lambda: _Resp(400, {"error": {"code": 9004, "message": "bad image super-secret-token"}}))
    with pytest.raises(InstagramError) as exc:
        await client.create_image_container("https://x/y.jpg")
    assert "super-secret-token" not in exc.value.message and exc.value.kind == "permanent"


async def test_a_story_and_a_carousel_item_are_requested_the_way_instagram_documents(monkeypatch):
    client = instagram.InstagramClient("123", "t")
    seen = _http(monkeypatch, lambda: _Resp(200, {"id": "c1"}))
    await client.create_image_container("https://x/s.jpg", story=True, alt_text="ignored for stories")
    assert seen["data"] == {"image_url": "https://x/s.jpg", "media_type": "STORIES"}
    await client.create_image_container("https://x/i.jpg", caption="no caption on children", carousel_item=True)
    assert seen["data"] == {"image_url": "https://x/i.jpg", "is_carousel_item": "true"}
    await client.create_carousel_container(["c1", "c2"], "cap")
    assert seen["data"] == {"media_type": "CAROUSEL", "children": "c1,c2", "caption": "cap"}
    _http(monkeypatch, lambda: _Resp(200, {"data": [{"quota_usage": 7, "config": {"quota_total": 100}}]}))
    limit = await client.publishing_limit()
    assert (limit.used, limit.total, limit.exhausted) == (7, 100, False)


# ---------------- scheduling ----------------


async def test_scheduling_needs_the_publish_permission_and_scheduled_mode(client, auth_headers, db_session, organization, storage, ig, rbac_seeded):
    from modules.authorization.service import AuthorizationService

    await _account(db_session, organization)
    post = await _approved(client, auth_headers, mode="manual")
    user, token = await _make_user(db_session, organization, is_superuser=False, email=f"mgr-{uuid.uuid4().hex[:6]}@erpx.example.com")
    service = AuthorizationService(db_session)
    role = await service.create_role(organization.id, "Social manager", f"sm-{uuid.uuid4().hex[:6]}", None)
    await service.set_role_permissions(role.id, organization.id, ["social_media.view", "social_media.manage", "social_media.approve"])
    await service.assign_role(user.id, role.id, organization.id, None)
    manager = {"Authorization": f"Bearer {token}"}
    for path in ("schedule", "unschedule", "publish-now", "retry", "reconcile", "resolve"):
        body = {"scheduled_at": (NOW + timedelta(hours=2)).isoformat()} if path == "schedule" else {"published": True} if path == "resolve" else None
        assert (await client.post(f"{_BASE}/posts/{post['id']}/{path}", json=body, headers=manager)).status_code == 403, path
    off = await _schedule(client, auth_headers, post["id"])
    assert off.status_code == 422 and "switched off" in off.text
    await _settings(client, auth_headers, publish_mode="scheduled")
    ok = await _schedule(client, auth_headers, post["id"])
    assert ok.status_code == 200 and ok.json()["status"] == "scheduled"
    assert datetime.fromisoformat(ok.json()["scheduled_at"]) == NOW + timedelta(hours=2)


async def test_only_an_approved_post_in_the_future_can_be_scheduled(client, auth_headers, db_session, organization, storage, ig):
    await _account(db_session, organization)
    await _settings(client, auth_headers, publish_mode="scheduled")
    draft = (await client.post(f"{_BASE}/posts", json={"title": "d", "content": {"caption": "c"}}, headers=auth_headers)).json()
    assert (await _schedule(client, auth_headers, draft["id"])).status_code == 409
    post = await _approved(client, auth_headers)
    assert "at least 5 minutes" in (await _schedule(client, auth_headers, post["id"], NOW + timedelta(minutes=1))).text
    assert "within the next 90 days" in (await _schedule(client, auth_headers, post["id"], NOW + timedelta(days=120))).text
    assert (await _schedule(client, auth_headers, post["id"], NOW - timedelta(days=1))).status_code == 422
    naive = await client.post(f"{_BASE}/posts/{post['id']}/schedule", json={"scheduled_at": (NOW + timedelta(days=3)).replace(tzinfo=None, hour=9, minute=0, second=0).isoformat()}, headers=auth_headers)
    assert naive.status_code == 200
    local = datetime.fromisoformat(naive.json()["scheduled_at"]).astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert (local.hour, local.minute) == (9, 0), "a time typed without a zone is read in the account timezone (Asia/Kolkata)"


async def test_a_time_that_the_clocks_make_ambiguous_is_refused(client, auth_headers, db_session, organization, storage, ig):
    await _account(db_session, organization)
    post = await _approved(client, auth_headers)
    await _settings(client, auth_headers, timezone="America/New_York")
    response = await client.post(f"{_BASE}/posts/{post['id']}/schedule", json={"scheduled_at": "2026-11-01T01:30:00"}, headers=auth_headers)
    assert response.status_code == 422 and "ambiguous" in response.text


async def test_scheduling_is_refused_with_a_reason_when_something_would_stop_it(client, auth_headers, db_session, organization, storage, ig):
    await _settings(client, auth_headers, publish_mode="scheduled")
    post = await _approved(client, auth_headers)
    no_account = await _schedule(client, auth_headers, post["id"])
    assert no_account.status_code == 422 and "isn't connected" in no_account.text
    account = await _account(db_session, organization, token_expires_at=NOW - timedelta(days=1))
    assert "token has expired" in (await _schedule(client, auth_headers, post["id"])).text
    account.token_expires_at, account.status = NOW + timedelta(days=5), "revoked"
    await db_session.flush()
    assert "needs attention" in (await _schedule(client, auth_headers, post["id"])).text
    account.status, account.token_encrypted = "connected", None
    await db_session.flush()
    assert "no Instagram access token" in (await _schedule(client, auth_headers, post["id"])).text
    account.token_encrypted = encrypt_token("t")
    await db_session.flush()
    assert (await _schedule(client, auth_headers, post["id"])).status_code == 200


async def test_reels_posts_without_artwork_and_stale_artwork_cannot_be_scheduled(client, auth_headers, db_session, organization, storage, ig):
    await _account(db_session, organization)
    await _settings(client, auth_headers, publish_mode="scheduled")
    reel = await _approved(client, auth_headers, fmt="reel")
    refused = await _schedule(client, auth_headers, reel["id"])
    assert refused.status_code == 422 and "finished video" in refused.text
    bare = (await client.post(f"{_BASE}/posts", json={"title": "b", "content": {"caption": "c"}}, headers=auth_headers)).json()
    await client.post(f"{_BASE}/posts/{bare['id']}/transition", json={"action": "submit"}, headers=auth_headers)
    await client.post(f"{_BASE}/posts/{bare['id']}/transition", json={"action": "approve", "acknowledge_warnings": True}, headers=auth_headers)
    assert "no artwork" in (await _schedule(client, auth_headers, bare["id"])).text.lower()
    post = await _approved(client, auth_headers)
    row = await _row(db_session, post["id"])
    row.content = {**row.content, "headline": "A changed headline"}  # changed behind the approval's back
    await db_session.flush()
    stale = await _schedule(client, auth_headers, post["id"])
    assert stale.status_code == 422 and "exactly what was approved" in stale.text


async def test_a_caption_over_instagrams_limit_with_its_cta_and_hashtags_is_refused(client, auth_headers, db_session, organization, storage, ig):
    await _account(db_session, organization)
    await _settings(client, auth_headers, publish_mode="scheduled")
    long = await _approved(client, auth_headers, extra={"content": {"headline": "Why logs matter", "caption": "x" * 2150, "cta": "y" * 80, "hashtags": ["SIEM"]}})
    refused = await _schedule(client, auth_headers, long["id"])
    assert refused.status_code == 422 and "Instagram allows 2200" in refused.text
    info = (await client.get(f"{_BASE}/posts/{long['id']}/readiness", headers=auth_headers)).json()
    assert info["ready"] is False and info["caption_length"] > 2200 and info["caption_limit"] == 2200


async def test_readiness_shows_the_exact_caption_and_what_is_missing(client, auth_headers, db_session, organization, storage, ig):
    post = await _approved(client, auth_headers)
    info = (await client.get(f"{_BASE}/posts/{post['id']}/readiness", headers=auth_headers)).json()
    assert info["caption"] == "Logs tell the story of an attack.\n\nSave this.\n\n#SIEM #SOC" and info["account_connected"] is False
    assert any("isn't connected" in p for p in info["problems"]) and info["ready"] is False
    await _account(db_session, organization)
    assert (await client.get(f"{_BASE}/posts/{post['id']}/readiness", headers=auth_headers)).json()["ready"] is True


async def test_the_planned_time_is_not_part_of_what_was_approved(client, auth_headers, db_session, organization, storage, ig):
    post = await _approved(client, auth_headers)
    moved = await client.patch(f"{_BASE}/posts/{post['id']}", json={"scheduled_at": (NOW + timedelta(days=2)).isoformat()}, headers=auth_headers)
    assert moved.json()["status"] == "approved" and moved.json()["approval_withdrawn"] is False
    await _account(db_session, organization)
    assert (await _schedule(client, auth_headers, post["id"])).status_code == 200, "scheduling doesn't invalidate the approval"
    row = await _row(db_session, post["id"])
    from modules.social_media.service import content_hash

    assert row.approved_content_hash == content_hash(row)


async def test_unscheduling_and_rescheduling(client, auth_headers, db_session, organization, storage, ig):
    post_id, _ = await _ready(client, auth_headers, db_session, organization)
    moved = await _schedule(client, auth_headers, post_id, NOW + timedelta(hours=5))
    assert moved.status_code == 200 and datetime.fromisoformat(moved.json()["scheduled_at"]) == NOW + timedelta(hours=5)
    off = await client.post(f"{_BASE}/posts/{post_id}/unschedule", headers=auth_headers)
    assert off.json()["status"] == "approved"
    assert (await client.post(f"{_BASE}/posts/{post_id}/unschedule", headers=auth_headers)).status_code == 409
    row = await _row(db_session, post_id)
    row.status = "publishing"
    await db_session.flush()
    assert (await client.post(f"{_BASE}/posts/{post_id}/unschedule", headers=auth_headers)).status_code == 409, "a post that has started publishing can't be pulled back"


async def test_publish_now_is_an_explicit_click_that_works_in_manual_mode_too(client, auth_headers, db_session, organization, storage, ig, notified):
    await _account(db_session, organization)
    draft = (await client.post(f"{_BASE}/posts", json={"title": "d", "content": {"caption": "c"}}, headers=auth_headers)).json()
    assert (await client.post(f"{_BASE}/posts/{draft['id']}/publish-now", headers=auth_headers)).status_code == 409
    post = await _approved(client, auth_headers, mode="manual")
    assert (await _schedule(client, auth_headers, post["id"])).status_code == 422  # scheduling is off in manual mode
    now = await client.post(f"{_BASE}/posts/{post['id']}/publish-now", headers=auth_headers)
    assert now.status_code == 200 and now.json()["status"] == "scheduled"
    assert notified.enqueued == [uuid.UUID(post["id"])], "it is queued at once; the every-minute worker would also find it"
    assert await _run(db_session, post["id"], utcnow_plus(5)) == "published"


def utcnow_plus(seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


async def test_nothing_unapproved_or_not_yet_due_is_ever_taken_by_the_worker(client, auth_headers, db_session, organization, storage, ig):
    draft = (await client.post(f"{_BASE}/posts", json={"title": "d", "content": {"caption": "c"}, "scheduled_at": (NOW - timedelta(days=1)).isoformat()}, headers=auth_headers)).json()
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    approved = await _approved(client, auth_headers)
    service = PublisherService(db_session)
    assert uuid.UUID(draft["id"]) not in await service.due_post_ids(NOW + timedelta(days=30))
    assert uuid.UUID(approved["id"]) not in await service.due_post_ids(NOW + timedelta(days=30)), "approved but not scheduled: never published"
    assert await service.due_post_ids(NOW + timedelta(minutes=30)) == []
    assert uuid.UUID(post_id) in await service.due_post_ids(run_at)
    assert await _run(db_session, draft["id"], NOW + timedelta(days=30)) == "skipped"
    assert ig.calls == []


# ---------------- publishing ----------------


async def test_a_post_is_published_and_marked_published_only_after_instagram_confirms(client, auth_headers, db_session, organization, storage, ig):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    assert await _run(db_session, post_id, run_at) == "published"
    row = await _row(db_session, post_id)
    assert row.status == "published" and row.external_media_id == "m1" and row.external_permalink == "https://www.instagram.com/p/abc123/"
    assert row.published_at == run_at and row.last_error is None and row.claimed_at is None
    create = ig.called("create_image_container")
    assert len(create) == 1 and create[0]["image_url"].startswith("https://files.test/social/") and create[0]["image_url"].endswith(".jpg")
    assert create[0]["caption"] == "Logs tell the story of an attack.\n\nSave this.\n\n#SIEM #SOC" and create[0]["alt_text"] == "Text on a plain background."
    assert [c[0] for c in ig.calls if c[0] in ("create_image_container", "publish")] == ["create_image_container", "publish"]
    jpg = storage.objects[next(k for k in storage.objects if k.endswith(".jpg"))]
    assert jpg[:3] == b"\xff\xd8\xff", "what Instagram downloads is a JPEG"
    (attempt,) = await _attempts(db_session, post_id)
    assert attempt.status == "published" and attempt.publish_started_at and attempt.media_id == "m1" and attempt.container_ids == ["c1"] and attempt.creation_id == "c1"
    assert attempt.caption == create[0]["caption"] and attempt.attempt_no == 1


async def test_publishing_twice_is_impossible_the_second_worker_finds_nothing_to_take(client, auth_headers, db_session, organization, storage, ig):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    service = PublisherService(db_session)
    first = await service.claim(uuid.UUID(post_id), run_at)
    second = await service.claim(uuid.UUID(post_id), run_at)
    assert first is not None and first.status == "publishing" and first.attempt_count == 1 and second is None
    assert await _run(db_session, post_id, run_at) == "skipped"
    assert ig.called("publish") == []


async def test_a_carousel_is_made_of_children_then_one_parent_and_published_once(client, auth_headers, db_session, organization, storage, ig):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization, fmt="carousel")
    assert await _run(db_session, post_id, run_at) == "published"
    children = ig.called("create_image_container")
    assert len(children) == 2 and all(c["carousel_item"] and c["caption"] is None for c in children)
    (parent,) = ig.called("create_carousel_container")
    assert parent["children"] == ["c1", "c2"] and parent["caption"].startswith("Logs tell the story")
    assert ig.called("publish") == [{"creation_id": "c3"}]


async def test_a_story_is_published_as_a_story_without_a_caption(client, auth_headers, db_session, organization, storage, ig):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization, fmt="story")
    assert await _run(db_session, post_id, run_at) == "published"
    (create,) = ig.called("create_image_container")
    assert create["story"] is True and create["caption"] is None


async def test_a_temporary_problem_is_retried_with_a_growing_wait_and_succeeds(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    ig.errors["create_image_container"] = [_transient()]
    assert await _run(db_session, post_id, run_at) == "retry"
    row = await _row(db_session, post_id)
    assert row.status == "scheduled" and row.attempt_count == 1 and row.claimed_at is None
    wait = row.next_attempt_at - run_at
    assert timedelta(seconds=48) <= wait <= timedelta(seconds=72), "about a minute after the first failure, with jitter"
    assert "Trying again" in row.last_error and notified.problems == [], "a retry isn't a problem to email about"
    assert await _run(db_session, post_id, run_at + timedelta(seconds=10)) == "skipped", "not before its time"
    assert await _run(db_session, post_id, row.next_attempt_at + timedelta(seconds=1)) == "published"
    first, second = await _attempts(db_session, post_id)
    assert (first.status, second.status, second.attempt_no) == ("retry", "published", 2)
    assert len(ig.called("publish")) == 1


async def test_containers_already_made_are_reused_by_a_retry_instead_of_piling_up(client, auth_headers, db_session, organization, storage, ig, monkeypatch):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    ig.statuses["c1"] = "IN_PROGRESS"
    monkeypatch.setattr(publisher, "POLL_TRIES", 2)
    assert await _run(db_session, post_id, run_at) == "retry"
    assert len(ig.called("create_image_container")) == 1
    ig.statuses["c1"] = "FINISHED"
    row = await _row(db_session, post_id)
    assert await _run(db_session, post_id, row.next_attempt_at + timedelta(seconds=1)) == "published"
    assert len(ig.called("create_image_container")) == 1, "the earlier container was reused"
    assert ig.called("publish") == [{"creation_id": "c1"}]


async def test_it_gives_up_after_five_attempts_says_so_and_tells_you(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    ig.errors["create_image_container"] = [_transient("Instagram is busy.")] * 6
    at = run_at
    outcomes = []
    for _ in range(5):
        outcomes.append(await _run(db_session, post_id, at))
        row = await _row(db_session, post_id)
        at = (row.next_attempt_at or at) + timedelta(seconds=1)
    assert outcomes == ["retry"] * 4 + ["failed"]
    row = await _row(db_session, post_id)
    assert row.status == "failed" and row.attempt_count == 5 and "Gave up after 5 attempts" in row.last_error
    assert len(notified.problems) == 1 and notified.problems[0][1] == "A post failed to publish"
    assert ig.called("publish") == []
    assert await _run(db_session, post_id, at + timedelta(days=1)) == "skipped", "a failed post is never retried without a person"


async def test_a_picture_instagram_rejects_fails_at_once_without_retrying(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    ig.errors["create_image_container"] = [InstagramError("permanent", "The image aspect ratio isn't supported.", code=36003, http_status=400)]
    assert await _run(db_session, post_id, run_at) == "failed"
    row = await _row(db_session, post_id)
    assert row.status == "failed" and row.attempt_count == 1 and "aspect ratio" in row.last_error
    assert notified.problems and notified.problems[0][0] == post_id
    assert len(ig.called("create_image_container")) == 1


async def test_an_expired_token_fails_the_post_and_marks_the_account_instead_of_looping(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    account = (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == organization.id))).scalar_one()
    ig.errors["create_image_container"] = [InstagramError("token", "Instagram says the access token is no longer valid. Reconnect the account.", code=190, http_status=401)]
    assert await _run(db_session, post_id, run_at) == "failed"
    await db_session.refresh(account)
    assert account.status == "expired" and "Reconnect" in account.last_error
    row = await _row(db_session, post_id)
    assert row.status == "failed" and "Reconnect the Instagram account" in row.last_error
    assert notified.problems[0][1] == "The Instagram connection needs attention"
    readiness = (await client.get(f"{_BASE}/posts/{post_id}/readiness", headers=auth_headers)).json()
    assert readiness["ready"] is False and any("needs attention" in p for p in readiness["problems"])


async def test_an_unreadable_stored_token_is_a_reconnect_problem_not_a_crash(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    account = (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == organization.id))).scalar_one()
    account.token_encrypted = "not-a-valid-token"
    await db_session.flush()
    assert await _run(db_session, post_id, run_at) == "failed"
    assert ig.calls == [] and (await _row(db_session, post_id)).status == "failed"


async def test_the_daily_limit_is_respected_and_a_broken_limit_check_does_not_block_publishing(client, auth_headers, db_session, organization, storage, ig):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    ig.limit = PublishLimit(100, 100)
    assert await _run(db_session, post_id, run_at) == "retry"
    assert "daily publishing limit" in (await _row(db_session, post_id)).last_error and ig.called("publish") == []
    ig.limit = PublishLimit(3, 100)
    ig.errors["publishing_limit"] = [InstagramError("permanent", "no permission for this endpoint", http_status=400)]
    row = await _row(db_session, post_id)
    assert await _run(db_session, post_id, row.next_attempt_at + timedelta(seconds=1)) == "published"


# ---------------- unclear outcomes: checked, never retried blindly ----------------


def _on_profile(attempt_caption, at):
    return {"id": "m77", "caption": attempt_caption, "permalink": "https://www.instagram.com/p/found/", "timestamp": at.strftime("%Y-%m-%dT%H:%M:%S+0000")}


async def test_an_unclear_publish_that_actually_went_through_is_found_and_not_repeated(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    row = await _row(db_session, post_id)
    ig.errors["publish"] = [_ambiguous()]
    original_publish = ig.publish

    async def publish_that_worked_but_timed_out(creation_id):
        ig.statuses[creation_id] = "PUBLISHED"
        ig.media = [_on_profile(compose_caption(row), run_at)]
        return await original_publish(creation_id)

    ig.publish = publish_that_worked_but_timed_out
    assert await _run(db_session, post_id, run_at) == "published"
    row = await _row(db_session, post_id)
    assert row.status == "published" and row.external_media_id == "m77" and row.external_permalink == "https://www.instagram.com/p/found/"
    assert len(ig.called("publish")) == 1, "the post was found on the profile; it was not published a second time"
    assert notified.problems == []


async def test_an_unclear_publish_that_instagram_says_did_not_happen_is_retried_after_checking(client, auth_headers, db_session, organization, storage, ig):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    ig.errors["publish"] = [_ambiguous()]
    assert await _run(db_session, post_id, run_at) == "retry"  # the container is still FINISHED, so it was not published
    row = await _row(db_session, post_id)
    assert row.status == "scheduled" and "did not publish it the first time" in row.last_error
    assert await _run(db_session, post_id, row.next_attempt_at + timedelta(seconds=1)) == "published"
    assert len(ig.called("publish")) == 2 and len(ig.called("create_image_container")) == 1, "the same container, published once it was proven unpublished"


async def test_an_unclear_publish_that_cannot_be_checked_is_never_retried_and_goes_to_a_person(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    ig.errors["publish"] = [_ambiguous()]
    ig.errors["container_status"] = [None, _transient("Instagram couldn't be reached.")]  # ready, then the check after the unclear publish fails
    assert await _run(db_session, post_id, run_at) == "unknown"
    row = await _row(db_session, post_id)
    assert row.status == "publish_unknown" and "Check the Instagram profile" in row.last_error
    assert notified.problems and notified.problems[0][1] == "A post's outcome can't be confirmed"
    assert await _run(db_session, post_id, run_at + timedelta(days=2)) == "skipped"
    assert await PublisherService(db_session).due_post_ids(run_at + timedelta(days=2)) == []
    assert len(ig.called("publish")) == 1, "never published a second time"
    (attempt,) = await _attempts(db_session, post_id)
    assert attempt.status == "unknown" and attempt.publish_started_at is not None


async def _unknown_post(client, auth_headers, db_session, organization, ig):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    ig.errors["publish"] = [_ambiguous()]
    ig.errors["container_status"] = [None, _transient("x")]
    assert await _run(db_session, post_id, run_at) == "unknown"
    return post_id, run_at


async def test_reconciling_asks_instagram_and_records_the_answer(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, _ = await _unknown_post(client, auth_headers, db_session, organization, ig)
    still = await client.post(f"{_BASE}/posts/{post_id}/reconcile", headers=auth_headers)
    assert still.status_code == 200 and still.json()["outcome"] == "not_published" and still.json()["post"]["status"] == "failed"
    assert "confirms this post was not published" in still.json()["post"]["last_error"]
    again, again_at = await _unknown_post(client, auth_headers, db_session, organization, ig)
    row = await _row(db_session, again)
    ig.statuses["c2"] = "PUBLISHED"
    ig.media = [_on_profile(compose_caption(row), again_at)]
    found = await client.post(f"{_BASE}/posts/{again}/reconcile", headers=auth_headers)
    assert found.json()["outcome"] == "published" and found.json()["post"]["status"] == "published" and found.json()["post"]["external_media_id"] == "m77"
    assert (await client.post(f"{_BASE}/posts/{again}/reconcile", headers=auth_headers)).status_code == 409


async def test_a_person_can_resolve_an_unclear_post_after_looking_at_instagram(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, _ = await _unknown_post(client, auth_headers, db_session, organization, ig)
    bad = await client.post(f"{_BASE}/posts/{post_id}/resolve", json={"published": True, "permalink": "http://insecure"}, headers=auth_headers)
    assert bad.status_code == 422
    yes = await client.post(f"{_BASE}/posts/{post_id}/resolve", json={"published": True, "media_id": "999", "permalink": "https://www.instagram.com/p/seen/"}, headers=auth_headers)
    assert yes.json()["status"] == "published" and yes.json()["external_permalink"] == "https://www.instagram.com/p/seen/"
    assert (await client.post(f"{_BASE}/posts/{post_id}/resolve", json={"published": False}, headers=auth_headers)).status_code == 409
    other, _ = await _unknown_post(client, auth_headers, db_session, organization, ig)
    no = await client.post(f"{_BASE}/posts/{other}/resolve", json={"published": False}, headers=auth_headers)
    assert no.json()["status"] == "failed" and "not on Instagram" in no.json()["last_error"]
    retried = await client.post(f"{_BASE}/posts/{other}/retry", headers=auth_headers)
    assert retried.status_code == 200 and retried.json()["status"] == "scheduled" and notified.enqueued[-1] == uuid.UUID(other)


async def test_the_attempt_history_keeps_counting_across_a_persons_retry(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    ig.errors["create_image_container"] = [InstagramError("permanent", "rejected", http_status=400)]
    await _run(db_session, post_id, run_at)
    assert (await client.post(f"{_BASE}/posts/{post_id}/retry", headers=auth_headers)).status_code == 200
    assert await _run(db_session, post_id, utcnow_plus(5)) == "published"
    assert [(a.attempt_no, a.status) for a in await _attempts(db_session, post_id)] == [(1, "failed"), (2, "published")]
    assert (await _row(db_session, post_id)).attempt_count == 1, "the automatic-retry limit starts again after a person's retry"


async def test_only_a_failed_post_can_be_retried_and_it_is_checked_again_first(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    assert (await client.post(f"{_BASE}/posts/{post_id}/retry", headers=auth_headers)).status_code == 409
    ig.errors["create_image_container"] = [InstagramError("permanent", "rejected", http_status=400)]
    await _run(db_session, post_id, run_at)
    account = (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == organization.id))).scalar_one()
    account.status = "expired"
    await db_session.flush()
    refused = await client.post(f"{_BASE}/posts/{post_id}/retry", headers=auth_headers)
    assert refused.status_code == 422 and "needs attention" in refused.text, "a retry can't skip the checks"
    account.status = "connected"
    await db_session.flush()
    ok = await client.post(f"{_BASE}/posts/{post_id}/retry", headers=auth_headers)
    assert ok.json()["status"] == "scheduled" and ok.json()["last_error"] is None
    assert await _run(db_session, post_id, utcnow_plus(5)) == "published"


# ---------------- missed, changed, paused ----------------


async def test_a_post_that_wakes_up_far_too_late_is_not_published_stale(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, _ = await _ready(client, auth_headers, db_session, organization)
    scheduled = (await _row(db_session, post_id)).scheduled_at
    assert await _run(db_session, post_id, scheduled + timedelta(hours=3)) == "failed"
    row = await _row(db_session, post_id)
    assert row.status == "failed" and "missed its time by 180 minutes" in row.last_error
    assert notified.problems[0][1] == "The post missed its time" and ig.calls == []


async def test_a_post_a_little_late_is_still_published(client, auth_headers, db_session, organization, storage, ig):
    post_id, _ = await _ready(client, auth_headers, db_session, organization)
    scheduled = (await _row(db_session, post_id)).scheduled_at
    assert await _run(db_session, post_id, scheduled + timedelta(minutes=40)) == "published"


async def test_content_changed_behind_the_approval_is_never_published(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    row = await _row(db_session, post_id)
    row.content = {**row.content, "caption": "Sneaky change after approval."}
    await db_session.flush()
    assert await _run(db_session, post_id, run_at) == "failed"
    assert "exactly what was approved" in (await _row(db_session, post_id)).last_error and ig.calls == []


async def test_a_post_whose_claims_turned_wrong_is_paused_not_published(client, auth_headers, db_session, organization, storage, ig, notified, monkeypatch):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)

    async def recheck(db, organization_id, post, settings):
        post.verification_status = "conflicting"
        post.warnings = [*post.warnings, {"severity": "blocking", "code": "chk_cvss_mismatch", "message": "The post says CVSS 10, but NVD lists 7.5."}]

    monkeypatch.setattr(publisher, "check_and_store", recheck)
    assert await _run(db_session, post_id, run_at) == "paused"
    row = await _row(db_session, post_id)
    assert row.status == "draft" and row.approved_at is None and row.approved_content_hash is None
    assert "Paused before publishing" in row.last_error and any(w.get("code") == "chk_paused_before_publish" for w in row.warnings)
    assert notified.problems[0][1] == "A scheduled post was paused" and ig.calls == []
    assert (await _attempts(db_session, post_id))[0].status == "paused"


async def test_a_time_sensitive_post_is_not_published_when_its_facts_cannot_be_rechecked(client, auth_headers, db_session, organization, storage, ig, monkeypatch):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    row = await _row(db_session, post_id)
    row.time_sensitive = True
    await db_session.flush()

    async def unreachable(db, organization_id, post, settings):
        post.warnings = [*post.warnings, {"severity": "warning", "code": "chk_cve_unreachable", "message": "CVE-2021-44228 could not be checked against NVD."}]

    monkeypatch.setattr(publisher, "check_and_store", unreachable)
    assert await _run(db_session, post_id, run_at) == "retry"
    row = await _row(db_session, post_id)
    assert row.status == "scheduled" and "couldn't be rechecked" in row.last_error and ig.calls == []


# ---------------- recovery after a crash, restart or deployment ----------------


async def _stuck(client, auth_headers, db_session, organization, ig, *, sent: bool, minutes: int = 20, attempt_count: int = 1):
    """A post a worker claimed and then died on. `sent` = it had got as far as the post-creating call."""
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    service = PublisherService(db_session)
    row = await service.claim(uuid.UUID(post_id), run_at)
    row.attempt_count = attempt_count
    row.claimed_at = run_at - timedelta(minutes=minutes)
    attempt = PublishAttempt(
        organization_id=organization.id, post_id=row.id, attempt_no=attempt_count, status="started", idempotency_key=row.idempotency_key,
        caption=compose_caption(row), container_ids=["c1"], creation_id="c1" if sent else None,
        publish_started_at=run_at - timedelta(minutes=minutes) if sent else None,
    )
    db_session.add(attempt)
    await db_session.commit()
    return post_id, run_at, row, attempt


async def test_a_crash_before_anything_was_sent_is_safely_put_back_in_the_queue(client, auth_headers, db_session, organization, storage, ig):
    post_id, run_at, row, attempt = await _stuck(client, auth_headers, db_session, organization, ig, sent=False)
    assert (await PublisherService(db_session).recover(run_at)) == {"requeued": 1, "published": 0, "unknown": 0, "waiting": 0}
    await db_session.refresh(row)
    assert row.status == "scheduled" and row.claimed_at is None
    assert await _run(db_session, post_id, run_at + timedelta(seconds=1)) == "published"
    assert len(ig.called("publish")) == 1


async def test_a_crash_after_the_publish_call_is_checked_and_a_post_that_went_out_is_not_published_again(client, auth_headers, db_session, organization, storage, ig):
    post_id, run_at, row, attempt = await _stuck(client, auth_headers, db_session, organization, ig, sent=True)
    ig.statuses["c1"] = "PUBLISHED"
    ig.media = [_on_profile(attempt.caption, run_at - timedelta(minutes=15))]
    result = await PublisherService(db_session).recover(run_at)
    assert result["published"] == 1
    await db_session.refresh(row)
    assert row.status == "published" and row.external_media_id == "m77"
    assert ig.called("publish") == [], "recovery never publishes anything itself"


async def test_a_crash_after_the_publish_call_where_instagram_says_not_published_goes_back_safely(client, auth_headers, db_session, organization, storage, ig):
    post_id, run_at, row, attempt = await _stuck(client, auth_headers, db_session, organization, ig, sent=True)
    ig.statuses["c1"] = "FINISHED"
    assert (await PublisherService(db_session).recover(run_at))["requeued"] == 1
    await db_session.refresh(row)
    await db_session.refresh(attempt)
    assert row.status == "scheduled" and attempt.publish_started_at is None
    assert ig.called("publish") == []


async def test_recovery_that_cannot_reach_instagram_waits_then_hands_over_to_a_person(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at, row, attempt = await _stuck(client, auth_headers, db_session, organization, ig, sent=True, minutes=20)
    ig.errors["container_status"] = [_transient("down")] * 3
    assert (await PublisherService(db_session).recover(run_at))["waiting"] == 1
    await db_session.refresh(row)
    assert row.status == "publishing", "still unsettled; checked again in five minutes"
    result = await PublisherService(db_session).recover(run_at + timedelta(hours=1))
    assert result["unknown"] == 1
    await db_session.refresh(row)
    assert row.status == "publish_unknown" and notified.problems[0][1] == "A post's outcome can't be confirmed"


async def test_a_fresh_claim_is_left_alone_and_a_post_that_keeps_crashing_stops_being_requeued(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at, row, attempt = await _stuck(client, auth_headers, db_session, organization, ig, sent=False, minutes=2)
    assert await PublisherService(db_session).recover(run_at) == {"requeued": 0, "published": 0, "unknown": 0, "waiting": 0}
    await db_session.refresh(row)
    assert row.status == "publishing"
    row.claimed_at = run_at - timedelta(minutes=30)
    row.attempt_count = publisher.MAX_ATTEMPTS
    await db_session.commit()
    await PublisherService(db_session).recover(run_at)
    await db_session.refresh(row)
    assert row.status == "failed" and notified.problems


# ---------------- queue, attempts, calendar ----------------


async def test_the_queue_lists_what_is_waiting_failed_or_unclear_with_the_last_attempt(client, auth_headers, db_session, organization, storage, ig, notified):
    scheduled_id, _ = await _ready(client, auth_headers, db_session, organization)
    failed = await _approved(client, auth_headers)
    await _schedule(client, auth_headers, failed["id"], NOW + timedelta(hours=3))
    ig.errors["create_image_container"] = [InstagramError("permanent", "rejected", http_status=400)]
    await _run(db_session, failed["id"], NOW + timedelta(hours=3, minutes=1))
    done = await _approved(client, auth_headers)
    await client.post(f"{_BASE}/posts/{done['id']}/publish-now", headers=auth_headers)
    await _run(db_session, done["id"], utcnow_plus(5))
    data = (await client.get(f"{_BASE}/queue", headers=auth_headers)).json()
    by_id = {i["post"]["id"]: i for i in data["items"]}
    assert set(by_id) == {scheduled_id, failed["id"]}, "published and draft posts aren't in the queue"
    assert by_id[failed["id"]]["last_attempt"]["status"] == "failed" and "rejected" in by_id[failed["id"]]["last_attempt"]["error"]
    assert by_id[scheduled_id]["last_attempt"] is None and "never retried" in data["worker_note"]


async def test_the_attempt_history_is_kept_and_private_to_the_organisation(client, auth_headers, db_session, organization, storage, ig, notified):
    post_id, run_at = await _ready(client, auth_headers, db_session, organization)
    ig.errors["create_image_container"] = [_transient()]
    await _run(db_session, post_id, run_at)
    row = await _row(db_session, post_id)
    await _run(db_session, post_id, row.next_attempt_at + timedelta(seconds=1))
    history = (await client.get(f"{_BASE}/posts/{post_id}/attempts", headers=auth_headers)).json()
    assert [a["attempt_no"] for a in history] == [2, 1] and [a["status"] for a in history] == ["published", "retry"]
    assert history[0]["media_id"] == "m1" and history[1]["error"] == "Instagram is busy."
    from modules.organizations.repository import OrganizationRepository

    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other, is_superuser=True, email=f"o-{uuid.uuid4().hex[:6]}@erpx.example.com")
    assert (await client.get(f"{_BASE}/posts/{post_id}/attempts", headers={"Authorization": f"Bearer {token}"})).status_code == 404


async def test_the_calendar_places_posts_on_their_local_day_and_lists_what_is_ready(client, auth_headers, db_session, organization, storage, ig):
    day = (NOW + timedelta(days=30)).date()
    d = lambda n, hm: f"{(day + timedelta(days=n)).isoformat()}T{hm}:00"  # noqa: E731
    iso = lambda n: (day + timedelta(days=n)).isoformat()  # noqa: E731
    await _account(db_session, organization)
    late = await _approved(client, auth_headers)
    # 23:30 in India is 18:00 UTC the same day; 00:30 the next local day is 19:00 UTC on the earlier date
    assert (await client.post(f"{_BASE}/posts/{late['id']}/schedule", json={"scheduled_at": d(0, "23:30")}, headers=auth_headers)).status_code == 200
    early = await _approved(client, auth_headers)
    await client.post(f"{_BASE}/posts/{early['id']}/schedule", json={"scheduled_at": d(1, "00:30")}, headers=auth_headers)
    waiting = await _approved(client, auth_headers)
    planned = (await client.post(f"{_BASE}/posts", json={"title": "planned draft", "content": {"caption": "c"}, "scheduled_at": d(15, "10:00")}, headers=auth_headers)).json()
    cancelled = (await client.post(f"{_BASE}/posts", json={"title": "gone", "content": {"caption": "c"}, "scheduled_at": d(2, "10:00")}, headers=auth_headers)).json()
    await client.post(f"{_BASE}/posts/{cancelled['id']}/transition", json={"action": "cancel"}, headers=auth_headers)
    data = (await client.get(f"{_BASE}/calendar?start={iso(-4)}&end={iso(20)}", headers=auth_headers)).json()
    days = {i["id"]: (i["local_date"], i["local_time"]) for i in data["items"]}
    assert days[late["id"]] == (iso(0), "23:30") and days[early["id"]] == (iso(1), "00:30")
    assert planned["id"] in days and cancelled["id"] not in days and data["timezone"] == "Asia/Kolkata"
    assert data["items"][0]["thumbnail"].startswith("https://files.test/") and data["publish_mode"] == "scheduled"
    assert [i["id"] for i in data["ready_to_schedule"]] == [waiting["id"]]
    narrow = (await client.get(f"{_BASE}/calendar?start={iso(1)}&end={iso(1)}", headers=auth_headers)).json()
    assert [i["id"] for i in narrow["items"]] == [early["id"]]
    with_cancelled = (await client.get(f"{_BASE}/calendar?start={iso(-4)}&end={iso(20)}&include_cancelled=true", headers=auth_headers)).json()
    assert cancelled["id"] in {i["id"] for i in with_cancelled["items"]}
    assert (await client.get(f"{_BASE}/calendar?start={iso(-100)}&end={iso(100)}", headers=auth_headers)).status_code == 422
    assert (await client.get(f"{_BASE}/calendar?start={iso(5)}&end={iso(1)}", headers=auth_headers)).status_code == 422


async def test_the_briefing_mentions_what_is_scheduled(client, auth_headers, db_session, organization, storage, ig):
    await _ready(client, auth_headers, db_session, organization)
    overview = (await client.get(f"{_BASE}/overview", headers=auth_headers)).json()
    assert any("1 post(s) scheduled" in i["message"] and "Asia/Kolkata" in i["message"] for i in overview["briefing"])


# ---------------- notifications ----------------


def test_a_notification_that_cannot_be_queued_never_hides_the_real_problem(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("broker down")

    monkeypatch.setattr(tasks, "enqueue_problem_email", boom)

    class P:
        id = uuid.uuid4()

    publisher.notify_problem(P, "x", "y")  # must not raise


def test_every_publishing_task_is_registered_and_scheduled():
    from app.core.celery_app import celery_app

    celery_app.loader.import_default_modules()
    names = {"social.publish_due", "social.publish_post", "social.recover_publishing", "social.send_problem_email"}
    assert names <= set(celery_app.tasks)
    scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert {"social.publish_due", "social.recover_publishing"} <= scheduled
