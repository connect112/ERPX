"""
Social Media phase 6: privacy, retention, safe links, abuse protection and monitoring.

The rules these tests hold the code to: personal text (comments, messages, replies) never reaches the audit trail or ordinary logs;
a link from outside is only followed if it is a plain https address on the expected site; the retention period is actually enforced
(and says what it keeps); one person's data can be erased on request; a stalled or failed job is noticed and emailed once a day.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.core.limiter import limiter
from modules.audit.models import AuditLog
from modules.crm.leads.models import Lead, LeadSource
from modules.social_media import health, retention, tasks
from modules.social_media.inbox import InboxService
from modules.social_media.leads import SocialLeadService
from modules.social_media.links import LinkService
from modules.social_media.models import AccountDay, IgComment, IgConversation, IgMedia, IgMessage, JobRun, LeadLink, MediaMetric, SocialReply, SocialSettings, WebhookEvent
from modules.social_media.safe_url import instagram_image, instagram_page, safe_url
from modules.social_media.schemas import ResolveRequest
from tests._fixtures import _make_user
from tests.api.social_inbox_fakes import NOW, add_comment, add_conversation, add_media, comment_item, connected_account, install, media_item

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"
SECRET_TEXT = "my-private-phrase-purple-elephant"


@pytest.fixture
def ig(monkeypatch):
    return install(monkeypatch)


@pytest.fixture
async def clean_jobs(db_session):
    """No heartbeats at the start of the test (inside the test's own transaction, so nothing leaks out)."""
    await db_session.execute(delete(JobRun))
    await db_session.flush()


async def _limited(db, organization, rbac_seeded, perms):
    from modules.authorization.service import AuthorizationService

    user, token = await _make_user(db, organization, is_superuser=False, email=f"p-{uuid.uuid4().hex[:6]}@erpx.example.com")
    service = AuthorizationService(db)
    role = await service.create_role(organization.id, "Helper", f"h-{uuid.uuid4().hex[:6]}", None)
    await service.set_role_permissions(role.id, organization.id, perms)
    await service.assign_role(user.id, role.id, organization.id, None)
    return {"Authorization": f"Bearer {token}"}


async def _audit(db, table, entity_id=None):
    query = select(AuditLog).where(AuditLog.entity_type == table)
    if entity_id is not None:
        query = query.where(AuditLog.entity_id == entity_id)
    return list((await db.execute(query)).scalars())


# ---------------- personal text stays out of the audit trail ----------------


async def test_a_comment_is_audited_without_the_words_or_the_person(db_session, organization):
    comment = await add_comment(db_session, organization, f"Call me, {SECRET_TEXT}")
    comment.author_username = "secret_handle"
    comment.suggested_reply = f"Reply about {SECRET_TEXT}"
    comment.summary = f"They said {SECRET_TEXT}"
    await db_session.flush()
    comment.status = "ignored"
    await db_session.flush()
    rows = await _audit(db_session, "social_comments", comment.id)
    assert rows, "the comment's creation and change are still recorded"
    dump = str([r.changes for r in rows])
    assert SECRET_TEXT not in dump and "secret_handle" not in dump and "suggested_reply" not in dump
    assert "ignored" in dump, "what a person did (setting it aside) is recorded"


async def test_a_conversation_and_a_reply_and_a_lead_link_are_audited_without_personal_text(db_session, organization, superuser):
    conversation = await add_conversation(db_session, organization, f"Hello {SECRET_TEXT}")
    conversation.participant_username = "dm_handle"
    conversation.summary = SECRET_TEXT
    await db_session.flush()
    reply = SocialReply(organization_id=organization.id, user_id=superuser[0].id, request_id=uuid.uuid4().hex, kind="dm", conversation_id=conversation.id, target_external_id="x", message=f"Our answer {SECRET_TEXT}", status="sent")
    db_session.add(reply)
    await db_session.flush()
    comment = await add_comment(db_session, organization, "fee?")
    comment.author_username = "lead_handle"
    done = await SocialLeadService(db_session).from_comment(organization.id, superuser[0], comment, {"full_name": "A", "phone": None, "email": None, "course_id": None, "course_label": None, "note": None, "assigned_to_user_id": None, "link_id": None, "marketing_campaign_id": None, "follow_up": None})
    for table, entity in (("social_conversations", conversation.id), ("social_replies", reply.id), ("social_lead_links", done["link_id"])):
        rows = await _audit(db_session, table, entity)
        assert rows, table
        dump = str([r.changes for r in rows])
        assert SECRET_TEXT not in dump and "dm_handle" not in dump and "lead_handle" not in dump, table
    replies = str([r.changes for r in await _audit(db_session, "social_replies", reply.id)])
    assert "sent" in replies, "who sent it and how it ended is still recorded"


async def test_synced_messages_figures_and_link_opens_do_not_fill_the_audit_trail(db_session, organization, superuser):
    conversation = await add_conversation(db_session, organization, f"private {SECRET_TEXT}")
    media = await add_media(db_session, organization, "m1")
    day = AccountDay(organization_id=organization.id, day=NOW.date(), metric="views", value=1, synced_at=NOW)
    metric = MediaMetric(organization_id=organization.id, media_external_id="m1", metric="reach", value=5, synced_at=NOW)
    event = WebhookEvent(organization_id=organization.id, event_hash=uuid.uuid4().hex, entry_id="1", field="comments", object_id="c")
    db_session.add_all([day, metric, event])
    link = await LinkService(db_session).create(organization.id, superuser[0].id, {"name": "L", "destination": "https://pentrix.in/x", "placement": "bio"})
    await LinkService(db_session).record_click(link.token)
    await db_session.flush()
    message_id = (await db_session.execute(select(IgMessage.id).where(IgMessage.conversation_id == conversation.id))).scalar_one()


    created = {"social_messages": message_id, "social_ig_media": media.id, "social_account_days": day.id, "social_media_metrics": metric.id, "social_webhook_events": event.id}
    for table, entity in created.items():
        assert await _audit(db_session, table, entity) == [], table
    from modules.social_media.models import LinkDay

    link_day_id = (await db_session.execute(select(LinkDay.id).where(LinkDay.link_id == link.id))).scalar_one()
    assert await _audit(db_session, "social_link_days", link_day_id) == []
    assert await _audit(db_session, "social_links", link.id), "making a link is a person's action and is audited"


def test_no_log_line_carries_personal_text():
    module = Path(__file__).resolve().parents[2] / "modules" / "social_media"
    pattern = re.compile(r"logger\.(?:debug|info|warning|error|exception)\([^)]*\b(?:text|message|body|caption|username|handle|phone|email|token|summary|suggested_reply|note)\s*=", re.S)
    offenders = [p.name for p in module.glob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == [], f"a log call passes personal text or a secret: {offenders}"


# ---------------- links from outside ----------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("https://www.instagram.com/p/abc/", "https://www.instagram.com/p/abc/"),
        ("https://instagram.com/reel/x", "https://instagram.com/reel/x"),
        ("javascript:alert(1)", None),
        ("data:text/html,<script>1</script>", None),
        ("http://www.instagram.com/p/abc/", None),
        ("https://evil.example/p/abc/?u=instagram.com", None),
        ("https://instagram.com.evil.example/p/1", None),
        ("https://user:pw@www.instagram.com/p/1", None),
        ("https://www.instagram.com/p/a b", None),
        ("", None),
        (None, None),
        (42, None),
    ],
)
def test_only_plain_https_instagram_pages_are_kept_as_post_links(value, expected):
    assert instagram_page(value) == expected


def test_pictures_may_come_from_instagrams_own_servers_and_nowhere_else():
    assert instagram_image("https://scontent-del1-1.cdninstagram.com/v/t51/abc.jpg") and instagram_image("https://scontent.xx.fbcdn.net/v/abc.jpg")
    assert instagram_image("https://evil.example/abc.jpg") is None and instagram_image("http://scontent.cdninstagram.com/a.jpg") is None
    assert safe_url("https://example.com/a" + "b" * 2000) is None


def test_a_person_resolving_a_post_can_only_give_an_instagram_address():
    assert ResolveRequest(published=True, permalink="https://www.instagram.com/p/seen/").permalink
    for bad in ("https://evil.example/p/1", "javascript:alert(1)", "http://www.instagram.com/p/1"):
        with pytest.raises(ValueError):
            ResolveRequest(published=True, permalink=bad)


async def test_reading_posts_drops_links_that_are_not_instagrams(db_session, organization, ig):
    await connected_account(db_session, organization)
    ig.media = [
        media_item("good", permalink="https://www.instagram.com/p/good/", thumbnail_url="https://scontent.cdninstagram.com/a.jpg"),
        media_item("evil", permalink="javascript:alert(document.cookie)", thumbnail_url="https://evil.example/x.jpg"),
    ]
    await InboxService(db_session).sync(organization.id, NOW)
    rows = {m.external_id: m for m in (await db_session.execute(select(IgMedia).where(IgMedia.organization_id == organization.id))).scalars()}
    assert rows["good"].permalink == "https://www.instagram.com/p/good/" and rows["good"].thumbnail_url
    assert rows["evil"].permalink is None and rows["evil"].thumbnail_url is None


def test_the_screens_never_inject_html_or_link_to_an_unchecked_address():
    web = Path(__file__).resolve().parents[2] / "apps" / "web" / "src" / "features" / "social-media"
    for path in web.rglob("*.tsx"):
        source = path.read_text(encoding="utf-8")
        assert "dangerouslySetInnerHTML" not in source and "innerHTML" not in source, f"{path.name} writes HTML"
        for anchor in re.findall(r"href=\{([^}]*)\}", source):
            assert anchor.startswith("safeHref(") or anchor.startswith('"/') or anchor.startswith("`/"), f"{path.name} links to an unchecked address: {anchor}"


# ---------------- abuse protection ----------------


async def test_the_public_redirect_is_rate_limited(client, auth_headers, db_session, organization):
    limiter.reset()
    made = await client.post(f"{_BASE}/links", json={"name": "L", "destination": "https://pentrix.in/x", "placement": "bio"}, headers=auth_headers)
    token = made.json()["token"]
    codes = [(await client.get(f"{_BASE}/l/{token}", follow_redirects=False)).status_code for _ in range(125)]
    assert codes[:120] == [302] * 120 and 429 in codes[120:], "after 120 opens a minute from one address, further ones are refused"
    limiter.reset()


# ---------------- retention ----------------


async def _old_and_new(db, organization, superuser):
    old, new = NOW - timedelta(days=400), NOW - timedelta(days=5)
    await add_media(db, organization, "old-post")
    (await db.execute(select(IgMedia).where(IgMedia.external_id == "old-post"))).scalar_one().posted_at = old
    await add_media(db, organization, "new-post")
    db.add(MediaMetric(organization_id=organization.id, media_external_id="old-post", metric="reach", value=9, synced_at=NOW))
    db.add(MediaMetric(organization_id=organization.id, media_external_id="new-post", metric="reach", value=9, synced_at=NOW))
    old_c = await add_comment(db, organization, "old comment", posted_at=old)
    new_c = await add_comment(db, organization, "new comment", posted_at=new)
    old_conv = await add_conversation(db, organization, "old chat", user_ago=timedelta(days=400))
    new_conv = await add_conversation(db, organization, "new chat", user_ago=timedelta(days=5))
    old_reply = SocialReply(organization_id=organization.id, user_id=superuser[0].id, request_id=uuid.uuid4().hex, kind="dm", conversation_id=old_conv.id, target_external_id="x", message="old answer", status="sent")
    new_reply = SocialReply(organization_id=organization.id, user_id=superuser[0].id, request_id=uuid.uuid4().hex, kind="dm", conversation_id=new_conv.id, target_external_id="x", message="new answer", status="sent")
    db.add_all([old_reply, new_reply])
    db.add(WebhookEvent(organization_id=organization.id, event_hash=uuid.uuid4().hex, entry_id="1", field="comments", object_id="c"))
    await db.flush()
    old_reply.created_at = old
    old_ev = WebhookEvent(organization_id=organization.id, event_hash=uuid.uuid4().hex, entry_id="1", field="comments", object_id="c")
    db.add(old_ev)
    await db.flush()
    old_ev.created_at = NOW - timedelta(days=40)
    await db.flush()
    return old_c, new_c, old_conv, new_conv, old_reply, new_reply


async def test_the_retention_period_removes_old_personal_data_and_keeps_the_record_of_replies(db_session, organization, superuser):
    old_c, new_c, old_conv, new_conv, old_reply, new_reply = await _old_and_new(db_session, organization, superuser)
    other_org_comment_text = "other organisation"
    assert (await retention.preview(db_session, organization.id, 365, NOW))["comments"] == 1
    removed = await retention.apply(db_session, organization.id, 365, NOW)
    assert removed["comments"] == 1 and removed["conversations"] == 1 and removed["messages"] == 1 and removed["reply_texts"] == 1 and removed["posts_read"] == 1 and removed["notifications"] == 1
    gone = (await db_session.execute(select(IgComment.id).where(IgComment.id.in_([old_c.id, new_c.id])))).scalars().all()
    assert gone == [new_c.id]
    assert (await db_session.execute(select(IgConversation.id).where(IgConversation.id.in_([old_conv.id, new_conv.id])))).scalars().all() == [new_conv.id]
    assert (await db_session.execute(select(func.count()).select_from(IgMessage).where(IgMessage.conversation_id == old_conv.id))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(IgMessage).where(IgMessage.conversation_id == new_conv.id))).scalar_one() == 1
    await db_session.refresh(old_reply)
    await db_session.refresh(new_reply)
    assert old_reply.message == retention.REMOVED_TEXT and old_reply.status == "sent" and old_reply.user_id == superuser[0].id, "the record of who sent it and how it ended stays"
    assert new_reply.message == "new answer"
    assert (await db_session.execute(select(IgMedia.external_id).where(IgMedia.organization_id == organization.id))).scalars().all() == ["new-post"]
    assert (await db_session.execute(select(MediaMetric.media_external_id).where(MediaMetric.organization_id == organization.id))).scalars().all() == ["new-post"]
    again = await retention.apply(db_session, organization.id, 365, NOW)
    assert all(v == 0 for v in again.values()), "running it twice removes nothing more"
    del other_org_comment_text


async def _second_org(db):
    from modules.organizations.repository import OrganizationRepository

    unique = uuid.uuid4().hex[:8]
    org = await OrganizationRepository(db).create(name=f"Other Org {unique}", slug=f"other-org-{unique}")
    await db.flush()
    return org


def _lead_data():
    return {"full_name": "Kept Lead", "phone": None, "email": None, "course_id": None, "course_label": None, "note": None, "assigned_to_user_id": None, "link_id": None, "marketing_campaign_id": None, "follow_up": None}


async def test_retention_never_touches_another_organisation_or_a_lead_in_the_crm(db_session, organization, superuser):
    other = await _second_org(db_session)
    mine = await add_comment(db_session, organization, "old", posted_at=NOW - timedelta(days=400))
    mine.author_username = "old_person"
    theirs = await add_comment(db_session, other, "their old comment", posted_at=NOW - timedelta(days=400))
    done = await SocialLeadService(db_session).from_comment(organization.id, superuser[0], mine, _lead_data())
    removed = await retention.apply(db_session, organization.id, 365, NOW)
    assert removed["comments"] == 1
    assert (await db_session.execute(select(IgComment.id).where(IgComment.id == theirs.id))).scalar_one_or_none() == theirs.id
    lead = (await db_session.execute(select(Lead).where(Lead.id == done["lead_id"]))).scalar_one()
    assert lead.full_name == "Kept Lead" and lead.source == LeadSource.SOCIAL_MEDIA, "the CRM keeps its own leads"
    link = (await db_session.execute(select(LeadLink).where(LeadLink.lead_id == lead.id))).scalar_one()
    assert link.comment_id is None, "the link to the removed comment is cleared, the lead and its record stay"


async def test_each_organisation_has_its_own_retention_period(db_session, organization):
    other = await _second_org(db_session)
    db_session.add_all([SocialSettings(organization_id=other.id, timezone="Asia/Kolkata", brand={}, pillars=[], personas=[], prohibited_claims=[], objectives=[], design_rules={}, budgets={}, notifications={}, retention_days=30)])
    await add_comment(db_session, other, "forty days old", posted_at=NOW - timedelta(days=40))
    await add_comment(db_session, organization, "forty days old", posted_at=NOW - timedelta(days=40))
    from modules.social_media.service import SettingsService

    await SettingsService(db_session).get(organization.id)  # creates the default (365 days) for this one
    await db_session.flush()
    await retention.apply_all(db_session, NOW)
    assert (await db_session.execute(select(func.count()).select_from(IgComment).where(IgComment.organization_id == other.id))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(IgComment).where(IgComment.organization_id == organization.id))).scalar_one() == 1


async def test_retention_is_shown_and_applied_from_settings_only_when_confirmed(client, auth_headers, db_session, organization, superuser, rbac_seeded):
    await client.get(f"{_BASE}/settings", headers=auth_headers)
    await client.put(f"{_BASE}/settings", json={"retention_days": 30}, headers=auth_headers)
    await add_comment(db_session, organization, "old", posted_at=NOW - timedelta(days=60))
    status = (await client.get(f"{_BASE}/privacy/retention", headers=auth_headers)).json()
    assert status["retention_days"] == 30 and status["past_the_period"]["comments"] == 1 and status["keeps"] and status["last_run_at"] is None
    dry = (await client.post(f"{_BASE}/privacy/retention/run", json={"confirm": False}, headers=auth_headers)).json()
    assert dry["removed"] is None and dry["would_remove"]["comments"] == 1
    assert (await db_session.execute(select(func.count()).select_from(IgComment).where(IgComment.organization_id == organization.id))).scalar_one() == 1
    done = (await client.post(f"{_BASE}/privacy/retention/run", json={"confirm": True}, headers=auth_headers)).json()
    assert done["removed"]["comments"] == 1
    viewer = await _limited(db_session, organization, rbac_seeded, ["social_media.view"])
    assert (await client.get(f"{_BASE}/privacy/retention", headers=viewer)).status_code == 403
    assert (await client.post(f"{_BASE}/privacy/retention/run", json={"confirm": True}, headers=viewer)).status_code == 403


# ---------------- erasing one person ----------------


async def test_a_person_can_be_erased_and_only_that_person(db_session, organization, superuser):
    target = await add_comment(db_session, organization, "mine to erase")
    target.author_username = "Erase_Me"
    keep = await add_comment(db_session, organization, "someone else")
    keep.author_username = "stay"
    gone_conv = await add_conversation(db_session, organization, "private words", participant_username="erase_me")
    keep_conv = await add_conversation(db_session, organization, "other private words", participant_username="stay")
    reply = SocialReply(organization_id=organization.id, user_id=superuser[0].id, request_id=uuid.uuid4().hex, kind="dm", conversation_id=gone_conv.id, target_external_id="x", message="our answer to them", status="sent")
    kept_reply = SocialReply(organization_id=organization.id, user_id=superuser[0].id, request_id=uuid.uuid4().hex, kind="dm", conversation_id=keep_conv.id, target_external_id="x", message="answer to the other", status="sent")
    db_session.add_all([reply, kept_reply])
    done = await SocialLeadService(db_session).from_comment(organization.id, superuser[0], target, _lead_data())
    await db_session.flush()
    count = await retention.erase_person(db_session, organization.id, "@erase_me", confirm=False)
    assert (count["comments"], count["conversations"], count["messages"], count["reply_texts"], count["crm_leads"], count["erased"]) == (1, 1, 1, 1, 1, False)
    assert (await db_session.execute(select(func.count()).select_from(IgComment).where(IgComment.organization_id == organization.id))).scalar_one() == 2, "a count changes nothing"
    result = await retention.erase_person(db_session, organization.id, "ERASE_ME", confirm=True)
    assert result["erased"] is True
    ids = (await db_session.execute(select(IgComment.id).where(IgComment.organization_id == organization.id))).scalars().all()
    assert ids == [keep.id]
    assert (await db_session.execute(select(IgConversation.id).where(IgConversation.organization_id == organization.id))).scalars().all() == [keep_conv.id]
    await db_session.refresh(reply)
    await db_session.refresh(kept_reply)
    assert reply.message == retention.ERASED_TEXT and reply.status == "sent" and kept_reply.message == "answer to the other"
    link = (await db_session.execute(select(LeadLink).where(LeadLink.lead_id == done["lead_id"]))).scalar_one()
    assert link.handle is None and "erased" in link.basis
    assert (await db_session.execute(select(Lead.id).where(Lead.id == done["lead_id"]))).scalar_one() == done["lead_id"], "the CRM lead stays; the CRM handles it"
    again = await retention.erase_person(db_session, organization.id, "erase_me", confirm=True)
    assert again["erased"] is False and again["comments"] == 0


async def test_erasing_needs_manage_and_inbox_and_counts_first(client, auth_headers, db_session, organization, rbac_seeded):
    comment = await add_comment(db_session, organization, "x")
    comment.author_username = "someone"
    await db_session.flush()
    for perms in (["social_media.view", "social_media.manage"], ["social_media.view", "social_media.inbox"]):
        headers = await _limited(db_session, organization, rbac_seeded, perms)
        assert (await client.post(f"{_BASE}/privacy/erase", json={"handle": "someone", "confirm": True}, headers=headers)).status_code == 403
    dry = (await client.post(f"{_BASE}/privacy/erase", json={"handle": "someone"}, headers=auth_headers)).json()
    assert dry["comments"] == 1 and dry["erased"] is False
    assert (await client.post(f"{_BASE}/privacy/erase", json={"handle": "someone", "confirm": True}, headers=auth_headers)).json()["erased"] is True
    assert (await client.post(f"{_BASE}/privacy/erase", json={"handle": ""}, headers=auth_headers)).status_code == 422


# ---------------- are the jobs running? ----------------


async def test_a_job_is_ok_late_failed_or_not_run_yet(db_session, organization, clean_jobs):
    now = NOW
    states = {j["key"]: j["state"] for j in await health.report(db_session, None, now)}
    assert set(states.values()) == {"never"}, "a fresh deployment is 'not run yet', not a fault"
    await health.record(db_session, "publish_due", True, count=0, now=now - timedelta(minutes=2))
    await health.record(db_session, "recover_publishing", True, now=now - timedelta(minutes=45))
    await health.record(db_session, "make_reports", False, "ValueError: boom", now=now - timedelta(minutes=1))
    states = {j["key"]: j for j in await health.report(db_session, None, now)}
    assert states["publish_due"]["state"] == "ok" and states["recover_publishing"]["state"] == "late" and states["make_reports"]["state"] == "failed"
    assert states["make_reports"]["last_error"] == "ValueError: boom" and states["make_reports"]["consecutive_failures"] == 1
    await health.record(db_session, "make_reports", False, "again", now=now)
    assert {j["key"]: j for j in await health.report(db_session, None, now)}["make_reports"]["consecutive_failures"] == 2
    await health.record(db_session, "make_reports", True, now=now)
    again = {j["key"]: j for j in await health.report(db_session, None, now)}["make_reports"]
    assert again["state"] == "ok" and again["last_error"] is None and again["consecutive_failures"] == 0, "a success clears the failure"


async def test_jobs_that_need_an_instagram_account_are_idle_without_one(db_session, organization, clean_jobs):
    idle = {j["key"]: j["state"] for j in await health.report(db_session, organization.id, NOW)}
    assert idle["sync_inbox"] == "idle" and idle["sync_insights"] == "idle" and idle["publish_due"] == "never"
    await connected_account(db_session, organization)
    assert {j["key"]: j["state"] for j in await health.report(db_session, organization.id, NOW)}["sync_inbox"] == "never"


async def test_a_stalled_or_failed_job_is_alerted_once_a_day_and_never_before_it_has_run(db_session, organization, clean_jobs):
    assert await health.due_alerts(db_session, NOW) == [], "nothing alarms for jobs that never ran"
    await health.record(db_session, "publish_due", True, now=NOW - timedelta(hours=2))
    await health.record(db_session, "apply_retention", False, "RuntimeError: db down", now=NOW - timedelta(minutes=5))
    first = await health.due_alerts(db_session, NOW)
    assert {p["key"]: p["state"] for p in first} == {"publish_due": "late", "apply_retention": "failed"}
    assert "RuntimeError: db down" in next(p for p in first if p["key"] == "apply_retention")["detail"] and "should run every 1 minute" in next(p for p in first if p["key"] == "publish_due")["detail"]
    assert await health.due_alerts(db_session, NOW + timedelta(hours=1)) == [], "told once, not every 15 minutes"
    later = await health.due_alerts(db_session, NOW + timedelta(hours=25))
    assert {p["key"] for p in later} == {"publish_due", "apply_retention"}, "and reminded a day later while it is still wrong"
    await connected_account(db_session, organization)  # an account now exists, so account jobs count too
    await health.record(db_session, "sync_inbox", True, now=NOW - timedelta(hours=5))
    assert "sync_inbox" in {p["key"] for p in await health.due_alerts(db_session, NOW + timedelta(hours=26))}


async def test_a_scheduled_job_leaves_a_heartbeat_even_when_it_fails(db_session, clean_jobs, monkeypatch):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def same_session():
        yield db_session

    monkeypatch.setattr(tasks, "get_db_context", same_session)
    async def fine():
        return 3

    async def broken():
        raise RuntimeError("the database went away")

    assert await tasks._tracked("sync_insights", fine()) == 3
    row = (await db_session.execute(select(JobRun).where(JobRun.job == "sync_insights"))).scalar_one()
    assert row.last_ok is True and row.last_count == 3
    with pytest.raises(RuntimeError):
        await tasks._tracked("sync_insights", broken())
    await db_session.refresh(row)
    assert row.last_ok is False and row.last_error == "RuntimeError: the database went away" and row.failures == 1


async def test_the_overview_warns_about_a_failed_job_and_points_at_a_standout_post(client, auth_headers, db_session, organization, clean_jobs, ig):
    await connected_account(db_session, organization)
    await health.record(db_session, "publish_due", False, "boom")
    await db_session.flush()
    for i, reach in enumerate((100, 110, 120, 105, 900)):
        row = await add_media(db_session, organization, f"s{i}")
        row.posted_at = NOW - timedelta(days=i + 1)
        db_session.add(MediaMetric(organization_id=organization.id, media_external_id=f"s{i}", metric="reach", value=reach, synced_at=NOW))
    await db_session.flush()
    briefing = (await client.get(f"{_BASE}/overview", headers=auth_headers)).json()["briefing"]
    messages = [b["message"] for b in briefing]
    assert any("Publishing scheduled posts" in m and "failed on its last run" in m for m in messages)
    assert any(m.startswith("Strongest recent post") and "900" in m and "typical 110" in m for m in messages)
    assert briefing[0]["level"] == "warning"
    assert not any("(Phase" in m for m in messages), "no stale phase wording"


async def test_health_is_readable_with_view_and_lists_every_job(client, auth_headers, db_session, organization, rbac_seeded, clean_jobs):
    viewer = await _limited(db_session, organization, rbac_seeded, ["social_media.view"])
    data = (await client.get(f"{_BASE}/health", headers=viewer)).json()
    assert [j["key"] for j in data["jobs"]] == [j.key for j in health.JOBS] and data["note"]
    assert (await client.get(f"{_BASE}/health")).status_code == 401


def test_the_housekeeping_jobs_are_scheduled_and_the_email_exists():
    from app.core.celery_app import celery_app
    from packages.email.registry import get_def

    celery_app.loader.import_default_modules()
    schedule = celery_app.conf.beat_schedule
    assert schedule["social-apply-retention"]["task"] == "social.apply_retention" and schedule["social-check-health"]["task"] == "social.check_health"
    assert {"social.apply_retention", "social.check_health"} <= set(celery_app.tasks)
    assert get_def("social_job_problem") is not None
