"""
Marketing email to Pentrix candidates through Email Studio: who may be emailed (an explicit opt-in, a verified address, no unsubscribe), the
templates made available and when, the previews, the explicit confirmation, the rate-limited sending that re-checks consent at the moment
of sending, never sends twice, and the unsubscribe link. Pentrix is replaced by the fake from the candidate tests.
"""
import hmac
import itertools
import uuid
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from modules.email_studio.models import EmailSendRecord, EmailStudioTemplate, EmailStudioVersion
from modules.pentrix_ops import client as client_module
from modules.pentrix_ops import marketing
from modules.pentrix_ops.client import sign
from modules.pentrix_ops.models import PentrixCandidate, PentrixMarketingCampaign, PentrixMarketingRecipient, PentrixMarketingSuppression
from modules.pentrix_ops.marketing import PentrixMarketingService, read_token, sign_token
from packages.email.history import take_send_meta
from tests.api.test_email_studio import create, page, publish
from tests.api.test_pentrix_candidates import FakePentrixWithCandidates
from tests.api.test_pentrix_ops import SECRET, person, push_headers, utc

pytestmark = pytest.mark.api

_P = "/api/v1/pentrix-ops"
_M = f"{_P}/marketing"
_PREFIX = "/api/v1/internal/erpx"

HTML = page('<h1>Hello {{first_name}}</h1><p>{{campaign_name}}: you are {{qualification_status}}. <a href="{{portal_url}}">Open the portal</a></p>')
HTML_WITH_UNSUB = page('<p>Hi {{first_name}}</p><p><a href="{{unsubscribe_url}}">Stop these emails</a></p>')


class FakePentrixMarketing(FakePentrixWithCandidates):
    """Adds Pentrix's marketing-unsubscribe endpoint to the fake."""

    def __init__(self):
        super().__init__()
        self.unsubscribed: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = urlparse(str(request.url))
        if request.method == "POST" and url.path.endswith("/marketing-unsubscribe"):
            if self.down:
                raise httpx.ConnectError("down")
            path_and_query = url.path + (f"?{url.query}" if url.query else "")
            body = request.content.decode() if request.content else ""
            if not hmac.compare_digest(sign(SECRET, request.headers.get("X-ERPX-Timestamp", ""), request.method, path_and_query, body), request.headers.get("X-ERPX-Signature", "")):
                return httpx.Response(401, json={"error": "auth_error", "message": "Invalid signature."})
            cid = url.path.split("/")[-2]
            self.unsubscribed.append(cid)
            return httpx.Response(200, json=self.candidates.get(cid, {"id": cid}))
        return super().handler(request)


@pytest.fixture
def pentrix(monkeypatch, organization):
    fake = FakePentrixMarketing()
    monkeypatch.setattr(settings, "PENTRIX_ORGANIZATION_SLUG", organization.slug)
    monkeypatch.setattr(settings, "PENTRIX_INTERNAL_API_BASE_URL", "http://pentrix.test")
    monkeypatch.setattr(settings, "ERPX_INTERNAL_SERVICE_SECRET", SECRET)
    monkeypatch.setattr(client_module, "DEFAULT_TRANSPORT", httpx.MockTransport(fake.handler))
    return fake


class Outbox(list):
    fail = False


@pytest.fixture
def outbox(monkeypatch):
    box = Outbox()

    async def send(to, subject, text, html=None, attachments=None):
        meta = take_send_meta()
        box.append({"to": to, "subject": subject, "text": text, "html": html, "headers": dict(meta.headers) if meta else {}, "meta": meta})
        return not box.fail

    monkeypatch.setattr(marketing.email_service, "send", send)
    return box


_clock = itertools.count()


async def candidate(db, organization, name, email, *, verified=True, opted=True, qualified=None, **extra) -> PentrixCandidate:
    row = PentrixCandidate(
        organization_id=organization.id, pentrix_user_id=str(uuid.uuid4()), full_name=name, email=email, email_verified=verified, registered_at=utc(-60 * 24) + timedelta(seconds=next(_clock)),
        marketing_opt_in=opted, marketing_changed_at=utc(-60 * 24) if opted else None, qualified=qualified, assessment_state="completed" if qualified is not None else "not_started", **extra,
    )
    db.add(row)
    await db.flush()
    return row


async def template(client, headers, name="November intake", html=HTML, subject="Hi {{first_name}}: {{campaign_name}}"):
    t = await create(client, headers, name=name, subject=subject, html=html)
    await publish(client, headers, t)
    return t


async def available(client, headers, t, campaign="November intake", **dates):
    r = await client.post(f"{_M}/templates", headers=headers, json={"template_id": t["id"], "campaign_name": campaign, **dates})
    assert r.status_code == 201, r.text
    return r.json()


def ids(*rows):
    return {"mode": "ids", "ids": [str(r.id) for r in rows]}


async def confirm(client, headers, assignment, selection, expected, key=None, expect=201):
    r = await client.post(
        f"{_M}/campaigns", headers=headers,
        json={"assignment_id": assignment["id"], "selection": selection, "expected_count": expected, "confirm": True, "idempotency_key": key or uuid.uuid4().hex},
    )
    assert r.status_code == expect, r.text
    return r.json()


async def run(db_session, limit=100):
    """One pass of the sender: claim a batch and send each message (what the every-minute task does)."""
    service = PentrixMarketingService(db_session)
    results = [await service.process(i) for i in await service.claim(limit)]
    await service.finish()
    return results


# ------------------------------------------------------------------ who may be emailed


async def test_only_opted_in_verified_unsubscribed_free_unique_addresses_are_eligible(client, db_session, organization, auth_headers, pentrix, outbox):
    ok = await candidate(db_session, organization, "Asha Rao", "asha@example.com")
    await candidate(db_session, organization, "Not Opted", "no@example.com", opted=False)
    await candidate(db_session, organization, "Unverified", "unverified@example.com", verified=False)
    gone = await candidate(db_session, organization, "Gone", "gone@example.com")
    await candidate(db_session, organization, "No Address", "")
    await candidate(db_session, organization, "Same Address", "ASHA@example.com")
    db_session.add(PentrixMarketingSuppression(organization_id=organization.id, email="gone@example.com", pentrix_user_id=gone.pentrix_user_id))
    await db_session.flush()
    res = await PentrixMarketingService(db_session).resolve(organization.id, {"mode": "filter", "filters": {}}, None)
    assert [c.full_name for c in res.eligible] == ["Asha Rao"] and res.selected == 6 and res.eligible[0].id == ok.id
    assert res.excluded == {"not_opted_in": 1, "email_unverified": 1, "unsubscribed": 1, "no_email": 1, "duplicate_address": 1}


async def test_nobody_is_emailable_just_because_they_registered(client, db_session, organization, auth_headers, pentrix):
    """A candidate synchronised from Pentrix with no marketing choice recorded is not opted in."""
    from modules.pentrix_ops.candidates import PentrixCandidateService

    summary = pentrix.candidate(full_name="Plain", email="plain@example.com", email_verified=True)
    row = await PentrixCandidateService(db_session).upsert(organization.id, summary)
    assert row.marketing_opt_in is False
    res = await PentrixMarketingService(db_session).resolve(organization.id, ids(row), None)
    assert res.eligible == [] and res.excluded == {"not_opted_in": 1}
    summary = {**summary, "marketing": {"opt_in": True, "changed_at": utc(-5).isoformat()}, "updated_at": (datetime.fromisoformat(summary["updated_at"]) + timedelta(seconds=5)).isoformat()}
    row = await PentrixCandidateService(db_session).upsert(organization.id, summary)
    assert row.marketing_opt_in is True
    assert len((await PentrixMarketingService(db_session).resolve(organization.id, ids(row), None)).eligible) == 1


async def test_the_registrations_list_can_be_filtered_by_marketing_choice(client, db_session, organization, auth_headers, pentrix):
    await candidate(db_session, organization, "In", "in@example.com", opted=True)
    await candidate(db_session, organization, "Out", "out@example.com", opted=False)
    names = lambda r: sorted(c["full_name"] for c in r.json()["items"])  # noqa: E731
    assert names(await client.get(f"{_P}/candidates?marketing=opted_in", headers=auth_headers)) == ["In"]
    assert names(await client.get(f"{_P}/candidates?marketing=not_opted_in", headers=auth_headers)) == ["Out"]
    assert (await client.get(f"{_P}/candidates?marketing=maybe", headers=auth_headers)).status_code == 422


async def test_choosing_by_filter_or_by_hand_and_taking_people_out(client, db_session, organization, auth_headers, pentrix):
    a = await candidate(db_session, organization, "A", "a@example.com", qualified=True)
    b = await candidate(db_session, organization, "B", "b@example.com", qualified=True)
    c = await candidate(db_session, organization, "C", "c@example.com", qualified=False)
    service = PentrixMarketingService(db_session)
    by_filter = await service.resolve(organization.id, {"mode": "filter", "filters": {"qualification": ["qualified"]}}, None)
    assert sorted(x.full_name for x in by_filter.eligible) == ["A", "B"]
    less = await service.resolve(organization.id, {"mode": "filter", "filters": {"qualification": ["qualified"]}, "exclude_ids": [b.id]}, None)
    assert [x.full_name for x in less.eligible] == ["A"]
    by_hand = await service.resolve(organization.id, ids(a, c), None)
    assert sorted(x.full_name for x in by_hand.eligible) == ["A", "C"]
    from app.core.exceptions import ValidationError

    for bad in ({"mode": "ids", "ids": []}, {"mode": "nonsense"}, {"mode": "filter", "filters": {"payment": ["maybe"]}}):
        with pytest.raises(ValidationError):
            await service.resolve(organization.id, bad, None)


# ------------------------------------------------------------------ the templates made available, and when


async def test_only_a_published_template_can_be_made_available_and_it_is_used_as_published(client, db_session, organization, auth_headers, pentrix):
    draft = await create(client, auth_headers, name="Draft only", html=HTML)
    r = await client.post(f"{_M}/templates", headers=auth_headers, json={"template_id": draft["id"], "campaign_name": "X"})
    assert r.status_code == 422 and "Publish" in r.text
    assert draft["id"] not in {t["template_id"] for t in (await client.get(f"{_M}/templates/assignable", headers=auth_headers)).json()}
    published = await template(client, auth_headers)
    assert published["id"] in {t["template_id"] for t in (await client.get(f"{_M}/templates/assignable", headers=auth_headers)).json()}
    item = await available(client, auth_headers, published, "November intake", available_from="2026-01-01")
    assert item["usable"] is True and item["campaign_name"] == "November intake" and item["name"] == "November intake" and item["subject"].startswith("Hi")
    assert (await client.post(f"{_M}/templates", headers=auth_headers, json={"template_id": published["id"], "campaign_name": "Again"})).status_code == 409
    assert published["id"] not in {t["template_id"] for t in (await client.get(f"{_M}/templates/assignable", headers=auth_headers)).json()}


async def test_templates_follow_their_available_dates(client, db_session, organization, auth_headers, pentrix):
    today = datetime.now(timezone.utc).date()
    soon = await available(client, auth_headers, await template(client, auth_headers, "Soon"), "Soon", available_from=str(today + timedelta(days=10)), available_until=str(today + timedelta(days=20)))
    now_ = await available(client, auth_headers, await template(client, auth_headers, "Now"), "Now", available_from=str(today - timedelta(days=1)), available_until=str(today + timedelta(days=1)))
    over = await available(client, auth_headers, await template(client, auth_headers, "Over"), "Over", available_until=str(today - timedelta(days=1)))
    always = await available(client, auth_headers, await template(client, auth_headers, "Always"), "Always")
    assert {t["campaign_name"] for t in (await client.get(f"{_M}/templates?usable=true", headers=auth_headers)).json()} == {"Now", "Always"}
    on_day = {t["campaign_name"] for t in (await client.get(f"{_M}/templates?usable=true&on={today + timedelta(days=15)}", headers=auth_headers)).json()}
    assert on_day == {"Soon", "Always"}  # filter by campaign date
    everything = {t["campaign_name"]: t for t in (await client.get(f"{_M}/templates", headers=auth_headers)).json()}
    assert everything["Over"]["usable"] is False and "available dates" in everything["Over"]["problem"] and everything["Soon"]["usable"] is False
    assert {s["campaign_name"] for s in (await client.get(f"{_M}/templates?q=Alw", headers=auth_headers)).json()} == {"Always"}
    assert always["id"] and now_["id"] and soon["id"] and over["id"]
    switched = await client.patch(f"{_M}/templates/{always['id']}", headers=auth_headers, json={"enabled": False})
    assert switched.json()["usable"] is False and switched.json()["problem"] == "Switched off."
    assert (await client.patch(f"{_M}/templates/{always['id']}", headers=auth_headers, json={"available_from": "2026-05-02", "available_until": "2026-05-01"})).status_code == 422
    assert (await client.patch(f"{_M}/templates/{always['id']}", headers=auth_headers, json={})).status_code == 422
    assert (await client.delete(f"{_M}/templates/{always['id']}", headers=auth_headers)).status_code == 200
    assert (await client.get(f"{_M}/templates?q=Alw", headers=auth_headers)).json() == []


async def test_a_template_needing_a_document_per_recipient_cannot_be_a_marketing_email(client, db_session, organization, auth_headers, pentrix):
    t = await template(client, auth_headers, "Offer letter style")
    version = await db_session.get(EmailStudioVersion, (await db_session.get(EmailStudioTemplate, uuid.UUID(t["id"]))).published_version_id)
    version.config = {"attachments": [{"kind": "recipient", "name": "offer_letter", "required": True}]}
    await db_session.flush()
    r = await client.post(f"{_M}/templates", headers=auth_headers, json={"template_id": t["id"], "campaign_name": "X"})
    assert r.status_code == 422 and "document made for each recipient" in r.text


# ------------------------------------------------------------------ previews


async def test_the_preview_resolves_the_content_for_a_sample_or_for_one_candidate(client, db_session, organization, auth_headers, pentrix):
    a = await candidate(db_session, organization, "Asha Rao", "asha@example.com", qualified=True)
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    sample = (await client.post(f"{_M}/preview", headers=auth_headers, json={"assignment_id": item["id"]})).json()
    assert sample["sample"] is True and sample["subject"] == "Hi Asha: November intake" and "Hello Asha" in sample["html"] and sample["candidate"] is None
    real = (await client.post(f"{_M}/preview", headers=auth_headers, json={"assignment_id": item["id"], "candidate_id": str(a.id)})).json()
    assert real["sample"] is False and real["candidate"]["email"] == "asha@example.com" and "you are Qualified" in real["html"]
    assert real["missing"] == [] and real["attachments"] == []


async def test_every_preview_and_email_carries_an_unsubscribe_link_even_if_the_template_has_none(client, db_session, organization, auth_headers, pentrix):
    item = await available(client, auth_headers, await template(client, auth_headers, html=HTML), "No link in the design")
    preview = (await client.post(f"{_M}/preview", headers=auth_headers, json={"assignment_id": item["id"]})).json()
    assert "Unsubscribe" in preview["html"] and "pentrix-unsubscribe?token=" in preview["html"] and "Unsubscribe:" in preview["text"]
    with_link = await available(client, auth_headers, await template(client, auth_headers, "Own link", html=HTML_WITH_UNSUB), "Own link")
    own = (await client.post(f"{_M}/preview", headers=auth_headers, json={"assignment_id": with_link["id"]})).json()
    assert own["html"].count("pentrix-unsubscribe?token=") == 1  # the template's own link is used, not doubled


async def test_the_final_preview_has_the_recipient_count_and_a_brand_and_signature_to_choose(client, db_session, organization, auth_headers, pentrix):
    from modules.email_studio.models import EmailBrandProfile, EmailSignature

    brand = EmailBrandProfile(organization_id=organization.id, name="Pentrix brand", company_name="GIR Technologies", is_default=True)
    signature = EmailSignature(organization_id=organization.id, name="Team signature", person_name="Priya Nair", designation="Programme lead", is_default=True)
    db_session.add_all([brand, signature])
    a = await candidate(db_session, organization, "A", "a@example.com")
    b = await candidate(db_session, organization, "B", "b@example.com")
    await candidate(db_session, organization, "Out", "out@example.com", opted=False)
    await db_session.flush()
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    options = (await client.get(f"{_M}/options", headers=auth_headers)).json()
    assert [o["name"] for o in options["brands"]] == ["Pentrix brand"] and [o["name"] for o in options["signatures"]] == ["Team signature"]
    body = (await client.post(f"{_M}/preview", headers=auth_headers, json={
        "assignment_id": item["id"], "selection": {"mode": "filter"}, "brand_profile_id": str(brand.id), "signature_id": str(signature.id)})).json()
    assert body["brand"] == "Pentrix brand" and body["signature"] == "Team signature" and body["subject"].startswith("Hi")
    assert body["recipients"]["eligible"] == 2 and body["recipients"]["selected"] == 3 and body["candidate"]["id"] in {str(a.id), str(b.id)}
    assert body["recipients"]["excluded"] == [{"reason": "not_opted_in", "label": "Has not agreed to marketing email", "count": 1}]
    as_b = (await client.post(f"{_M}/preview", headers=auth_headers, json={"assignment_id": item["id"], "selection": {"mode": "filter"}, "candidate_id": str(b.id)})).json()
    assert as_b["candidate"]["id"] == str(b.id)
    assert (await client.post(f"{_M}/preview", headers=auth_headers, json={"assignment_id": item["id"], "brand_profile_id": str(uuid.uuid4())})).status_code == 422


async def test_the_recipient_preview_lists_the_people_and_why_others_are_left_out(client, db_session, organization, auth_headers, pentrix):
    a = await candidate(db_session, organization, "A", "a@example.com")
    await candidate(db_session, organization, "B", "b@example.com", verified=False)
    r = (await client.post(f"{_M}/recipients/preview", headers=auth_headers, json={"selection": {"mode": "filter"}})).json()
    assert r["eligible"] == 1 and r["people"] == [{"id": str(a.id), "name": "A", "email": "a@example.com"}]
    assert r["excluded"][0]["label"] == "Email address not verified"


# ------------------------------------------------------------------ confirming


async def test_a_send_needs_an_explicit_confirmation_the_shown_count_and_someone_to_send_to(client, db_session, organization, auth_headers, pentrix, outbox):
    a = await candidate(db_session, organization, "A", "a@example.com")
    out = await candidate(db_session, organization, "Out", "out@example.com", opted=False)
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    body = {"assignment_id": item["id"], "selection": ids(a), "expected_count": 1, "idempotency_key": uuid.uuid4().hex}
    assert (await client.post(f"{_M}/campaigns", headers=auth_headers, json=body)).status_code == 422  # no confirm
    assert (await client.post(f"{_M}/campaigns", headers=auth_headers, json={**body, "confirm": False})).status_code == 422
    assert (await client.post(f"{_M}/campaigns", headers=auth_headers, json={**body, "confirm": True, "expected_count": 2})).status_code == 409  # not the number shown
    assert (await client.post(f"{_M}/campaigns", headers=auth_headers, json={**body, "confirm": True, "selection": ids(out), "expected_count": 1})).status_code == 422  # nobody eligible
    assert outbox == [] and (await db_session.execute(select(PentrixMarketingCampaign))).first() is None
    made = await confirm(client, auth_headers, item, ids(a), 1)
    assert made["status"] == "sending" and made["recipient_count"] == 1 and made["counts"]["queued"] == 1 and outbox == []  # confirming sends nothing by itself
    assert made["subject"] == "Hi {{first_name}}: {{campaign_name}}"  # the campaign shows the template's subject, not one person's


async def test_the_same_confirmation_twice_makes_one_campaign(client, db_session, organization, auth_headers, pentrix):
    a = await candidate(db_session, organization, "A", "a@example.com")
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    first = await confirm(client, auth_headers, item, ids(a), 1, key="same-click-001")
    second = await confirm(client, auth_headers, item, ids(a), 1, key="same-click-001")
    assert first["id"] == second["id"]
    assert len((await db_session.execute(select(PentrixMarketingCampaign))).scalars().all()) == 1
    assert len((await db_session.execute(select(PentrixMarketingRecipient))).scalars().all()) == 1


async def test_a_campaign_is_capped_and_a_template_outside_its_dates_cannot_be_sent(client, db_session, organization, auth_headers, pentrix, monkeypatch):
    a = await candidate(db_session, organization, "A", "a@example.com")
    b = await candidate(db_session, organization, "B", "b@example.com")
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    monkeypatch.setattr(marketing, "MAX_RECIPIENTS", 1)
    assert "at most 1" in (await client.post(f"{_M}/campaigns", headers=auth_headers, json={"assignment_id": item["id"], "selection": ids(a, b), "expected_count": 2, "confirm": True, "idempotency_key": uuid.uuid4().hex})).text
    expired = await available(client, auth_headers, await template(client, auth_headers, "Old"), "Old", available_until="2020-01-01")
    r = await client.post(f"{_M}/campaigns", headers=auth_headers, json={"assignment_id": expired["id"], "selection": ids(a), "expected_count": 1, "confirm": True, "idempotency_key": uuid.uuid4().hex})
    assert r.status_code == 422 and "available dates" in r.text


async def test_someone_who_got_this_template_recently_is_not_sent_it_again_but_a_different_template_is_fine(client, db_session, organization, auth_headers, pentrix, outbox):
    a = await candidate(db_session, organization, "A", "a@example.com")
    first = await available(client, auth_headers, await template(client, auth_headers, "First"), "First")
    other = await available(client, auth_headers, await template(client, auth_headers, "Other"), "Other")
    await confirm(client, auth_headers, first, ids(a), 1)
    again = await client.post(f"{_M}/campaigns", headers=auth_headers, json={"assignment_id": first["id"], "selection": ids(a), "expected_count": 1, "confirm": True, "idempotency_key": uuid.uuid4().hex})
    assert again.status_code == 422  # nobody left: already queued for this template
    r = (await client.post(f"{_M}/recipients/preview", headers=auth_headers, json={"selection": ids(a), "assignment_id": first["id"]})).json()
    assert r["eligible"] == 0 and r["excluded"][0]["label"].startswith("Already received")
    await confirm(client, auth_headers, other, ids(a), 1)


# ------------------------------------------------------------------ sending


async def test_messages_go_out_with_the_candidates_values_and_a_working_unsubscribe_link(client, db_session, organization, auth_headers, pentrix, outbox):
    a = await candidate(db_session, organization, "Asha Rao", "asha@example.com", qualified=True)
    b = await candidate(db_session, organization, "Bina Shah", "bina@example.com", qualified=False)
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    campaign = await confirm(client, auth_headers, item, ids(a, b), 2)
    assert await run(db_session) == ["sent", "sent"]
    by_to = {m["to"]: m for m in outbox}
    assert by_to["asha@example.com"]["subject"] == "Hi Asha: November intake" and "you are Qualified" in by_to["asha@example.com"]["html"]
    assert "you are Not qualified" in by_to["bina@example.com"]["html"]
    for m in outbox:
        link = m["headers"]["List-Unsubscribe"]
        assert link.startswith("<http") and "/api/v1/public/pentrix-marketing/unsubscribe?token=" in link and m["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        token = link.split("token=")[1].rstrip(">")
        claims = read_token(token)
        assert claims and claims["email"] == m["to"] and claims["organization_id"] == organization.id
        assert "pentrix-unsubscribe?token=" + token in m["html"]
        assert m["meta"].key == "pentrix_marketing" and m["meta"].idempotency_key.startswith("pxm:")
    done = (await client.get(f"{_M}/campaigns/{campaign['id']}", headers=auth_headers)).json()
    assert done["status"] == "completed" and done["counts"]["sent"] == 2 and done["completed_at"]


async def test_sending_is_rate_limited_and_nothing_is_sent_twice(client, db_session, organization, auth_headers, pentrix, outbox):
    people = [await candidate(db_session, organization, f"P{i}", f"p{i}@example.com") for i in range(5)]
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    campaign = await confirm(client, auth_headers, item, ids(*people), 5)
    assert await run(db_session, limit=2) == ["sent", "sent"] and len(outbox) == 2
    status = (await client.get(f"{_M}/campaigns/{campaign['id']}", headers=auth_headers)).json()
    assert status["status"] == "sending" and status["counts"]["sent"] == 2 and status["counts"]["queued"] == 3
    await run(db_session, limit=2)
    await run(db_session, limit=2)
    assert await run(db_session, limit=2) == []  # nothing left
    assert sorted(m["to"] for m in outbox) == sorted(p.email for p in people)  # five addresses, five messages
    service = PentrixMarketingService(db_session)
    for rid in (await db_session.execute(select(PentrixMarketingRecipient.id))).scalars().all():
        assert await service.process(rid) == "skipped"  # already done: a second pass does nothing
    assert len(outbox) == 5
    assert (await client.get(f"{_M}/campaigns/{campaign['id']}", headers=auth_headers)).json()["status"] == "completed"


async def test_the_database_itself_refuses_the_same_address_twice_in_one_campaign(client, db_session, organization, auth_headers, pentrix):
    from sqlalchemy.exc import IntegrityError

    a = await candidate(db_session, organization, "A", "a@example.com")
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    campaign = await confirm(client, auth_headers, item, ids(a), 1)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(PentrixMarketingRecipient(campaign_id=uuid.UUID(campaign["id"]), pentrix_user_id=a.pentrix_user_id, email="a@example.com", name="A"))
            await db_session.flush()


async def test_consent_is_checked_again_at_the_moment_each_message_is_sent(client, db_session, organization, auth_headers, pentrix, outbox):
    stays = await candidate(db_session, organization, "Stays", "stays@example.com")
    opts_out = await candidate(db_session, organization, "Opts out", "out@example.com")
    unsubscribes = await candidate(db_session, organization, "Unsubscribes", "unsub@example.com")
    unverified = await candidate(db_session, organization, "Changed", "changed@example.com")
    moved = await candidate(db_session, organization, "Moved", "moved@example.com")
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    await confirm(client, auth_headers, item, ids(stays, opts_out, unsubscribes, unverified, moved), 5)
    # after the campaign was confirmed, but before it went out:
    opts_out.marketing_opt_in = False  # turned it off in their Pentrix Settings
    db_session.add(PentrixMarketingSuppression(organization_id=organization.id, email="unsub@example.com", pentrix_user_id=unsubscribes.pentrix_user_id))
    unverified.email_verified = False
    moved.email = "new-address@example.com"
    await db_session.flush()
    results = await run(db_session)
    assert sorted(results) == ["sent", "skipped", "skipped", "skipped", "skipped"]
    assert [m["to"] for m in outbox] == ["stays@example.com"]
    reasons = {r.email: r.error for r in (await db_session.execute(select(PentrixMarketingRecipient))).scalars() if r.status == "skipped"}
    assert reasons["out@example.com"] == "Has not agreed to marketing email" and reasons["unsub@example.com"] == "Unsubscribed"
    assert reasons["changed@example.com"] == "Email address not verified" and reasons["moved@example.com"] == "Their email address has changed."


async def test_a_message_the_mail_server_refuses_is_tried_again_a_few_times_and_then_failed(client, db_session, organization, auth_headers, pentrix, outbox):
    a = await candidate(db_session, organization, "A", "a@example.com")
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    campaign = await confirm(client, auth_headers, item, ids(a), 1)
    outbox.fail = True
    assert await run(db_session) == ["queued"] and await run(db_session) == ["queued"] and await run(db_session) == ["failed"]
    assert await run(db_session) == []  # given up
    row = (await db_session.execute(select(PentrixMarketingRecipient))).scalar_one()
    assert row.status == "failed" and row.attempts == 3 and "did not accept" in row.error
    final = (await client.get(f"{_M}/campaigns/{campaign['id']}", headers=auth_headers)).json()
    assert final["status"] == "completed" and final["counts"]["failed"] == 1


async def test_a_worker_that_died_mid_batch_does_not_cause_a_duplicate_or_lose_the_message(client, db_session, organization, auth_headers, pentrix, outbox):
    a = await candidate(db_session, organization, "A", "a@example.com")
    b = await candidate(db_session, organization, "B", "b@example.com")
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    await confirm(client, auth_headers, item, ids(a, b), 2)
    service = PentrixMarketingService(db_session)
    claimed = await service.claim(10)
    assert len(claimed) == 2 and await service.claim(10) == []  # claimed: a second worker gets nothing
    # the worker died: one message had in fact gone out and been recorded, the other had not
    rows = {r.email: r for r in (await db_session.execute(select(PentrixMarketingRecipient))).scalars()}
    for r in rows.values():
        r.claimed_at = datetime.now(timezone.utc) - marketing.CLAIM_TIMEOUT - timedelta(minutes=1)
    db_session.add(EmailSendRecord(organization_id=organization.id, recipient="a@example.com", status="sent", idempotency_key=f"pxm:{rows['a@example.com'].id}", key="pentrix_marketing"))
    await db_session.flush()
    assert len(await service.claim(10)) == 2  # both come back
    results = {r.email: await service.process(r.id) for r in rows.values()}
    assert results == {"a@example.com": "sent", "b@example.com": "sent"}
    assert [m["to"] for m in outbox] == ["b@example.com"]  # a's earlier send is recorded, so it is not sent again


async def test_cancelling_stops_what_has_not_gone_out(client, db_session, organization, auth_headers, pentrix, outbox):
    people = [await candidate(db_session, organization, f"P{i}", f"p{i}@example.com") for i in range(3)]
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    campaign = await confirm(client, auth_headers, item, ids(*people), 3)
    await run(db_session, limit=1)
    cancelled = (await client.post(f"{_M}/campaigns/{campaign['id']}/cancel", headers=auth_headers)).json()
    assert cancelled["status"] == "cancelled" and cancelled["counts"]["sent"] == 1 and cancelled["counts"]["skipped"] == 2
    assert await run(db_session) == [] and len(outbox) == 1
    assert (await client.post(f"{_M}/campaigns/{campaign['id']}/cancel", headers=auth_headers)).status_code == 409


async def test_a_template_with_a_value_nobody_supplies_cannot_be_sent(client, db_session, organization, auth_headers, pentrix):
    a = await candidate(db_session, organization, "A", "a@example.com")
    html = page("<p>Hi {{first_name}}, your code is {{no_such_value}}</p>")
    item = await available(client, auth_headers, await template(client, auth_headers, "Broken", html=html), "Broken")
    preview = (await client.post(f"{_M}/preview", headers=auth_headers, json={"assignment_id": item["id"], "candidate_id": str(a.id)})).json()
    assert preview["warnings"] and "no_such_value" in " ".join(preview["warnings"])
    r = await client.post(f"{_M}/campaigns", headers=auth_headers, json={"assignment_id": item["id"], "selection": ids(a), "expected_count": 1, "confirm": True, "idempotency_key": uuid.uuid4().hex})
    assert r.status_code == 422 and "no_such_value" in r.text


async def test_the_campaign_list_and_each_campaigns_recipients_can_be_read_by_status(client, db_session, organization, auth_headers, pentrix, outbox):
    people = [await candidate(db_session, organization, f"P{i}", f"p{i}@example.com") for i in range(3)]
    await candidate(db_session, organization, "Out", "out@example.com", opted=False)
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    campaign = await confirm(client, auth_headers, item, {"mode": "filter"}, 3)
    await run(db_session, limit=2)
    listing = (await client.get(f"{_M}/campaigns", headers=auth_headers)).json()
    assert listing["total"] == 1 and listing["items"][0]["counts"]["sent"] == 2 and listing["items"][0]["excluded"] == {"Has not agreed to marketing email": 1}
    queued = (await client.get(f"{_M}/campaigns/{campaign['id']}/recipients?status=queued", headers=auth_headers)).json()
    sent = (await client.get(f"{_M}/campaigns/{campaign['id']}/recipients?status=sent&page_size=1", headers=auth_headers)).json()
    assert queued["total"] == 1 and sent["total"] == 2 and len(sent["items"]) == 1 and people
    assert (await client.get(f"{_M}/campaigns/{campaign['id']}/recipients?status=weird", headers=auth_headers)).status_code == 422


# ------------------------------------------------------------------ unsubscribing


def unsubscribe_url(organization, row, path="/api/v1/public/pentrix-marketing/unsubscribe"):
    return f"{path}?token={sign_token(organization.id, row.pentrix_user_id, row.email)}"


async def test_the_unsubscribe_link_works_without_signing_in_and_stops_future_email(client, db_session, organization, auth_headers, pentrix, outbox):
    a = await candidate(db_session, organization, "Asha Rao", "asha.rao@example.com")
    pentrix.candidate(id=a.pentrix_user_id, email=a.email)
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    await confirm(client, auth_headers, item, ids(a), 1)
    info = await client.get(unsubscribe_url(organization, a))  # no Authorization header
    assert info.status_code == 200 and info.json() == {"email": "a*******@example.com", "unsubscribed": False}
    done = await client.post(unsubscribe_url(organization, a))
    assert done.status_code == 200 and done.json()["unsubscribed"] is True
    again = await client.post(unsubscribe_url(organization, a))  # clicking twice is harmless
    assert again.status_code == 200
    suppressions = (await db_session.execute(select(PentrixMarketingSuppression))).scalars().all()
    assert len(suppressions) == 1 and suppressions[0].email == "asha.rao@example.com" and suppressions[0].pentrix_synced is True
    await db_session.refresh(a)
    assert a.marketing_opt_in is False and pentrix.unsubscribed == [a.pentrix_user_id]  # Pentrix was told, once
    assert await run(db_session) == [] and outbox == []  # the waiting message was dropped
    res = await PentrixMarketingService(db_session).resolve(organization.id, ids(a), None)
    assert res.eligible == [] and res.excluded == {"not_opted_in": 1}


async def test_the_one_click_header_post_from_a_mail_program_is_accepted(client, db_session, organization, auth_headers, pentrix):
    a = await candidate(db_session, organization, "A", "a@example.com")
    r = await client.post(unsubscribe_url(organization, a), content="List-Unsubscribe=One-Click", headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 200 and r.json()["unsubscribed"] is True


async def test_a_forged_or_damaged_link_unsubscribes_nobody(client, db_session, organization, auth_headers, pentrix):
    a = await candidate(db_session, organization, "A", "a@example.com")
    token = sign_token(organization.id, a.pentrix_user_id, a.email)
    body, _, sig = token.partition(".")
    for bad in ("", "nonsense", f"{body}.{'0' * 64}", f"{body[:-2]}xx.{sig}", f".{sig}"):
        assert (await client.get(f"/api/v1/public/pentrix-marketing/unsubscribe?token={bad}")).status_code == 422, bad
        assert (await client.post(f"/api/v1/public/pentrix-marketing/unsubscribe?token={bad}")).status_code == 422, bad
    other = sign_token(organization.id, a.pentrix_user_id, "someone.else@example.com")  # a real signature, for a different address
    assert read_token(other)["email"] == "someone.else@example.com"  # (valid, but only ever for that address)
    assert (await db_session.execute(select(PentrixMarketingSuppression))).first() is None


async def test_the_unsubscribe_is_honoured_here_even_when_pentrix_cannot_be_told_and_is_passed_on_later(client, db_session, organization, auth_headers, pentrix):
    a = await candidate(db_session, organization, "A", "a@example.com")
    pentrix.candidate(id=a.pentrix_user_id, email=a.email)
    pentrix.down = True
    assert (await client.post(unsubscribe_url(organization, a))).status_code == 200
    suppression = (await db_session.execute(select(PentrixMarketingSuppression))).scalar_one()
    assert suppression.pentrix_synced is False
    res = await PentrixMarketingService(db_session).resolve(organization.id, ids(a), None)
    assert res.eligible == []  # already unsubscribed here, whatever Pentrix knows
    pentrix.down = False
    assert await PentrixMarketingService(db_session).retry_unsynced() == 1
    await db_session.refresh(suppression)
    assert suppression.pentrix_synced is True and pentrix.unsubscribed == [a.pentrix_user_id]


async def test_opting_in_again_in_pentrix_lifts_an_old_unsubscribe_but_an_old_state_does_not(client, db_session, organization, auth_headers, pentrix):
    from modules.pentrix_ops.candidates import PentrixCandidateService

    summary = pentrix.candidate(full_name="Asha", email="asha@example.com", email_verified=True, marketing={"opt_in": True, "changed_at": utc(-120).isoformat()})
    row = await PentrixCandidateService(db_session).upsert(organization.id, summary)
    assert (await client.post(unsubscribe_url(organization, row))).status_code == 200
    suppression_at = (await db_session.execute(select(PentrixMarketingSuppression.created_at))).scalar_one()
    # Pentrix still shows the OLD opt-in (it has not been told yet): the unsubscribe must stand
    stale = {**summary, "updated_at": (datetime.fromisoformat(summary["updated_at"]) + timedelta(seconds=30)).isoformat()}
    row = await PentrixCandidateService(db_session).upsert(organization.id, stale)
    assert (await db_session.execute(select(PentrixMarketingSuppression))).first() is not None
    assert (await PentrixMarketingService(db_session).resolve(organization.id, ids(row), None)).eligible == []
    # the candidate opts in again themselves, later
    fresh = {**summary, "updated_at": (datetime.fromisoformat(summary["updated_at"]) + timedelta(seconds=60)).isoformat(),
             "marketing": {"opt_in": True, "changed_at": (suppression_at + timedelta(minutes=5)).isoformat()}}
    row = await PentrixCandidateService(db_session).upsert(organization.id, fresh)
    assert (await db_session.execute(select(PentrixMarketingSuppression))).first() is None
    assert len((await PentrixMarketingService(db_session).resolve(organization.id, ids(row), None)).eligible) == 1


# ------------------------------------------------------------------ who may do what, and the wiring


async def test_viewing_choosing_templates_and_sending_are_separate_permissions(client, db_session, organization, auth_headers, pentrix):
    a = await candidate(db_session, organization, "A", "a@example.com")
    t = await template(client, auth_headers)
    item = await available(client, auth_headers, t, "November intake")
    _, viewer = await person(db_session, organization, ["pentrix_ops.marketing.view"])
    _, manager = await person(db_session, organization, ["pentrix_ops.marketing.view", "pentrix_ops.marketing.manage"])
    _, sender = await person(db_session, organization, ["pentrix_ops.marketing.send"])
    _, nobody = await person(db_session, organization, ["pentrix_ops.registrations.view", "pentrix_ops.bookings.assigned"])
    for headers in (viewer, manager):
        assert (await client.get(f"{_M}/templates", headers=headers)).status_code == 200
        assert (await client.get(f"{_M}/campaigns", headers=headers)).status_code == 200
    assert (await client.post(f"{_M}/templates", headers=viewer, json={"template_id": t["id"], "campaign_name": "x"})).status_code == 403
    assert (await client.patch(f"{_M}/templates/{item['id']}", headers=viewer, json={"enabled": False})).status_code == 403
    assert (await client.get(f"{_M}/templates/assignable", headers=manager)).status_code == 200
    for path_headers in ((viewer, "preview"), (manager, "preview"), (viewer, "recipients/preview")):
        r = await client.post(f"{_M}/{path_headers[1]}", headers=path_headers[0], json={"assignment_id": item["id"], "selection": {"mode": "filter"}})
        assert r.status_code == 403
    assert (await client.post(f"{_M}/recipients/preview", headers=sender, json={"selection": ids(a)})).status_code == 200
    assert (await client.post(f"{_M}/campaigns", headers=viewer, json={"assignment_id": item["id"], "selection": ids(a), "expected_count": 1, "confirm": True, "idempotency_key": "k" * 12})).status_code == 403
    assert (await client.post(f"{_M}/campaigns", headers=sender, json={"assignment_id": item["id"], "selection": ids(a), "expected_count": 1, "confirm": True, "idempotency_key": "k" * 12})).status_code == 201
    assert (await client.get(f"{_M}/campaigns", headers=sender)).status_code == 403  # sending is not viewing history
    for path in ("/templates", "/campaigns", "/options"):
        assert (await client.get(f"{_M}{path}", headers=nobody)).status_code == 403


async def test_another_organisation_cannot_use_the_templates_or_candidates(client, db_session, organization, auth_headers, pentrix):
    from modules.organizations.repository import OrganizationRepository
    from tests._fixtures import _make_user

    a = await candidate(db_session, organization, "A", "a@example.com")
    item = await available(client, auth_headers, await template(client, auth_headers), "November intake")
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other, is_superuser=True, email=f"o-{uuid.uuid4().hex[:8]}@erpx.example.com")
    theirs = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"{_M}/templates", headers=theirs)).status_code == 422
    assert (await client.post(f"{_M}/campaigns", headers=theirs, json={"assignment_id": item["id"], "selection": ids(a), "expected_count": 1, "confirm": True, "idempotency_key": "z" * 12})).status_code == 422


def test_the_wiring_exists():
    from app.core.celery_app import celery_app
    from modules.authorization.service import DEFAULT_PERMISSIONS
    from modules.email_studio.schemas import CATEGORIES
    from packages.email.registry import get_def

    assert "pentrix.dispatch_marketing" in {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert {"pentrix_ops.marketing.view", "pentrix_ops.marketing.manage", "pentrix_ops.marketing.send"} <= {p[0] for p in DEFAULT_PERMISSIONS}
    assert "Pentrix Marketing" in CATEGORIES
    definition = get_def("pentrix_marketing")
    assert definition and {"first_name", "full_name", "unsubscribe_url", "portal_url", "campaign_name"} <= {v.name for v in definition.variables}


def test_the_token_round_trips_and_is_for_one_address_only():
    org = uuid.uuid4()
    token = sign_token(org, "user-1", "Asha@Example.com")
    assert read_token(token) == {"organization_id": org, "pentrix_user_id": "user-1", "email": "asha@example.com"}
    assert marketing.mask("asha@example.com") == "a***@example.com"
    assert marketing.with_unsubscribe("<html><body><p>x</p></body></html>", "x", "https://u")[0].count("https://u") == 1
    assert date.today() and push_headers
