"""
Pentrix candidates in ERPX: the synchronised summaries (pushed by Pentrix and pulled by cursor), the Registrations and Assessments lists
(filters that combine, sorting, paging), opening one candidate, editing the few details ERPX may change, the Overview numbers, and who
may see what. Pentrix is replaced by the fake from the bookings tests, extended with candidates.
"""
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from modules.email_studio.models import EmailSendRecord
from modules.pentrix_ops import client as client_module
from modules.pentrix_ops.client import sign
from modules.pentrix_ops.models import PentrixBooking, PentrixCandidate, PentrixSyncState
from tests.api.test_pentrix_ops import SECRET, FakePentrix, person, push_headers, utc

pytestmark = pytest.mark.api

_P = "/api/v1/pentrix-ops"
_PREFIX = "/api/v1/internal/erpx"


class FakePentrixWithCandidates(FakePentrix):
    def __init__(self):
        super().__init__()
        self.candidates: dict[str, dict] = {}
        self.profiles: dict[str, dict] = {}

    def candidate(self, **over) -> dict:
        cid = over.pop("id", str(uuid.uuid4()))
        summary = {
            "id": cid, "full_name": "Asha Rao", "email": f"{cid[:6]}@example.com", "phone": None, "email_verified": True,
            "registered_at": utc(-60 * 24).isoformat(),
            "assessment": {"state": "not_started", "attempts": 0, "readiness_commitment_pct": None, "technical_pct": None, "qualified": None, "assessed_at": None},
            "booking": None,
            "payment": {"status": "none", "paid_total_paise": 0, "currency": "INR", "last_paid_at": None, "payment_count": 0},
            "enrolled": False, "last_activity_at": utc(-60 * 24).isoformat(), "updated_at": self._stamp(),
        }
        for key, value in over.items():
            if isinstance(value, dict) and isinstance(summary.get(key), dict):
                summary[key] = {**summary[key], **value}
            else:
                summary[key] = value
        self.candidates[cid] = summary
        return summary

    def touch(self, cid: str, **over) -> dict:
        summary = self.candidates[cid]
        for key, value in over.items():
            summary[key] = {**summary[key], **value} if isinstance(value, dict) and isinstance(summary.get(key), dict) else value
        summary["updated_at"] = self._stamp()
        return summary

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = urlparse(str(request.url))
        if not url.path.startswith(f"{_PREFIX}/candidates"):
            return super().handler(request)
        if self.down:
            raise httpx.ConnectError("down")
        path_and_query = url.path + (f"?{url.query}" if url.query else "")
        body = request.content.decode() if request.content else ""
        expected = sign(SECRET, request.headers.get("X-ERPX-Timestamp", ""), request.method, path_and_query, body)
        if not hmac.compare_digest(expected, request.headers.get("X-ERPX-Signature", "")):
            return httpx.Response(401, json={"error": "auth_error", "message": "Invalid signature."})
        payload = json.loads(body) if body else None
        path = url.path.replace(_PREFIX, "")
        self.calls.append((request.method, path, payload, request.headers.get("X-ERPX-Actor")))
        if self.fail:
            code, message = self.fail
            return httpx.Response(code, json={"error": "x", "message": message})
        if request.method == "GET" and path == "/candidates":
            cursor = parse_qs(url.query).get("cursor", [""])[0]
            items = sorted(self.candidates.values(), key=lambda c: (c["updated_at"], c["id"]))
            if cursor:
                stamp, _, last = cursor.partition("|")
                items = [c for c in items if (c["updated_at"], c["id"]) > (stamp, last)]
            last_item = items[-1] if items else None
            return httpx.Response(200, json={"items": items, "next_cursor": f"{last_item['updated_at']}|{last_item['id']}" if last_item else cursor or None, "has_more": False})
        parts = path.split("/")  # ['', 'candidates', id, maybe 'assessment']
        cid = parts[2] if len(parts) > 2 else ""
        summary = self.candidates.get(cid)
        if summary is None:
            return httpx.Response(404, json={"error": "not_found", "message": "That candidate was not found."})
        if request.method == "GET" and len(parts) == 3:
            profile = self.profiles.get(cid) or {"registration": {"id": cid, "email": summary["email"]}, "assessment": {"attempts": []}, "bookings": [], "payments": [], "activity": []}
            return httpx.Response(200, json={**profile, "summary": summary})
        if request.method == "GET" and parts[3:] == ["assessment"]:
            return httpx.Response(200, json={"summary": summary, "assessment": {"state": summary["assessment"]["state"], "criteria": {"readiness_commitment_pct": 100.0, "technical_pct": 40.0}, "qualified": summary["assessment"]["qualified"], "attempts": [{"id": "a1", "qualified": summary["assessment"]["qualified"]}]}})
        if request.method == "PATCH":
            if set(payload) - {"full_name", "phone"}:
                return httpx.Response(422, json={"error": "validation_error", "message": "Only the name and phone number can be changed."})
            if payload.get("phone") == "bad":
                return httpx.Response(422, json={"error": "validation_error", "message": "A phone number may contain digits."})
            self.touch(cid, **payload)
            return httpx.Response(200, json=summary)
        return httpx.Response(404, json={"error": "not_found", "message": "unknown"})


@pytest.fixture
def pentrix(monkeypatch, organization):
    fake = FakePentrixWithCandidates()
    monkeypatch.setattr(settings, "PENTRIX_ORGANIZATION_SLUG", organization.slug)
    monkeypatch.setattr(settings, "PENTRIX_INTERNAL_API_BASE_URL", "http://pentrix.test")
    monkeypatch.setattr(settings, "ERPX_INTERNAL_SERVICE_SECRET", SECRET)
    monkeypatch.setattr(client_module, "DEFAULT_TRANSPORT", httpx.MockTransport(fake.handler))
    return fake


async def sync(client, headers):
    r = await client.post(f"{_P}/candidates/sync", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["updated"]


def qualified(**more):
    return {"assessment": {"state": "completed", "attempts": 1, "readiness_commitment_pct": 100.0, "technical_pct": 80.0, "qualified": True, "assessed_at": utc(-60).isoformat()}, **more}


def failed(**more):
    return {"assessment": {"state": "completed", "attempts": 1, "readiness_commitment_pct": 100.0, "technical_pct": 20.0, "qualified": False, "assessed_at": utc(-30).isoformat()}, **more}


def booked(status="confirmed", start=None):
    start = start or utc(60 * 24)
    return {"booking": {"id": str(uuid.uuid4()), "reference": "BK-1", "status": status, "slot_start": start.isoformat(), "slot_end": (start + timedelta(hours=1)).isoformat(), "open": True}}


def payment(status, total=0):
    return {"payment": {"status": status, "paid_total_paise": total, "payment_count": 1 if status != "none" else 0, "last_paid_at": utc(-5).isoformat() if status == "paid" else None}}


async def names(client, headers, query=""):
    r = await client.get(f"{_P}/candidates?{query}", headers=headers)
    assert r.status_code == 200, r.text
    return sorted(c["full_name"] for c in r.json()["items"])


# ------------------------------------------------------------------ the copy


async def test_pentrix_pushes_a_candidate_and_a_repeat_or_older_message_changes_nothing(client, db_session, organization, pentrix):
    cand = pentrix.candidate(full_name="Asha Rao", **qualified())
    body = json.dumps(cand)
    assert (await client.post("/api/v1/internal/pentrix/candidates", content=body, headers=push_headers(body))).status_code == 200
    assert (await client.post("/api/v1/internal/pentrix/candidates", content=body, headers=push_headers(body))).status_code == 200  # twice
    rows = (await db_session.execute(select(PentrixCandidate))).scalars().all()
    assert len(rows) == 1 and rows[0].pentrix_user_id == cand["id"] and rows[0].qualified is True and rows[0].technical_pct == 80.0
    older = {**cand, "full_name": "Old Name", "assessment": {**cand["assessment"], "qualified": False}, "updated_at": (datetime.fromisoformat(cand["updated_at"]) - timedelta(seconds=9)).isoformat()}
    await client.post("/api/v1/internal/pentrix/candidates", content=json.dumps(older), headers=push_headers(json.dumps(older)))
    await db_session.refresh(rows[0])
    assert rows[0].full_name == "Asha Rao" and rows[0].qualified is True  # the older message did not overwrite the newer state


async def test_candidate_pushes_without_a_valid_signature_are_refused(client, db_session, organization, pentrix):
    body = json.dumps(pentrix.candidate())
    assert (await client.post("/api/v1/internal/pentrix/candidates", content=body)).status_code == 401
    assert (await client.post("/api/v1/internal/pentrix/candidates", content=body, headers=push_headers(body, "wrong"))).status_code == 401
    assert (await db_session.execute(select(PentrixCandidate))).first() is None


async def test_the_pull_resumes_from_its_cursor_and_picks_up_only_what_changed(client, db_session, organization, auth_headers, pentrix):
    a, b, c = (pentrix.candidate(full_name=n) for n in ("Asha", "Bina", "Chitra"))
    assert await sync(client, auth_headers) == 3
    assert await sync(client, auth_headers) == 0
    pentrix.touch(b["id"], **qualified())
    assert await sync(client, auth_headers) == 1
    assert (await db_session.execute(select(PentrixCandidate.qualified).where(PentrixCandidate.pentrix_user_id == b["id"]))).scalar_one() is True
    assert (await db_session.execute(select(PentrixCandidate))).scalars().all().__len__() == 3  # no duplicates, matched by Pentrix's id


async def test_a_failed_pull_keeps_its_place_and_says_what_went_wrong(client, db_session, organization, auth_headers, pentrix):
    pentrix.candidate(full_name="Asha")
    assert await sync(client, auth_headers) == 1
    pentrix.candidate(full_name="Bina")
    pentrix.down = True
    assert (await client.post(f"{_P}/candidates/sync", headers=auth_headers)).status_code == 503
    pentrix.down = False
    assert await sync(client, auth_headers) == 1  # resumed from where it had got to
    state = (await db_session.execute(select(PentrixSyncState).where(PentrixSyncState.key == "candidates_cursor"))).scalar_one()
    assert state.last_run_at is not None and state.last_error is None


# ------------------------------------------------------------------ the lists


async def seed_funnel(client, auth_headers, pentrix):
    """Six people at different points of the journey."""
    pentrix.candidate(full_name="New Person", phone="+91 90000 00001")
    pentrix.candidate(full_name="Started", assessment={"state": "in_progress", "attempts": 0})
    pentrix.candidate(full_name="Failed One", **failed())
    pentrix.candidate(full_name="Qualified Only", **qualified())
    pentrix.candidate(full_name="Qualified Booked", **qualified(), **booked())
    pentrix.candidate(full_name="Qualified Pending Pay", **qualified(), **payment("pending"))
    pentrix.candidate(full_name="Paid Booked", **qualified(), **booked(), **payment("paid", 250000))
    pentrix.candidate(full_name="Payment Failed", **qualified(), **payment("failed"))
    await sync(client, auth_headers)


async def test_filters_combine_so_that_qualified_unpaid_and_unbooked_can_be_asked_for(client, db_session, organization, auth_headers, pentrix):
    await seed_funnel(client, auth_headers, pentrix)
    assert await names(client, auth_headers, "qualification=qualified&payment=not_paid&booking=not_scheduled") == ["Payment Failed", "Qualified Only", "Qualified Pending Pay"]
    assert await names(client, auth_headers, "assessment=completed&qualification=qualified&payment=pending") == ["Qualified Pending Pay"]
    assert await names(client, auth_headers, "qualification=qualified&booking=scheduled") == ["Paid Booked", "Qualified Booked"]
    assert await names(client, auth_headers, "payment=paid") == ["Paid Booked"]
    assert await names(client, auth_headers, "payment=failed&payment=pending") == ["Payment Failed", "Qualified Pending Pay"]  # several values widen one group


async def test_not_qualified_means_tried_and_missed_not_just_not_yet(client, db_session, organization, auth_headers, pentrix):
    await seed_funnel(client, auth_headers, pentrix)
    assert await names(client, auth_headers, "qualification=not_qualified") == ["Failed One"]
    assert await names(client, auth_headers, "qualification=pending") == ["New Person", "Started"]
    assert await names(client, auth_headers, "assessment=not_started") == ["New Person"]
    assert await names(client, auth_headers, "assessment=in_progress") == ["Started"]
    assert await names(client, auth_headers, "assessment=pending") == ["New Person", "Started"]


async def test_a_past_appointment_is_not_scheduled_and_the_status_filters_work(client, db_session, organization, auth_headers, pentrix):
    pentrix.candidate(full_name="Future", **booked("confirmed", utc(60 * 24)))
    pentrix.candidate(full_name="Long Gone", **booked("confirmed", utc(-60 * 48)))
    pentrix.candidate(full_name="Done", **booked("completed", utc(-60 * 48)))
    pentrix.candidate(full_name="Cancelled", **booked("cancelled", utc(60 * 24)))
    pentrix.candidate(full_name="Absent", **booked("no_show", utc(-60 * 48)))
    pentrix.candidate(full_name="Never Booked")
    await sync(client, auth_headers)
    assert await names(client, auth_headers, "booking=scheduled") == ["Future"]
    assert await names(client, auth_headers, "booking=not_scheduled") == ["Absent", "Cancelled", "Done", "Long Gone", "Never Booked"]
    assert await names(client, auth_headers, "booking=completed") == ["Done"]
    assert await names(client, auth_headers, "booking=cancelled") == ["Cancelled"]
    assert await names(client, auth_headers, "booking=no_show") == ["Absent"]


async def test_search_finds_name_email_or_phone_and_dates_narrow_by_registration(client, db_session, organization, auth_headers, pentrix):
    pentrix.candidate(full_name="Meera Iyer", email="meera@example.com", registered_at=utc(-60 * 24 * 10).isoformat())
    pentrix.candidate(full_name="Kabir Shah", email="kabir@corp.example", phone="+91 98765 43210", registered_at=utc(-60 * 24 * 2).isoformat())
    await sync(client, auth_headers)
    assert await names(client, auth_headers, "q=meer") == ["Meera Iyer"]
    assert await names(client, auth_headers, "q=corp.example") == ["Kabir Shah"]
    assert await names(client, auth_headers, "q=43210") == ["Kabir Shah"]
    since = (utc(-60 * 24 * 5)).isoformat().replace("+00:00", "Z")
    assert await names(client, auth_headers, f"registered_from={since}") == ["Kabir Shah"]
    assert await names(client, auth_headers, f"registered_to={since}") == ["Meera Iyer"]


async def test_sorting_and_paging_happen_in_the_database(client, db_session, organization, auth_headers, pentrix):
    for i in range(7):
        pentrix.candidate(full_name=f"Person {i}", registered_at=utc(-60 * (i + 1)).isoformat())
    await sync(client, auth_headers)
    newest_first = (await client.get(f"{_P}/candidates?page_size=3", headers=auth_headers)).json()
    assert newest_first["total"] == 7 and [c["full_name"] for c in newest_first["items"]] == ["Person 0", "Person 1", "Person 2"]
    page3 = (await client.get(f"{_P}/candidates?page_size=3&page=3", headers=auth_headers)).json()
    assert [c["full_name"] for c in page3["items"]] == ["Person 6"]
    by_name = (await client.get(f"{_P}/candidates?sort=name&order=asc&page_size=2", headers=auth_headers)).json()
    assert [c["full_name"] for c in by_name["items"]] == ["Person 0", "Person 1"]
    assert (await client.get(f"{_P}/candidates?sort=password", headers=auth_headers)).status_code == 422
    assert (await client.get(f"{_P}/candidates?qualification=maybe", headers=auth_headers)).status_code == 422
    assert (await client.get(f"{_P}/candidates?page_size=1000", headers=auth_headers)).status_code == 422


async def test_the_assessments_list_shows_scores_and_filters_like_the_spec(client, db_session, organization, auth_headers, pentrix):
    await seed_funnel(client, auth_headers, pentrix)
    r = await client.get(f"{_P}/assessments?qualification=qualified&payment=paid", headers=auth_headers)
    row = r.json()["items"][0]
    assert [c["full_name"] for c in r.json()["items"]] == ["Paid Booked"]
    assert row["assessment"]["technical_pct"] == 80.0 and row["assessment"]["qualified"] is True and row["booking"]["scheduled"] is True and row["payment"]["status"] == "paid"
    pending = (await client.get(f"{_P}/assessments?assessment=pending", headers=auth_headers)).json()
    assert sorted(c["full_name"] for c in pending["items"]) == ["New Person", "Started"]
    ordered = (await client.get(f"{_P}/assessments?assessment=completed&sort=assessed&order=asc", headers=auth_headers)).json()["items"]
    assert ordered[0]["full_name"] == "Qualified Only" or ordered[0]["assessment"]["assessed_at"] <= ordered[-1]["assessment"]["assessed_at"]


# ------------------------------------------------------------------ opening one

async def test_opening_a_candidate_asks_pentrix_for_the_full_record_and_refreshes_the_summary(client, db_session, organization, auth_headers, pentrix):
    cand = pentrix.candidate(full_name="Asha Rao", email="asha@example.com")
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixCandidate))).scalar_one()
    pentrix.profiles[cand["id"]] = {"registration": {"id": cand["id"], "email": "asha@example.com", "sign_in": "google"}, "assessment": {"attempts": []}, "bookings": [], "payments": [{"invoice_number": "INV-1"}], "activity": []}
    pentrix.touch(cand["id"], **qualified())  # changed in Pentrix since the last pull
    body = (await client.get(f"{_P}/candidates/{row.id}", headers=auth_headers)).json()
    assert body["live"] is True and body["error"] is None and body["profile"]["payments"] == [{"invoice_number": "INV-1"}]
    assert body["candidate"]["assessment"]["qualified"] is True  # the summary caught up from the answer
    await db_session.refresh(row)
    assert row.qualified is True


async def test_the_email_history_is_what_erpx_sent_to_that_address_only(client, db_session, organization, auth_headers, pentrix):
    pentrix.candidate(full_name="Asha Rao", email="Asha@Example.com")
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixCandidate))).scalar_one()
    db_session.add_all([
        EmailSendRecord(organization_id=organization.id, recipient="asha@example.com", subject="Booking reminder", status="sent", key="pentrix_booking_reminder_30m_candidate"),
        EmailSendRecord(organization_id=organization.id, recipient="asha@example.com", subject="A test send", status="sent", is_test=True),
        EmailSendRecord(organization_id=organization.id, recipient="someone.else@example.com", subject="Not hers", status="sent"),
    ])
    await db_session.flush()
    emails = (await client.get(f"{_P}/candidates/{row.id}", headers=auth_headers)).json()["emails"]
    assert [(e["subject"], e["status"]) for e in emails] == [("Booking reminder", "sent")]


async def test_when_pentrix_cannot_be_reached_the_page_still_shows_what_erpx_holds(client, db_session, organization, auth_headers, pentrix):
    pentrix.candidate(full_name="Asha Rao")
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixCandidate))).scalar_one()
    pentrix.down = True
    body = (await client.get(f"{_P}/candidates/{row.id}", headers=auth_headers)).json()
    assert body["live"] is False and "did not respond" in body["error"] and body["profile"] is None and body["candidate"]["full_name"] == "Asha Rao"


async def test_an_unknown_candidate_and_another_organisation_get_nothing(client, db_session, organization, auth_headers, pentrix):
    from modules.organizations.repository import OrganizationRepository
    from tests._fixtures import _make_user

    pentrix.candidate()
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixCandidate))).scalar_one()
    assert (await client.get(f"{_P}/candidates/{uuid.uuid4()}", headers=auth_headers)).status_code == 404
    other_org = await OrganizationRepository(db_session).create(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other_org, is_superuser=True, email=f"o-{uuid.uuid4().hex[:8]}@erpx.example.com")
    theirs = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"{_P}/candidates", headers=theirs)).status_code == 422
    assert (await client.get(f"{_P}/candidates/{row.id}", headers=theirs)).status_code == 422


# ------------------------------------------------------------------ editing


async def test_name_and_phone_are_changed_in_pentrix_with_the_editor_recorded(client, db_session, organization, auth_headers, pentrix, superuser):
    cand = pentrix.candidate(full_name="Asha Rao")
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixCandidate))).scalar_one()
    r = await client.patch(f"{_P}/candidates/{row.id}", headers=auth_headers, json={"full_name": "Asha R. Rao", "phone": "+91 98765 43210"})
    assert r.status_code == 200 and r.json()["full_name"] == "Asha R. Rao" and r.json()["phone"] == "+91 98765 43210"
    method, path, sent, actor = pentrix.calls[-1]
    assert (method, path, sent) == ("PATCH", f"/candidates/{cand['id']}", {"full_name": "Asha R. Rao", "phone": "+91 98765 43210"}) and actor == str(superuser[0].id)
    await db_session.refresh(row)
    assert row.full_name == "Asha R. Rao"


async def test_a_renamed_candidate_is_renamed_on_their_appointments_too(client, db_session, organization, auth_headers, pentrix):
    cand = pentrix.candidate(full_name="Asha Rao", email="asha@example.com")
    await sync(client, auth_headers)
    db_session.add(PentrixBooking(organization_id=organization.id, pentrix_booking_id="b1", pentrix_user_id=cand["id"], candidate_name="Asha Rao",
                                  candidate_email="asha@example.com", slot_start=utc(60), slot_end=utc(120), status="confirmed", scheduled_at=utc(-5)))
    other = PentrixBooking(organization_id=organization.id, pentrix_booking_id="b2", pentrix_user_id="someone-else", candidate_name="Other", candidate_email="o@example.com",
                           slot_start=utc(60), slot_end=utc(120), status="confirmed", scheduled_at=utc(-5))
    db_session.add(other)
    await db_session.flush()
    row = (await db_session.execute(select(PentrixCandidate))).scalar_one()
    assert (await client.patch(f"{_P}/candidates/{row.id}", headers=auth_headers, json={"full_name": "Asha R. Rao"})).status_code == 200
    names = {b.pentrix_booking_id: b.candidate_name for b in (await db_session.execute(select(PentrixBooking))).scalars()}
    await db_session.refresh(other)
    assert names["b1"] == "Asha R. Rao" and other.candidate_name == "Other"


async def test_nothing_else_can_be_edited_and_pentrix_refusing_changes_nothing(client, db_session, organization, auth_headers, pentrix):
    pentrix.candidate(full_name="Asha Rao", email="asha@example.com")
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixCandidate))).scalar_one()
    assert (await client.patch(f"{_P}/candidates/{row.id}", headers=auth_headers, json={})).status_code == 422
    assert (await client.patch(f"{_P}/candidates/{row.id}", headers=auth_headers, json={"email": "other@example.com"})).status_code == 422  # not an editable field
    assert (await client.patch(f"{_P}/candidates/{row.id}", headers=auth_headers, json={"full_name": ""})).status_code == 422
    refused = await client.patch(f"{_P}/candidates/{row.id}", headers=auth_headers, json={"phone": "bad"})
    assert refused.status_code == 422 and "digits" in refused.text
    await db_session.refresh(row)
    assert row.email == "asha@example.com" and row.phone is None and row.full_name == "Asha Rao"


# ------------------------------------------------------------------ one candidate's assessment


async def test_the_assessment_view_carries_attempts_and_criteria_but_no_contact_or_payment_history(client, db_session, organization, auth_headers, pentrix):
    pentrix.candidate(full_name="Asha Rao", **qualified())
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixCandidate))).scalar_one()
    body = (await client.get(f"{_P}/assessments/{row.id}", headers=auth_headers)).json()
    assert body["live"] is True and body["assessment"]["criteria"] == {"readiness_commitment_pct": 100.0, "technical_pct": 40.0}
    assert body["assessment"]["attempts"] and set(body) == {"candidate", "live", "error", "assessment"}
    assert pentrix.calls[-1][1].endswith("/assessment")  # asked for only that part


# ------------------------------------------------------------------ the overview


async def test_the_overview_counts_the_journey_and_the_appointments(client, db_session, organization, auth_headers, pentrix):
    await seed_funnel(client, auth_headers, pentrix)
    midnight = datetime.now(ZoneInfo(settings.PENTRIX_TIMEZONE)).replace(hour=0, minute=0, second=1, microsecond=0).astimezone(timezone.utc)
    for index, (start, end, status) in enumerate([
        (midnight, utc(30), "confirmed"),                      # today and not over
        (utc(60 * 30), utc(60 * 31), "requested"),             # tomorrow-ish
        (utc(60 * 30), utc(60 * 31), "cancelled"),             # cancelled: not counted
        (utc(-60 * 48), utc(-60 * 47), "completed"),           # over
    ]):
        db_session.add(PentrixBooking(organization_id=organization.id, pentrix_booking_id=f"b{index}", pentrix_user_id="u", slot_start=start, slot_end=end, status=status, scheduled_at=utc(-300)))
    await db_session.flush()
    body = (await client.get(f"{_P}/overview", headers=auth_headers)).json()
    totals = body["totals"]
    assert totals["registered"] == 8 and totals["assessments_completed"] == 6 and totals["assessments_in_progress"] == 1
    assert totals["qualified"] == 5 and totals["not_qualified"] == 1  # a person who has not been assessed is neither
    assert totals["paid"] == 1 and totals["payment_pending"] == 1
    assert body["payment_status"] == {"paid": 1, "pending": 1, "failed": 1, "refunded": 0, "none": 5}
    assert body["bookings"] == {"upcoming": 2, "today": 1}
    assert [(s["key"], s["count"]) for s in body["funnel"]] == [("registered", 8), ("assessed", 6), ("qualified", 5), ("booked", 2), ("paid", 1)]
    assert len(body["recent_registrations"]) == 5 and body["configured"] is True and body["last_synced_at"] is not None


async def test_an_empty_overview_is_all_zeros(client, db_session, organization, auth_headers, pentrix):
    body = (await client.get(f"{_P}/overview", headers=auth_headers)).json()
    assert all(v == 0 for v in body["totals"].values()) and body["bookings"] == {"upcoming": 0, "today": 0} and body["recent_registrations"] == []


# ------------------------------------------------------------------ who may see what


async def test_overview_registrations_and_assessments_are_separate_permissions(client, db_session, organization, auth_headers, pentrix):
    pentrix.candidate(full_name="Asha Rao", **qualified())
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixCandidate))).scalar_one()
    _, only_overview = await person(db_session, organization, ["pentrix_ops.overview.view"])
    _, only_assessments = await person(db_session, organization, ["pentrix_ops.assessments.view"])
    _, viewer = await person(db_session, organization, ["pentrix_ops.registrations.view"])
    _, editor = await person(db_session, organization, ["pentrix_ops.registrations.view", "pentrix_ops.registrations.manage"])
    _, staff = await person(db_session, organization, ["pentrix_ops.bookings.assigned"])

    assert (await client.get(f"{_P}/overview", headers=only_overview)).status_code == 200
    assert (await client.get(f"{_P}/candidates", headers=only_overview)).status_code == 403
    assert (await client.get(f"{_P}/assessments", headers=only_overview)).status_code == 403

    assert (await client.get(f"{_P}/assessments", headers=only_assessments)).status_code == 200
    assert (await client.get(f"{_P}/assessments/{row.id}", headers=only_assessments)).status_code == 200
    assert (await client.get(f"{_P}/candidates", headers=only_assessments)).status_code == 403  # results, but not contact details
    assert (await client.get(f"{_P}/candidates/{row.id}", headers=only_assessments)).status_code == 403
    assert (await client.get(f"{_P}/overview", headers=only_assessments)).status_code == 403

    assert (await client.get(f"{_P}/candidates", headers=viewer)).status_code == 200
    assert (await client.get(f"{_P}/candidates/{row.id}", headers=viewer)).status_code == 200
    assert (await client.patch(f"{_P}/candidates/{row.id}", headers=viewer, json={"phone": "123456"})).status_code == 403
    assert (await client.patch(f"{_P}/candidates/{row.id}", headers=editor, json={"phone": "123456"})).status_code == 200

    # a team member who only takes appointments sees no candidate records at all
    for path in ("/overview", "/candidates", f"/candidates/{row.id}", "/assessments", f"/assessments/{row.id}"):
        assert (await client.get(f"{_P}{path}", headers=staff)).status_code == 403, path
    assert (await client.get(f"{_P}/candidates")).status_code in (401, 403)


def test_the_candidate_pull_is_scheduled_and_the_permissions_exist():
    from app.core.celery_app import celery_app
    from modules.authorization.service import DEFAULT_PERMISSIONS

    assert "pentrix.sync_candidates" in {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    codes = {p[0] for p in DEFAULT_PERMISSIONS}
    assert {"pentrix_ops.overview.view", "pentrix_ops.registrations.view", "pentrix_ops.registrations.manage", "pentrix_ops.assessments.view"} <= codes
