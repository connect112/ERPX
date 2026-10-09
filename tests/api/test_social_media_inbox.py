"""
Social Media phase 4b, reading: comments and direct messages come into ERPX, get plain-rule labels, and are listed for people.
Nothing in this file sends anything; the reply tests are in test_social_media_replies.py.
"""

import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from modules.social_media import instagram
from modules.social_media.classify import classify
from modules.social_media.inbox import InboxService, parse_time
from modules.social_media.instagram import InstagramClient, InstagramError
from modules.social_media.models import IgComment, IgConversation, IgMedia, IgMessage, SocialAccount, SocialPost, WebhookEvent
from tests._fixtures import _make_user
from tests.api.social_inbox_fakes import NOW, OWN_ID, add_comment, add_conversation, add_media, comment_item, connected_account, install, iso, media_item, message_detail

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"


@pytest.fixture
def ig(monkeypatch):
    return install(monkeypatch)


# ---------------- plain-rule labels ----------------


@pytest.mark.parametrize(
    "text, category, priority, care",
    [
        ("How much is the fee for the SOC course?", "enquiry", "medium", False),
        ("When does the next batch start? Please share details", "enquiry", "medium", False),
        ("fees kitna hai?", "enquiry", "medium", False),
        ("I want a refund right now", "complaint", "high", True),
        ("This is a scam, I will go to consumer court", "complaint", "high", True),
        ("My account got hacked after I joined your lab", "complaint", "high", True),
        ("Worst experience, total waste of money", "complaint", "high", True),
        ("Call me on 9876543210 about the admission", "enquiry", "medium", True),
        ("Great post! Thanks for explaining", "thanks", "low", False),
        ("Follow me back f4f check my profile https://x.com https://y.com", "spam", "low", False),
        ("earn $500 a day crypto dm me for details", "spam", "low", False),
        ("What is a SIEM?", "question", "low", False),
        ("🔥🔥", "other", "low", False),
        ("", "other", "low", False),
        (None, "other", "low", False),
    ],
)
def test_comments_get_a_category_a_priority_and_a_care_flag_from_plain_rules(text, category, priority, care):
    triage = classify(text)
    assert (triage.category, triage.priority, triage.needs_care) == (category, priority, care)
    assert bool(triage.care_reason) == care


def test_something_sensitive_is_never_filed_as_spam_and_contact_details_are_flagged():
    triage = classify("legal notice incoming. check my profile https://a.com https://b.com")
    assert triage.category == "complaint" and triage.needs_care and "legal" in triage.care_reason
    assert "contact details" in classify("email me at asha@example.com about the course fees").care_reason


def test_times_from_instagram_are_read_in_both_forms():
    assert parse_time("2026-10-10T10:00:00+0000") == parse_time("2026-10-10T10:00:00+00:00") == parse_time(1791626400)
    assert parse_time(None) is None and parse_time("not a time") is None and parse_time(True) is None


# ---------------- reading the profile ----------------


async def test_nothing_is_read_unless_instagram_is_connected(db_session, organization):
    from app.core.exceptions import ConflictError

    with pytest.raises(ConflictError, match="isn't connected"):
        await InboxService(db_session).sync(organization.id)


async def test_a_read_stores_the_posts_the_comments_and_the_replies_with_labels(db_session, organization, ig):
    await connected_account(db_session, organization)
    post = SocialPost(organization_id=organization.id, title="siem", format="image", status="published", external_media_id="m1", content={}, artwork={})
    db_session.add(post)
    await db_session.flush()
    ig.media = [media_item("m1", comments=3), media_item("m0", comments=0, at=NOW - timedelta(days=9))]
    ig.comment_pages["m1"] = [[
        comment_item("c1", "How much is the course fee?", "asha", "900"),
        comment_item("c2", "Great post, thanks!", "ravi", "901", replies=[comment_item("r1", "Thank you, Ravi!", "pentrix", OWN_ID)]),
        comment_item("c3", "I want a refund", "kiran", "902", hidden=True),
    ]]
    result = await InboxService(db_session).sync(organization.id, NOW)
    assert result["skipped"] is False and result["stages"]["comments"] == {"ok": True, "error": None, "count": 3}
    rows = {c.external_id: c for c in (await db_session.execute(select(IgComment).where(IgComment.organization_id == organization.id))).scalars()}
    assert set(rows) == {"c1", "c2", "c3", "r1"}
    assert (rows["c1"].category, rows["c1"].priority, rows["c1"].status, rows["c1"].author_username) == ("enquiry", "medium", "new", "asha")
    assert rows["c2"].status == "answered", "answered in the Instagram app counts"
    assert rows["r1"].is_own and rows["r1"].parent_external_id == "c2" and rows["r1"].status == "answered"
    assert rows["c3"].needs_care and rows["c3"].priority == "high" and rows["c3"].hidden is True
    media = {m.external_id: m for m in (await db_session.execute(select(IgMedia).where(IgMedia.organization_id == organization.id))).scalars()}
    assert media["m1"].post_id == post.id and media["m1"].comments_count == 3
    assert ig.count("list_comments") == 1, "a post with no comments isn't asked about"


async def test_our_own_comments_are_recognised_by_id_or_by_name(db_session, organization, ig):
    await connected_account(db_session, organization)
    ig.media = [media_item("m1")]
    ig.comment_pages["m1"] = [[comment_item("a", "by id", "someone-else", OWN_ID), comment_item("b", "by name", "PENTRIX", "555"), comment_item("c", "a visitor", "asha", "900")]]
    await InboxService(db_session).sync(organization.id, NOW)
    own = {c.external_id: c.is_own for c in (await db_session.execute(select(IgComment))).scalars()}
    assert own == {"a": True, "b": True, "c": False}


async def test_when_instagram_withholds_who_wrote_a_comment_that_is_shown_as_not_provided(db_session, organization, ig):
    await connected_account(db_session, organization)
    ig.media = [media_item("m1")]
    ig.comment_pages["m1"] = [[{"id": "c1", "text": "Is there a demo class?", "timestamp": iso(NOW)}]]
    await InboxService(db_session).sync(organization.id, NOW)
    row = (await db_session.execute(select(IgComment).where(IgComment.external_id == "c1"))).scalar_one()
    assert row.author_username is None and row.author_id is None and row.category == "enquiry"


async def test_a_second_read_updates_without_undoing_what_a_person_decided(db_session, organization, ig):
    await connected_account(db_session, organization)
    ig.media = [media_item("m1")]
    ig.comment_pages["m1"] = [[comment_item("c1", "What is the fee?", "asha"), comment_item("c2", "nice", "ravi")]]
    service = InboxService(db_session)
    await service.sync(organization.id, NOW)
    rows = {c.external_id: c for c in (await db_session.execute(select(IgComment))).scalars()}
    rows["c1"].status, rows["c2"].status = "ignored", "answered"
    await db_session.flush()
    ig.comment_pages["m1"] = [[comment_item("c1", "What is the fee? I want a refund", "asha"), comment_item("c2", "nice", "ravi")]]
    await service.sync(organization.id, NOW + timedelta(minutes=5))
    await db_session.refresh(rows["c1"])
    await db_session.refresh(rows["c2"])
    assert rows["c1"].status == "ignored" and rows["c2"].status == "answered", "a person's decision is kept"
    assert rows["c1"].category == "complaint" and rows["c1"].needs_care, "an edited comment is labelled again"
    assert len((await db_session.execute(select(IgComment).where(IgComment.external_id == "c1"))).scalars().all()) == 1


async def test_comments_are_read_page_by_page_up_to_a_limit(db_session, organization, ig):
    await connected_account(db_session, organization)
    ig.media = [media_item("m1")]
    ig.comment_pages["m1"] = [[comment_item(f"p{i}", "first page") for i in range(3)], [comment_item(f"q{i}", "second page") for i in range(3)], [comment_item("z", "third page, never read")]]
    result = await InboxService(db_session).sync(organization.id, NOW)
    assert result["stages"]["comments"]["count"] == 6 and ig.count("list_comments") == 2
    assert (await db_session.execute(select(IgComment).where(IgComment.external_id == "z"))).first() is None


async def test_only_the_latest_posts_comments_are_read(db_session, organization, ig):
    await connected_account(db_session, organization)
    ig.media = [media_item(f"m{i}", at=NOW - timedelta(days=i)) for i in range(15)]
    for i in range(15):
        ig.comment_pages[f"m{i}"] = [[comment_item(f"c{i}", "hi")]]
    await InboxService(db_session).sync(organization.id, NOW)
    assert ig.count("list_comments") == 10


async def test_a_read_that_is_too_soon_after_the_last_one_does_not_ask_instagram_again(db_session, organization, ig):
    await connected_account(db_session, organization)
    ig.media = [media_item("m1")]
    service = InboxService(db_session)
    await service.sync(organization.id, NOW)
    calls = len(ig.calls)
    again = await service.sync(organization.id, NOW + timedelta(seconds=20))
    assert again["skipped"] is True and "once a minute" in again["message"] and len(ig.calls) == calls
    assert (await service.sync(organization.id, NOW + timedelta(seconds=20), force=True))["skipped"] is False
    assert (await service.sync(organization.id, NOW + timedelta(minutes=2)))["skipped"] is False


async def test_what_the_account_was_not_allowed_to_read_is_skipped_and_says_why(db_session, organization, ig):
    account = await connected_account(db_session, organization, capabilities={"comments": "unavailable", "messages": "needs_app_review"})
    ig.media = [media_item("m1")]
    result = await InboxService(db_session).sync(organization.id, NOW)
    assert result["stages"]["comments"]["skipped"] and result["stages"]["messages"]["skipped"] and "permission" in result["stages"]["messages"]["error"]
    assert ig.count("list_comments") == 0 and ig.count("conversations_page") == 0
    assert account.sync_state["messages"]["ok"] is False


async def test_a_temporary_problem_is_recorded_for_that_part_and_not_as_zero(db_session, organization, ig):
    account = await connected_account(db_session, organization)
    ig.media = [media_item("m1")]
    ig.comment_pages["m1"] = [[comment_item("c1", "hello")]]
    ig.errors["list_comments"] = [InstagramError("transient", "Instagram is busy.", http_status=503)]
    result = await InboxService(db_session).sync(organization.id, NOW)
    assert result["stages"]["comments"] == {"ok": False, "error": "Instagram is busy."}
    assert result["stages"]["media"]["ok"] is True and result["stages"]["messages"]["ok"] is True
    assert account.sync_state["comments"]["ok"] is False and account.last_synced_at == NOW


async def test_a_dead_token_stops_the_read_and_marks_the_account(db_session, organization, ig):
    account = await connected_account(db_session, organization)
    ig.errors["media_page"] = [InstagramError("token", "Instagram says the access token is no longer valid. Reconnect the account.", code=190, http_status=401)]
    result = await InboxService(db_session).sync(organization.id, NOW)
    assert result["stages"]["media"]["ok"] is False and "comments" not in result["stages"]
    assert account.status == "revoked" and "Reconnect" in account.last_error


async def test_a_read_marks_the_webhook_notifications_as_dealt_with(db_session, organization, ig):
    await connected_account(db_session, organization)
    db_session.add(WebhookEvent(organization_id=organization.id, event_hash="h" * 64, entry_id=OWN_ID, field="comments"))
    await db_session.flush()
    await InboxService(db_session).sync(organization.id, NOW)
    event = (await db_session.execute(select(WebhookEvent))).scalar_one()
    assert event.processed_at == NOW


# ---------------- conversations ----------------


def _conversation(ig, conv_id="conv1", ids=("m3", "m2", "m1"), updated=None):
    ig.conversations = [{"id": conv_id, "updated_time": int((updated or NOW).timestamp())}]
    ig.message_ids[conv_id] = [{"id": i, "created_time": iso(NOW)} for i in ids]


async def test_a_conversation_is_read_with_direction_window_and_labels(db_session, organization, ig):
    await connected_account(db_session, organization)
    _conversation(ig)
    ig.messages = {
        "m1": message_detail("m1", "Hi, what is the fee for the course?", "900", "asha", NOW - timedelta(hours=5)),
        "m2": message_detail("m2", "Hello Asha! A counsellor will call you.", OWN_ID, "pentrix", NOW - timedelta(hours=4)),
        "m3": message_detail("m3", "Ok, can you also share the batch timings?", "900", "asha", NOW - timedelta(hours=2)),
    }
    result = await InboxService(db_session).sync(organization.id, NOW)
    assert result["stages"]["messages"]["count"] == 1
    conv = (await db_session.execute(select(IgConversation).where(IgConversation.organization_id == organization.id))).scalar_one()
    assert (conv.participant_id, conv.participant_username, conv.status) == ("900", "asha", "open")
    assert conv.last_user_message_at == NOW - timedelta(hours=2) and conv.last_message_from_us is False
    assert InboxService.window_expires(conv) == NOW - timedelta(hours=2) + timedelta(hours=24)
    assert (conv.category, conv.priority) == ("enquiry", "medium")
    messages = (await db_session.execute(select(IgMessage).where(IgMessage.conversation_id == conv.id).order_by(IgMessage.sent_at))).scalars().all()
    assert [(m.direction, m.text[:12]) for m in messages] == [("in", "Hi, what is "), ("out", "Hello Asha! "), ("in", "Ok, can you ")]


async def test_a_conversation_whose_last_message_is_ours_is_answered(db_session, organization, ig):
    await connected_account(db_session, organization)
    _conversation(ig, ids=("m2", "m1"))
    ig.messages = {"m1": message_detail("m1", "Hi", "900", "asha", NOW - timedelta(hours=3)), "m2": message_detail("m2", "Hello!", OWN_ID, "pentrix", NOW - timedelta(hours=2))}
    await InboxService(db_session).sync(organization.id, NOW)
    conv = (await db_session.execute(select(IgConversation))).scalar_one()
    assert conv.status == "answered" and conv.last_message_from_us is True


async def test_unchanged_conversations_and_stored_messages_are_not_read_again(db_session, organization, ig):
    await connected_account(db_session, organization)
    _conversation(ig, ids=("m2", "m1"))
    ig.messages = {"m1": message_detail("m1", "Hi", at=NOW - timedelta(hours=3)), "m2": message_detail("m2", "Is there a demo class?", at=NOW - timedelta(hours=2))}
    service = InboxService(db_session)
    await service.sync(organization.id, NOW)
    assert ig.count("get_message") == 2
    await service.sync(organization.id, NOW + timedelta(minutes=5))
    assert ig.count("get_message") == 2 and ig.count("conversation_message_ids") == 1, "nothing changed, so nothing was fetched"
    _conversation(ig, ids=("m3", "m2", "m1"), updated=NOW + timedelta(minutes=6))
    ig.messages["m3"] = message_detail("m3", "Thank you!", at=NOW + timedelta(minutes=6))
    await service.sync(organization.id, NOW + timedelta(minutes=10))
    assert ig.count("get_message") == 3, "only the new message was fetched"
    assert len((await db_session.execute(select(IgMessage))).scalars().all()) == 3


async def test_messages_instagram_no_longer_returns_are_skipped_and_the_rest_are_kept(db_session, organization, ig):
    await connected_account(db_session, organization)
    _conversation(ig, ids=("m2", "m1"))
    ig.messages = {"m2": message_detail("m2", "Hello, any batch this month?", at=NOW)}  # m1 has been deleted by Instagram
    result = await InboxService(db_session).sync(organization.id, NOW)
    assert result["stages"]["messages"]["ok"] is True
    assert [m.external_id for m in (await db_session.execute(select(IgMessage))).scalars()] == ["m2"]


async def test_a_temporary_problem_while_reading_messages_is_recorded_and_stops_that_part(db_session, organization, ig):
    await connected_account(db_session, organization)
    _conversation(ig, ids=("m1",))
    ig.messages = {"m1": message_detail("m1", "Hi")}
    ig.errors["get_message"] = [InstagramError("transient", "Instagram is busy.", http_status=503)]
    result = await InboxService(db_session).sync(organization.id, NOW)
    assert result["stages"]["messages"] == {"ok": False, "error": "Instagram is busy."}


async def test_a_conversation_with_only_attachments_is_kept_without_inventing_text(db_session, organization, ig):
    await connected_account(db_session, organization)
    _conversation(ig, ids=("m1",))
    ig.messages = {"m1": {"id": "m1", "created_time": iso(NOW), "from": {"id": "900", "username": "asha"}, "to": {"data": [{"id": OWN_ID}]}}}
    await InboxService(db_session).sync(organization.id, NOW)
    message = (await db_session.execute(select(IgMessage))).scalar_one()
    assert message.text is None and message.direction == "in"


# ---------------- listing, filters and privacy ----------------


async def _seed(db_session, organization):
    await connected_account(db_session, organization)
    await add_media(db_session, organization)
    rows = {
        "fee": await add_comment(db_session, organization, "What is the fee?", category="enquiry", priority="medium"),
        "refund": await add_comment(db_session, organization, "I want a refund", category="complaint", priority="high", needs_care=True, care_reason="This asks for a refund. Handle it personally."),
        "spam": await add_comment(db_session, organization, "follow me https://a.com https://b.com", category="spam", priority="low"),
        "old": await add_comment(db_session, organization, "nice", category="thanks", priority="low", posted_at=NOW - timedelta(days=30)),
        "done": await add_comment(db_session, organization, "Is there a demo?", category="enquiry", status="answered"),
        "own": await add_comment(db_session, organization, "Thanks for asking!", is_own=True, status="answered", category="other"),
        "reply": await add_comment(db_session, organization, "me too", parent_external_id="x", category="other"),
    }
    return rows


async def test_the_comment_views_show_what_each_name_promises(client, auth_headers, db_session, organization):
    await _seed(db_session, organization)

    async def view(name, **extra):
        response = await client.get(f"{_BASE}/comments", params={"view": name, **extra}, headers=auth_headers)
        assert response.status_code == 200, response.text
        return sorted(i["text"] for i in response.json()["items"])

    assert await view("unanswered") == sorted(["What is the fee?", "I want a refund", "follow me https://a.com https://b.com", "nice"])
    assert await view("enquiries") == ["Is there a demo?", "What is the fee?"]
    assert await view("complaints") == ["I want a refund"]
    assert await view("spam") == ["follow me https://a.com https://b.com"]
    assert "nice" not in await view("recent") and "What is the fee?" in await view("recent")
    everything = await view("all")
    assert "Thanks for asking!" not in everything and "me too" not in everything, "our own comments and replies are not items to answer"
    assert await view("all", q="refund") == ["I want a refund"]
    assert (await client.get(f"{_BASE}/comments?view=bogus", headers=auth_headers)).status_code == 422


async def test_a_comment_comes_with_its_post_the_labels_the_ai_draft_and_the_replies_so_far(client, auth_headers, db_session, organization):
    rows = await _seed(db_session, organization)
    rows["refund"].summary, rows["refund"].suggested_reply = "Wants a refund", "We're sorry to hear that."
    await add_comment(db_session, organization, "Sorry about that, we'll message you.", ident="own-1", parent_external_id=rows["refund"].external_id, is_own=True, status="answered", author_username="pentrix", category="other")
    item = next(i for i in (await client.get(f"{_BASE}/comments?view=complaints", headers=auth_headers)).json()["items"])
    assert item["author_username"] == "asha" and item["author_known"] is True
    assert item["triage"] == {"category": "complaint", "priority": "high", "needs_care": True, "care_reason": "This asks for a refund. Handle it personally."}
    assert item["suggestion"]["reply"] == "We're sorry to hear that." and item["suggestion"]["summary"] == "Wants a refund"
    assert item["media"]["permalink"].startswith("https://www.instagram.com/p/") and item["media"]["caption"] == "What is a SIEM?"
    assert [(r["by"], r["status"]) for r in item["replies"]] == [("instagram", "sent")]


async def test_text_from_outside_is_returned_as_plain_text_for_the_screen_to_escape(client, auth_headers, db_session, organization):
    await connected_account(db_session, organization)
    await add_comment(db_session, organization, "<script>alert(1)</script> [click](javascript:alert(1)) hello")
    item = (await client.get(f"{_BASE}/comments?view=all", headers=auth_headers)).json()["items"][0]
    assert item["text"] == "<script>alert(1)</script> [click](javascript:alert(1)) hello"


async def test_putting_a_comment_aside_changes_nothing_on_instagram(client, auth_headers, db_session, organization, ig):
    await connected_account(db_session, organization)
    comment = await add_comment(db_session, organization)
    ignored = await client.post(f"{_BASE}/comments/{comment.id}/handled", json={"action": "ignore"}, headers=auth_headers)
    assert ignored.json()["status"] == "ignored"
    assert comment.id not in [uuid.UUID(i["id"]) for i in (await client.get(f"{_BASE}/comments?view=unanswered", headers=auth_headers)).json()["items"]]
    assert (await client.post(f"{_BASE}/comments/{comment.id}/handled", json={"action": "reopen"}, headers=auth_headers)).json()["status"] == "new"
    assert ig.calls == []


async def test_the_conversation_views_thread_and_window(client, auth_headers, db_session, organization):
    await connected_account(db_session, organization)
    open_one = await add_conversation(db_session, organization, "Hi, is there a batch in November?", user_ago=timedelta(hours=2))
    stale = await add_conversation(db_session, organization, "Any demo class?", user_ago=timedelta(hours=30), participant_username="ravi")
    await add_conversation(db_session, organization, "Thanks", status="answered", last_message_from_us=True, category="thanks", priority="low", participant_username="kiran")
    await add_conversation(db_session, organization, "I want my money back", category="complaint", priority="high", needs_care=True, care_reason="This asks for a refund. Handle it personally.", participant_username="meera")

    async def names(view):
        response = await client.get(f"{_BASE}/conversations", params={"view": view}, headers=auth_headers)
        assert response.status_code == 200, response.text
        return {i["participant_username"] for i in response.json()["items"]}

    assert await names("needs_reply") == {"asha", "ravi", "meera"}
    assert await names("enquiries") == {"asha", "ravi"} and await names("complaints") == {"meera"} and await names("high_priority") == {"meera"}
    assert await names("all") == {"asha", "ravi", "kiran", "meera"}
    thread = (await client.get(f"{_BASE}/conversations/{open_one.id}", headers=auth_headers)).json()
    assert thread["conversation"]["window_open"] is True and thread["conversation"]["participant_known"] is True
    assert [m["text"] for m in thread["messages"]] == ["Hi, is there a batch in November?"]
    closed = (await client.get(f"{_BASE}/conversations/{stale.id}", headers=auth_headers)).json()["conversation"]
    assert closed["window_open"] is False and closed["window_expires_at"] is not None, "30 hours after their message the 24-hour window is shut"
    listed = (await client.get(f"{_BASE}/conversations?view=all", headers=auth_headers)).json()["items"]
    assert any(i["preview"] == "Hi, is there a batch in November?" for i in listed)


async def test_the_summary_counts_what_needs_a_person_and_is_honest_about_what_instagram_does_not_say(client, auth_headers, db_session, organization):
    await _seed(db_session, organization)
    await add_conversation(db_session, organization)
    await add_conversation(db_session, organization, "refund please", category="complaint", priority="high", needs_care=True, care_reason="x")
    data = (await client.get(f"{_BASE}/inbox/summary", headers=auth_headers)).json()
    assert data["connected"] is True and data["can_read_comments"] and data["can_read_messages"]
    assert data["counts"]["comments_unanswered"] == 4 and data["counts"]["comments_enquiries"] == 1 and data["counts"]["comments_high_priority"] == 1
    assert data["counts"]["messages_need_reply"] == 2 and data["counts"]["messages_enquiries"] == 1 and data["counts"]["messages_high_priority"] == 1
    assert "which messages you have read" in data["note"] and data["last_sync_at"] is None


async def test_the_briefing_mentions_unanswered_comments_and_messages(client, auth_headers, db_session, organization):
    await _seed(db_session, organization)
    await add_conversation(db_session, organization)
    overview = (await client.get(f"{_BASE}/overview", headers=auth_headers)).json()
    text = " ".join(i["message"] for i in overview["briefing"])
    assert "4 comment(s) are unanswered (1 look like course enquiries)" in text and "1 conversation(s) need a reply" in text


async def test_syncing_from_the_screen_reads_and_reports(client, auth_headers, db_session, organization, ig):
    await connected_account(db_session, organization)
    ig.media = [media_item("m1")]
    ig.comment_pages["m1"] = [[comment_item("c1", "What is the fee?")]]
    first = (await client.post(f"{_BASE}/inbox/sync", headers=auth_headers)).json()
    assert first["skipped"] is False and first["stages"]["comments"]["count"] == 1
    second = (await client.post(f"{_BASE}/inbox/sync", headers=auth_headers)).json()
    assert second["skipped"] is True
    assert (await client.get(f"{_BASE}/inbox/summary", headers=auth_headers)).json()["last_sync_at"] is not None


async def test_syncing_without_a_connection_is_a_clear_conflict(client, auth_headers):
    response = await client.post(f"{_BASE}/inbox/sync", headers=auth_headers)
    assert response.status_code == 409 and "isn't connected" in response.text


# ---------------- who may see this ----------------


async def test_comments_and_messages_need_the_inbox_permission(client, staff_headers, rbac_seeded, db_session, organization):
    comment = await add_comment(db_session, organization)
    conversation = await add_conversation(db_session, organization)
    for method, path in (
        ("get", "/inbox/summary"), ("post", "/inbox/sync"), ("get", "/comments"), ("get", "/conversations"), ("get", f"/conversations/{conversation.id}"),
        ("post", f"/comments/{comment.id}/suggest"), ("post", f"/conversations/{conversation.id}/suggest"), ("get", "/replies"),
        ("post", f"/comments/{comment.id}/handled"), ("post", f"/conversations/{conversation.id}/handled"),
    ):
        response = await getattr(client, method)(f"{_BASE}{path}", headers=staff_headers, **({"json": {"action": "ignore"}} if path.endswith("handled") else {}))
        assert response.status_code == 403, path


async def test_the_inbox_is_private_to_the_organisation(client, auth_headers, db_session, organization):
    from modules.organizations.repository import OrganizationRepository

    comment = await add_comment(db_session, organization)
    conversation = await add_conversation(db_session, organization)
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other, is_superuser=True, email=f"o-{uuid.uuid4().hex[:6]}@erpx.example.com")
    theirs = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"{_BASE}/comments?view=all", headers=theirs)).json()["total"] == 0
    assert (await client.get(f"{_BASE}/conversations?view=all", headers=theirs)).json()["total"] == 0
    assert (await client.get(f"{_BASE}/conversations/{conversation.id}", headers=theirs)).status_code == 404
    assert (await client.post(f"{_BASE}/comments/{comment.id}/handled", json={"action": "ignore"}, headers=theirs)).status_code == 404


# ---------------- the Instagram client's reading calls ----------------


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._payload = status, payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _http(monkeypatch, *answers):
    seen = []
    queue = list(answers)

    class Http:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, method, url, data=None, params=None, headers=None, json=None):
            seen.append({"method": method, "url": url, "data": data, "params": params, "json": json})
            result = queue.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr(instagram.httpx, "AsyncClient", Http)
    return seen


async def test_comments_are_asked_for_with_the_fuller_fields_first_and_the_plain_ones_if_refused(monkeypatch):
    seen = _http(
        monkeypatch,
        _Resp(400, {"error": {"code": 100, "message": "(#100) Tried accessing nonexisting field (hidden)"}}),
        _Resp(200, {"data": [{"id": "c1", "text": "hi", "timestamp": "2026-10-10T10:00:00+0000"}], "paging": {"cursors": {"after": "CUR"}, "next": "https://x"}}),
    )
    rows, after = await InstagramClient("1", "t").list_comments("m1")
    assert [r["id"] for r in rows] == ["c1"] and after == "CUR"
    assert "username" in seen[0]["params"]["fields"] and seen[1]["params"]["fields"] == "id,text,timestamp"


async def test_an_error_that_is_not_about_fields_is_not_retried_with_fewer_fields(monkeypatch):
    seen = _http(monkeypatch, _Resp(403, {"error": {"code": 10, "message": "no permission"}}))
    with pytest.raises(InstagramError) as exc:
        await InstagramClient("1", "t").list_comments("m1")
    assert exc.value.kind == "permanent" and len(seen) == 1


async def test_the_last_page_has_no_cursor_even_if_instagram_still_sends_one(monkeypatch):
    _http(monkeypatch, _Resp(200, {"data": [{"id": "c1"}], "paging": {"cursors": {"after": "CUR"}}}))
    assert (await InstagramClient("1", "t").list_comments("m1"))[1] is None


async def test_conversations_and_messages_are_read_the_documented_way(monkeypatch):
    seen = _http(
        monkeypatch,
        _Resp(200, {"data": [{"id": "conv1", "updated_time": 1791626400}]}),
        _Resp(200, {"messages": {"data": [{"id": "m2", "created_time": "x"}, {"id": "m1", "created_time": "y"}]}, "id": "conv1"}),
        _Resp(200, {"id": "m1", "created_time": "2026-10-10T10:00:00+0000", "from": {"id": "9", "username": "asha"}, "message": "hi"}),
    )
    client = InstagramClient("1784", "t")
    rows, _ = await client.conversations_page(25)
    assert rows[0]["id"] == "conv1" and seen[0]["url"].endswith("/1784/conversations") and seen[0]["params"]["platform"] == "instagram"
    assert [m["id"] for m in await client.conversation_message_ids("conv1")] == ["m2", "m1"] and seen[1]["params"] == {"fields": "messages"}
    assert (await client.get_message("m1"))["message"] == "hi" and seen[2]["params"] == {"fields": "id,created_time,from,to,message"}


async def test_a_comment_reply_and_a_message_are_sent_the_documented_way_and_timeouts_are_ambiguous(monkeypatch):
    seen = _http(monkeypatch, _Resp(200, {"id": "reply1"}), _Resp(200, {"recipient_id": "9", "message_id": "mid1"}), httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow"), _Resp(200, {"recipient_id": "9"}))
    client = InstagramClient("1784", "t")
    assert await client.reply_to_comment("c1", "Thanks!") == "reply1"
    assert seen[0]["method"] == "POST" and seen[0]["url"].endswith("/c1/replies") and seen[0]["data"] == {"message": "Thanks!"}
    assert await client.send_message("9", "Hello") == "mid1"
    assert seen[1]["url"].endswith("/1784/messages") and seen[1]["json"] == {"recipient": {"id": "9"}, "message": {"text": "Hello"}} and seen[1]["data"] is None
    for call in (lambda: client.reply_to_comment("c1", "x"), lambda: client.send_message("9", "x")):
        with pytest.raises(InstagramError) as exc:
            await call()
        assert exc.value.kind == "ambiguous"
    with pytest.raises(InstagramError) as noid:
        await client.send_message("9", "x")
    assert noid.value.kind == "ambiguous", "an answer with no message id doesn't prove it was sent"


def test_the_new_tasks_are_registered_and_scheduled():
    from app.core.celery_app import celery_app

    celery_app.loader.import_default_modules()
    assert {"social.sync_account", "social.sync_inbox"} <= set(celery_app.tasks)
    assert "social.sync_inbox" in {e["task"] for e in celery_app.conf.beat_schedule.values()}


async def test_a_webhook_notification_wakes_the_background_read_and_nothing_else(client, db_session, organization, monkeypatch):
    import hashlib
    import hmac
    import json

    from app.core.config import settings
    from modules.social_media import tasks

    monkeypatch.setattr(settings, "INSTAGRAM_APP_SECRET", "s3cret")
    woken = []
    monkeypatch.setattr(tasks, "enqueue_sync", lambda organization_id: woken.append(organization_id) or True)
    await connected_account(db_session, organization)
    body = json.dumps({"object": "instagram", "entry": [{"id": OWN_ID, "time": 1, "changes": [{"field": "comments", "value": {"id": "c9"}}]}, {"id": "other", "time": 1, "changes": [{"field": "comments", "value": {"id": "c10"}}]}]}).encode()
    signature = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": signature, "Content-Type": "application/json"}
    assert (await client.post(f"{_BASE}/webhooks/instagram", content=body, headers=headers)).json() == {"received": 2, "new": 2}
    assert woken == [organization.id], "only the organisation that owns the account is woken"
    assert (await client.post(f"{_BASE}/webhooks/instagram", content=body, headers=headers)).json()["new"] == 0
    assert woken == [organization.id], "a retried notification wakes nothing"
