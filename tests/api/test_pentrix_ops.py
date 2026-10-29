"""
Pentrix appointments in ERPX: the synchronised copy (pushed by Pentrix and pulled by cursor), assigning team members, the screens'
actions (carried out in Pentrix), what a team member can and cannot do, and the reminder emails (when they go, that they never go
twice, and that a changed or cancelled appointment gets the right ones). Pentrix is replaced by a fake that checks every signature.
"""
import hashlib
import hmac
import json
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.pentrix_ops import client as client_module
from modules.pentrix_ops import reminders
from modules.pentrix_ops.client import sign
from modules.pentrix_ops.models import PentrixBooking, PentrixBookingReminder, PentrixSyncState
from modules.pentrix_ops.service import PentrixBookingService
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

_P = "/api/v1/pentrix-ops"
SECRET = "test-shared-secret"


def utc(minutes: int = 0, base: datetime | None = None) -> datetime:
    return (base or datetime.now(timezone.utc).replace(microsecond=0)) + timedelta(minutes=minutes)


class FakePentrix:
    """Just enough of Pentrix's internal API: keeps bookings, checks the signature of every call, can be told to fail."""

    def __init__(self):
        self.bookings: dict[str, dict] = {}
        self.calls: list[tuple[str, str, dict | None, str | None]] = []
        self.fail: tuple[int, str] | None = None
        self.down = False
        self.clock = 0
        self.settings = {"start_time": "18:00", "end_time": "21:00", "timezone": "Asia/Kolkata", "slot_minutes": 60, "capacity": 1, "working_days": [0, 1, 2, 3, 4]}
        self.blocks: list[dict] = []

    def add(self, **over) -> dict:
        self.clock += 1
        start = over.pop("start", utc(120))
        booking = {
            "id": str(uuid.uuid4()), "reference": "BK-" + uuid.uuid4().hex[:6].upper(), "user_id": str(uuid.uuid4()), "candidate_name": "Meera Iyer",
            "candidate_email": "meera@example.com", "slot_start": start.isoformat(), "slot_end": (start + timedelta(hours=1)).isoformat(), "duration_minutes": 60,
            "status": "confirmed", "assigned_staff_ref": None, "assigned_staff_name": None, "meeting_url": None, "notes": None, "reschedule_count": 0,
            "cancelled_by": None, "created_at": utc(-5).isoformat(), "updated_at": self._stamp(), **over,
        }
        self.bookings[booking["id"]] = booking
        return booking

    def _stamp(self) -> str:
        self.clock += 1
        return (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=self.clock)).isoformat()

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("down")
        url = urlparse(str(request.url))
        path_and_query = url.path + (f"?{url.query}" if url.query else "")
        body = request.content.decode() if request.content else ""
        expected = sign(SECRET, request.headers.get("X-ERPX-Timestamp", ""), request.method, path_and_query, body)
        if not hmac.compare_digest(expected, request.headers.get("X-ERPX-Signature", "")):
            return httpx.Response(401, json={"error": "auth_error", "message": "Invalid signature."})
        payload = json.loads(body) if body else None
        self.calls.append((request.method, url.path.replace("/api/v1/internal/erpx", ""), payload, request.headers.get("X-ERPX-Actor")))
        if self.fail:
            code, message = self.fail
            return httpx.Response(code, json={"error": "x", "message": message})
        path = url.path.replace("/api/v1/internal/erpx", "")
        if request.method == "GET" and path == "/bookings":
            cursor = parse_qs(url.query).get("cursor", [""])[0]
            items = sorted(self.bookings.values(), key=lambda b: (b["updated_at"], b["id"]))
            if cursor:
                stamp, _, last = cursor.partition("|")
                items = [b for b in items if (b["updated_at"], b["id"]) > (stamp, last)]
            last_item = items[-1] if items else None
            return httpx.Response(200, json={"items": items, "next_cursor": f"{last_item['updated_at']}|{last_item['id']}" if last_item else cursor or None, "has_more": False})
        match = re.match(r"^/bookings/([^/]+)/(assign|status|reschedule|cancel|meeting|notes)$", path)
        if match and request.method == "POST":
            booking = self.bookings.get(match.group(1))
            if booking is None:
                return httpx.Response(404, json={"error": "not_found", "message": "Booking not found."})
            action = match.group(2)
            if action == "assign":
                booking["assigned_staff_ref"], booking["assigned_staff_name"] = payload["staff_ref"], payload["staff_name"]
            elif action == "status":
                booking["status"] = payload["status"]
            elif action == "reschedule":
                start = datetime.fromisoformat(payload["slot_start"])
                booking.update(slot_start=start.isoformat(), slot_end=(start + timedelta(hours=1)).isoformat(), reschedule_count=booking["reschedule_count"] + 1)
            elif action == "cancel":
                booking.update(status="cancelled", cancelled_by="team")
            elif action == "meeting":
                booking["meeting_url"] = payload["meeting_url"]
            elif action == "notes":
                booking["notes"] = payload["notes"]
            booking["updated_at"] = self._stamp()
            return httpx.Response(200, json=booking)
        if path == "/booking-settings":
            if request.method == "PUT":
                self.settings.update(payload)
            return httpx.Response(200, json=self.settings)
        if path == "/booking-blocks":
            if request.method == "POST":
                self.blocks.append({"id": f"b{len(self.blocks) + 1}", **payload})
                return httpx.Response(201, json=self.blocks[-1])
            return httpx.Response(200, json=self.blocks)
        if request.method == "DELETE" and path.startswith("/booking-blocks/"):
            self.blocks = [b for b in self.blocks if b["id"] != path.rsplit("/", 1)[1]]
            return httpx.Response(200, json={"deleted": True})
        if path == "/availability":
            return httpx.Response(200, json={"timezone": "Asia/Kolkata", "slot_minutes": 60, "capacity": 1, "dates": []})
        return httpx.Response(404, json={"error": "not_found", "message": "unknown"})


@pytest.fixture
def pentrix(monkeypatch, organization):
    fake = FakePentrix()
    monkeypatch.setattr(settings, "PENTRIX_ORGANIZATION_SLUG", organization.slug)  # other tests leave organisations behind
    monkeypatch.setattr(settings, "PENTRIX_INTERNAL_API_BASE_URL", "http://pentrix.test")
    monkeypatch.setattr(settings, "ERPX_INTERNAL_SERVICE_SECRET", SECRET)
    monkeypatch.setattr(client_module, "DEFAULT_TRANSPORT", httpx.MockTransport(fake.handler))
    return fake


@pytest.fixture
def mailbox(monkeypatch):
    sent: list[dict] = []

    async def send(to, subject, text, html=None, attachments=None):
        sent.append({"to": to, "subject": subject, "text": text, "html": html})
        return True

    monkeypatch.setattr(reminders.email_service, "send", send)
    return sent


async def person(db_session, organization, permissions, name="Staff Person"):
    user, token = await _make_user(db_session, organization, is_superuser=False, email=f"u-{uuid.uuid4().hex[:8]}@erpx.example.com")
    user.full_name = name
    repo = AuthorizationRepository(db_session)
    role = await repo.create_role(f"Role {uuid.uuid4().hex[:6]}", f"role-{uuid.uuid4().hex[:8]}", "test")
    await db_session.flush()
    perms = [await repo.get_or_create_permission(code, code.split(".")[0], code) for code in permissions]
    await repo.set_role_permissions(role, perms)
    await AuthorizationService(db_session).assign_role(user.id, role.id, organization.id, assigned_by_user_id=None)
    await db_session.flush()
    return user, {"Authorization": f"Bearer {token}"}


def push_headers(body: str, secret: str = SECRET) -> dict:
    ts = str(int(time.time()))
    return {"X-ERPX-Timestamp": ts, "X-ERPX-Signature": hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest(), "Content-Type": "application/json"}


async def sync(client, headers):
    r = await client.post(f"{_P}/sync", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["updated"]


# ------------------------------------------------------------------ the copy


async def test_pentrix_pushes_a_booking_and_a_repeat_or_older_message_changes_nothing(client, db_session, organization, auth_headers, pentrix):
    booking = FakePentrix().add(status="confirmed")
    body = json.dumps(booking)
    assert (await client.post("/api/v1/internal/pentrix/bookings", content=body, headers=push_headers(body))).status_code == 200
    assert (await client.post("/api/v1/internal/pentrix/bookings", content=body, headers=push_headers(body))).status_code == 200  # twice
    rows = (await db_session.execute(select(PentrixBooking))).scalars().all()
    assert len(rows) == 1 and rows[0].pentrix_booking_id == booking["id"] and rows[0].candidate_email == "meera@example.com" and rows[0].status == "confirmed"
    newer = {**booking, "status": "completed", "updated_at": (datetime.fromisoformat(booking["updated_at"]) + timedelta(seconds=5)).isoformat()}
    await client.post("/api/v1/internal/pentrix/bookings", content=json.dumps(newer), headers=push_headers(json.dumps(newer)))
    older = {**booking, "status": "confirmed", "updated_at": (datetime.fromisoformat(booking["updated_at"]) - timedelta(seconds=5)).isoformat()}
    await client.post("/api/v1/internal/pentrix/bookings", content=json.dumps(older), headers=push_headers(json.dumps(older)))
    await db_session.refresh(rows[0])
    assert rows[0].status == "completed"  # the older message did not overwrite the newer state


async def test_pushes_without_a_valid_signature_are_refused(client, db_session, organization, pentrix):
    body = json.dumps(FakePentrix().add())
    assert (await client.post("/api/v1/internal/pentrix/bookings", content=body)).status_code == 401
    assert (await client.post("/api/v1/internal/pentrix/bookings", content=body, headers=push_headers(body, "wrong-secret"))).status_code == 401
    assert (await db_session.execute(select(PentrixBooking))).first() is None


async def test_the_pull_reads_changes_from_a_cursor_and_nothing_twice(client, db_session, organization, auth_headers, pentrix):
    first = pentrix.add(candidate_name="Asha")
    assert await sync(client, auth_headers) == 1
    assert await sync(client, auth_headers) == 0  # nothing new
    pentrix.add(candidate_name="Ravi")
    first_row = pentrix.bookings[first["id"]]
    first_row["status"] = "completed"
    first_row["updated_at"] = pentrix._stamp()
    assert await sync(client, auth_headers) == 2  # the change to the first, and the new one
    rows = {r.candidate_name: r for r in (await db_session.execute(select(PentrixBooking))).scalars().all()}
    assert set(rows) == {"Asha", "Ravi"} and rows["Asha"].status == "completed"


async def test_a_failed_pull_keeps_its_place_and_says_what_went_wrong(client, db_session, organization, auth_headers, pentrix):
    pentrix.add()
    await sync(client, auth_headers)
    pentrix.add()
    pentrix.down = True
    assert (await client.post(f"{_P}/sync", headers=auth_headers)).status_code == 503
    state = (await db_session.execute(select(PentrixSyncState))).scalar_one()
    assert state.last_error
    pentrix.down = False
    assert await sync(client, auth_headers) == 1  # resumes from where it was


# ------------------------------------------------------------------ who can see and do what


async def test_viewing_managing_and_taking_appointments_are_separate_permissions(client, db_session, organization, auth_headers, pentrix):
    booking = pentrix.add()
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixBooking))).scalar_one()
    nobody = (await person(db_session, organization, ["email_templates.view"]))[1]
    viewer = (await person(db_session, organization, ["pentrix_ops.bookings.view"]))[1]
    assert (await client.get(f"{_P}/bookings", headers=nobody)).status_code == 403
    listed = await client.get(f"{_P}/bookings", headers=viewer)
    assert listed.status_code == 200 and listed.json()["total"] == 1 and listed.json()["items"][0]["candidate_email"] == "meera@example.com"
    assert (await client.post(f"{_P}/bookings/{row.id}/status", headers=viewer, json={"status": "completed"})).status_code == 403
    assert (await client.post(f"{_P}/bookings/{row.id}/assign", headers=viewer, json={"staff_user_id": None})).status_code == 403
    assert (await client.put(f"{_P}/availability-settings", headers=viewer, json={"capacity": 2})).status_code == 403
    assert booking["status"] == "confirmed"  # nothing reached Pentrix


async def test_a_team_member_sees_only_their_own_appointments_and_may_only_progress_them(client, db_session, organization, auth_headers, pentrix):
    mine_user, mine = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    other_user, other = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Other Person")
    a = pentrix.add(candidate_name="Asha", assigned_staff_ref=str(mine_user.id), assigned_staff_name="Priya Nair", start=utc(60))
    b = pentrix.add(candidate_name="Ravi", assigned_staff_ref=str(other_user.id), assigned_staff_name="Other Person", start=utc(180))
    pentrix.add(candidate_name="Unassigned", start=utc(240))
    await sync(client, auth_headers)
    got = (await client.get(f"{_P}/my-bookings", headers=mine)).json()
    assert [i["candidate_name"] for i in got["items"]] == ["Asha"] and got["total"] == 1
    assert (await client.get(f"{_P}/bookings", headers=mine)).status_code == 403  # no access to the full list
    row_a = (await db_session.execute(select(PentrixBooking).where(PentrixBooking.pentrix_booking_id == a["id"]))).scalar_one()
    row_b = (await db_session.execute(select(PentrixBooking).where(PentrixBooking.pentrix_booking_id == b["id"]))).scalar_one()
    started = await client.post(f"{_P}/my-bookings/{row_a.id}/status", headers=mine, json={"status": "in_progress"})
    assert started.status_code == 200 and started.json()["status"] == "in_progress" and pentrix.bookings[a["id"]]["status"] == "in_progress"
    assert pentrix.calls[-1][3] == str(mine_user.id)  # Pentrix is told who did it
    assert (await client.post(f"{_P}/my-bookings/{row_a.id}/status", headers=mine, json={"status": "cancelled"})).status_code == 422  # not theirs to cancel
    assert (await client.post(f"{_P}/my-bookings/{row_b.id}/status", headers=mine, json={"status": "completed"})).status_code == 404  # someone else's
    assert (await client.put(f"{_P}/my-bookings/{row_b.id}/notes", headers=mine, json={"notes": "x"})).status_code == 404
    assert (await client.put(f"{_P}/my-bookings/{row_a.id}/notes", headers=mine, json={"notes": "Prefers evenings"})).json()["notes"] == "Prefers evenings"
    assert (await client.post(f"{_P}/bookings/{row_a.id}/reschedule", headers=mine, json={"slot_start": utc(300).isoformat()})).status_code == 403


async def test_another_organisation_gets_nothing(client, db_session, organization, auth_headers, pentrix):
    from modules.organizations.repository import OrganizationRepository

    pentrix.add()
    await sync(client, auth_headers)
    other_org = await OrganizationRepository(db_session).create(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other_org, is_superuser=True, email=f"o-{uuid.uuid4().hex[:8]}@erpx.example.com")
    r = await client.get(f"{_P}/bookings", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422 and "not set up for your organization" in r.text


# ------------------------------------------------------------------ assigning


async def test_assigning_a_team_member_tells_pentrix_and_only_eligible_people_can_be_chosen(client, db_session, organization, auth_headers, pentrix):
    staff_user, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    plain_user, _ = await person(db_session, organization, ["email_templates.view"], "No Access")
    pentrix.add(candidate_name="Asha", start=utc(120))
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixBooking))).scalar_one()
    team = (await client.get(f"{_P}/staff", headers=auth_headers)).json()
    assert [t["full_name"] for t in team] == ["Priya Nair"]
    assert (await client.post(f"{_P}/bookings/{row.id}/assign", headers=auth_headers, json={"staff_user_id": str(plain_user.id)})).status_code == 422
    done = await client.post(f"{_P}/bookings/{row.id}/assign", headers=auth_headers, json={"staff_user_id": str(staff_user.id)})
    assert done.status_code == 200 and done.json()["assigned_staff_user_id"] == str(staff_user.id) and done.json()["assigned_staff_name"] == "Priya Nair"
    sent_to_pentrix = pentrix.calls[-1]
    assert sent_to_pentrix[1].endswith("/assign") and sent_to_pentrix[2] == {"staff_ref": str(staff_user.id), "staff_name": "Priya Nair"}
    off = await client.post(f"{_P}/bookings/{row.id}/assign", headers=auth_headers, json={"staff_user_id": None})
    assert off.json()["assigned_staff_user_id"] is None


async def test_a_team_member_cannot_be_given_two_appointments_at_the_same_time(client, db_session, organization, auth_headers, pentrix):
    staff_user, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    when = utc(90)
    pentrix.add(candidate_name="First", start=when, assigned_staff_ref=str(staff_user.id), assigned_staff_name="Priya Nair")
    second = pentrix.add(candidate_name="Second", start=when + timedelta(minutes=30))
    far = pentrix.add(candidate_name="Third", start=when + timedelta(hours=3))
    await sync(client, auth_headers)
    rows = {r.candidate_name: r for r in (await db_session.execute(select(PentrixBooking))).scalars().all()}
    clash = await client.post(f"{_P}/bookings/{rows['Second'].id}/assign", headers=auth_headers, json={"staff_user_id": str(staff_user.id)})
    assert clash.status_code == 409 and "already has an appointment" in clash.text
    assert pentrix.bookings[second["id"]]["assigned_staff_ref"] is None  # Pentrix was never asked
    assert (await client.post(f"{_P}/bookings/{rows['Third'].id}/assign", headers=auth_headers, json={"staff_user_id": str(staff_user.id)})).status_code == 200
    # rescheduling onto a time the assigned person is busy is refused as well
    moved = await client.post(f"{_P}/bookings/{rows['Third'].id}/reschedule", headers=auth_headers, json={"slot_start": when.isoformat()})
    assert moved.status_code == 409 and far["slot_start"] == pentrix.bookings[far["id"]]["slot_start"]


# ------------------------------------------------------------------ actions are carried out in Pentrix


async def test_the_actions_go_to_pentrix_and_its_answer_becomes_the_copy(client, db_session, organization, auth_headers, pentrix):
    b = pentrix.add(start=utc(200))
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixBooking))).scalar_one()
    new_start = utc(400)
    r = await client.post(f"{_P}/bookings/{row.id}/reschedule", headers=auth_headers, json={"slot_start": new_start.isoformat()})
    assert r.status_code == 200 and datetime.fromisoformat(r.json()["slot_start"]) == new_start and r.json()["reschedule_count"] == 1
    assert (await client.put(f"{_P}/bookings/{row.id}/meeting", headers=auth_headers, json={"meeting_url": "https://meet.example.com/x"})).json()["meeting_url"] == "https://meet.example.com/x"
    assert (await client.put(f"{_P}/bookings/{row.id}/notes", headers=auth_headers, json={"notes": "Cloud track"})).json()["notes"] == "Cloud track"
    assert (await client.post(f"{_P}/bookings/{row.id}/status", headers=auth_headers, json={"status": "in_progress"})).json()["status_label"] == "In progress"
    assert (await client.post(f"{_P}/bookings/{row.id}/status", headers=auth_headers, json={"status": "bogus"})).status_code == 422
    cancelled = await client.post(f"{_P}/bookings/{row.id}/cancel", headers=auth_headers)
    assert cancelled.json()["status"] == "cancelled" and cancelled.json()["cancelled_by"] == "team" and pentrix.bookings[b["id"]]["status"] == "cancelled"


async def test_pentrix_refusing_or_being_down_is_reported_and_changes_nothing_here(client, db_session, organization, auth_headers, pentrix):
    pentrix.add()
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixBooking))).scalar_one()
    pentrix.fail = (409, "That slot is already full.")
    refused = await client.post(f"{_P}/bookings/{row.id}/reschedule", headers=auth_headers, json={"slot_start": utc(500).isoformat()})
    assert refused.status_code == 409 and "already full" in refused.text
    pentrix.fail = (422, "Those times are not open.")
    assert (await client.post(f"{_P}/bookings/{row.id}/reschedule", headers=auth_headers, json={"slot_start": utc(500).isoformat()})).status_code == 422
    pentrix.fail = None
    pentrix.down = True
    assert (await client.post(f"{_P}/bookings/{row.id}/cancel", headers=auth_headers)).status_code == 503
    await db_session.refresh(row)
    assert row.status == "confirmed"


async def test_the_booking_hours_and_closed_periods_are_managed_through_pentrix(client, db_session, organization, auth_headers, pentrix):
    assert (await client.get(f"{_P}/availability-settings", headers=auth_headers)).json()["start_time"] == "18:00"
    put = await client.put(f"{_P}/availability-settings", headers=auth_headers, json={"capacity": 3, "start_time": "17:00"})
    assert put.json()["capacity"] == 3 and put.json()["start_time"] == "17:00"
    assert pentrix.calls[-1][2] == {"capacity": 3, "start_time": "17:00"}  # only what was changed was sent
    made = await client.post(f"{_P}/closed-periods", headers=auth_headers, json={"start_at": utc(60).isoformat(), "end_at": utc(600).isoformat(), "reason": "Diwali"})
    assert made.status_code == 201
    assert [b["reason"] for b in (await client.get(f"{_P}/closed-periods", headers=auth_headers)).json()] == ["Diwali"]
    assert (await client.delete(f"{_P}/closed-periods/{made.json()['id']}", headers=auth_headers)).status_code == 200
    assert (await client.get(f"{_P}/closed-periods", headers=auth_headers)).json() == []


async def test_the_list_filters_by_status_staff_time_and_search_and_pages(client, db_session, organization, auth_headers, pentrix):
    staff_user, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    pentrix.add(candidate_name="Asha Rao", start=utc(60), assigned_staff_ref=str(staff_user.id), assigned_staff_name="Priya Nair")
    pentrix.add(candidate_name="Ravi Kumar", start=utc(120))
    pentrix.add(candidate_name="Done Person", start=utc(-600), status="completed")
    for n in range(3):
        pentrix.add(candidate_name=f"Extra {n}", start=utc(200 + n))
    await sync(client, auth_headers)

    def names(r):
        return [i["candidate_name"] for i in r.json()["items"]]

    assert names(await client.get(f"{_P}/bookings", headers=auth_headers, params={"page_size": 2})) == ["Asha Rao", "Ravi Kumar"]
    assert (await client.get(f"{_P}/bookings", headers=auth_headers, params={"page_size": 2, "page": 4})).json()["items"] == []
    assert (await client.get(f"{_P}/bookings", headers=auth_headers)).json()["total"] == 5  # upcoming only
    assert names(await client.get(f"{_P}/bookings", headers=auth_headers, params={"scope": "past"})) == ["Done Person"]
    assert names(await client.get(f"{_P}/bookings", headers=auth_headers, params={"staff": str(staff_user.id)})) == ["Asha Rao"]
    assert "Asha Rao" not in names(await client.get(f"{_P}/bookings", headers=auth_headers, params={"staff": "unassigned"}))
    assert names(await client.get(f"{_P}/bookings", headers=auth_headers, params={"q": "ravi"})) == ["Ravi Kumar"]
    assert names(await client.get(f"{_P}/bookings", headers=auth_headers, params={"scope": "all", "status": "completed"})) == ["Done Person"]


# ------------------------------------------------------------------ reminders


async def booked(db_session, organization, *, start, scheduled_ago=60, staff=None, **over):
    row = PentrixBooking(
        organization_id=organization.id, pentrix_booking_id=str(uuid.uuid4()), reference="BK-TEST22", pentrix_user_id=str(uuid.uuid4()), candidate_name="Meera Iyer",
        candidate_email="meera@example.com", slot_start=start, slot_end=start + timedelta(hours=1), scheduled_at=start - timedelta(minutes=scheduled_ago),
        assigned_staff_user_id=staff.id if staff else None, assigned_staff_name=staff.full_name if staff else None, **{"status": "confirmed", **over},
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def test_the_three_reminders_go_to_the_candidate_and_the_assigned_team_member(db_session, organization, mailbox):
    staff, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    start = utc(300)
    row = await booked(db_session, organization, start=start, staff=staff, meeting_url="https://meet.example.com/bk")
    quiet = await reminders.send_due_reminders(db_session, now=start - timedelta(minutes=45))
    assert quiet.sent == 0 and mailbox == []  # nothing is due yet
    s = await reminders.send_due_reminders(db_session, now=start - timedelta(minutes=30))
    assert s.sent == 2 and {m["to"] for m in mailbox} == {"meera@example.com", staff.email}
    candidate_mail = next(m for m in mailbox if m["to"] == "meera@example.com")
    staff_mail = next(m for m in mailbox if m["to"] == staff.email)
    assert "starts in 30 minutes" in candidate_mail["subject"] and "Meera Iyer" in staff_mail["subject"]  # different wording for each
    assert "https://meet.example.com/bk" in candidate_mail["html"] and "IST" in candidate_mail["text"] and row.reference in candidate_mail["text"]
    assert "Priya Nair" in candidate_mail["text"] and "Priya Nair" in staff_mail["text"]  # recipient name and representative
    await reminders.send_due_reminders(db_session, now=start - timedelta(minutes=5))
    await reminders.send_due_reminders(db_session, now=start)
    assert [m["subject"].split(":")[0] for m in mailbox if m["to"] == "meera@example.com"] == [
        "Your appointment starts in 30 minutes", "Your appointment starts in 5 minutes", "Your appointment is starting now",
    ]
    sent_rows = (await db_session.execute(select(PentrixBookingReminder))).scalars().all()
    assert len(sent_rows) == 6 and all(r.status == "sent" and r.sent_at for r in sent_rows)


async def test_running_again_or_overlapping_never_sends_a_reminder_twice(db_session, organization, mailbox):
    start = utc(300)
    await booked(db_session, organization, start=start)
    for minute in (0, 1, 2, 3):  # the scheduler runs every minute; each moment's window lasts longer than that
        await reminders.send_due_reminders(db_session, now=start - timedelta(minutes=30) + timedelta(minutes=minute))
    assert len(mailbox) == 1 and mailbox[0]["to"] == "meera@example.com"  # only the candidate: nobody is assigned


async def test_a_late_or_a_too_late_booking_gets_only_the_reminders_that_still_make_sense(db_session, organization, mailbox):
    start = utc(300)
    await booked(db_session, organization, start=start, scheduled_ago=10)  # booked ten minutes before it starts
    await reminders.send_due_reminders(db_session, now=start - timedelta(minutes=30))
    assert mailbox == []  # the 30-minute moment came before it was booked
    await reminders.send_due_reminders(db_session, now=start - timedelta(minutes=5))
    await reminders.send_due_reminders(db_session, now=start)
    assert len(mailbox) == 2
    # a worker that was down is not allowed to send an old reminder late
    mailbox.clear()
    other = await booked(db_session, organization, start=utc(900))
    await reminders.send_due_reminders(db_session, now=other.slot_start - timedelta(minutes=30) + timedelta(minutes=15))
    assert mailbox == []


async def test_cancelled_finished_and_ended_appointments_get_no_reminders(db_session, organization, mailbox):
    start = utc(300)
    for status in ("cancelled", "completed", "no_show", "in_progress"):
        await booked(db_session, organization, start=start, status=status)
    ended = await booked(db_session, organization, start=start + timedelta(hours=5))
    await reminders.send_due_reminders(db_session, now=start - timedelta(minutes=30))
    await reminders.send_due_reminders(db_session, now=ended.slot_end + timedelta(minutes=1))
    assert mailbox == []


async def test_a_rescheduled_appointment_gets_reminders_for_its_new_time_only(db_session, organization, mailbox):
    old, new = utc(300), utc(600)
    row = await booked(db_session, organization, start=old)
    await reminders.send_due_reminders(db_session, now=old - timedelta(minutes=30))
    assert len(mailbox) == 1
    row.slot_start, row.slot_end, row.scheduled_at = new, new + timedelta(hours=1), old - timedelta(minutes=20)  # moved: Pentrix's update
    await db_session.flush()
    await reminders.send_due_reminders(db_session, now=old - timedelta(minutes=5))
    assert len(mailbox) == 1  # nothing for the old time
    await reminders.send_due_reminders(db_session, now=new - timedelta(minutes=30))
    assert len(mailbox) == 2  # a fresh 30-minute reminder for the new time (it was booked well before then)


async def test_a_failed_send_is_retried_a_few_times_and_then_left_alone(db_session, organization, monkeypatch):
    calls = []

    async def failing(to, subject, text, html=None, attachments=None):
        calls.append(to)
        return False

    monkeypatch.setattr(reminders.email_service, "send", failing)
    start = utc(300)
    await booked(db_session, organization, start=start)
    for minute in range(6):
        await reminders.send_due_reminders(db_session, now=start - timedelta(minutes=30) + timedelta(minutes=minute))
    assert len(calls) == reminders.MAX_ATTEMPTS
    row = (await db_session.execute(select(PentrixBookingReminder))).scalar_one()
    assert row.status == "failed" and row.attempts == reminders.MAX_ATTEMPTS and row.error


async def test_a_published_email_studio_template_changes_the_wording(client, auth_headers, db_session, organization, mailbox):
    from tests.api.test_email_studio import create, draft, publish

    html = '<!DOCTYPE html><html><body><p>Custom: {{full_name}} meets {{candidate_name}} at {{booking_time}} {{timezone}}. <a href="{{meeting_url}}">Go</a></p></body></html>'
    t = await create(client, auth_headers, name="Staff reminder", subject="Custom reminder {{booking_time}}", html=html)
    await publish(client, auth_headers, t)
    r = await client.put("/api/v1/email-studio/assignments/pentrix_booking_reminder_30m_staff", json={"template_id": t["id"]}, headers=auth_headers)
    assert r.status_code == 200, r.text
    staff, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    start = utc(300)
    await booked(db_session, organization, start=start, staff=staff)
    await reminders.send_due_reminders(db_session, now=start - timedelta(minutes=30))
    staff_mail = next(m for m in mailbox if m["to"] == staff.email)
    assert staff_mail["subject"].startswith("Custom reminder") and "Meera Iyer" in staff_mail["text"]
    assert next(m for m in mailbox if m["to"] == "meera@example.com")["subject"].startswith("Your appointment starts in 30 minutes")  # candidate keeps the default


def test_the_reminder_templates_exist_for_each_moment_and_audience():
    from packages.email.registry import get_def

    for kind in ("30m", "5m", "now"):
        for who in ("candidate", "staff"):
            d = get_def(f"pentrix_booking_reminder_{kind}_{who}")
            assert d is not None and "meeting_url" in d.required and {v.name for v in d.variables} >= {"full_name", "booking_date", "booking_time", "timezone", "meeting_url", "representative"}
