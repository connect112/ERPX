"""
Pentrix candidates in ERPX: the synchronised summaries, the Registrations and Assessments lists (filtered, sorted and paged by the
database, never in the browser), the Overview numbers, and opening one candidate.

Pentrix is the source of truth for everything here. ERPX keeps a summary of each candidate so lists and filters are fast; opening a
candidate asks Pentrix for the full record (every attempt, booking, payment) and refreshes the summary from the answer. Qualification,
payment and booking state are never worked out in ERPX: they arrive from Pentrix, which gets them from the same services the candidate's
own portal uses.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, not_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ServiceUnavailableError, ValidationError
from app.core.logging_config import get_logger
from modules.email_studio.models import EmailSendRecord
from modules.pentrix_ops.client import PentrixClient
from modules.pentrix_ops.mirror import insert_or_existing
from modules.pentrix_ops.models import ACTIVE_STATUSES, PentrixBooking, PentrixCandidate, PentrixSyncState
from modules.pentrix_ops.service import STATUS_LABEL, parse_time, pentrix_organization_id

logger = get_logger(__name__)

CANDIDATES_CURSOR = "candidates_cursor"
ASSESSMENT_FILTERS = {"not_started", "in_progress", "completed", "pending"}
QUALIFICATION_FILTERS = {"qualified", "not_qualified", "pending"}
BOOKING_FILTERS = {"scheduled", "not_scheduled", "completed", "cancelled", "no_show"}
PAYMENT_FILTERS = {"paid", "pending", "failed", "refunded", "none", "not_paid"}
SORTS = {
    "registered": PentrixCandidate.registered_at,
    "name": func.lower(PentrixCandidate.full_name),
    "activity": PentrixCandidate.last_activity_at,
    "assessed": PentrixCandidate.assessed_at,
    "technical": PentrixCandidate.technical_pct,
    "payment": PentrixCandidate.payment_status,
}


@dataclass
class CandidateFilters:
    """Every group narrows the list; several values inside one group widen it (qualified OR not qualified). Groups combine with AND,
    which is how "Qualified + Not paid + No booking" is asked."""

    q: str | None = None
    assessment: list[str] = field(default_factory=list)
    qualification: list[str] = field(default_factory=list)
    booking: list[str] = field(default_factory=list)
    payment: list[str] = field(default_factory=list)
    registered_from: datetime | None = None
    registered_to: datetime | None = None

    def validate(self) -> "CandidateFilters":
        for name, allowed in (("assessment", ASSESSMENT_FILTERS), ("qualification", QUALIFICATION_FILTERS), ("booking", BOOKING_FILTERS), ("payment", PAYMENT_FILTERS)):
            bad = [v for v in getattr(self, name) if v not in allowed]
            if bad:
                raise ValidationError(f"'{bad[0]}' is not a {name} filter.")
        return self


def _scheduled(now: datetime):
    return and_(PentrixCandidate.booking_status.in_(ACTIVE_STATUSES), PentrixCandidate.booking_end > now)


def conditions(organization_id: uuid.UUID, f: CandidateFilters, now: datetime) -> list:
    out: list[Any] = [PentrixCandidate.organization_id == organization_id]
    if f.q:
        like = f"%{f.q.strip()}%"
        out.append(or_(PentrixCandidate.full_name.ilike(like), PentrixCandidate.email.ilike(like), PentrixCandidate.phone.ilike(like)))
    if f.assessment:
        parts = {
            "not_started": PentrixCandidate.assessment_state == "not_started",
            "in_progress": PentrixCandidate.assessment_state == "in_progress",
            "completed": PentrixCandidate.assessment_state == "completed",
            "pending": PentrixCandidate.assessment_state != "completed",
        }
        out.append(or_(*[parts[v] for v in f.assessment]))
    if f.qualification:
        parts = {
            "qualified": PentrixCandidate.qualified.is_(True),
            "not_qualified": PentrixCandidate.qualified.is_(False),
            "pending": PentrixCandidate.qualified.is_(None),
        }
        out.append(or_(*[parts[v] for v in f.qualification]))
    if f.booking:
        parts = {
            "scheduled": _scheduled(now),
            "not_scheduled": not_(func.coalesce(_scheduled(now), False)),
            "completed": PentrixCandidate.booking_status == "completed",
            "cancelled": PentrixCandidate.booking_status == "cancelled",
            "no_show": PentrixCandidate.booking_status == "no_show",
        }
        out.append(or_(*[parts[v] for v in f.booking]))
    if f.payment:
        parts = {v: PentrixCandidate.payment_status == v for v in ("paid", "pending", "failed", "refunded", "none")}
        parts["not_paid"] = PentrixCandidate.payment_status != "paid"
        out.append(or_(*[parts[v] for v in f.payment]))
    if f.registered_from:
        out.append(PentrixCandidate.registered_at >= f.registered_from)
    if f.registered_to:
        out.append(PentrixCandidate.registered_at < f.registered_to)
    return out


class PentrixCandidateService:
    def __init__(self, db: AsyncSession, client: PentrixClient | None = None):
        self.db = db
        self.client = client or PentrixClient()

    # ------------------------------------------------------------------ the copy

    async def upsert(self, organization_id: uuid.UUID, data: dict) -> PentrixCandidate:
        """Write one Pentrix candidate summary into the copy. An older message never overwrites a newer state; the same one twice
        changes nothing."""
        pentrix_id = str(data.get("id") or "")
        if not pentrix_id:
            raise ValidationError("A candidate is required.")
        row = (await self.db.execute(select(PentrixCandidate).where(PentrixCandidate.pentrix_user_id == pentrix_id))).scalar_one_or_none()
        updated = parse_time(data.get("updated_at"))
        if row is not None and row.source_updated_at and updated and updated < row.source_updated_at:
            return row
        registered = parse_time(data.get("registered_at")) or datetime.now(timezone.utc)
        if row is None:
            row = await insert_or_existing(
                self.db, PentrixCandidate, PentrixCandidate.pentrix_user_id, pentrix_id,
                lambda: PentrixCandidate(organization_id=organization_id, pentrix_user_id=pentrix_id, registered_at=registered),
            )
        assessment = data.get("assessment") or {}
        booking = data.get("booking") or {}
        payment = data.get("payment") or {}
        name, email = data.get("full_name") or "", (data.get("email") or "").strip()
        if row.full_name != name or row.email != email:
            # The appointments carry a copy of who it is with; keep it in step when the candidate's details change.
            await self.db.execute(
                update(PentrixBooking).where(PentrixBooking.pentrix_user_id == pentrix_id).values(candidate_name=name, candidate_email=email)
            )
        row.full_name = name
        row.email = email
        row.phone = data.get("phone") or None
        row.email_verified = bool(data.get("email_verified"))
        row.registered_at = registered
        row.assessment_state = assessment.get("state") or "not_started"
        row.assessment_attempts = int(assessment.get("attempts") or 0)
        row.readiness_pct = assessment.get("readiness_commitment_pct")
        row.technical_pct = assessment.get("technical_pct")
        row.qualified = assessment.get("qualified")
        row.assessed_at = parse_time(assessment.get("assessed_at"))
        row.booking_pentrix_id = booking.get("id")
        row.booking_status = booking.get("status")
        row.booking_start = parse_time(booking.get("slot_start"))
        row.booking_end = parse_time(booking.get("slot_end"))
        row.payment_status = payment.get("status") or "none"
        row.paid_total_paise = int(payment.get("paid_total_paise") or 0)
        row.payment_currency = payment.get("currency") or "INR"
        row.last_paid_at = parse_time(payment.get("last_paid_at"))
        row.payment_count = int(payment.get("payment_count") or 0)
        row.enrolled = bool(data.get("enrolled"))
        row.last_activity_at = parse_time(data.get("last_activity_at"))
        row.source_updated_at = updated
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def sync(self, max_pages: int = 50) -> int:
        """Pull every candidate Pentrix changed since the saved cursor. Safe to run any time and as often as wanted."""
        org = await pentrix_organization_id(self.db)
        state = (await self.db.execute(select(PentrixSyncState).where(PentrixSyncState.key == CANDIDATES_CURSOR))).scalar_one_or_none()
        if state is None:
            state = PentrixSyncState(key=CANDIDATES_CURSOR, value="")
            self.db.add(state)
            await self.db.flush()
        cursor, count = state.value or None, 0
        try:
            for _ in range(max_pages):
                page = await self.client.candidate_changes(cursor)
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
            logger.warning("pentrix_candidate_sync_failed", error=str(exc)[:200])
            await self.db.flush()
            raise
        state.last_run_at = datetime.now(timezone.utc)
        await self.db.flush()
        return count

    # ------------------------------------------------------------------ the lists

    async def get(self, organization_id: uuid.UUID, candidate_id: uuid.UUID) -> PentrixCandidate:
        row = await self.db.get(PentrixCandidate, candidate_id)
        if row is None or row.organization_id != organization_id:
            raise NotFoundError("Pentrix candidate", candidate_id)
        return row

    async def search(
        self, organization_id: uuid.UUID, filters: CandidateFilters, *, sort: str = "registered", descending: bool = True, page: int = 1, page_size: int = 25
    ) -> tuple[list[PentrixCandidate], int]:
        filters.validate()
        if sort not in SORTS:
            raise ValidationError(f"Cannot sort by '{sort}'.")
        now = datetime.now(timezone.utc)
        where = and_(*conditions(organization_id, filters, now))
        total = (await self.db.execute(select(func.count()).select_from(PentrixCandidate).where(where))).scalar_one()
        column = SORTS[sort]
        order = (column.desc() if descending else column.asc()).nulls_last()
        rows = (
            await self.db.execute(
                select(PentrixCandidate).where(where).order_by(order, PentrixCandidate.id).offset((max(page, 1) - 1) * page_size).limit(page_size)
            )
        ).scalars().all()
        return list(rows), total

    # ------------------------------------------------------------------ the overview

    async def overview(self, organization_id: uuid.UUID) -> dict:
        now = datetime.now(timezone.utc)
        zone = ZoneInfo(settings.PENTRIX_TIMEZONE)
        midnight = datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0)
        today_start, today_end = midnight.astimezone(timezone.utc), (midnight + timedelta(days=1)).astimezone(timezone.utc)
        C = PentrixCandidate

        def count_where(*cond):
            return func.count().filter(and_(*cond)) if cond else func.count()

        row = (
            await self.db.execute(
                select(
                    func.count(),
                    count_where(C.assessment_state == "completed"),
                    count_where(C.assessment_state == "in_progress"),
                    count_where(C.qualified.is_(True)),
                    count_where(C.qualified.is_(False)),
                    count_where(C.payment_status == "paid"),
                    count_where(C.payment_status == "pending"),
                    count_where(C.payment_status == "failed"),
                    count_where(C.payment_status == "refunded"),
                    count_where(C.registered_at >= now - timedelta(days=7)),
                    count_where(C.registered_at >= today_start),
                    count_where(C.booking_status.isnot(None), C.booking_status != "cancelled"),
                ).where(C.organization_id == organization_id)
            )
        ).one()
        total, completed, in_progress, qualified, not_qualified, paid, pending, failed, refunded, week, today, ever_booked = row

        B = PentrixBooking
        bookings = (
            await self.db.execute(
                select(
                    count_where(B.slot_end >= now, B.status.in_(ACTIVE_STATUSES)),
                    count_where(B.slot_start >= today_start, B.slot_start < today_end, B.status.in_(ACTIVE_STATUSES)),
                ).where(B.organization_id == organization_id)
            )
        ).one()
        states = {
            s.key: s
            for s in (await self.db.execute(select(PentrixSyncState).where(PentrixSyncState.key.in_([CANDIDATES_CURSOR, "bookings_cursor"])))).scalars()
        }
        candidate_state = states.get(CANDIDATES_CURSOR)
        recent = (await self.db.execute(select(C).where(C.organization_id == organization_id).order_by(C.registered_at.desc()).limit(5))).scalars().all()
        return {
            "configured": PentrixClient.configured(),
            "last_synced_at": candidate_state.last_run_at if candidate_state else None,
            "last_sync_error": (candidate_state.last_error if candidate_state else None),
            "totals": {
                "registered": total, "registered_today": today, "registered_last_7_days": week,
                "assessments_completed": completed, "assessments_in_progress": in_progress,
                "qualified": qualified, "not_qualified": not_qualified,
                "paid": paid, "payment_pending": pending,
            },
            "bookings": {"upcoming": bookings[0], "today": bookings[1]},
            "funnel": [
                {"key": "registered", "label": "Registered", "count": total},
                {"key": "assessed", "label": "Assessment completed", "count": completed},
                {"key": "qualified", "label": "Qualified", "count": qualified},
                {"key": "booked", "label": "Booked an appointment", "count": ever_booked},
                {"key": "paid", "label": "Paid", "count": paid},
            ],
            "payment_status": {"paid": paid, "pending": pending, "failed": failed, "refunded": refunded, "none": total - paid - pending - failed - refunded},
            "recent_registrations": [self.out(r, now) for r in recent],
        }

    # ------------------------------------------------------------------ opening one candidate

    async def detail(self, organization_id: uuid.UUID, candidate_id: uuid.UUID) -> dict:
        """The summary, plus Pentrix's full record when it can be reached (and the summary refreshed from it), plus the emails ERPX has
        sent to this address. When Pentrix cannot be reached the page still shows what ERPX holds, and says so."""
        row = await self.get(organization_id, candidate_id)
        profile: dict | None = None
        error: str | None = None
        try:
            profile = await self.client.candidate(row.pentrix_user_id)
            row = await self.upsert(organization_id, profile["summary"])
        except (ServiceUnavailableError, NotFoundError) as exc:
            error = str(exc)
        return {
            "candidate": self.out(row),
            "live": profile is not None,
            "error": error,
            "profile": profile,
            "emails": await self.email_history(organization_id, row.email),
        }

    async def assessment_detail(self, organization_id: uuid.UUID, candidate_id: uuid.UUID) -> dict:
        row = await self.get(organization_id, candidate_id)
        assessment: dict | None = None
        error: str | None = None
        try:
            answer = await self.client.candidate_assessment(row.pentrix_user_id)
            assessment = answer["assessment"]
            row = await self.upsert(organization_id, answer["summary"])
        except (ServiceUnavailableError, NotFoundError) as exc:
            error = str(exc)
        return {"candidate": self.out(row), "live": assessment is not None, "error": error, "assessment": assessment}

    async def email_history(self, organization_id: uuid.UUID, email: str, limit: int = 50) -> list[dict]:
        if not email:
            return []
        rows = (
            await self.db.execute(
                select(EmailSendRecord)
                .where(EmailSendRecord.organization_id == organization_id, func.lower(EmailSendRecord.recipient) == email.lower(), EmailSendRecord.is_test.is_(False))
                .order_by(EmailSendRecord.created_at.desc())
                .limit(limit)
            )
        ).scalars()
        return [
            {"id": r.id, "subject": r.subject, "status": r.status, "template_key": r.key, "module": r.module, "error": r.error, "sent_at": r.created_at}
            for r in rows
        ]

    async def update(self, organization_id: uuid.UUID, candidate_id: uuid.UUID, changes: dict, actor: uuid.UUID) -> PentrixCandidate:
        """Name and phone, changed in Pentrix (which owns them and keeps the record of who changed what); the answer is written back."""
        row = await self.get(organization_id, candidate_id)
        summary = await self.client.update_candidate(row.pentrix_user_id, changes, str(actor))
        return await self.upsert(organization_id, summary)

    # ------------------------------------------------------------------ shape

    @staticmethod
    def out(row: PentrixCandidate, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        scheduled = bool(row.booking_status in ACTIVE_STATUSES and row.booking_end and row.booking_end > now)
        return {
            "id": row.id,
            "pentrix_user_id": row.pentrix_user_id,
            "full_name": row.full_name,
            "email": row.email,
            "phone": row.phone,
            "email_verified": row.email_verified,
            "registered_at": row.registered_at,
            "assessment": {
                "state": row.assessment_state,
                "attempts": row.assessment_attempts,
                "readiness_commitment_pct": row.readiness_pct,
                "technical_pct": row.technical_pct,
                "qualified": row.qualified,
                "assessed_at": row.assessed_at,
            },
            "booking": None
            if row.booking_status is None
            else {
                "status": row.booking_status,
                "status_label": STATUS_LABEL.get(row.booking_status, row.booking_status),
                "slot_start": row.booking_start,
                "slot_end": row.booking_end,
                "scheduled": scheduled,
            },
            "payment": {
                "status": row.payment_status,
                "paid_total_paise": row.paid_total_paise,
                "currency": row.payment_currency,
                "last_paid_at": row.last_paid_at,
                "payment_count": row.payment_count,
            },
            "enrolled": row.enrolled,
            "last_activity_at": row.last_activity_at,
        }

