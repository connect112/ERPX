"""
Pentrix payments in ERPX: the synchronised records (pushed by Pentrix and pulled by cursor, never stored twice), the Payments list and
its filters, invoices, the daily summary in India time, the nightly reconciliation against Pentrix (including repairing what differs and
reporting what cannot be repaired), and who may see money. Pentrix is replaced by a fake that checks every signature.
"""
import hmac
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from modules.pentrix_ops import client as client_module
from modules.pentrix_ops.client import sign
from modules.pentrix_ops.models import PentrixCandidate, PentrixDailySummary, PentrixPayment, PentrixSyncState
from modules.pentrix_ops.payments import PentrixPaymentService, day_bounds, totals_for
from tests.api.test_pentrix_ops import SECRET, FakePentrix, person, push_headers, utc

pytestmark = pytest.mark.api

_P = "/api/v1/pentrix-ops"
_PREFIX = "/api/v1/internal/erpx"
IST = ZoneInfo("Asia/Kolkata")
DAY = date(2026, 10, 20)  # a closed day well in the past


def at(day: date, hour: int, minute: int = 0) -> str:
    """A wall-clock time in India, as the UTC instant Pentrix would send."""
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST).astimezone(timezone.utc).isoformat()


class FakePentrixWithPayments(FakePentrix):
    def __init__(self):
        super().__init__()
        self.payments: dict[str, dict] = {}
        self.broken_payments: set[str] = set()

    def payment(self, **over) -> dict:
        pid = over.pop("id", str(uuid.uuid4()))
        record = {
            "id": pid, "user_id": over.pop("user_id", "user-1"), "candidate_name": "Asha Rao", "candidate_email": "asha@example.com", "provider": "razorpay",
            "provider_order_id": f"order_{pid[:6]}", "provider_payment_id": None, "reference": f"order_{pid[:6]}", "amount_paise": 250000, "currency": "INR",
            "purpose": "program_fee", "status": "created", "invoice_number": None, "receipt_number": f"RCPT-{pid[:6]}", "adjusted_against_program_fee": False,
            "provisioning_status": None, "created_at": at(DAY, 9), "paid_at": None, "failed_at": None, "refunded_at": None, "updated_at": self._stamp(),
        }
        status = over.get("status")
        if status in ("succeeded", "partially_refunded", "refunded"):
            over.setdefault("paid_at", at(DAY, 11))
            over.setdefault("provider_payment_id", f"pay_{pid[:6]}")
            over.setdefault("reference", over["provider_payment_id"])
        if status == "failed" and "failed_at" not in over:
            over["failed_at"] = at(DAY, 12)
        if status in ("refunded", "partially_refunded") and "refunded_at" not in over:
            over["refunded_at"] = at(DAY, 15)
        record.update(over)
        self.payments[pid] = record
        return record

    def touch_payment(self, pid: str, **over) -> dict:
        self.payments[pid].update(over)
        self.payments[pid]["updated_at"] = self._stamp()
        return self.payments[pid]

    def _day(self, d: str) -> dict:
        day = date.fromisoformat(d)
        start = datetime(day.year, day.month, day.day, tzinfo=IST).astimezone(timezone.utc)
        end = start + timedelta(days=1)
        inside = lambda v: v is not None and start <= datetime.fromisoformat(v) < end  # noqa: E731
        involved = [
            p for p in self.payments.values()
            if inside(p["paid_at"]) or inside(p["failed_at"]) or inside(p["refunded_at"]) or (p["status"] in ("created", "pending") and inside(p["created_at"]))
        ]
        paid = [p for p in involved if inside(p["paid_at"])]
        refunded = [p for p in involved if inside(p["refunded_at"])]
        return {
            "date": d, "timezone": "Asia/Kolkata",
            "successful": {"count": len(paid), "amount_paise": sum(p["amount_paise"] for p in paid)},
            "failed": {"count": sum(1 for p in involved if inside(p["failed_at"]))},
            "pending": {"count": sum(1 for p in involved if p["status"] in ("created", "pending") and inside(p["created_at"]))},
            "refunds": {"count": len(refunded), "amount_paise": sum(p["amount_paise"] for p in refunded if p["status"] == "refunded"), "partial_count": sum(1 for p in refunded if p["status"] == "partially_refunded")},
            "transactions": [{"id": p["id"], "status": p["status"], "amount_paise": p["amount_paise"], "invoice_number": p["invoice_number"], "updated_at": p["updated_at"]} for p in involved],
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = urlparse(str(request.url))
        if not url.path.startswith(f"{_PREFIX}/payments"):
            return super().handler(request)
        if self.down:
            raise httpx.ConnectError("down")
        path_and_query = url.path + (f"?{url.query}" if url.query else "")
        body = request.content.decode() if request.content else ""
        if not hmac.compare_digest(sign(SECRET, request.headers.get("X-ERPX-Timestamp", ""), request.method, path_and_query, body), request.headers.get("X-ERPX-Signature", "")):
            return httpx.Response(401, json={"error": "auth_error", "message": "Invalid signature."})
        path = url.path.replace(_PREFIX, "")
        self.calls.append((request.method, path, None, request.headers.get("X-ERPX-Actor")))
        if path == "/payments":
            cursor = parse_qs(url.query).get("cursor", [""])[0]
            items = sorted(self.payments.values(), key=lambda p: (p["updated_at"], p["id"]))
            if cursor:
                stamp, _, last = cursor.partition("|")
                items = [p for p in items if (p["updated_at"], p["id"]) > (stamp, last)]
            last_item = items[-1] if items else None
            return httpx.Response(200, json={"items": items, "next_cursor": f"{last_item['updated_at']}|{last_item['id']}" if last_item else cursor or None, "has_more": False})
        if path.startswith("/payments/day/"):
            return httpx.Response(200, json=self._day(path.rsplit("/", 1)[1]))
        pid = path.rsplit("/", 1)[1]
        if pid in self.broken_payments:
            return httpx.Response(500, json={"error": "x", "message": "boom"})
        if pid not in self.payments:
            return httpx.Response(404, json={"error": "not_found", "message": "That payment was not found."})
        return httpx.Response(200, json=self.payments[pid])


@pytest.fixture
def pentrix(monkeypatch, organization):
    fake = FakePentrixWithPayments()
    monkeypatch.setattr(settings, "PENTRIX_ORGANIZATION_SLUG", organization.slug)
    monkeypatch.setattr(settings, "PENTRIX_INTERNAL_API_BASE_URL", "http://pentrix.test")
    monkeypatch.setattr(settings, "ERPX_INTERNAL_SERVICE_SECRET", SECRET)
    monkeypatch.setattr(client_module, "DEFAULT_TRANSPORT", httpx.MockTransport(fake.handler))
    return fake


async def sync(client, headers):
    r = await client.post(f"{_P}/payments/sync", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["updated"]


async def listed(client, headers, query=""):
    r = await client.get(f"{_P}/payments?{query}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def rows(db_session):
    return (await db_session.execute(select(PentrixPayment))).scalars().all()


# ------------------------------------------------------------------ the copy


async def test_a_pushed_payment_is_stored_once_with_its_original_reference(client, db_session, organization, pentrix):
    pay = pentrix.payment(status="succeeded", invoice_number="INV-1")
    body = json.dumps(pay)
    for _ in range(3):  # a retry storm
        assert (await client.post("/api/v1/internal/pentrix/payments", content=body, headers=push_headers(body))).status_code == 200
    stored = await rows(db_session)
    assert len(stored) == 1 and stored[0].pentrix_payment_id == pay["id"]
    assert (stored[0].reference, stored[0].invoice_number, stored[0].amount_paise, stored[0].status) == (pay["reference"], "INV-1", 250000, "succeeded")
    assert stored[0].paid_at is not None


async def test_an_older_message_never_regresses_a_settled_payment(client, db_session, organization, pentrix):
    pay = pentrix.payment(status="succeeded")
    newer = {**pay, "status": "refunded", "refunded_at": at(DAY, 16), "updated_at": (datetime.fromisoformat(pay["updated_at"]) + timedelta(seconds=9)).isoformat()}
    older = {**pay, "status": "failed", "updated_at": (datetime.fromisoformat(pay["updated_at"]) - timedelta(seconds=9)).isoformat()}
    for message in (pay, newer, older):
        await client.post("/api/v1/internal/pentrix/payments", content=json.dumps(message), headers=push_headers(json.dumps(message)))
    (stored,) = await rows(db_session)
    assert stored.status == "refunded"


async def test_unsigned_or_wrongly_signed_pushes_are_refused(client, db_session, organization, pentrix):
    body = json.dumps(pentrix.payment(status="succeeded"))
    assert (await client.post("/api/v1/internal/pentrix/payments", content=body)).status_code == 401
    assert (await client.post("/api/v1/internal/pentrix/payments", content=body, headers=push_headers(body, "wrong"))).status_code == 401
    assert await rows(db_session) == []


async def test_a_push_and_a_pull_of_the_same_payment_do_not_duplicate_it(client, db_session, organization, auth_headers, pentrix):
    pay = pentrix.payment(status="succeeded")
    body = json.dumps(pay)
    await client.post("/api/v1/internal/pentrix/payments", content=body, headers=push_headers(body))
    assert await sync(client, auth_headers) == 1
    assert await sync(client, auth_headers) == 0
    assert len(await rows(db_session)) == 1


async def test_a_failed_pull_keeps_its_place_reports_it_and_the_retry_catches_up(client, db_session, organization, auth_headers, pentrix):
    pentrix.payment(status="succeeded")
    assert await sync(client, auth_headers) == 1
    pentrix.payment(status="succeeded")
    pentrix.down = True
    assert (await client.post(f"{_P}/payments/sync", headers=auth_headers)).status_code == 503
    summary = (await client.get(f"{_P}/payments/summary", headers=auth_headers)).json()
    assert summary["sync"]["last_error"]  # the screen can say the synchronisation failed
    pentrix.down = False
    assert await sync(client, auth_headers) == 1  # the retry resumes where it stopped
    state = (await db_session.execute(select(PentrixSyncState).where(PentrixSyncState.key == "payments_cursor"))).scalar_one()
    assert state.last_error is None and len(await rows(db_session)) == 2


# ------------------------------------------------------------------ the list


async def seed(client, db_session, organization, auth_headers, pentrix):
    pentrix.payment(user_id="u-asha", candidate_name="Asha Rao", candidate_email="asha@example.com", status="succeeded", amount_paise=250000, invoice_number="INV-ASHA", paid_at=at(DAY, 11))
    pentrix.payment(user_id="u-bina", candidate_name="Bina Shah", candidate_email="bina@example.com", status="pending", amount_paise=250000)
    pentrix.payment(user_id="u-chirag", candidate_name="Chirag", candidate_email="chirag@example.com", status="failed", amount_paise=250000)
    pentrix.payment(user_id="u-dev", candidate_name="Dev", candidate_email="dev@example.com", status="refunded", amount_paise=300000, purpose="individual_interaction_token", invoice_number="INV-DEV", paid_at=at(DAY - timedelta(days=3), 10))
    pentrix.payment(user_id="u-esha", candidate_name="Esha", candidate_email="esha@example.com", status="partially_refunded", amount_paise=400000, paid_at=at(DAY - timedelta(days=2), 10))
    await sync(client, auth_headers)


async def test_statuses_are_shown_in_the_teams_words(client, db_session, organization, auth_headers, pentrix):
    await seed(client, db_session, organization, auth_headers, pentrix)
    by_name = {p["candidate_name"]: p for p in (await listed(client, auth_headers))["items"]}
    assert {n: p["status_label"] for n, p in by_name.items()} == {
        "Asha Rao": "Paid", "Bina Shah": "Pending", "Chirag": "Failed", "Dev": "Refunded", "Esha": "Partially refunded"}
    assert by_name["Asha Rao"]["method"] == "Razorpay" and by_name["Asha Rao"]["reference"].startswith("pay_")
    assert by_name["Dev"]["purpose_label"] == "Token fee"
    assert {n: p["invoice_available"] for n, p in by_name.items()} == {"Asha Rao": True, "Bina Shah": False, "Chirag": False, "Dev": True, "Esha": True}


async def test_filters_search_sort_and_paging(client, db_session, organization, auth_headers, pentrix):
    await seed(client, db_session, organization, auth_headers, pentrix)

    async def names(query):
        return sorted(p["candidate_name"] for p in (await listed(client, auth_headers, query))["items"])

    assert await names("status=paid") == ["Asha Rao"]
    assert await names("status=refunded&status=partially_refunded") == ["Dev", "Esha"]
    assert await names("q=INV-DEV") == ["Dev"]
    assert await names("q=bina") == ["Bina Shah"]
    assert await names("purpose=individual_interaction_token") == ["Dev"]
    assert await names("candidate=u-chirag") == ["Chirag"]
    assert await names(f"date_from={at(DAY, 10).replace('+00:00', 'Z')}&date_to={at(DAY, 12).replace('+00:00', 'Z')}") == ["Asha Rao"]  # known by when it was paid
    top = (await listed(client, auth_headers, "sort=amount&page_size=2"))["items"]
    assert [p["amount_paise"] for p in top] == [400000, 300000]
    assert (await listed(client, auth_headers, "page_size=2&page=3"))["items"].__len__() == 1
    assert (await client.get(f"{_P}/payments?status=maybe", headers=auth_headers)).status_code == 422
    assert (await client.get(f"{_P}/payments?sort=password", headers=auth_headers)).status_code == 422


async def test_a_payment_links_to_the_candidate_and_follows_their_current_name(client, db_session, organization, auth_headers, pentrix):
    pay = pentrix.payment(user_id="u-asha", candidate_name="Asha Rao", status="succeeded")
    await sync(client, auth_headers)
    assert (await listed(client, auth_headers))["items"][0]["candidate_id"] is None  # not mirrored as a candidate yet
    cand = PentrixCandidate(organization_id=organization.id, pentrix_user_id="u-asha", full_name="Asha R. Rao", email="asha.new@example.com", registered_at=utc(-60))
    db_session.add(cand)
    await db_session.flush()
    item = (await listed(client, auth_headers))["items"][0]
    assert item["candidate_id"] == str(cand.id) and item["candidate_name"] == "Asha R. Rao" and item["candidate_email"] == "asha.new@example.com"
    assert (await client.get(f"{_P}/payments/{item['id']}", headers=auth_headers)).json()["pentrix_payment_id"] == pay["id"]


# ------------------------------------------------------------------ invoices


async def test_an_invoice_is_a_pdf_with_pentrixs_number_for_a_payment_that_was_made(client, db_session, organization, auth_headers, pentrix):
    await seed(client, db_session, organization, auth_headers, pentrix)
    by_name = {p["candidate_name"]: p for p in (await listed(client, auth_headers))["items"]}
    shown = await client.get(f"{_P}/payments/{by_name['Asha Rao']['id']}/invoice", headers=auth_headers)
    assert shown.status_code == 200 and shown.headers["content-type"] == "application/pdf" and shown.content.startswith(b"%PDF")
    assert shown.headers["content-disposition"] == 'inline; filename="INV-ASHA.pdf"'
    saved = await client.get(f"{_P}/payments/{by_name['Asha Rao']['id']}/invoice?download=true", headers=auth_headers)
    assert saved.headers["content-disposition"].startswith("attachment")
    assert (await client.get(f"{_P}/payments/{by_name['Dev']['id']}/invoice", headers=auth_headers)).status_code == 200  # still available after a refund
    for unpaid in ("Bina Shah", "Chirag"):
        assert (await client.get(f"{_P}/payments/{by_name[unpaid]['id']}/invoice", headers=auth_headers)).status_code == 422
    assert (await client.get(f"{_P}/payments/{uuid.uuid4()}/invoice", headers=auth_headers)).status_code == 404


def test_a_payment_without_an_invoice_number_gets_a_receipt_and_erpx_numbers_nothing():
    base = dict(organization_id=uuid.uuid4(), pentrix_payment_id="p", pentrix_user_id="u", candidate_name="Asha", candidate_email="a@example.com", provider="razorpay",
                purpose="program_fee", status="succeeded", amount_paise=250000, currency="INR", paid_at=datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc), reference="pay_1")
    _, name = PentrixPaymentService.invoice_pdf(PentrixPayment(**base, receipt_number="RCPT-9"), None)
    assert name == "RCPT-9.pdf"
    _, name = PentrixPaymentService.invoice_pdf(PentrixPayment(**base, invoice_number="INV-9", receipt_number="RCPT-9"), None)
    assert name == "INV-9.pdf"


# ------------------------------------------------------------------ a day in India


def test_a_day_is_midnight_to_midnight_in_india_and_figures_follow_when_things_happened():
    start, end = day_bounds(DAY)
    assert start == datetime(2026, 10, 19, 18, 30, tzinfo=timezone.utc) and end == datetime(2026, 10, 20, 18, 30, tzinfo=timezone.utc)

    def p(status, paid=None, refunded=None, failed=None, created=None, amount=1000):
        return PentrixPayment(pentrix_payment_id=str(uuid.uuid4()), status=status, amount_paise=amount, paid_at=paid, refunded_at=refunded, failed_at=failed, created_at_source=created)

    rows_ = [
        p("succeeded", paid=start + timedelta(hours=1), amount=250000),
        p("succeeded", paid=end - timedelta(minutes=1), amount=50000),          # 23:59
        p("succeeded", paid=start - timedelta(minutes=1), amount=999),           # 23:59 the day before: not today's
        p("succeeded", paid=end, amount=999),                                    # exactly midnight after: not today's
        p("refunded", paid=start - timedelta(days=2), refunded=start + timedelta(hours=5), amount=300000),
        p("partially_refunded", paid=start - timedelta(days=2), refunded=start + timedelta(hours=6), amount=400000),
        p("failed", failed=start + timedelta(hours=2)),
        p("pending", created=start + timedelta(hours=3)),
        p("pending", created=start - timedelta(days=1)),                         # started the day before
    ]
    figures = totals_for(rows_, start, end)
    assert figures == {"successful_count": 2, "collected_paise": 300000, "failed_count": 1, "pending_count": 1, "refund_count": 2, "refunded_paise": 300000, "partial_refund_count": 1}


async def test_the_daily_list_shows_reconciled_days_and_live_figures_for_the_rest(client, db_session, organization, auth_headers, pentrix):
    pentrix.payment(status="succeeded", amount_paise=250000)
    await sync(client, auth_headers)
    live = (await client.get(f"{_P}/payments/daily?date_from={DAY}&date_to={DAY}", headers=auth_headers)).json()[0]
    assert live["date"] == str(DAY) and live["reconciled"] is False and live["status"] == "unreconciled" and live["collected_paise"] == 250000
    assert (await client.post(f"{_P}/payments/daily/{DAY}/reconcile", headers=auth_headers)).json()["status"] == "matched"
    done = (await client.get(f"{_P}/payments/daily?date_from={DAY}&date_to={DAY}", headers=auth_headers)).json()[0]
    assert done["reconciled"] is True and done["status"] == "matched" and done["successful_count"] == 1 and done["net_paise"] == 250000
    default = (await client.get(f"{_P}/payments/daily", headers=auth_headers)).json()
    assert len(default) == 14 and default[0]["status"] == "open"  # newest first, today still going
    assert (await client.get(f"{_P}/payments/daily?date_from=2025-01-01&date_to=2026-10-20", headers=auth_headers)).status_code == 422
    assert (await client.get(f"{_P}/payments/daily?date_from=2026-10-20&date_to=2026-10-01", headers=auth_headers)).status_code == 422


async def test_the_summary_for_today_counts_what_was_collected_today(client, db_session, organization, auth_headers, pentrix):
    now = datetime.now(IST)
    pentrix.payment(status="succeeded", amount_paise=250000, paid_at=at(now.date(), 0, 1))
    pentrix.payment(status="succeeded", amount_paise=100000, paid_at=at(now.date() - timedelta(days=1), 12))
    pentrix.payment(status="pending")
    await sync(client, auth_headers)
    s = (await client.get(f"{_P}/payments/summary", headers=auth_headers)).json()
    assert (s["collected_today_paise"], s["successful_today"], s["pending_payments"]) == (250000, 1, 1)
    assert s["latest_payment"]["status"] == "paid" and len(s["recent"]) == 3 and s["sync"]["configured"] is True


# ------------------------------------------------------------------ reconciliation


async def test_a_day_that_agrees_with_pentrix_is_matched(client, db_session, organization, auth_headers, pentrix):
    pentrix.payment(status="succeeded", amount_paise=250000)
    pentrix.payment(status="failed")
    pentrix.payment(status="refunded", amount_paise=300000, paid_at=at(DAY - timedelta(days=3), 10), refunded_at=at(DAY, 16))
    await sync(client, auth_headers)
    r = (await client.post(f"{_P}/payments/daily/{DAY}/reconcile", headers=auth_headers)).json()
    assert r["status"] == "matched" and r["mismatches"] == [] and r["repaired_count"] == 0
    assert (r["successful_count"], r["collected_paise"], r["failed_count"], r["refund_count"], r["refunded_paise"], r["net_paise"]) == (1, 250000, 1, 1, 300000, -50000)


async def test_a_payment_whose_message_was_lost_is_found_and_repaired_from_pentrix(client, db_session, organization, auth_headers, pentrix):
    kept = pentrix.payment(status="succeeded", amount_paise=250000)
    lost = pentrix.payment(status="succeeded", amount_paise=100000)
    await sync(client, auth_headers)
    # ERPX never heard that `lost` succeeded: it still holds the earlier "pending" state, and a third payment never arrived at all
    row = (await db_session.execute(select(PentrixPayment).where(PentrixPayment.pentrix_payment_id == lost["id"]))).scalar_one()
    row.status, row.paid_at = "pending", None
    never = pentrix.payment(status="succeeded", amount_paise=50000)
    await db_session.flush()
    assert kept["id"] != never["id"]
    r = (await client.post(f"{_P}/payments/daily/{DAY}/reconcile", headers=auth_headers)).json()
    assert r["status"] == "matched" and r["repaired_count"] == 2 and r["mismatches"] == []
    assert (r["successful_count"], r["collected_paise"]) == (3, 400000)
    assert {p.pentrix_payment_id for p in await rows(db_session)} == {kept["id"], lost["id"], never["id"]}


async def test_what_cannot_be_repaired_is_reported_as_a_mismatch(client, db_session, organization, auth_headers, pentrix):
    pay = pentrix.payment(status="succeeded", amount_paise=250000)
    await sync(client, auth_headers)
    pentrix.broken_payments.add(pay["id"])
    row = (await db_session.execute(select(PentrixPayment))).scalar_one()
    row.status, row.paid_at = "pending", None  # stale here, and Pentrix will not hand the payment over again
    await db_session.flush()
    r = (await client.post(f"{_P}/payments/daily/{DAY}/reconcile", headers=auth_headers)).json()
    assert r["status"] == "mismatch" and r["repaired_count"] == 0
    kinds = {m["kind"] for m in r["mismatches"]}
    assert "status_differs" in kinds and "total_differs" in kinds
    pentrix.broken_payments.clear()  # a retry once Pentrix answers again clears it
    again = (await client.post(f"{_P}/payments/daily/{DAY}/reconcile", headers=auth_headers)).json()
    assert again["status"] == "matched" and again["attempts"] == 2


async def test_reconciling_again_rewrites_the_one_summary_and_never_counts_twice(client, db_session, organization, auth_headers, pentrix):
    pentrix.payment(status="succeeded", amount_paise=250000)
    await sync(client, auth_headers)
    for _ in range(3):
        r = (await client.post(f"{_P}/payments/daily/{DAY}/reconcile", headers=auth_headers)).json()
    assert r["collected_paise"] == 250000 and r["attempts"] == 3
    assert len((await db_session.execute(select(PentrixDailySummary))).scalars().all()) == 1


async def test_a_pentrix_that_cannot_be_reached_is_recorded_as_an_error_on_that_day(client, db_session, organization, auth_headers, pentrix):
    pentrix.payment(status="succeeded")
    await sync(client, auth_headers)
    pentrix.down = True
    r = (await client.post(f"{_P}/payments/daily/{DAY}/reconcile", headers=auth_headers)).json()
    assert r["status"] == "error" and "did not respond" in r["last_error"]
    pentrix.down = False
    assert (await client.post(f"{_P}/payments/daily/{DAY}/reconcile", headers=auth_headers)).json()["status"] == "matched"


async def test_a_day_that_has_not_ended_cannot_be_reconciled(client, db_session, organization, auth_headers, pentrix):
    today = datetime.now(IST).date()
    assert (await client.post(f"{_P}/payments/daily/{today}/reconcile", headers=auth_headers)).status_code == 422
    assert (await client.post(f"{_P}/payments/daily/{today + timedelta(days=1)}/reconcile", headers=auth_headers)).status_code == 422
    assert (await client.post(f"{_P}/payments/daily/not-a-date/reconcile", headers=auth_headers)).status_code == 422


async def test_the_nightly_job_checks_the_closed_days_and_revisits_the_ones_that_did_not_match(client, db_session, organization, auth_headers, pentrix):
    two_days_ago = DAY
    pentrix.payment(status="succeeded", amount_paise=250000, paid_at=at(two_days_ago, 11))
    pentrix.payment(status="succeeded", amount_paise=100000, paid_at=at(two_days_ago + timedelta(days=1), 11))
    await sync(client, auth_headers)
    service = PentrixPaymentService(db_session)
    today = two_days_ago + timedelta(days=2)  # "tonight": yesterday is DAY + 1
    done = await service.reconcile_due(organization.id, today=today)
    assert {r.day: r.status for r in done} == {two_days_ago: "matched", two_days_ago + timedelta(days=1): "matched"}
    assert [r.collected_paise for r in sorted(done, key=lambda r: r.day)] == [250000, 100000]
    again = await service.reconcile_due(organization.id, today=today)  # running it twice changes nothing
    assert len(again) == 2 and len((await db_session.execute(select(PentrixDailySummary))).scalars().all()) == 2
    pentrix.down = True
    failed = await service.reconcile_due(organization.id, today=today)
    assert {r.status for r in failed} == {"error"}
    pentrix.down = False
    recovered = await service.reconcile_due(organization.id, today=today)
    assert {r.status for r in recovered} == {"matched"}


async def test_the_nightly_job_has_nothing_to_do_before_any_payment_exists(db_session, organization, pentrix):
    assert await PentrixPaymentService(db_session).reconcile_due(organization.id) == []


# ------------------------------------------------------------------ export


async def test_the_daily_summary_and_a_days_payments_export_as_csv_with_formulas_defused(client, db_session, organization, auth_headers, pentrix):
    pentrix.payment(candidate_name="=HYPERLINK(\"http://evil.example\")", status="succeeded", amount_paise=250000, invoice_number="INV-1")
    await sync(client, auth_headers)
    await client.post(f"{_P}/payments/daily/{DAY}/reconcile", headers=auth_headers)
    days = await client.get(f"{_P}/payments/daily/export?date_from={DAY}&date_to={DAY}", headers=auth_headers)
    assert days.headers["content-type"].startswith("text/csv") and "attachment" in days.headers["content-disposition"]
    lines = days.text.strip().splitlines()
    assert lines[0].startswith("Date (IST),Status,Successful payments") and lines[1].startswith(f"{DAY},matched,1,2500.00")
    detail = await client.get(f"{_P}/payments/daily/{DAY}/export", headers=auth_headers)
    assert "INV-1" in detail.text and "'=HYPERLINK" in detail.text and ",=HYPERLINK" not in detail.text


async def test_a_days_detail_lists_its_transactions(client, db_session, organization, auth_headers, pentrix):
    pentrix.payment(status="succeeded", amount_paise=250000)
    pentrix.payment(status="succeeded", amount_paise=100000, paid_at=at(DAY + timedelta(days=1), 10))
    await sync(client, auth_headers)
    body = (await client.get(f"{_P}/payments/daily/{DAY}", headers=auth_headers)).json()
    assert body["summary"]["collected_paise"] == 250000 and [t["amount_paise"] for t in body["transactions"]] == [250000]


# ------------------------------------------------------------------ who may see money


async def test_payments_are_their_own_permissions_and_candidate_access_does_not_grant_them(client, db_session, organization, auth_headers, pentrix):
    pay = pentrix.payment(status="succeeded", invoice_number="INV-1")
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixPayment))).scalar_one()
    _, viewer = await person(db_session, organization, ["pentrix_ops.payments.view"])
    _, manager = await person(db_session, organization, ["pentrix_ops.payments.view", "pentrix_ops.payments.manage"])
    _, registrations = await person(db_session, organization, ["pentrix_ops.registrations.view", "pentrix_ops.overview.view", "pentrix_ops.assessments.view", "pentrix_ops.bookings.view"])
    _, staff = await person(db_session, organization, ["pentrix_ops.bookings.assigned"])

    reads = ["/payments", "/payments/summary", f"/payments/{row.id}", f"/payments/{row.id}/invoice", "/payments/daily", f"/payments/daily/{DAY}", f"/payments/daily/{DAY}/export", "/payments/daily/export"]
    for path in reads:
        assert (await client.get(f"{_P}{path}", headers=viewer)).status_code == 200, path
        for nobody in (registrations, staff):
            assert (await client.get(f"{_P}{path}", headers=nobody)).status_code == 403, path
    assert (await client.post(f"{_P}/payments/sync", headers=viewer)).status_code == 403
    assert (await client.post(f"{_P}/payments/daily/{DAY}/reconcile", headers=viewer)).status_code == 403
    assert (await client.post(f"{_P}/payments/sync", headers=manager)).status_code == 200
    assert (await client.post(f"{_P}/payments/daily/{DAY}/reconcile", headers=manager)).status_code == 200
    assert pay["id"]  # (the payment above is the one every request read)


async def test_another_organisation_gets_no_payments(client, db_session, organization, auth_headers, pentrix):
    from modules.organizations.repository import OrganizationRepository
    from tests._fixtures import _make_user

    pentrix.payment(status="succeeded")
    await sync(client, auth_headers)
    row = (await db_session.execute(select(PentrixPayment))).scalar_one()
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other, is_superuser=True, email=f"o-{uuid.uuid4().hex[:8]}@erpx.example.com")
    theirs = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"{_P}/payments", headers=theirs)).status_code == 422
    assert (await client.get(f"{_P}/payments/{row.id}/invoice", headers=theirs)).status_code == 422


def test_the_payment_jobs_are_scheduled_and_the_permissions_exist():
    from app.core.celery_app import celery_app
    from modules.authorization.service import DEFAULT_PERMISSIONS

    schedule = {entry["task"]: entry["schedule"] for entry in celery_app.conf.beat_schedule.values()}
    assert "pentrix.sync_payments" in schedule and "pentrix.reconcile_payments" in schedule
    codes = {p[0] for p in DEFAULT_PERMISSIONS}
    assert {"pentrix_ops.payments.view", "pentrix_ops.payments.manage"} <= codes


# ------------------------------------------------------------------ two messages about the same payment at the same moment


async def test_two_messages_racing_to_create_the_same_record_both_succeed_and_leave_one_row(db_session, organization, pentrix):
    from modules.pentrix_ops.mirror import insert_or_existing

    pay = pentrix.payment(status="succeeded")
    first = await insert_or_existing(db_session, PentrixPayment, PentrixPayment.pentrix_payment_id, pay["id"],
                                     lambda: PentrixPayment(organization_id=organization.id, pentrix_payment_id=pay["id"], pentrix_user_id="u", status="created"))
    # the second message looked for the row before the first one made it, so it also tries to insert
    second = await insert_or_existing(db_session, PentrixPayment, PentrixPayment.pentrix_payment_id, pay["id"],
                                      lambda: PentrixPayment(organization_id=organization.id, pentrix_payment_id=pay["id"], pentrix_user_id="u", status="created"))
    assert second.id == first.id
    saved = await PentrixPaymentService(db_session).upsert(organization.id, pay)  # and the session is still usable afterwards
    assert saved.id == first.id and saved.status == "succeeded"
    assert len(await rows(db_session)) == 1
