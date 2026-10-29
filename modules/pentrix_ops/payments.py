"""
Pentrix payments in ERPX: the synchronised records, the Payments list, invoices, the daily summaries and the nightly reconciliation.

This module only *records and reports*. Pentrix decides that a payment succeeded (after its provider's signature-verified webhook);
ERPX keeps a copy keyed by Pentrix's payment id, so a payment can never be stored twice and the original transaction reference is
preserved. Nothing here moves money or marks a payment paid: a message that says "succeeded" is a report of what Pentrix recorded.

A "day" is a calendar day in India (Asia/Kolkata). The nightly job reconciles the day that has just closed: it asks Pentrix what it
holds for that day, compares payment by payment with ERPX's copy, repairs what differs by fetching those payments again, and records
whatever still disagrees so a person can see it and retry.
"""
import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.pentrix_ops.client import PentrixClient
from modules.pentrix_ops.mirror import insert_or_existing
from modules.pentrix_ops.models import PentrixCandidate, PentrixDailySummary, PentrixPayment, PentrixSyncState
from modules.pentrix_ops.service import parse_time, pentrix_organization_id

logger = get_logger(__name__)

IST = ZoneInfo("Asia/Kolkata")
PAYMENTS_CURSOR = "payments_cursor"
OPEN = ("created", "pending")
PAID_EVER = ("succeeded", "partially_refunded", "refunded")  # states a payment can only be in after it was paid
# Pentrix's statuses in the words the team uses (Pending, Paid, Failed, Refunded, Partially Refunded).
GROUP = {"created": "pending", "pending": "pending", "succeeded": "paid", "failed": "failed", "refunded": "refunded", "partially_refunded": "partially_refunded"}
GROUP_LABEL = {"pending": "Pending", "paid": "Paid", "failed": "Failed", "refunded": "Refunded", "partially_refunded": "Partially refunded"}
PROVIDER_LABEL = {"razorpay": "Razorpay", "stripe": "Stripe"}
PURPOSE_LABEL = {"program_fee": "Programme fee", "individual_interaction_token": "Token fee"}
STATUS_FILTERS = set(GROUP_LABEL)
MAX_DAYS = 93


def ist_day(value: datetime) -> date:
    return value.astimezone(IST).date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """The UTC start (inclusive) and end (exclusive) of a calendar day in India."""
    start = datetime.combine(day, time.min, tzinfo=IST).astimezone(timezone.utc)
    return start, start + timedelta(days=1)


def today_ist() -> date:
    return datetime.now(IST).date()


def parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("A date looks like 2026-10-29.") from exc


@dataclass
class PaymentFilters:
    q: str | None = None
    status: list[str] = field(default_factory=list)
    purpose: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    candidate_pentrix_id: str | None = None

    def validate(self) -> "PaymentFilters":
        bad = [s for s in self.status if s not in STATUS_FILTERS]
        if bad:
            raise ValidationError(f"'{bad[0]}' is not a payment status.")
        return self


def _inside(value: datetime | None, start: datetime, end: datetime) -> bool:
    return value is not None and start <= value < end


def totals_for(rows: list[PentrixPayment], start: datetime, end: datetime) -> dict:
    """The day's figures from a set of payments: counted by when each thing happened, not by when the row last changed."""
    succeeded = [p for p in rows if _inside(p.paid_at, start, end)]
    refunded = [p for p in rows if _inside(p.refunded_at, start, end)]
    return {
        "successful_count": len(succeeded),
        "collected_paise": sum(p.amount_paise for p in succeeded),
        "failed_count": sum(1 for p in rows if _inside(p.failed_at, start, end)),
        "pending_count": sum(1 for p in rows if p.status in OPEN and _inside(p.created_at_source, start, end)),
        "refund_count": len(refunded),
        # A partial refund's amount is not recorded in Pentrix, so only complete refunds carry one.
        "refunded_paise": sum(p.amount_paise for p in refunded if p.status == "refunded"),
        "partial_refund_count": sum(1 for p in refunded if p.status == "partially_refunded"),
    }


def _csv_cell(value: Any) -> Any:
    """A spreadsheet runs text that starts with = + - @ as a formula, and names and references come from outside: defuse them."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


class PentrixPaymentService:
    def __init__(self, db: AsyncSession, client: PentrixClient | None = None):
        self.db = db
        self.client = client or PentrixClient()

    # ------------------------------------------------------------------ the copy

    async def upsert(self, organization_id: uuid.UUID, data: dict) -> PentrixPayment:
        """Write one Pentrix payment into the copy. Matched only by Pentrix's payment id, so a repeat changes nothing and an older
        message never overwrites a newer state."""
        pid = str(data.get("id") or "")
        if not pid:
            raise ValidationError("A payment is required.")
        row = (await self.db.execute(select(PentrixPayment).where(PentrixPayment.pentrix_payment_id == pid))).scalar_one_or_none()
        updated = parse_time(data.get("updated_at"))
        if row is not None and row.source_updated_at and updated and updated < row.source_updated_at:
            return row
        if row is None:
            row = await insert_or_existing(
                self.db, PentrixPayment, PentrixPayment.pentrix_payment_id, pid,
                lambda: PentrixPayment(organization_id=organization_id, pentrix_payment_id=pid, pentrix_user_id=str(data.get("user_id") or ""), status=str(data.get("status") or "created")),
            )
        row.pentrix_user_id = str(data.get("user_id") or row.pentrix_user_id)
        row.candidate_name = data.get("candidate_name") or ""
        row.candidate_email = data.get("candidate_email") or ""
        row.provider = data.get("provider") or ""
        row.provider_order_id = data.get("provider_order_id")
        row.provider_payment_id = data.get("provider_payment_id")
        row.reference = data.get("reference")
        row.purpose = data.get("purpose") or ""
        row.status = str(data.get("status") or row.status)
        row.amount_paise = int(data.get("amount_paise") or 0)
        row.currency = data.get("currency") or "INR"
        row.invoice_number = data.get("invoice_number")
        row.receipt_number = data.get("receipt_number")
        row.provisioning_status = data.get("provisioning_status")
        row.created_at_source = parse_time(data.get("created_at"))
        row.paid_at = parse_time(data.get("paid_at"))
        row.failed_at = parse_time(data.get("failed_at"))
        row.refunded_at = parse_time(data.get("refunded_at"))
        row.source_updated_at = updated
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def sync(self, max_pages: int = 50) -> int:
        """Pull every payment Pentrix changed since the saved cursor. Safe to run any time and as often as wanted; this is also the
        retry for a synchronisation that failed."""
        org = await pentrix_organization_id(self.db)
        state = (await self.db.execute(select(PentrixSyncState).where(PentrixSyncState.key == PAYMENTS_CURSOR))).scalar_one_or_none()
        if state is None:
            state = PentrixSyncState(key=PAYMENTS_CURSOR, value="")
            self.db.add(state)
            await self.db.flush()
        cursor, count = state.value or None, 0
        try:
            for _ in range(max_pages):
                page = await self.client.payment_changes(cursor)
                for item in page["items"]:
                    await self.upsert(org, item)
                    count += 1
                cursor = page.get("next_cursor") or cursor
                state.value = cursor or ""
                if not page.get("has_more"):
                    break
            state.last_error = None
        except Exception as exc:  # noqa: BLE001 - recorded, and the next run starts from the saved cursor
            state.last_error = str(exc)[:500]
            state.last_run_at = datetime.now(timezone.utc)
            logger.warning("pentrix_payment_sync_failed", error=str(exc)[:200])
            await self.db.flush()
            raise
        state.last_run_at = datetime.now(timezone.utc)
        await self.db.flush()
        return count

    async def sync_state(self) -> dict:
        state = (await self.db.execute(select(PentrixSyncState).where(PentrixSyncState.key == PAYMENTS_CURSOR))).scalar_one_or_none()
        return {
            "configured": PentrixClient.configured(),
            "last_synced_at": state.last_run_at if state else None,
            "last_error": state.last_error if state else None,
        }

    # ------------------------------------------------------------------ the list

    async def get(self, organization_id: uuid.UUID, payment_id: uuid.UUID) -> PentrixPayment:
        row = await self.db.get(PentrixPayment, payment_id)
        if row is None or row.organization_id != organization_id:
            raise NotFoundError("Pentrix payment", payment_id)
        return row

    def _conditions(self, organization_id: uuid.UUID, f: PaymentFilters) -> list:
        P = PentrixPayment
        out: list[Any] = [P.organization_id == organization_id]
        if f.q:
            like = f"%{f.q.strip()}%"
            out.append(or_(P.candidate_name.ilike(like), P.candidate_email.ilike(like), P.reference.ilike(like), P.invoice_number.ilike(like), P.receipt_number.ilike(like)))
        if f.status:
            wanted: list[str] = []
            for group in f.status:
                wanted += [s for s, g in GROUP.items() if g == group]
            out.append(P.status.in_(wanted))
        if f.purpose:
            out.append(P.purpose == f.purpose)
        when = func.coalesce(P.paid_at, P.created_at_source)  # the date a payment is known by: when it was paid, otherwise when it was started
        if f.date_from:
            out.append(when >= f.date_from)
        if f.date_to:
            out.append(when < f.date_to)
        if f.candidate_pentrix_id:
            out.append(P.pentrix_user_id == f.candidate_pentrix_id)
        return out

    async def search(
        self, organization_id: uuid.UUID, filters: PaymentFilters, *, sort: str = "date", descending: bool = True, page: int = 1, page_size: int = 25
    ) -> tuple[list[tuple[PentrixPayment, PentrixCandidate | None]], int]:
        filters.validate()
        P = PentrixPayment
        orderings = {"date": func.coalesce(P.paid_at, P.created_at_source), "amount": P.amount_paise, "status": P.status}
        if sort not in orderings:
            raise ValidationError(f"Cannot sort by '{sort}'.")
        where = and_(*self._conditions(organization_id, filters))
        total = (await self.db.execute(select(func.count()).select_from(P).where(where))).scalar_one()
        column = orderings[sort]
        order = (column.desc() if descending else column.asc()).nulls_last()
        rows = (
            await self.db.execute(
                select(P, PentrixCandidate)
                .outerjoin(PentrixCandidate, PentrixCandidate.pentrix_user_id == P.pentrix_user_id)
                .where(where)
                .order_by(order, P.id)
                .offset((max(page, 1) - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [(p, c) for p, c in rows], total

    async def with_candidate(self, payment: PentrixPayment) -> tuple[PentrixPayment, PentrixCandidate | None]:
        candidate = (await self.db.execute(select(PentrixCandidate).where(PentrixCandidate.pentrix_user_id == payment.pentrix_user_id))).scalar_one_or_none()
        return payment, candidate

    @staticmethod
    def out(payment: PentrixPayment, candidate: PentrixCandidate | None) -> dict:
        group = GROUP.get(payment.status, "pending")
        return {
            "id": payment.id,
            "pentrix_payment_id": payment.pentrix_payment_id,
            "candidate_id": candidate.id if candidate else None,
            # The candidate's current details when ERPX has them (a rename shows at once), otherwise what the payment carried.
            "candidate_name": (candidate.full_name if candidate else None) or payment.candidate_name,
            "candidate_email": (candidate.email if candidate else None) or payment.candidate_email,
            "provider": payment.provider,
            # Pentrix records the payment provider, not the instrument (card, UPI...), so that is what "method" shows.
            "method": PROVIDER_LABEL.get(payment.provider, payment.provider.title() if payment.provider else "—"),
            "purpose": payment.purpose,
            "purpose_label": PURPOSE_LABEL.get(payment.purpose, payment.purpose.replace("_", " ").capitalize()),
            "amount_paise": payment.amount_paise,
            "currency": payment.currency,
            "status": group,
            "status_label": GROUP_LABEL[group],
            "pentrix_status": payment.status,
            "reference": payment.reference,
            "provider_order_id": payment.provider_order_id,
            "invoice_number": payment.invoice_number,
            "receipt_number": payment.receipt_number,
            "provisioning_status": payment.provisioning_status,
            "created_at": payment.created_at_source,
            "paid_at": payment.paid_at,
            "failed_at": payment.failed_at,
            "refunded_at": payment.refunded_at,
            # An invoice exists for a payment that was successfully made (it stays available if the payment was refunded later).
            "invoice_available": payment.status in PAID_EVER,
        }

    # ------------------------------------------------------------------ the figures on the overview and the dashboard

    async def summary(self, organization_id: uuid.UUID) -> dict:
        """Today's collections, what is pending and the latest transactions. Computed from the synchronised payments."""
        P = PentrixPayment
        start, end = day_bounds(today_ist())
        rows = (
            await self.db.execute(
                select(P).where(
                    P.organization_id == organization_id,
                    or_(and_(P.paid_at >= start, P.paid_at < end), and_(P.refunded_at >= start, P.refunded_at < end), P.status.in_(OPEN)),
                )
            )
        ).scalars().all()
        today = totals_for(list(rows), start, end)
        pending_total = sum(1 for p in rows if p.status in OPEN)
        latest = (
            await self.db.execute(
                select(P, PentrixCandidate)
                .outerjoin(PentrixCandidate, PentrixCandidate.pentrix_user_id == P.pentrix_user_id)
                .where(P.organization_id == organization_id)
                .order_by(func.coalesce(P.paid_at, P.created_at_source).desc().nulls_last(), P.id)
                .limit(6)
            )
        ).all()
        latest_paid = next((self.out(p, c) for p, c in latest if p.paid_at), None)
        state = await self.sync_state()
        return {
            "date": today_ist(),
            "collected_today_paise": today["collected_paise"],
            "successful_today": today["successful_count"],
            "refunded_today_paise": today["refunded_paise"],
            "pending_payments": pending_total,
            "latest_payment": latest_paid,
            "recent": [self.out(p, c) for p, c in latest],
            "sync": state,
        }

    # ------------------------------------------------------------------ daily summaries

    async def _rows_for_days(self, organization_id: uuid.UUID, first: date, last: date) -> list[PentrixPayment]:
        """Every payment with something that happened between those days (inclusive), by any of its times."""
        P = PentrixPayment
        start, _ = day_bounds(first)
        _, end = day_bounds(last)
        inside = lambda column: and_(column >= start, column < end)  # noqa: E731
        return list(
            (
                await self.db.execute(
                    select(P)
                    .where(P.organization_id == organization_id, or_(inside(P.paid_at), inside(P.failed_at), inside(P.refunded_at), and_(inside(P.created_at_source), P.status.in_(OPEN))))
                    .order_by(P.created_at_source, P.id)
                )
            ).scalars()
        )

    @staticmethod
    def _involved(rows: list[PentrixPayment], start: datetime, end: datetime) -> list[PentrixPayment]:
        return [
            p for p in rows
            if _inside(p.paid_at, start, end) or _inside(p.failed_at, start, end) or _inside(p.refunded_at, start, end)
            or (p.status in OPEN and _inside(p.created_at_source, start, end))
        ]

    @staticmethod
    def summary_out(row: PentrixDailySummary | None, day: date, live: dict | None = None) -> dict:
        """One day for the screen: the reconciled record when there is one, otherwise the live figures (labelled as not yet reconciled)."""
        if row is not None:
            return {
                "date": day, "status": row.status, "reconciled": True, "reconciled_at": row.reconciled_at,
                "successful_count": row.successful_count, "collected_paise": row.collected_paise,
                "pending_count": row.pending_count, "failed_count": row.failed_count,
                "refund_count": row.refund_count, "refunded_paise": row.refunded_paise, "partial_refund_count": row.partial_refund_count,
                "net_paise": row.collected_paise - row.refunded_paise, "mismatches": row.mismatches or [], "repaired_count": row.repaired_count,
                "attempts": row.attempts, "last_error": row.last_error,
            }
        t = live or {}
        return {
            "date": day, "status": "open" if day >= today_ist() else "unreconciled", "reconciled": False, "reconciled_at": None,
            "successful_count": t.get("successful_count", 0), "collected_paise": t.get("collected_paise", 0),
            "pending_count": t.get("pending_count", 0), "failed_count": t.get("failed_count", 0),
            "refund_count": t.get("refund_count", 0), "refunded_paise": t.get("refunded_paise", 0), "partial_refund_count": t.get("partial_refund_count", 0),
            "net_paise": t.get("collected_paise", 0) - t.get("refunded_paise", 0), "mismatches": [], "repaired_count": 0, "attempts": 0, "last_error": None,
        }

    async def days(self, organization_id: uuid.UUID, first: date, last: date) -> list[dict]:
        """One entry per calendar day, newest first: the reconciled summary where there is one, otherwise the live figures."""
        if last < first:
            raise ValidationError("The end date is before the start date.")
        if (last - first).days + 1 > MAX_DAYS:
            raise ValidationError(f"Ask for at most {MAX_DAYS} days at a time.")
        stored = {
            r.day: r
            for r in (
                await self.db.execute(select(PentrixDailySummary).where(PentrixDailySummary.organization_id == organization_id, PentrixDailySummary.day.between(first, last)))
            ).scalars()
        }
        rows = await self._rows_for_days(organization_id, first, last)
        out = []
        day = last
        while day >= first:
            if day in stored:
                out.append(self.summary_out(stored[day], day))
            else:
                start, end = day_bounds(day)
                out.append(self.summary_out(None, day, totals_for(self._involved(rows, start, end), start, end)))
            day -= timedelta(days=1)
        return out

    async def day_transactions(self, organization_id: uuid.UUID, day: date) -> list[tuple[PentrixPayment, PentrixCandidate | None]]:
        start, end = day_bounds(day)
        involved = self._involved(await self._rows_for_days(organization_id, day, day), start, end)
        out = []
        for p in involved:
            out.append(await self.with_candidate(p))
        return out

    # ------------------------------------------------------------------ reconciliation

    @staticmethod
    def _fingerprint(status: str, amount: int, invoice: str | None) -> tuple:
        return (status, int(amount), invoice or None)

    def _diff(self, mine: list[PentrixPayment], theirs: list[dict]) -> list[dict]:
        ours = {p.pentrix_payment_id: p for p in mine}
        pentrix = {t["id"]: t for t in theirs}
        found: list[dict] = []
        for pid, t in pentrix.items():
            p = ours.get(pid)
            if p is None:
                found.append({"kind": "missing_in_erpx", "payment_id": pid, "detail": f"Pentrix has a {t['status']} payment of {t['amount_paise']} paise that ERPX does not have."})
                continue
            if p.status != t["status"]:
                found.append({"kind": "status_differs", "payment_id": pid, "detail": f"Pentrix says {t['status']}, ERPX says {p.status}."})
            elif int(p.amount_paise) != int(t["amount_paise"]):
                found.append({"kind": "amount_differs", "payment_id": pid, "detail": f"Pentrix says {t['amount_paise']} paise, ERPX says {p.amount_paise}."})
            elif (p.invoice_number or None) != (t.get("invoice_number") or None):
                found.append({"kind": "invoice_differs", "payment_id": pid, "detail": f"Pentrix says invoice {t.get('invoice_number')}, ERPX says {p.invoice_number}."})
        for pid in ours.keys() - pentrix.keys():
            found.append({"kind": "extra_in_erpx", "payment_id": pid, "detail": "ERPX has a payment for this day that Pentrix does not list for it."})
        return found

    async def reconcile(self, organization_id: uuid.UUID, day: date) -> PentrixDailySummary:
        """Check one closed day against Pentrix, repair what differs, and record the outcome. Safe to run again for the same day: it
        rewrites that day's one summary, so nothing is counted twice."""
        row = (
            await self.db.execute(select(PentrixDailySummary).where(PentrixDailySummary.organization_id == organization_id, PentrixDailySummary.day == day))
        ).scalar_one_or_none()
        if row is None:
            row = PentrixDailySummary(organization_id=organization_id, day=day, status="error")
            self.db.add(row)
        row.attempts = (row.attempts or 0) + 1
        start, end = day_bounds(day)
        try:
            theirs = await self.client.payment_day(day.isoformat())
        except Exception as exc:  # noqa: BLE001 - recorded on the day, so the screen can say so and a person can retry
            row.status, row.last_error = "error", str(exc)[:500]
            await self.db.flush()
            logger.warning("pentrix_reconcile_failed", day=day.isoformat(), error=str(exc)[:200])
            return row

        mine = self._involved(await self._rows_for_days(organization_id, day, day), start, end)
        differences = self._diff(mine, theirs["transactions"])
        repaired = 0
        for d in differences:
            try:  # fetch that payment again from Pentrix: the usual cause is a message that never arrived
                await self.upsert(organization_id, await self.client.payment(d["payment_id"]))
                repaired += 1
            except Exception as exc:  # noqa: BLE001 - it stays listed as a difference
                logger.warning("pentrix_reconcile_repair_failed", payment=d["payment_id"], error=str(exc)[:200])
        if repaired:
            mine = self._involved(await self._rows_for_days(organization_id, day, day), start, end)
            differences = self._diff(mine, theirs["transactions"])

        figures = totals_for(mine, start, end)
        expected = {
            "successful_count": theirs["successful"]["count"], "collected_paise": theirs["successful"]["amount_paise"], "failed_count": theirs["failed"]["count"],
            "pending_count": theirs["pending"]["count"], "refund_count": theirs["refunds"]["count"], "refunded_paise": theirs["refunds"]["amount_paise"],
            "partial_refund_count": theirs["refunds"]["partial_count"],
        }
        for key, value in expected.items():
            if figures[key] != value:
                differences.append({"kind": "total_differs", "payment_id": None, "detail": f"{key.replace('_', ' ')}: Pentrix {value}, ERPX {figures[key]}."})

        for key, value in figures.items():
            setattr(row, key, value)
        row.pentrix_totals = expected
        row.mismatches = differences
        row.repaired_count = repaired
        row.status = "mismatch" if differences else "matched"
        row.last_error = None
        row.reconciled_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def reconcile_due(self, organization_id: uuid.UUID, today: date | None = None, lookback: int = 60) -> list[PentrixDailySummary]:
        """The nightly job: the two most recent closed days are always checked again (a webhook can arrive late), and so is any earlier
        day that was never reconciled or did not match."""
        today = today or today_ist()
        yesterday = today - timedelta(days=1)
        first_payment = (await self.db.execute(select(func.min(PentrixPayment.created_at_source)).where(PentrixPayment.organization_id == organization_id))).scalar_one_or_none()
        if first_payment is None:
            return []
        oldest = max(ist_day(first_payment), yesterday - timedelta(days=lookback))
        stored = {
            r.day: r.status
            for r in (
                await self.db.execute(select(PentrixDailySummary).where(PentrixDailySummary.organization_id == organization_id, PentrixDailySummary.day >= oldest))
            ).scalars()
        }
        wanted = {yesterday, yesterday - timedelta(days=1)}
        day = oldest
        while day <= yesterday:
            if stored.get(day) != "matched":
                wanted.add(day)
            day += timedelta(days=1)
        return [await self.reconcile(organization_id, d) for d in sorted(wanted) if d >= oldest]

    # ------------------------------------------------------------------ export

    def days_csv(self, days: list[dict]) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Date (IST)", "Status", "Successful payments", "Collected (INR)", "Refunds", "Refunded (INR)", "Partial refunds", "Net (INR)", "Pending", "Failed", "Differences"])
        for d in days:
            writer.writerow([
                d["date"].isoformat(), d["status"], d["successful_count"], f"{d['collected_paise'] / 100:.2f}", d["refund_count"], f"{d['refunded_paise'] / 100:.2f}",
                d["partial_refund_count"], f"{d['net_paise'] / 100:.2f}", d["pending_count"], d["failed_count"], len(d["mismatches"]),
            ])
        return buffer.getvalue()

    def transactions_csv(self, rows: list[tuple[PentrixPayment, PentrixCandidate | None]]) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Candidate", "Email", "Amount (INR)", "Status", "Paid at (IST)", "Method", "Transaction reference", "Invoice number", "Receipt number"])
        for payment, candidate in rows:
            o = self.out(payment, candidate)
            writer.writerow([
                _csv_cell(o["candidate_name"]), _csv_cell(o["candidate_email"]), f"{o['amount_paise'] / 100:.2f}", o["status_label"],
                o["paid_at"].astimezone(IST).strftime("%Y-%m-%d %H:%M") if o["paid_at"] else "", o["method"], _csv_cell(o["reference"] or ""),
                _csv_cell(o["invoice_number"] or ""), _csv_cell(o["receipt_number"] or ""),
            ])
        return buffer.getvalue()

    # ------------------------------------------------------------------ invoice

    @staticmethod
    def invoice_pdf(payment: PentrixPayment, candidate: PentrixCandidate | None) -> tuple[bytes, str]:
        """An invoice (or, when Pentrix issued only a receipt number, a receipt) for a payment that was made, using the numbers Pentrix
        gave it. ERPX never numbers invoices itself: the existing numbering stays Pentrix's."""
        if payment.status not in PAID_EVER:
            raise ValidationError("An invoice is available once the payment has succeeded.")
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas

        title = "INVOICE" if payment.invoice_number else "PAYMENT RECEIPT"
        number = payment.invoice_number or payment.receipt_number or payment.reference or str(payment.pentrix_payment_id)
        name = (candidate.full_name if candidate else None) or payment.candidate_name or "Candidate"
        email = (candidate.email if candidate else None) or payment.candidate_email
        paid = payment.paid_at.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST") if payment.paid_at else "—"
        amount = f"{payment.currency} {payment.amount_paise / 100:,.2f}"
        description = PURPOSE_LABEL.get(payment.purpose, payment.purpose.replace("_", " ").capitalize())

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        pdf.setTitle(f"{title.title()} {number}")
        width, height = A4
        left, right, y = 22 * mm, width - 22 * mm, height - 28 * mm
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(left, y, "Pentrix")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(left, y - 5 * mm, "by GIR Technologies")
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawRightString(right, y, title)
        pdf.setFont("Helvetica", 10)
        pdf.drawRightString(right, y - 6 * mm, f"No. {number}")
        y -= 22 * mm
        pdf.line(left, y, right, y)
        y -= 9 * mm
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(left, y, "Billed to")
        pdf.drawString(width / 2, y, "Payment")
        pdf.setFont("Helvetica", 10)
        for i, line in enumerate([name, email or ""]):
            pdf.drawString(left, y - (6 + 5 * i) * mm, line)
        details = [f"Date: {paid}", f"Method: {PROVIDER_LABEL.get(payment.provider, payment.provider.title())}", f"Reference: {payment.reference or '—'}"]
        for i, line in enumerate(details):
            pdf.drawString(width / 2, y - (6 + 5 * i) * mm, line)
        y -= 32 * mm
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(left, y, "Description")
        pdf.drawRightString(right, y, "Amount")
        pdf.line(left, y - 2 * mm, right, y - 2 * mm)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(left, y - 9 * mm, description)
        pdf.drawRightString(right, y - 9 * mm, amount)
        pdf.line(left, y - 13 * mm, right, y - 13 * mm)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(left, y - 21 * mm, "Total paid")
        pdf.drawRightString(right, y - 21 * mm, amount)
        if payment.status in ("refunded", "partially_refunded"):
            pdf.setFont("Helvetica", 9)
            pdf.drawString(left, y - 29 * mm, "This payment was later " + ("refunded." if payment.status == "refunded" else "partially refunded."))
        pdf.setFont("Helvetica", 8)
        pdf.drawString(left, 22 * mm, "Generated by ERPX from the payment record held in Pentrix. The amount shown is the amount paid; no tax breakdown is included.")
        pdf.showPage()
        pdf.save()
        return buffer.getvalue(), f"{number}.pdf"
