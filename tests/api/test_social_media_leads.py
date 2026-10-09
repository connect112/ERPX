"""
Social Media phase 5b: tracked links, leads made by a person, the enquiry-to-enrolment report, and hashtag measurements.

The rules these tests hold the code to: a lead only exists because a person created it; a tracked link records a daily count and no
visitor; the report never says a post or link caused an enrolment; follow-ups made from here never send a message by themselves;
a hashtag is never called an effect, and trend figures Instagram doesn't provide are not invented.
"""

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions import ValidationError
from modules.courses.models import Course
from modules.crm.admissions.models import Admission, AdmissionStatus
from modules.crm.followups.models import FollowUp, FollowUpType
from modules.crm.leads.models import Lead, LeadSource, LeadStatus
from modules.marketing.campaigns.models import Campaign, CampaignChannel, CampaignStatus
from modules.social_media import hashtags
from modules.social_media.attribution import AttributionService
from modules.social_media.inbox import InboxService
from modules.social_media.leads import SocialLeadService, suggest_course
from modules.social_media.links import LinkService, clean_destination, is_robot, slug, target_url
from modules.social_media.models import LeadLink, LinkDay, MediaMetric, SocialPost, TrackedLink
from tests._fixtures import _make_user
from tests.api.social_inbox_fakes import NOW, add_comment, add_conversation, add_media, comment_item, connected_account, install, media_item, message_detail

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"
SOON = lambda: (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()  # noqa: E731


@pytest.fixture
def ig(monkeypatch):
    return install(monkeypatch)


async def _user(db, organization, rbac_seeded, perms):
    from modules.authorization.service import AuthorizationService

    user, token = await _make_user(db, organization, is_superuser=False, email=f"l-{uuid.uuid4().hex[:6]}@erpx.example.com")
    service = AuthorizationService(db)
    role = await service.create_role(organization.id, "Helper", f"h-{uuid.uuid4().hex[:6]}", None)
    await service.set_role_permissions(role.id, organization.id, perms)
    await service.assign_role(user.id, role.id, organization.id, None)
    return user, {"Authorization": f"Bearer {token}"}


async def _link(client, headers, **kw):
    body = {"name": "Bio link", "destination": "https://pentrix.in/courses/soc", "placement": "bio", **kw}
    return await client.post(f"{_BASE}/links", json=body, headers=headers)


async def _create_link(db, organization, user, **kw):
    data = {"name": "Bio link", "destination": "https://pentrix.in/courses/soc", "placement": "bio", **kw}
    return await LinkService(db).create(organization.id, user.id, data)


async def _course(db, organization, title="SOC Analyst Foundations", published=True):
    course = Course(organization_id=organization.id, title=title, slug=f"c-{uuid.uuid4().hex[:6]}", short_description="d", is_published=published, price=1000)
    db.add(course)
    await db.flush()
    return course


def _lead_data(**kw):
    return {"full_name": "Asha K", "phone": None, "email": None, "course_id": None, "course_label": None, "note": None, "assigned_to_user_id": None, "link_id": None, "marketing_campaign_id": None, "follow_up": None, **kw}


# ---------------- tracked links: what they accept ----------------


@pytest.mark.parametrize(
    "url, text",
    [
        ("http://pentrix.in/x", "https://"),
        ("https://user:pass@pentrix.in/x", "username or password"),
        ("https://localhost/x", "real website"),
        ("javascript:alert(1)", "https://"),
        ("//pentrix.in/x", "https://"),
        ("https://pentrix.in/" + "a" * 500, "too long"),
    ],
)
def test_a_destination_must_be_a_plain_https_address(url, text):
    with pytest.raises(ValidationError, match=text):
        clean_destination(url)


def test_the_final_address_adds_utm_parameters_and_never_overwrites_existing_ones(db_session):
    link = TrackedLink(destination="https://pentrix.in/c?ref=1&utm_source=newsletter", placement="story", utm_campaign="soc-oct", utm_content=None)
    final = target_url(link)
    assert "ref=1" in final and "utm_source=newsletter" in final and "utm_source=instagram" not in final
    assert "utm_medium=social" in final and "utm_campaign=soc-oct" in final and "utm_content=story" in final
    assert slug("SOC Analyst – October!") == "soc-analyst-october" and slug("!!!") == "link"
    assert is_robot("facebookexternalhit/1.1") and is_robot("Mozilla/5.0 (compatible; Googlebot/2.1)") and not is_robot("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1")


async def test_creating_a_link_validates_its_references_and_gives_a_short_address(client, auth_headers, db_session, organization):
    ok = await _link(client, auth_headers, course_label="SOC", utm_content="Autumn Push")
    assert ok.status_code == 201, ok.text
    data = ok.json()
    assert len(data["token"]) >= 9 and data["short_url"].endswith(f"/api/v1/social-media/l/{data['token']}") and data["is_active"] and data["clicks_total"] == 0
    assert "utm_campaign=bio-link" in data["final_url"] and "utm_content=autumn-push" in data["final_url"]
    other = (await _link(client, auth_headers)).json()
    assert other["token"] != data["token"]
    assert (await _link(client, auth_headers, post_id=str(uuid.uuid4()))).status_code == 422
    assert (await _link(client, auth_headers, marketing_campaign_id=str(uuid.uuid4()))).status_code == 422
    assert (await _link(client, auth_headers, destination="http://pentrix.in")).status_code == 422
    assert (await _link(client, auth_headers, placement="billboard")).status_code == 422
    campaign = Campaign(organization_id=organization.id, campaign_code="OCT1", name="October push", channel=CampaignChannel.SOCIAL_MEDIA, status=CampaignStatus.ACTIVE, start_date=date.today())
    db_session.add(campaign)
    await db_session.flush()
    assert (await _link(client, auth_headers, marketing_campaign_id=str(campaign.id))).status_code == 201


# ---------------- tracked links: what an open does ----------------


async def test_opening_a_link_counts_one_and_redirects_without_any_login(client, auth_headers, db_session, organization):
    data = (await _link(client, auth_headers, destination="https://pentrix.in/c?ref=1")).json()
    first = await client.get(f"{_BASE}/l/{data['token']}", follow_redirects=False)
    assert first.status_code == 302 and first.headers["location"] == data["final_url"] and first.headers["cache-control"] == "no-store"
    await client.get(f"{_BASE}/l/{data['token']}", follow_redirects=False, headers={"user-agent": "Mozilla/5.0 (iPhone) Safari"})
    days = (await db_session.execute(select(LinkDay))).scalars().all()
    assert [d.clicks for d in days if str(d.link_id) == data["id"]] == [2], "one row per day, a running count"
    listed = (await client.get(f"{_BASE}/links", headers=auth_headers)).json()
    assert listed[0]["clicks_total"] == 2 and listed[0]["clicks_28d"] == 2 and listed[0]["last_click_day"]


async def test_link_previews_and_robots_are_sent_on_but_not_counted(client, auth_headers, db_session):
    data = (await _link(client, auth_headers)).json()
    for agent in ("facebookexternalhit/1.1", "Mozilla/5.0 (compatible; Googlebot/2.1)", "Instagram link preview bot"):
        assert (await client.get(f"{_BASE}/l/{data['token']}", follow_redirects=False, headers={"user-agent": agent})).status_code == 302
    assert (await db_session.execute(select(func.coalesce(func.sum(LinkDay.clicks), 0)))).scalar_one() == 0


async def test_a_paused_or_unknown_link_goes_nowhere(client, auth_headers, db_session):
    data = (await _link(client, auth_headers)).json()
    paused = await client.patch(f"{_BASE}/links/{data['id']}", json={"is_active": False}, headers=auth_headers)
    assert paused.json()["is_active"] is False
    assert (await client.get(f"{_BASE}/l/{data['token']}", follow_redirects=False)).status_code == 404
    assert (await client.get(f"{_BASE}/l/not-a-real-one", follow_redirects=False)).status_code == 404
    assert (await client.get(f"{_BASE}/l/{'x' * 40}", follow_redirects=False)).status_code == 404
    assert (await db_session.execute(select(LinkDay))).first() is None
    resumed = await client.patch(f"{_BASE}/links/{data['id']}", json={"is_active": True}, headers=auth_headers)
    assert resumed.json()["is_active"] is True and (await client.get(f"{_BASE}/l/{data['token']}", follow_redirects=False)).status_code == 302


def test_a_link_open_keeps_no_trace_of_the_visitor():
    columns = {c.name for c in LinkDay.__table__.columns}
    assert columns == {"id", "created_at", "updated_at", "link_id", "day", "clicks"}, "only a daily count: no address, device, agent or referrer"
    source = (Path(__file__).resolve().parents[2] / "modules" / "social_media" / "links.py").read_text(encoding="utf-8")
    assert "request.client" not in source and "x-forwarded-for" not in source.lower()


async def test_only_those_who_may_manage_can_make_links_and_the_destination_comes_only_from_staff(client, auth_headers, db_session, organization, rbac_seeded):
    _, viewer = await _user(db_session, organization, rbac_seeded, ["social_media.view"])
    assert (await client.get(f"{_BASE}/links", headers=viewer)).status_code == 200
    assert (await _link(client, viewer)).status_code == 403
    assert (await client.get(f"{_BASE}/links")).status_code == 401
    data = (await _link(client, auth_headers)).json()
    assert (await client.patch(f"{_BASE}/links/{data['id']}", json={"is_active": False}, headers=viewer)).status_code == 403
    attempt = await client.get(f"{_BASE}/l/{data['token']}", params={"to": "https://evil.example", "url": "https://evil.example"}, follow_redirects=False)
    assert attempt.headers["location"].startswith("https://pentrix.in/"), "an address can't be redirected somewhere it wasn't set to"


# ---------------- leads made by a person ----------------


async def test_a_lead_is_created_from_a_comment_by_a_person_and_the_record_says_what_that_means(db_session, organization, superuser):
    user = superuser[0]
    await add_media(db_session, organization, "m1")
    comment = await add_comment(db_session, organization, "Does the SOC course include live labs? Please call me", media_external_id="m1")
    comment.author_username = "asha_k"
    course = await _course(db_session, organization)
    done = await SocialLeadService(db_session).from_comment(organization.id, user, comment, _lead_data(course_id=course.id, phone="+91 98765 43210", note="Asked about labs.", assigned_to_user_id=user.id))
    lead = (await db_session.execute(select(Lead).where(Lead.id == done["lead_id"]))).scalar_one()
    assert lead.source == LeadSource.SOCIAL_MEDIA and lead.status == LeadStatus.NEW and lead.assigned_to_user_id == user.id and lead.phone == "+91 98765 43210"
    assert "@asha_k" in lead.notes and "SOC Analyst Foundations" in lead.notes and "Asked about labs." in lead.notes
    assert "live labs" not in lead.notes and "call me" not in lead.notes, "the comment's words aren't copied into the CRM"
    link = (await db_session.execute(select(LeadLink).where(LeadLink.lead_id == lead.id))).scalar_one()
    assert (link.origin, link.comment_id, link.handle, link.course_label, link.created_by_user_id) == ("comment", comment.id, "asha_k", "SOC Analyst Foundations", user.id)
    assert "created this lead" in done["basis"] and "Nothing shows that Instagram caused the enquiry" in done["basis"]


async def test_a_message_becomes_a_lead_without_copying_the_private_text(db_session, organization, superuser):
    conversation = await add_conversation(db_session, organization, "My secret phrase is purple-elephant. Is there a November batch?")
    conversation.participant_username = "ravi_s"
    done = await SocialLeadService(db_session).from_conversation(organization.id, superuser[0], conversation, _lead_data(full_name="Ravi S"))
    lead = (await db_session.execute(select(Lead).where(Lead.id == done["lead_id"]))).scalar_one()
    assert "direct message" in lead.notes and "@ravi_s" in lead.notes and "purple-elephant" not in lead.notes
    link = (await db_session.execute(select(LeadLink).where(LeadLink.lead_id == lead.id))).scalar_one()
    assert link.origin == "message" and link.conversation_id == conversation.id


async def test_one_lead_per_comment_and_a_second_lead_for_the_same_handle_is_warned_about(db_session, organization, superuser):
    service = SocialLeadService(db_session)
    first = await add_comment(db_session, organization, "fee?")
    first.author_username = "same_person"
    second = await add_comment(db_session, organization, "batch dates?")
    second.author_username = "same_person"
    await service.from_comment(organization.id, superuser[0], first, _lead_data())
    with pytest.raises(ValidationError, match="already created from this comment"):
        await service.from_comment(organization.id, superuser[0], first, _lead_data())
    again = await service.from_comment(organization.id, superuser[0], second, _lead_data())
    assert again["warnings"] and "@same_person" in again["warnings"][0] and "twice" in again["warnings"][0]
    assert (await db_session.execute(select(func.count()).select_from(Lead).where(Lead.organization_id == organization.id))).scalar_one() == 2, "warned, not blocked: a person decides"


async def test_you_cannot_make_a_lead_from_your_own_comment(client, auth_headers, db_session, organization, ig):
    await connected_account(db_session, organization)
    own = await add_comment(db_session, organization, "Thanks everyone", is_own=True, status="answered")
    assert (await client.post(f"{_BASE}/comments/{own.id}/lead", json={"full_name": "x"}, headers=auth_headers)).status_code == 404


async def test_lead_input_is_checked_and_nothing_is_created_when_it_is_wrong(db_session, organization, superuser):
    service = SocialLeadService(db_session)
    comment = await add_comment(db_session, organization)
    bad = [
        (_lead_data(full_name="   "), "name is needed"),
        (_lead_data(email="not-an-email"), "email"),
        (_lead_data(phone="abc"), "phone"),
        (_lead_data(course_id=uuid.uuid4()), "course doesn't exist"),
        (_lead_data(link_id=uuid.uuid4()), "tracked link doesn't exist"),
        (_lead_data(marketing_campaign_id=uuid.uuid4()), "campaign doesn't exist"),
        (_lead_data(assigned_to_user_id=uuid.uuid4()), "team member doesn't exist"),
        (_lead_data(follow_up={"type": "whatsapp", "scheduled_at": datetime.now(timezone.utc) + timedelta(days=1), "notes": None}), "send a message by themselves"),
        (_lead_data(follow_up={"type": "sms", "scheduled_at": datetime.now(timezone.utc) + timedelta(days=1), "notes": None}), "send a message by themselves"),
        (_lead_data(follow_up={"type": "call", "scheduled_at": datetime.now(timezone.utc) - timedelta(hours=1), "notes": None}), "in the future"),
    ]
    for data, text in bad:
        with pytest.raises(ValidationError, match=text):
            await service.from_comment(organization.id, superuser[0], comment, data)
    assert (await db_session.execute(select(func.count()).select_from(Lead).where(Lead.organization_id == organization.id))).scalar_one() == 0
    assert (await db_session.execute(select(LeadLink).where(LeadLink.organization_id == organization.id))).first() is None


async def test_a_follow_up_made_here_is_a_quiet_reminder_that_sends_nothing(client, auth_headers, db_session, organization, ig, monkeypatch):
    from modules.crm.followups import tasks as crm_tasks

    def forbidden(*args, **kwargs):
        raise AssertionError("a message was sent to the lead")

    for name in ("send_followup_whatsapp_task", "send_followup_sms_task"):
        monkeypatch.setattr(getattr(crm_tasks, name), "delay", forbidden)
    await connected_account(db_session, organization)
    comment = await add_comment(db_session, organization)
    made = await client.post(f"{_BASE}/comments/{comment.id}/lead", json={"full_name": "Asha", "phone": "+919876543210", "follow_up": {"type": "call", "scheduled_at": SOON(), "notes": "Ask about labs"}}, headers=auth_headers)
    assert made.status_code == 201, made.text
    follow = (await db_session.execute(select(FollowUp).where(FollowUp.lead_id == uuid.UUID(made.json()["lead_id"])))).scalar_one()
    assert follow.follow_up_type == FollowUpType.CALL and follow.notes == "Ask about labs"
    second = await add_comment(db_session, organization)
    refused = await client.post(f"{_BASE}/comments/{second.id}/lead", json={"full_name": "B", "phone": "+919876543211", "follow_up": {"type": "whatsapp", "scheduled_at": SOON()}}, headers=auth_headers)
    assert refused.status_code == 422, "WhatsApp and SMS follow-ups message the lead on their own, so they can't be made from here"


async def test_creating_a_lead_needs_inbox_and_the_crms_own_permission_and_a_follow_up_needs_its_own(client, auth_headers, db_session, organization, rbac_seeded, ig):
    await connected_account(db_session, organization)
    comment = await add_comment(db_session, organization)
    body = {"full_name": "Asha"}
    for perms, expected in (
        (["social_media.view", "social_media.inbox"], 403),
        (["social_media.view", "crm.leads.manage"], 403),
        (["social_media.view", "social_media.reply", "crm.leads.manage"], 403),
    ):
        _, headers = await _user(db_session, organization, rbac_seeded, perms)
        assert (await client.post(f"{_BASE}/comments/{comment.id}/lead", json=body, headers=headers)).status_code == expected, perms
    _, both = await _user(db_session, organization, rbac_seeded, ["social_media.view", "social_media.inbox", "crm.leads.manage"])
    with_follow = {**body, "follow_up": {"type": "call", "scheduled_at": SOON()}}
    assert (await client.post(f"{_BASE}/comments/{comment.id}/lead", json=with_follow, headers=both)).status_code == 403
    assert (await client.post(f"{_BASE}/comments/{comment.id}/lead", json=body, headers=both)).status_code == 201
    assert (await client.get(f"{_BASE}/comments/{comment.id}/lead-hint", headers=both)).json()["existing_lead_id"]


async def test_the_course_a_person_mentions_is_suggested_never_assigned(db_session, organization):
    soc = await _course(db_session, organization, "SOC Analyst Foundations")
    await _course(db_session, organization, "Ethical Hacking Essentials")
    await _course(db_session, organization, "Secret Draft Course Unpublished", published=False)
    suggestion = await suggest_course(db_session, organization.id, "Is the SOC analyst course good for beginners?")
    assert suggestion["course_id"] == soc.id and suggestion["title"] == "SOC Analyst Foundations" and {"soc", "analyst"} <= set(suggestion["matched"])
    assert await suggest_course(db_session, organization.id, "How much is the fee? Please share the details") is None, "common words don't match a course"
    assert await suggest_course(db_session, organization.id, "unpublished secret draft") is None, "an unpublished course is never suggested"
    assert await suggest_course(db_session, organization.id, "") is None


async def test_nothing_creates_a_lead_on_its_own(db_session, organization, ig):
    await connected_account(db_session, organization)
    ig.media = [media_item("m1")]
    ig.comment_pages["m1"] = [[comment_item("c1", "How much is the SOC course fee? I want to enrol")]]
    ig.conversations = [{"id": "conv1", "updated_time": int(NOW.timestamp())}]
    ig.message_ids["conv1"] = [{"id": "x1"}]
    ig.messages = {"x1": message_detail("x1", "Hi, I want to join the November batch")}
    await InboxService(db_session).sync(organization.id, NOW)
    assert (await db_session.execute(select(func.count()).select_from(Lead).where(Lead.organization_id == organization.id))).scalar_one() == 0
    assert (await db_session.execute(select(LeadLink).where(LeadLink.organization_id == organization.id))).first() is None


def test_only_the_lead_routes_can_create_leads_from_social_media():
    module = Path(__file__).resolve().parents[2] / "modules" / "social_media"
    users = {p.name for p in module.glob("*.py") if "SocialLeadService" in p.read_text(encoding="utf-8") and p.name != "leads.py"}
    assert users == {"lead_routes.py"}, f"a lead may only be created by an explicit request: {users}"
    for name in ("tasks.py", "inbox.py", "suggest.py", "analytics.py", "reports.py"):
        assert "LeadService" not in (module / name).read_text(encoding="utf-8"), f"{name} must never create leads"


# ---------------- the report ----------------


async def _linked_lead(db, organization, user, text="fee?", *, status=LeadStatus.NEW, course=None, link=None, handle=None, media="m1", at=None, admission=None):
    comment = await add_comment(db, organization, text, media_external_id=media)
    comment.author_username = handle or f"h-{uuid.uuid4().hex[:5]}"
    done = await SocialLeadService(db).from_comment(organization.id, user, comment, _lead_data(course_id=course.id if course else None, link_id=link.id if link else None))
    lead = (await db.execute(select(Lead).where(Lead.id == done["lead_id"]))).scalar_one()
    lead.status = status
    row = (await db.execute(select(LeadLink).where(LeadLink.lead_id == lead.id))).scalar_one()
    if at:
        row.created_at = at
    if admission:
        db.add(Admission(organization_id=organization.id, lead_id=lead.id, course_name="SOC", fee_amount=1000, admission_date=date.today(), status=admission))
    await db.flush()
    return lead


async def test_the_report_counts_how_far_linked_leads_got_without_crediting_anything(db_session, organization, superuser):
    user = superuser[0]
    await add_media(db_session, organization, "m1")
    await add_media(db_session, organization, "m2")
    soc = await _course(db_session, organization)
    link = await _create_link(db_session, organization, user, name="Bio", course_label="SOC")
    day = LinkDay(link_id=link.id, day=date.today(), clicks=40)
    db_session.add(day)
    await _linked_lead(db_session, organization, user, status=LeadStatus.NEW, course=soc, link=link)
    await _linked_lead(db_session, organization, user, status=LeadStatus.CONTACTED, course=soc)
    await _linked_lead(db_session, organization, user, status=LeadStatus.QUALIFIED, admission=AdmissionStatus.ON_HOLD, media="m2")
    await _linked_lead(db_session, organization, user, status=LeadStatus.CONVERTED, admission=AdmissionStatus.CONFIRMED, course=soc, media="m2")
    await _linked_lead(db_session, organization, user, status=LeadStatus.LOST, media="m2")
    await _linked_lead(db_session, organization, user, status=LeadStatus.CONTACTED, admission=AdmissionStatus.CANCELLED)
    gone = await _linked_lead(db_session, organization, user, status=LeadStatus.CONVERTED)
    gone.deleted_at = NOW
    await add_comment(db_session, organization, "enquiry one", category="enquiry")
    await add_comment(db_session, organization, "thanks!", category="thanks")
    await add_conversation(db_session, organization, "Interested", category="enquiry")
    await db_session.flush()
    today = date.today()
    funnel = await AttributionService(db_session).funnel(organization.id, today - timedelta(days=6), today)
    assert funnel["linked"] == {"leads": 6, "contacted": 4, "qualified": 2, "applied": 2, "enrolled": 1, "lost": 1}, "a deleted lead isn't counted; a cancelled admission isn't an application"
    assert funnel["enquiries_seen"]["comments"] == 8 and funnel["enquiries_seen"]["messages"] == 1, "the seven lead comments and one more are labelled enquiries; thanks and a deleted lead don't change that"
    by_post = {r["permalink"].rstrip("/").split("/")[-1]: r for r in funnel["by_post"]}
    assert set(by_post) == {"m1", "m2"} and sum(r["leads"] for r in by_post.values()) == 6
    assert (by_post["m1"]["leads"], by_post["m1"]["contacted"], by_post["m1"]["applied"], by_post["m1"]["enrolled"]) == (3, 2, 0, 0)
    assert (by_post["m2"]["leads"], by_post["m2"]["qualified"], by_post["m2"]["applied"], by_post["m2"]["enrolled"], by_post["m2"]["lost"]) == (3, 2, 2, 1, 1)
    bio = next(r for r in funnel["by_link"] if r["label"] == "Bio")
    assert bio["opens"] == 40 and bio["leads"] == 1
    assert {"conversion_rate", "click_to_lead", "roi", "revenue"}.isdisjoint(funnel.keys()) and {"conversion_rate", "rate"}.isdisjoint(bio.keys()), "opens sit beside leads and are never turned into a rate"
    assert next(r for r in funnel["by_course"] if r["label"] == "SOC Analyst Foundations")["leads"] == 3 and next(r for r in funnel["by_course"] if r["label"] == "Not recorded")["leads"] == 3
    assert {r["label"] for r in funnel["by_origin"]} == {"comment", "link"}
    text = " ".join(funnel["assumptions"]).lower()
    assert "never says that a post produced an enrolment" in text and "only because a team member created it" in text and "not people" in text


async def test_the_report_only_covers_leads_linked_in_the_period_and_lists_links_that_were_opened_but_made_no_lead(db_session, organization, superuser):
    user = superuser[0]
    await add_media(db_session, organization, "m1")
    await _linked_lead(db_session, organization, user, at=NOW - timedelta(days=40))
    link = await _create_link(db_session, organization, user, name="Story link", placement="story")
    db_session.add(LinkDay(link_id=link.id, day=date.today(), clicks=7))
    await db_session.flush()
    today = date.today()
    funnel = await AttributionService(db_session).funnel(organization.id, today - timedelta(days=27), today)
    assert funnel["linked"]["leads"] == 0
    story = next(r for r in funnel["by_link"] if r["label"] == "Story link")
    assert story["opens"] == 7 and story["leads"] == 0
    wider = await AttributionService(db_session).funnel(organization.id, today - timedelta(days=89), today)
    assert wider["linked"]["leads"] == 1


async def test_the_list_of_social_leads_shows_who_needs_a_first_contact_or_a_follow_up(db_session, organization, superuser):
    user = superuser[0]
    await add_media(db_session, organization, "m1")
    service = AttributionService(db_session)
    await _linked_lead(db_session, organization, user, at=NOW - timedelta(days=5), handle="stale")
    await _linked_lead(db_session, organization, user, handle="fresh")
    overdue = await _linked_lead(db_session, organization, user, status=LeadStatus.CONTACTED, handle="late")
    planned = await _linked_lead(db_session, organization, user, status=LeadStatus.QUALIFIED, handle="planned")
    await _linked_lead(db_session, organization, user, status=LeadStatus.LOST, handle="closed")
    from modules.crm.followups.repository import FollowUpRepository

    repo = FollowUpRepository(db_session)
    await repo.create(lead_id=overdue.id, created_by_user_id=user.id, follow_up_type=FollowUpType.CALL, scheduled_at=datetime.now(timezone.utc) - timedelta(days=1))
    await repo.create(lead_id=planned.id, created_by_user_id=user.id, follow_up_type=FollowUpType.CALL, scheduled_at=datetime.now(timezone.utc) + timedelta(days=2))
    rows = {r["handle"]: r for r in await service.social_leads(organization.id)}
    assert rows["stale"]["needs_first_contact"] is True and rows["fresh"]["needs_first_contact"] is False
    assert (rows["late"]["follow_up"], rows["planned"]["follow_up"], rows["closed"]["follow_up"], rows["stale"]["follow_up"]) == ("overdue", "scheduled", "closed", "none")
    assert rows["planned"]["next_follow_up_at"] and rows["stale"]["basis"]
    assert await service.attention(organization.id) == {"needs_first_contact": 1, "overdue_follow_ups": 1}


async def test_the_screens_need_the_right_permissions_and_the_overview_points_at_leads_that_need_contact(client, auth_headers, db_session, organization, rbac_seeded, ig, superuser):
    await connected_account(db_session, organization)
    await add_media(db_session, organization, "m1")
    await _linked_lead(db_session, organization, superuser[0], at=NOW - timedelta(days=5))
    _, viewer = await _user(db_session, organization, rbac_seeded, ["social_media.view"])
    assert (await client.get(f"{_BASE}/leads/funnel", headers=viewer)).status_code == 200
    assert (await client.get(f"{_BASE}/leads/people", headers=viewer)).status_code == 403, "names of people need the CRM's view permission too"
    _, crm = await _user(db_session, organization, rbac_seeded, ["social_media.view", "crm.leads.view"])
    assert len((await client.get(f"{_BASE}/leads/people", headers=crm)).json()["items"]) == 1
    assert (await client.get(f"{_BASE}/leads/options", headers=viewer)).status_code == 403
    options = (await client.get(f"{_BASE}/leads/options", headers=auth_headers)).json()
    assert set(options) == {"courses", "campaigns", "team"} and options["team"]
    briefing = (await client.get(f"{_BASE}/overview", headers=auth_headers)).json()["briefing"]
    assert any("haven't been contacted yet" in b["message"] and b["link"] == "leads" for b in briefing)
    assert (await client.get(f"{_BASE}/leads/funnel", params={"days": 400}, headers=auth_headers)).status_code == 422


# ---------------- hashtags ----------------


def test_hashtags_are_pulled_out_of_a_caption_as_distinct_lower_case_words():
    assert hashtags.extract("Learn SIEM! #SIEM #Cybersecurity #siem and #blue_team, c#, #2026 email me@x.com#nope") == ["siem", "cybersecurity", "blue_team", "2026"]
    assert hashtags.extract(None) == [] and hashtags.extract("no tags here") == []
    assert hashtags.extract("#साइबर #सुरक्षा") == ["साइबर", "सुरक्षा"]


async def _posts_with(db, organization, spec):
    """spec: list of (caption, reach or None)."""
    for i, (caption, reach) in enumerate(spec):
        row = await add_media(db, organization, f"h{i}")
        row.caption = caption
        row.posted_at = NOW - timedelta(days=i + 1)
        if reach is not None:
            db.add(MediaMetric(organization_id=organization.id, media_external_id=f"h{i}", metric="reach", value=reach, synced_at=NOW))
    await db.flush()


async def test_a_hashtag_is_compared_only_with_enough_posts_on_both_sides_and_never_called_an_effect(db_session, organization):
    spec = [("a #soc #blue", 900), ("b #soc", 800), ("c #soc #blue", 1000), ("d #red", 100), ("e #red", 120), ("f #red", 90), ("g #red", 110)]
    await _posts_with(db_session, organization, spec)
    data = await hashtags.report(db_session, organization.id)
    items = {i["tag"]: i for i in data["items"]}
    assert items["soc"]["comparison"] == "higher" and items["soc"]["median_reach_with"] == 900 and items["soc"]["median_reach_without"] == 105 and items["soc"]["kind"] == "observed"
    assert items["blue"]["comparison"] is None and "Needs at least 3 posts" in items["blue"]["caution"], "two posts with it isn't enough to compare"
    assert data["label"] == "Measured from this profile's own posts" and any("doesn't show the hashtag caused it" in l for l in data["limitations"])
    assert data["typical_reach_posts"] == 7


async def test_overused_and_repeated_hashtags_and_long_lists_are_flagged(db_session, organization):
    same = "x #cyber #infosec #soc"
    long_caption = "y " + " ".join(f"#t{i}" for i in range(32))
    await _posts_with(db_session, organization, [(same, 1), (same, 2), (same, 3), (same + " #extra", 4), ("z #cyber", 5), (long_caption, 6)])
    data = await hashtags.report(db_session, organization.id)
    items = {i["tag"]: i for i in data["items"]}
    assert items["cyber"]["overused"] is True and items["t0"]["overused"] is False
    assert data["repeated_sets"][0] == {"tags": ["cyber", "infosec", "soc"], "posts": 3}
    assert data["too_many"] == 1 and data["many"] == 1 and data["average_per_post"] > 3


async def test_hashtag_trends_are_stated_as_unavailable_not_invented(client, auth_headers, db_session, organization):
    data = (await client.get(f"{_BASE}/analytics/hashtags", headers=auth_headers)).json()
    assert data["items"] == [] and data["trend"]["available"] is False
    assert "restricted" in data["trend"]["reason"] and "doesn't scrape" in data["trend"]["reason"] and "suggestions, not measurements" in data["trend"]["reason"]
    caps = (await client.get(f"{_BASE}/integration", headers=auth_headers)).json()["capabilities"]
    trend = next(c for c in caps if c["key"] == "hashtag_trends")
    assert trend["implemented"] == "never" and "Not available" in trend["note"]
    assert (await client.get(f"{_BASE}/analytics/hashtags")).status_code == 401


def test_no_lead_or_link_code_uses_an_ai_or_sends_a_message():
    module = Path(__file__).resolve().parents[2] / "modules" / "social_media"
    for name in ("links.py", "leads.py", "attribution.py", "hashtags.py", "lead_routes.py"):
        source = (module / name).read_text(encoding="utf-8")
        assert "get_ai_client" not in source and "packages.ai" not in source, f"{name} must stay rule-based"
        assert not re.search(r"\.(reply_to_comment|send_message|publish)\(", source), f"{name} must not post or message anyone"
        assert "followups.service" not in source and "FollowUpService" not in source, f"{name} must not use the CRM follow-up service, which can message leads by itself"
