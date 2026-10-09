"""
Social Media module, phase 1: settings and strategy, the integration status, and the draft -> review -> approved
workflow. The workflow rules matter most: nothing is approved without a recorded, informed approval, an edit withdraws
it, and the publishing states can't be reached from the API at all.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from modules.authorization.service import AuthorizationService
from modules.crm.leads.models import Lead, LeadSource
from modules.social_media import defaults
from modules.social_media.models import SocialAccount, SocialPost
from modules.social_media.schemas import AccountPublic
from modules.social_media.token_crypto import encrypt_token
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"


def _post(**kw):
    body = {
        "title": "What is a SIEM?",
        "format": "image",
        "pillar": "soc",
        "content": {"headline": "What is a SIEM?", "caption": "A SIEM collects and correlates security logs.", "hashtags": ["#SIEM", "cybersecurity"]},
    }
    body.update(kw)
    return body


async def _create(client, headers, **kw):
    response = await client.post(f"{_BASE}/posts", json=_post(**kw), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _act(client, headers, post_id, action, **kw):
    return await client.post(f"{_BASE}/posts/{post_id}/transition", json={"action": action, **kw}, headers=headers)


@pytest.fixture
async def manager_headers(db_session, organization, rbac_seeded):
    """A user who can view and manage the module but is NOT allowed to approve."""
    user, token = await _make_user(db_session, organization, is_superuser=False, email=f"mgr-{uuid.uuid4().hex[:8]}@erpx.example.com")
    service = AuthorizationService(db_session)
    role = await service.create_role(organization.id, "Social manager", f"social-manager-{uuid.uuid4().hex[:6]}", None)
    await service.set_role_permissions(role.id, organization.id, ["social_media.view", "social_media.manage"])
    await service.assign_role(user.id, role.id, organization.id, None)
    await db_session.flush()
    return {"Authorization": f"Bearer {token}"}


# ---------------- access ----------------


async def test_everything_needs_a_login_and_the_right_permission(client, staff_headers, rbac_seeded):
    assert (await client.get(f"{_BASE}/overview")).status_code == 401
    for path in ("/overview", "/settings", "/integration", "/posts"):
        assert (await client.get(f"{_BASE}{path}", headers=staff_headers)).status_code == 403, path
    assert (await client.post(f"{_BASE}/posts", json=_post(), headers=staff_headers)).status_code == 403
    assert (await client.put(f"{_BASE}/settings", json={"timezone": "UTC"}, headers=staff_headers)).status_code == 403


# ---------------- settings and strategy ----------------


async def test_settings_start_with_the_defaults_and_can_be_changed(client, auth_headers):
    first = (await client.get(f"{_BASE}/settings", headers=auth_headers)).json()
    assert first["timezone"] == "Asia/Kolkata" and first["publish_mode"] == "manual"
    assert first["brand"]["tagline"] == "Pentest Practice Dominate"
    assert first["brand"]["colors_confirmed"] is False and first["brand"]["logo_key"] is None
    assert len(first["pillars"]) == len(defaults.DEFAULT_PILLARS)
    assert sum(p["share"] for p in first["pillars"] if p["enabled"]) <= 100
    assert any("placement" in claim.lower() for claim in first["prohibited_claims"])

    update = await client.put(
        f"{_BASE}/settings",
        json={"timezone": "UTC", "publish_mode": "scheduled", "retention_days": 90, "budgets": {"monthly_budget_inr": 5000, "alert_at_percent": 70}},
        headers=auth_headers,
    )
    assert update.status_code == 200, update.text
    again = (await client.get(f"{_BASE}/settings", headers=auth_headers)).json()
    assert again["timezone"] == "UTC" and again["publish_mode"] == "scheduled" and again["retention_days"] == 90
    assert again["budgets"] == {"monthly_budget_inr": 5000, "alert_at_percent": 70}
    assert again["brand"] == first["brand"]  # what wasn't sent is unchanged


@pytest.mark.parametrize(
    "body",
    [
        {"timezone": "Mars/Olympus"},
        {"publish_mode": "autopilot"},
        {"retention_days": 3},
        {"brand": {"name": "P", "tagline": "t", "voice": "v", "colors": {"background": "red", "ink": "#000000", "primary": "#000000", "accent": "#000000", "muted": "#000000"}, "fonts": {"heading": "Inter", "body": "Inter"}}},
        {"pillars": [{"key": "a_b", "label": "A", "share": 60}, {"key": "c_d", "label": "C", "share": 60}]},
        {"pillars": [{"key": "dup_x", "label": "A", "share": 10}, {"key": "dup_x", "label": "B", "share": 10}]},
        {"notifications": {"emails": ["not-an-email"]}},
        {"budgets": {"monthly_budget_inr": -1, "alert_at_percent": 80}},
    ],
)
async def test_invalid_settings_are_rejected(client, auth_headers, body):
    assert (await client.put(f"{_BASE}/settings", json=body, headers=auth_headers)).status_code == 422


# ---------------- integration status ----------------


async def test_integration_status_is_honest_about_what_is_not_connected_or_verified(client, auth_headers):
    data = (await client.get(f"{_BASE}/integration", headers=auth_headers)).json()
    assert data["account"] is None and data["connected"] is False
    assert data["capabilities"] and all(c["verified_live"] is False for c in data["capabilities"])
    by_key = {c["key"]: c for c in data["capabilities"]}
    assert by_key["save_share_identities"]["api"] == "unavailable"
    assert by_key["comments_reply"]["note"].lower().count("person") >= 1  # replies are manual only
    built = {c["key"] for c in data["capabilities"] if c["implemented"] == "yes"}
    # built: the grid preview and publishing of images, carousels and stories. Not built: connecting, Reels, comments, messages
    assert built == {"connect", "profile_grid", "publish_image", "publish_carousel", "publish_story"}
    assert {"publish_reel", "comments_read", "comments_reply", "dm_read", "dm_reply"}.isdisjoint(built)
    assert data["setup_steps"]


def test_an_account_never_exposes_its_token():
    assert "token_encrypted" not in AccountPublic.model_fields
    assert not [name for name in AccountPublic.model_fields if "token" in name and name not in ("token_expires_at", "token_days_left")]


async def test_the_account_token_is_left_out_of_the_audit_trail():
    assert "token_encrypted" in SocialAccount.__audit_exclude_fields__


# ---------------- posts ----------------


async def test_a_post_is_created_as_a_draft_with_cleaned_content(client, auth_headers):
    post = await _create(client, auth_headers)
    assert post["status"] == "draft" and post["verification_status"] == "not_required"
    assert post["content"]["hashtags"] == ["SIEM", "cybersecurity"]  # '#' removed
    assert post["approved_at"] is None and post["external_permalink"] is None
    listed = (await client.get(f"{_BASE}/posts?status=draft", headers=auth_headers)).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == post["id"]
    assert (await client.get(f"{_BASE}/posts?q=siem", headers=auth_headers)).json()["total"] == 1
    assert (await client.get(f"{_BASE}/posts?q=zzz", headers=auth_headers)).json()["total"] == 0


@pytest.mark.parametrize(
    "content",
    [
        {"caption": "x" * 2201},
        {"hashtags": [f"tag{i}" for i in range(31)]},
        {"hashtags": ["bad tag!"]},
        {"slides": [{"heading": "s"}] * 11},
    ],
)
async def test_content_beyond_instagrams_limits_is_rejected(client, auth_headers, content):
    assert (await client.post(f"{_BASE}/posts", json=_post(content=content), headers=auth_headers)).status_code == 422


async def test_a_carousel_needs_two_to_ten_slides(client, auth_headers):
    one = await client.post(f"{_BASE}/posts", json=_post(format="carousel", content={"caption": "c", "slides": [{"heading": "a"}]}), headers=auth_headers)
    assert one.status_code == 422
    post = await _create(client, auth_headers, format="carousel", content={"caption": "c", "slides": [{"heading": "a"}, {"heading": "b"}]})
    assert (await _act(client, auth_headers, post["id"], "submit")).status_code == 200
    # A carousel left without slides can't be approved either.
    empty = await _create(client, auth_headers, format="carousel", content={"caption": "c"})
    await _act(client, auth_headers, empty["id"], "submit")
    assert (await _act(client, auth_headers, empty["id"], "approve")).status_code == 422


async def test_a_time_typed_without_a_timezone_means_the_account_timezone(client, auth_headers):
    post = await _create(client, auth_headers, scheduled_at="2026-11-01T09:00:00")
    assert datetime.fromisoformat(post["scheduled_at"]).utcoffset().total_seconds() == 5.5 * 3600  # Asia/Kolkata
    await client.put(f"{_BASE}/settings", json={"timezone": "UTC"}, headers=auth_headers)
    other = await _create(client, auth_headers, scheduled_at="2026-11-01T09:00:00")
    assert datetime.fromisoformat(other["scheduled_at"]).utcoffset().total_seconds() == 0
    aware = await _create(client, auth_headers, scheduled_at="2026-11-01T09:00:00+02:00")
    assert datetime.fromisoformat(aware["scheduled_at"]).utcoffset().total_seconds() == 2 * 3600


# ---------------- approval ----------------


async def test_the_normal_path_draft_review_approved_records_who_and_what(client, auth_headers, superuser, db_session):
    post = await _create(client, auth_headers)
    assert (await _act(client, auth_headers, post["id"], "approve")).status_code == 409  # not reviewed yet
    assert (await _act(client, auth_headers, post["id"], "submit")).json()["status"] == "review"
    approved = (await _act(client, auth_headers, post["id"], "approve")).json()
    assert approved["status"] == "approved" and approved["approved_at"] and approved["approved_by_user_id"] == str(superuser[0].id)
    row = (await db_session.execute(select(SocialPost).where(SocialPost.id == uuid.UUID(post["id"])))).scalar_one()
    assert len(row.approved_content_hash) == 64


async def test_only_someone_allowed_to_approve_can_approve(client, manager_headers):
    post = await _create(client, manager_headers)
    await _act(client, manager_headers, post["id"], "submit")
    denied = await _act(client, manager_headers, post["id"], "approve")
    assert denied.status_code == 403 and "social_media.approve" in denied.text
    assert (await client.get(f"{_BASE}/posts/{post['id']}", headers=manager_headers)).json()["status"] == "review"


async def test_a_post_needs_a_caption_and_no_unresolved_claims_to_be_approved(client, auth_headers):
    nocaption = await _create(client, auth_headers, content={"headline": "h"})
    await _act(client, auth_headers, nocaption["id"], "submit")
    assert (await _act(client, auth_headers, nocaption["id"], "approve")).status_code == 422

    for status_value in ("unverified", "conflicting", "outdated"):
        post = await _create(client, auth_headers, verification_status=status_value)
        await _act(client, auth_headers, post["id"], "submit")
        response = await _act(client, auth_headers, post["id"], "approve", acknowledge_warnings=True, acknowledge_high_risk=True)
        assert response.status_code == 422, status_value


async def test_marking_claims_verified_needs_sources_and_the_approve_permission(client, auth_headers, manager_headers):
    post = await _create(client, manager_headers, verification_status="unverified", time_sensitive=True)
    denied = await client.patch(f"{_BASE}/posts/{post['id']}", json={"verification_status": "verified"}, headers=manager_headers)
    assert denied.status_code == 403
    # An approver can, but a verified post still has to list where its facts come from.
    await client.patch(f"{_BASE}/posts/{post['id']}", json={"verification_status": "verified"}, headers=auth_headers)
    await _act(client, auth_headers, post["id"], "submit")
    assert (await _act(client, auth_headers, post["id"], "approve", acknowledge_high_risk=True)).status_code == 422
    sources = [{"url": "https://www.cisa.gov/news-events/alerts/x", "title": "CISA alert", "published_at": "2026-10-01"}]
    await client.patch(f"{_BASE}/posts/{post['id']}", json={"sources": sources}, headers=auth_headers)
    assert (await _act(client, auth_headers, post["id"], "approve", acknowledge_high_risk=True)).json()["status"] == "approved"


async def test_high_risk_and_time_sensitive_posts_need_an_explicit_acknowledgement(client, auth_headers):
    post = await _create(client, auth_headers, high_risk=True)
    await _act(client, auth_headers, post["id"], "submit")
    refused = await _act(client, auth_headers, post["id"], "approve")
    assert refused.status_code == 422 and "high-risk" in refused.text
    assert (await _act(client, auth_headers, post["id"], "approve", acknowledge_high_risk=True)).json()["status"] == "approved"


async def test_warnings_must_be_read_and_blocking_ones_resolved(client, auth_headers, db_session):
    post = await _create(client, auth_headers)
    row = (await db_session.execute(select(SocialPost).where(SocialPost.id == uuid.UUID(post["id"])))).scalar_one()
    row.warnings = [{"severity": "warning", "message": "Hashtag reused in 4 of the last 5 posts"}]
    await db_session.flush()
    await _act(client, auth_headers, post["id"], "submit")
    assert (await _act(client, auth_headers, post["id"], "approve")).status_code == 422
    row.warnings = [{"severity": "blocking", "message": "CVE ID could not be verified"}]
    await db_session.flush()
    blocked = await _act(client, auth_headers, post["id"], "approve", acknowledge_warnings=True)
    assert blocked.status_code == 422 and "CVE ID" in blocked.text
    row.warnings = [{"severity": "warning", "message": "x"}]
    await db_session.flush()
    assert (await _act(client, auth_headers, post["id"], "approve", acknowledge_warnings=True)).json()["status"] == "approved"


async def test_editing_an_approved_post_withdraws_the_approval(client, auth_headers):
    post = await _create(client, auth_headers)
    await _act(client, auth_headers, post["id"], "submit")
    await _act(client, auth_headers, post["id"], "approve")
    # Changing something that is not published content (the title) keeps the approval.
    kept = (await client.patch(f"{_BASE}/posts/{post['id']}", json={"title": "Renamed"}, headers=auth_headers)).json()
    assert kept["status"] == "approved" and kept["approval_withdrawn"] is False
    # Saving the same caption again changes nothing either.
    same = (await client.patch(f"{_BASE}/posts/{post['id']}", json={"content": post["content"]}, headers=auth_headers)).json()
    assert same["status"] == "approved"
    changed = (await client.patch(f"{_BASE}/posts/{post['id']}", json={"content": {**post["content"], "caption": "A different caption."}}, headers=auth_headers)).json()
    assert changed["status"] == "draft" and changed["approval_withdrawn"] is True
    assert changed["approved_at"] is None and changed["approved_by_user_id"] is None


async def test_withdrawing_cancelling_and_reopening(client, auth_headers):
    post = await _create(client, auth_headers)
    await _act(client, auth_headers, post["id"], "submit")
    assert (await _act(client, auth_headers, post["id"], "request_changes")).json()["status"] == "draft"
    await _act(client, auth_headers, post["id"], "submit")
    await _act(client, auth_headers, post["id"], "approve")
    assert (await _act(client, auth_headers, post["id"], "unapprove")).json()["approved_at"] is None
    assert (await _act(client, auth_headers, post["id"], "cancel")).json()["status"] == "cancelled"
    assert (await client.patch(f"{_BASE}/posts/{post['id']}", json={"title": "x"}, headers=auth_headers)).status_code == 409
    assert (await _act(client, auth_headers, post["id"], "reopen")).json()["status"] == "draft"


# ---------------- publishing states can't be reached from here ----------------


@pytest.mark.parametrize("state", ["scheduled", "publishing", "published", "publish_unknown"])
async def test_a_post_on_its_way_to_instagram_cannot_be_edited_deleted_or_moved(client, auth_headers, db_session, state):
    post = await _create(client, auth_headers)
    row = (await db_session.execute(select(SocialPost).where(SocialPost.id == uuid.UUID(post["id"])))).scalar_one()
    row.status = state
    await db_session.flush()
    assert (await client.patch(f"{_BASE}/posts/{post['id']}", json={"title": "x"}, headers=auth_headers)).status_code == 409
    assert (await client.delete(f"{_BASE}/posts/{post['id']}", headers=auth_headers)).status_code == 409
    for action in ("submit", "approve", "cancel", "reopen", "request_changes", "unapprove"):
        assert (await _act(client, auth_headers, post["id"], action)).status_code == 409, (state, action)


async def test_the_api_has_no_way_to_set_a_publishing_state(client, auth_headers):
    post = await _create(client, auth_headers)
    assert (await _act(client, auth_headers, post["id"], "publish")).status_code == 422
    assert (await client.patch(f"{_BASE}/posts/{post['id']}", json={"status": "published"}, headers=auth_headers)).json()["status"] == "draft"
    assert (await client.post(f"{_BASE}/posts", json=_post(status="published"), headers=auth_headers)).json()["status"] == "draft"


async def test_drafts_can_be_deleted_and_duplicated(client, auth_headers):
    post = await _create(client, auth_headers, verification_status="verified", sources=[{"url": "https://nvd.nist.gov/vuln/detail/CVE-2024-0001"}])
    copy = (await client.post(f"{_BASE}/posts/{post['id']}/duplicate", headers=auth_headers)).json()
    assert copy["status"] == "draft" and copy["title"].endswith("(copy)") and copy["duplicate_of_id"] == post["id"]
    assert copy["verification_status"] == "unverified"  # a copy's claims have to be checked again
    assert copy["content"] == post["content"] and copy["id"] != post["id"]
    assert (await client.delete(f"{_BASE}/posts/{copy['id']}", headers=auth_headers)).status_code == 204
    assert (await client.get(f"{_BASE}/posts/{copy['id']}", headers=auth_headers)).status_code == 404
    await _act(client, auth_headers, post["id"], "submit")
    assert (await client.delete(f"{_BASE}/posts/{post['id']}", headers=auth_headers)).status_code == 409


async def test_each_post_has_its_own_idempotency_key_for_publishing(client, auth_headers, db_session):
    a, b = await _create(client, auth_headers), await _create(client, auth_headers)
    keys = (await db_session.execute(select(SocialPost.idempotency_key).where(SocialPost.id.in_([uuid.UUID(a["id"]), uuid.UUID(b["id"])])))).scalars().all()
    assert len(set(keys)) == 2 and all(len(k) == 32 for k in keys)


# ---------------- organisations ----------------


async def test_posts_are_private_to_their_organisation(client, auth_headers, db_session):
    from modules.organizations.repository import OrganizationRepository

    post = await _create(client, auth_headers)
    other_org = await OrganizationRepository(db_session).create(name="Other", slug=f"other-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other_org, is_superuser=True, email=f"o-{uuid.uuid4().hex[:6]}@erpx.example.com")
    other = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"{_BASE}/posts/{post['id']}", headers=other)).status_code == 404
    assert (await client.get(f"{_BASE}/posts", headers=other)).json()["total"] == 0
    assert (await _act(client, other, post["id"], "submit")).status_code == 404


# ---------------- overview ----------------


async def test_the_overview_counts_posts_and_crm_leads_without_inventing_attribution(client, auth_headers, superuser, db_session, organization):
    post = await _create(client, auth_headers)
    await _act(client, auth_headers, post["id"], "submit")
    for source, name in ((LeadSource.SOCIAL_MEDIA, "A"), (LeadSource.SOCIAL_MEDIA, "B"), (LeadSource.WEBSITE, "C")):
        db_session.add(Lead(organization_id=organization.id, full_name=name, source=source))
    await db_session.flush()
    data = (await client.get(f"{_BASE}/overview", headers=auth_headers)).json()
    assert data["post_counts"]["review"] == 1 and data["post_counts"]["draft"] == 0 and data["post_counts"]["published"] == 0
    assert [p["id"] for p in data["awaiting_approval"]] == [post["id"]]
    assert data["leads"]["last_30_days"] == 2 and data["leads"]["by_status"] == {"new": 2}
    assert "not yet linked" in data["leads"]["note"]
    messages = " ".join(item["message"] for item in data["briefing"])
    assert "waiting for your approval" in messages and "isn't connected" in messages and "placeholders" in messages
    assert data["connected"] is False
    assert [r["phase"] for r in data["roadmap"]] == [1, 2, 3, 4, 5, 6]


async def test_the_overview_knows_a_connected_account(client, auth_headers, db_session, organization):
    db_session.add(SocialAccount(organization_id=organization.id, external_account_id="123", username="pentrix", status="connected", token_encrypted=encrypt_token("t"), token_expires_at=datetime.now(timezone.utc) + timedelta(days=40), connected_at=datetime.now(timezone.utc)))
    await db_session.flush()
    data = (await client.get(f"{_BASE}/overview", headers=auth_headers)).json()
    assert data["connected"] is True
    integration = (await client.get(f"{_BASE}/integration", headers=auth_headers)).json()
    assert integration["account"]["username"] == "pentrix" and "token" not in str(integration["account"]).replace("token_expires_at", "").replace("token_days_left", "")
