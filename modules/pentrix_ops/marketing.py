"""
Marketing email to Pentrix candidates, sent through Email Studio.

Nothing here builds, stores or sends mail by itself: the designs, wording, brand profiles and signatures are Email Studio's, and delivery
is ERPX's existing email service. This module decides *who* may be emailed and *when something may go out*:

* A candidate can be emailed only if they agreed to marketing email in Pentrix (an explicit opt-in, off by default), their address is
  verified, and they have not unsubscribed. That is checked when the recipients are chosen **and again at the moment each message is sent**.
* Every message carries a working unsubscribe link and List-Unsubscribe headers. An unsubscribe is honoured here at once and then passed
  to Pentrix, so the candidate's own Settings show it too.
* A send is a deliberate, confirmed act on a previewed set of people; it goes out at a limited rate, once per address per campaign (the
  database refuses a second), and not again to someone who received the same template recently.
* Booking confirmations, reminders and payment emails are different mail and never go through this.
"""
import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, RateLimitError, ValidationError
from app.core.logging_config import get_logger
from modules.email_studio.engine import MissingPlaceholders, draft_of, render_draft
from modules.email_studio.models import EmailBrandProfile, EmailSendRecord, EmailSignature, EmailStudioTemplate, EmailStudioVersion, SendStatus, TemplateStatus
from modules.email_studio.service import allowed_for_key
from modules.pentrix_ops.candidates import CandidateFilters, conditions
from modules.pentrix_ops.client import PentrixClient
from modules.pentrix_ops.models import (
    PentrixCandidate,
    PentrixMarketingCampaign,
    PentrixMarketingRecipient,
    PentrixMarketingSuppression,
    PentrixMarketingTemplate,
)
from packages.email.history import SendMeta, set_send_meta
from packages.email.registry import get_def, sample_values
from packages.email.service import email_service

logger = get_logger(__name__)

KEY = "pentrix_marketing"
MAX_RECIPIENTS = 5000  # most people one campaign can go to
SELECTION_LIMIT = 20000  # most candidates looked at when choosing
REPEAT_DAYS = 30  # someone who got this template within this many days is not sent it again
MAX_ATTEMPTS = 3
CLAIM_TIMEOUT = timedelta(minutes=10)  # a message claimed this long ago by a worker that has since gone is picked up again
CAMPAIGNS_PER_HOUR = 20
REASONS = ("no_email", "email_unverified", "not_opted_in", "unsubscribed", "duplicate_address", "already_received")
REASON_LABEL = {
    "no_email": "No email address",
    "email_unverified": "Email address not verified",
    "not_opted_in": "Has not agreed to marketing email",
    "unsubscribed": "Unsubscribed",
    "duplicate_address": "Same address as another selected candidate",
    "already_received": f"Already received this template in the last {REPEAT_DAYS} days",
}
ASSESSMENT_WORDS = {"not_started": "Not started", "in_progress": "In progress", "completed": "Completed"}


# ------------------------------------------------------------------ unsubscribe links


def _key() -> bytes:
    return settings.JWT_SECRET_KEY.encode("utf-8")


def sign_token(organization_id: uuid.UUID, pentrix_user_id: str, email: str) -> str:
    """The proof inside an unsubscribe link: who it is for, signed so it cannot be forged or aimed at someone else. It does not expire:
    an unsubscribe link in an old email must keep working."""
    payload = json.dumps({"o": str(organization_id), "u": pentrix_user_id, "e": email.lower()}, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    return f"{body}.{hmac.new(_key(), f'pentrix-unsubscribe.{body}'.encode(), hashlib.sha256).hexdigest()}"


def read_token(token: str) -> dict | None:
    body, _, signature = (token or "").partition(".")
    if not body or not signature:
        return None
    expected = hmac.new(_key(), f"pentrix-unsubscribe.{body}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return {"organization_id": uuid.UUID(data["o"]), "pentrix_user_id": str(data["u"]), "email": str(data["e"])}
    except (ValueError, KeyError, TypeError):
        return None


def page_url(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/pentrix-unsubscribe?token={token}"


def one_click_url(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/public/pentrix-marketing/unsubscribe?token={token}"


def mask(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:1]}{'*' * max(len(name) - 1, 1)}@{domain}"


def with_unsubscribe(html: str, text: str, url: str) -> tuple[str, str]:
    """Make sure the message shows the unsubscribe link, whether or not the template's author put one in."""
    if url not in html:
        block = (
            '<div style="max-width:600px;margin:16px auto;padding:0 16px;font:12px/1.5 Arial,sans-serif;color:#6b7280;text-align:center">'
            f'You are receiving this email because you chose to hear from Pentrix. <a href="{url}" style="color:#6b7280">Unsubscribe</a>.</div>'
        )
        index = html.lower().rfind("</body>")
        html = html[:index] + block + html[index:] if index != -1 else html + block
    if url not in text:
        text = f"{text}\n\n--\nYou are receiving this email because you chose to hear from Pentrix. Unsubscribe: {url}"
    return html, text


# ------------------------------------------------------------------ choosing people


@dataclass
class Resolution:
    eligible: list[PentrixCandidate] = field(default_factory=list)
    excluded: dict[str, int] = field(default_factory=dict)
    selected: int = 0

    @property
    def excluded_total(self) -> int:
        return sum(self.excluded.values())


def candidate_values(candidate: PentrixCandidate | None, campaign_name: str, unsubscribe_url: str) -> dict[str, object]:
    if candidate is None:
        return {**sample_values(get_def(KEY)), "campaign_name": campaign_name, "unsubscribe_url": unsubscribe_url}  # type: ignore[arg-type]
    name = (candidate.full_name or "").strip() or "there"
    qualification = "No result yet" if candidate.qualified is None else ("Qualified" if candidate.qualified else "Not qualified")
    return {
        "full_name": name, "first_name": name.split()[0], "email": candidate.email, "campaign_name": campaign_name,
        "assessment_status": ASSESSMENT_WORDS.get(candidate.assessment_state, candidate.assessment_state), "qualification_status": qualification,
        "portal_url": settings.PENTRIX_PORTAL_URL.rstrip("/") + "/portal", "unsubscribe_url": unsubscribe_url,
    }


class PentrixMarketingService:
    def __init__(self, db: AsyncSession, client: PentrixClient | None = None):
        self.db = db
        self.client = client or PentrixClient()

    # ------------------------------------------------------------------ templates made available for Pentrix marketing

    @staticmethod
    def window(row: PentrixMarketingTemplate, on: date) -> bool:
        return row.enabled and (row.available_from is None or row.available_from <= on) and (row.available_until is None or on <= row.available_until)

    @staticmethod
    def _needs_document(version: EmailStudioVersion | None) -> bool:
        """A template that needs a document made for each recipient (an offer letter) cannot be a bulk marketing email."""
        attachments = ((version.config if version else None) or {}).get("attachments")
        return any(isinstance(a, dict) and a.get("kind") == "recipient" and a.get("required") for a in (attachments if isinstance(attachments, list) else []))

    async def _template_and_version(self, organization_id: uuid.UUID, template_id: uuid.UUID) -> tuple[EmailStudioTemplate, EmailStudioVersion | None]:
        template = await self.db.get(EmailStudioTemplate, template_id)
        if template is None or template.organization_id != organization_id or template.deleted_at is not None:
            raise NotFoundError("Email template", template_id)
        version = await self.db.get(EmailStudioVersion, template.published_version_id) if template.published_version_id else None
        return template, version

    def _template_out(self, row: PentrixMarketingTemplate, template: EmailStudioTemplate, version: EmailStudioVersion | None, on: date) -> dict:
        published = template.status == TemplateStatus.PUBLISHED.value and version is not None
        problem = None
        if template.deleted_at is not None:
            problem = "The template was deleted in Email Studio."
        elif not published:
            problem = "Publish the template in Email Studio before it can be used."
        elif self._needs_document(version):
            problem = "This template needs a document made for each recipient, so it cannot be a marketing email."
        usable = problem is None and self.window(row, on)
        return {
            "id": row.id, "template_id": template.id, "name": template.name, "campaign_name": row.campaign_name, "category": template.category,
            "available_from": row.available_from, "available_until": row.available_until, "enabled": row.enabled,
            "published": published, "usable": usable, "problem": problem or (None if usable else "Outside its available dates." if row.enabled else "Switched off."),
            "subject": version.subject if version else "", "source_type": template.source_type,
            "last_updated": (version.published_at if version and version.published_at else template.updated_at),
        }

    async def templates(self, organization_id: uuid.UUID, *, on: date | None = None, usable_only: bool = False, category: str | None = None, q: str | None = None) -> list[dict]:
        """The templates made available for Pentrix marketing. With ``usable_only`` just those that can be sent on that date (default today)."""
        on = on or datetime.now(timezone.utc).date()
        query = (
            select(PentrixMarketingTemplate, EmailStudioTemplate)
            .join(EmailStudioTemplate, EmailStudioTemplate.id == PentrixMarketingTemplate.template_id)
            .where(PentrixMarketingTemplate.organization_id == organization_id, EmailStudioTemplate.deleted_at.is_(None))
            .order_by(PentrixMarketingTemplate.available_from.desc().nulls_last(), PentrixMarketingTemplate.campaign_name)
        )
        if category:
            query = query.where(EmailStudioTemplate.category == category)
        if q:
            like = f"%{q.strip()}%"
            query = query.where(or_(PentrixMarketingTemplate.campaign_name.ilike(like), EmailStudioTemplate.name.ilike(like)))
        out = []
        for row, template in (await self.db.execute(query)).all():
            version = await self.db.get(EmailStudioVersion, template.published_version_id) if template.published_version_id else None
            item = self._template_out(row, template, version, on)
            if not usable_only or item["usable"]:
                out.append(item)
        return out

    async def assignable(self, organization_id: uuid.UUID) -> list[dict]:
        """Published Email Studio templates not yet made available for Pentrix marketing."""
        taken = select(PentrixMarketingTemplate.template_id).where(PentrixMarketingTemplate.organization_id == organization_id)
        rows = (
            await self.db.execute(
                select(EmailStudioTemplate)
                .where(
                    EmailStudioTemplate.organization_id == organization_id, EmailStudioTemplate.deleted_at.is_(None),
                    EmailStudioTemplate.status == TemplateStatus.PUBLISHED.value, EmailStudioTemplate.id.notin_(taken),
                )
                .order_by(EmailStudioTemplate.category.desc(), EmailStudioTemplate.name)
            )
        ).scalars().all()
        out = []
        for template in rows:
            version = await self.db.get(EmailStudioVersion, template.published_version_id) if template.published_version_id else None
            if version is not None and not self._needs_document(version):
                out.append({"template_id": template.id, "name": template.name, "category": template.category, "subject": version.subject, "source_type": template.source_type})
        return out

    @staticmethod
    def _dates(available_from: date | None, available_until: date | None) -> None:
        if available_from and available_until and available_until < available_from:
            raise ValidationError("The last day it is available cannot be before the first.")

    async def assign(self, organization_id: uuid.UUID, user_id: uuid.UUID, template_id: uuid.UUID, campaign_name: str, available_from: date | None, available_until: date | None) -> dict:
        template, version = await self._template_and_version(organization_id, template_id)
        if template.status != TemplateStatus.PUBLISHED.value or version is None:
            raise ValidationError("Publish the template in Email Studio first; only a published template can be used.")
        if self._needs_document(version):
            raise ValidationError("This template needs a document made for each recipient, so it cannot be a marketing email.")
        self._dates(available_from, available_until)
        if (await self.db.execute(select(PentrixMarketingTemplate.id).where(PentrixMarketingTemplate.organization_id == organization_id, PentrixMarketingTemplate.template_id == template_id))).first():
            raise ConflictError("That template is already available for Pentrix marketing.")
        row = PentrixMarketingTemplate(
            organization_id=organization_id, template_id=template_id, campaign_name=campaign_name.strip(), available_from=available_from,
            available_until=available_until, created_by_user_id=user_id,
        )
        self.db.add(row)
        await self.db.flush()
        return self._template_out(row, template, version, datetime.now(timezone.utc).date())

    async def _assignment(self, organization_id: uuid.UUID, assignment_id: uuid.UUID) -> PentrixMarketingTemplate:
        row = await self.db.get(PentrixMarketingTemplate, assignment_id)
        if row is None or row.organization_id != organization_id:
            raise NotFoundError("Marketing template", assignment_id)
        return row

    async def update_assignment(self, organization_id: uuid.UUID, assignment_id: uuid.UUID, changes: dict) -> dict:
        row = await self._assignment(organization_id, assignment_id)
        for name in ("campaign_name", "available_from", "available_until", "enabled"):
            if name in changes:
                setattr(row, name, changes[name].strip() if name == "campaign_name" else changes[name])
        self._dates(row.available_from, row.available_until)
        await self.db.flush()
        template, version = await self._template_and_version(organization_id, row.template_id)
        return self._template_out(row, template, version, datetime.now(timezone.utc).date())

    async def remove_assignment(self, organization_id: uuid.UUID, assignment_id: uuid.UUID) -> None:
        await self.db.delete(await self._assignment(organization_id, assignment_id))
        await self.db.flush()

    async def usable_assignment(self, organization_id: uuid.UUID, assignment_id: uuid.UUID) -> tuple[PentrixMarketingTemplate, EmailStudioTemplate, EmailStudioVersion]:
        row = await self._assignment(organization_id, assignment_id)
        template, version = await self._template_and_version(organization_id, row.template_id)
        item = self._template_out(row, template, version, datetime.now(timezone.utc).date())
        if not item["usable"] or version is None:
            raise ValidationError(f"This template cannot be sent: {item['problem']}")
        return row, template, version

    async def options(self, organization_id: uuid.UUID) -> dict:
        brands = (await self.db.execute(select(EmailBrandProfile).where(EmailBrandProfile.organization_id == organization_id).order_by(EmailBrandProfile.name))).scalars().all()
        signatures = (await self.db.execute(select(EmailSignature).where(EmailSignature.organization_id == organization_id).order_by(EmailSignature.name))).scalars().all()
        return {
            "brands": [{"id": b.id, "name": b.name, "is_default": b.is_default} for b in brands],
            "signatures": [{"id": s.id, "name": s.name, "is_default": s.is_default} for s in signatures],
        }

    # ------------------------------------------------------------------ who would receive it

    async def _selected(self, organization_id: uuid.UUID, selection: dict) -> list[PentrixCandidate]:
        C = PentrixCandidate
        exclude = {uuid.UUID(str(i)) for i in selection.get("exclude_ids") or []}
        if selection.get("mode") == "ids":
            ids = list({uuid.UUID(str(i)) for i in selection.get("ids") or []})
            if not ids:
                raise ValidationError("Choose at least one candidate.")
            if len(ids) > SELECTION_LIMIT:
                raise ValidationError("That is too many candidates to choose by hand; use the filters instead.")
            query = select(C).where(C.organization_id == organization_id, C.id.in_(ids))
        elif selection.get("mode") == "filter":
            filters = CandidateFilters(**{k: v for k, v in (selection.get("filters") or {}).items() if k in CandidateFilters.__dataclass_fields__}).validate()
            query = select(C).where(and_(*conditions(organization_id, filters, datetime.now(timezone.utc))))
        else:
            raise ValidationError("Choose candidates one by one, or everyone matching the filters.")
        rows = list((await self.db.execute(query.order_by(C.registered_at, C.id).limit(SELECTION_LIMIT + 1))).scalars())
        if len(rows) > SELECTION_LIMIT:
            raise ValidationError("That matches too many candidates. Narrow the filters first.")
        return [r for r in rows if r.id not in exclude]

    async def _suppressed(self, organization_id: uuid.UUID, rows: list[PentrixCandidate]) -> tuple[set[str], set[str]]:
        emails = {r.email.lower() for r in rows if r.email}
        users = {r.pentrix_user_id for r in rows}
        found = (
            await self.db.execute(
                select(PentrixMarketingSuppression.email, PentrixMarketingSuppression.pentrix_user_id).where(
                    PentrixMarketingSuppression.organization_id == organization_id,
                    or_(PentrixMarketingSuppression.email.in_(emails or {""}), PentrixMarketingSuppression.pentrix_user_id.in_(users or {""})),
                )
            )
        ).all()
        return {e for e, _ in found}, {u for _, u in found if u}

    async def _recently_received(self, organization_id: uuid.UUID, template_id: uuid.UUID, emails: set[str]) -> set[str]:
        since = datetime.now(timezone.utc) - timedelta(days=REPEAT_DAYS)
        rows = (
            await self.db.execute(
                select(PentrixMarketingRecipient.email)
                .join(PentrixMarketingCampaign, PentrixMarketingCampaign.id == PentrixMarketingRecipient.campaign_id)
                .where(
                    PentrixMarketingCampaign.organization_id == organization_id, PentrixMarketingCampaign.template_id == template_id,
                    PentrixMarketingCampaign.created_at >= since, PentrixMarketingRecipient.status.in_(("queued", "sending", "sent", "delivered")),
                    PentrixMarketingRecipient.email.in_(emails or {""}),
                )
            )
        ).scalars()
        return set(rows)

    async def resolve(self, organization_id: uuid.UUID, selection: dict, template_id: uuid.UUID | None) -> Resolution:
        """Who of the chosen people may be emailed, and for everyone left out, why. The same rules are applied again when each is sent."""
        rows = await self._selected(organization_id, selection)
        suppressed_emails, suppressed_users = await self._suppressed(organization_id, rows)
        already = await self._recently_received(organization_id, template_id, {r.email.lower() for r in rows if r.email}) if template_id else set()
        result = Resolution(selected=len(rows), excluded={})
        seen: set[str] = set()

        def skip(reason: str) -> None:
            result.excluded[reason] = result.excluded.get(reason, 0) + 1

        for row in rows:
            email = (row.email or "").strip().lower()
            if not email or "@" not in email:
                skip("no_email")
            elif not row.email_verified:
                skip("email_unverified")
            elif not row.marketing_opt_in:
                skip("not_opted_in")
            elif email in suppressed_emails or row.pentrix_user_id in suppressed_users:
                skip("unsubscribed")
            elif email in seen:
                skip("duplicate_address")
            elif email in already:
                skip("already_received")
            else:
                seen.add(email)
                result.eligible.append(row)
        return result

    # ------------------------------------------------------------------ previews

    async def preview(
        self, organization_id: uuid.UUID, assignment_id: uuid.UUID, *, candidate_id: uuid.UUID | None = None,
        brand_profile_id: uuid.UUID | None = None, signature_id: uuid.UUID | None = None, require_usable: bool = False,
    ) -> dict:
        """The email as one candidate (or a sample) would receive it. Nothing is sent."""
        row = await self._assignment(organization_id, assignment_id)
        template, version = await self._template_and_version(organization_id, row.template_id)
        if version is None:
            raise ValidationError("Publish the template in Email Studio first.")
        if require_usable:
            await self.usable_assignment(organization_id, assignment_id)
        candidate = None
        if candidate_id:
            candidate = await self.db.get(PentrixCandidate, candidate_id)
            if candidate is None or candidate.organization_id != organization_id:
                raise NotFoundError("Pentrix candidate", candidate_id)
        brand = await self._own(EmailBrandProfile, organization_id, brand_profile_id)
        signature = await self._own(EmailSignature, organization_id, signature_id)
        draft = draft_of(version, template.source_type)
        if brand_profile_id:
            draft.brand_profile_id = brand_profile_id
        if signature_id:
            draft.signature_id = signature_id
        placeholder_url = page_url("preview")
        values = candidate_values(candidate, row.campaign_name, placeholder_url)
        try:
            rendered = await render_draft(self.db, organization_id, draft, values, allowed=allowed_for_key(get_def(KEY)), strict=False)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        html, text = with_unsubscribe(rendered.html, rendered.text, placeholder_url)
        effective_brand = brand or (await self.db.get(EmailBrandProfile, version.brand_profile_id) if version.brand_profile_id else None)
        effective_signature = signature or (await self.db.get(EmailSignature, version.signature_id) if version.signature_id else None)
        return {
            "assignment_id": row.id, "campaign_name": row.campaign_name, "template_name": template.name, "subject": rendered.subject, "html": html, "text": text,
            "brand": effective_brand.name if effective_brand else None, "brand_profile_id": effective_brand.id if effective_brand else None,
            "signature": effective_signature.name if effective_signature else None, "signature_id": effective_signature.id if effective_signature else None,
            "attachments": [{"name": a.filename, "size_bytes": len(a.content)} for a in rendered.attachments],
            "missing": rendered.missing, "warnings": rendered.warnings,
            "candidate": {"id": candidate.id, "name": candidate.full_name, "email": candidate.email} if candidate else None,
            "sample": candidate is None,
        }

    async def _own(self, model: type, organization_id: uuid.UUID, row_id: uuid.UUID | None):
        if row_id is None:
            return None
        found = await self.db.get(model, row_id)
        if found is None or found.organization_id != organization_id:
            raise ValidationError("That brand profile or signature was not found.")
        return found

    # ------------------------------------------------------------------ confirming a send

    async def create_campaign(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, assignment_id: uuid.UUID, selection: dict, *, expected_count: int,
        brand_profile_id: uuid.UUID | None, signature_id: uuid.UUID | None, idempotency_key: str,
    ) -> PentrixMarketingCampaign:
        """The explicit confirmation. The people are chosen again here, and if that is not the number the administrator was shown, nothing
        is sent: they are shown the new number first."""
        existing = (
            await self.db.execute(select(PentrixMarketingCampaign).where(PentrixMarketingCampaign.organization_id == organization_id, PentrixMarketingCampaign.idempotency_key == idempotency_key))
        ).scalar_one_or_none()
        if existing is not None:
            return existing  # the same confirmation sent twice (a double click, a retry)
        row, template, version = await self.usable_assignment(organization_id, assignment_id)
        await self._own(EmailBrandProfile, organization_id, brand_profile_id)
        await self._own(EmailSignature, organization_id, signature_id)
        recent = (
            await self.db.execute(
                select(func.count()).select_from(PentrixMarketingCampaign).where(
                    PentrixMarketingCampaign.created_by_user_id == user_id, PentrixMarketingCampaign.created_at >= datetime.now(timezone.utc) - timedelta(hours=1)
                )
            )
        ).scalar_one()
        if recent >= CAMPAIGNS_PER_HOUR:
            raise RateLimitError(f"You can start {CAMPAIGNS_PER_HOUR} marketing sends an hour. Try again later.")
        resolution = await self.resolve(organization_id, selection, template.id)
        count = len(resolution.eligible)
        if count == 0:
            raise ValidationError("Nobody in this selection can be emailed.")
        if count > MAX_RECIPIENTS:
            raise ValidationError(f"One send can go to at most {MAX_RECIPIENTS} people; this one is {count}. Narrow the selection.")
        if count != expected_count:
            raise ConflictError(f"The selection now has {count} recipients, not {expected_count}. Review it again before sending.")

        probe = await self.preview(organization_id, assignment_id, candidate_id=resolution.eligible[0].id, brand_profile_id=brand_profile_id, signature_id=signature_id)
        if probe["missing"]:
            raise ValidationError("The email uses values that are missing: " + ", ".join("{{" + n + "}}" for n in probe["missing"]))
        now = datetime.now(timezone.utc)
        campaign = PentrixMarketingCampaign(
            organization_id=organization_id, template_id=template.id, version_id=version.id, campaign_name=row.campaign_name, subject=(version.subject or probe["subject"])[:300],  # the template's own subject, not one person's resolved copy
            brand_profile_id=brand_profile_id, signature_id=signature_id, status="sending", recipient_count=count,
            excluded={k: v for k, v in resolution.excluded.items()}, selection={"mode": selection.get("mode"), "filters": selection.get("filters"), "chosen": resolution.selected},
            idempotency_key=idempotency_key, created_by_user_id=user_id, confirmed_at=now,
        )
        self.db.add(campaign)
        try:
            await self.db.flush()
        except IntegrityError as exc:  # two confirmations at once: the other one made the campaign
            raise ConflictError("This send was already confirmed.") from exc
        for candidate in resolution.eligible:
            self.db.add(PentrixMarketingRecipient(campaign_id=campaign.id, pentrix_user_id=candidate.pentrix_user_id, email=candidate.email.strip().lower(), name=candidate.full_name or ""))
        await self.db.flush()
        await self.db.refresh(campaign)
        return campaign

    async def cancel(self, organization_id: uuid.UUID, campaign_id: uuid.UUID) -> PentrixMarketingCampaign:
        campaign = await self.campaign(organization_id, campaign_id)
        if campaign.status != "sending":
            raise ConflictError("Only a send that is still going can be cancelled.")
        campaign.status, campaign.completed_at = "cancelled", datetime.now(timezone.utc)
        await self.db.execute(
            update(PentrixMarketingRecipient).where(PentrixMarketingRecipient.campaign_id == campaign.id, PentrixMarketingRecipient.status == "queued")
            .values(status="skipped", error="Cancelled before it was sent.")
        )
        await self.db.flush()
        return campaign

    # ------------------------------------------------------------------ reading campaigns

    async def campaign(self, organization_id: uuid.UUID, campaign_id: uuid.UUID) -> PentrixMarketingCampaign:
        row = await self.db.get(PentrixMarketingCampaign, campaign_id)
        if row is None or row.organization_id != organization_id:
            raise NotFoundError("Marketing campaign", campaign_id)
        return row

    async def counts(self, campaign_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
        out: dict[uuid.UUID, dict[str, int]] = {i: {s: 0 for s in ("queued", "sending", "sent", "delivered", "failed", "bounced", "skipped")} for i in campaign_ids}
        if campaign_ids:
            rows = await self.db.execute(
                select(PentrixMarketingRecipient.campaign_id, PentrixMarketingRecipient.status, func.count())
                .where(PentrixMarketingRecipient.campaign_id.in_(campaign_ids)).group_by(PentrixMarketingRecipient.campaign_id, PentrixMarketingRecipient.status)
            )
            for campaign_id, status, n in rows:
                out[campaign_id][status] = n
        return out

    async def campaigns(self, organization_id: uuid.UUID, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        where = PentrixMarketingCampaign.organization_id == organization_id
        total = (await self.db.execute(select(func.count()).select_from(PentrixMarketingCampaign).where(where))).scalar_one()
        rows = list(
            (await self.db.execute(select(PentrixMarketingCampaign).where(where).order_by(PentrixMarketingCampaign.confirmed_at.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size))).scalars()
        )
        counts = await self.counts([r.id for r in rows])
        return [self.campaign_out(r, counts[r.id]) for r in rows], total

    @staticmethod
    def campaign_out(row: PentrixMarketingCampaign, counts: dict[str, int]) -> dict:
        return {
            "id": row.id, "campaign_name": row.campaign_name, "subject": row.subject, "status": row.status, "recipient_count": row.recipient_count,
            "counts": counts, "excluded": {REASON_LABEL.get(k, k): v for k, v in (row.excluded or {}).items()}, "confirmed_at": row.confirmed_at,
            "completed_at": row.completed_at, "template_id": row.template_id,
        }

    async def recipients(self, organization_id: uuid.UUID, campaign_id: uuid.UUID, status: str | None, page: int, page_size: int) -> tuple[list[PentrixMarketingRecipient], int]:
        campaign = await self.campaign(organization_id, campaign_id)
        where = [PentrixMarketingRecipient.campaign_id == campaign.id]
        if status:
            where.append(PentrixMarketingRecipient.status == status)
        total = (await self.db.execute(select(func.count()).select_from(PentrixMarketingRecipient).where(*where))).scalar_one()
        rows = (
            await self.db.execute(select(PentrixMarketingRecipient).where(*where).order_by(PentrixMarketingRecipient.email).offset((max(page, 1) - 1) * page_size).limit(page_size))
        ).scalars().all()
        return list(rows), total

    # ------------------------------------------------------------------ sending (run every minute)

    async def claim(self, limit: int) -> list[uuid.UUID]:
        """Take up to ``limit`` waiting messages, so a second worker does not send them too. Messages claimed long ago by a worker that
        has gone are put back (or failed once they have been tried enough)."""
        now = datetime.now(timezone.utc)
        R, C = PentrixMarketingRecipient, PentrixMarketingCampaign
        stale = and_(R.status == "sending", R.claimed_at < now - CLAIM_TIMEOUT)
        await self.db.execute(update(R).where(stale, R.attempts >= MAX_ATTEMPTS).values(status="failed", error="Sending did not finish."))
        await self.db.execute(update(R).where(stale, R.attempts < MAX_ATTEMPTS).values(status="queued"))
        rows = (
            await self.db.execute(
                select(R).join(C, C.id == R.campaign_id).where(C.status == "sending", R.status == "queued")
                .order_by(R.created_at, R.id).limit(limit).with_for_update(skip_locked=True, of=R)
            )
        ).scalars().all()
        for row in rows:
            row.status, row.claimed_at, row.attempts = "sending", now, (row.attempts or 0) + 1
        await self.db.flush()
        return [r.id for r in rows]

    async def _ineligible(self, organization_id: uuid.UUID, candidate: PentrixCandidate | None, email: str) -> str | None:
        """The checks made again at the moment of sending: the person may have unsubscribed since the campaign was confirmed."""
        if candidate is None:
            return "The candidate is no longer on record."
        if (candidate.email or "").strip().lower() != email:
            return "Their email address has changed."
        if not candidate.email_verified:
            return REASON_LABEL["email_unverified"]
        if not candidate.marketing_opt_in:
            return REASON_LABEL["not_opted_in"]
        suppressed_emails, suppressed_users = await self._suppressed(organization_id, [candidate])
        if email in suppressed_emails or candidate.pentrix_user_id in suppressed_users:
            return REASON_LABEL["unsubscribed"]
        return None

    async def process(self, recipient_id: uuid.UUID) -> str:
        """Send one claimed message. Returns what happened to it: sent, failed, queued (to be tried again) or skipped."""
        recipient = await self.db.get(PentrixMarketingRecipient, recipient_id)
        if recipient is None or recipient.status != "sending":
            return "skipped"
        campaign = await self.db.get(PentrixMarketingCampaign, recipient.campaign_id)
        if campaign is None or campaign.status != "sending":
            recipient.status, recipient.error = "skipped", "The send was cancelled."
            return "skipped"
        organization_id = campaign.organization_id
        candidate = (
            await self.db.execute(select(PentrixCandidate).where(PentrixCandidate.organization_id == organization_id, PentrixCandidate.pentrix_user_id == recipient.pentrix_user_id))
        ).scalar_one_or_none()
        reason = await self._ineligible(organization_id, candidate, recipient.email)
        if reason:
            recipient.status, recipient.error = "skipped", reason
            return "skipped"
        template = await self.db.get(EmailStudioTemplate, campaign.template_id) if campaign.template_id else None
        version = await self.db.get(EmailStudioVersion, campaign.version_id) if campaign.version_id else None
        if template is None or version is None:
            recipient.status, recipient.error = "failed", "The template is no longer available."
            return "failed"

        token = sign_token(organization_id, recipient.pentrix_user_id, recipient.email)
        draft = draft_of(version, template.source_type)
        if campaign.brand_profile_id:
            draft.brand_profile_id = campaign.brand_profile_id
        if campaign.signature_id:
            draft.signature_id = campaign.signature_id
        try:
            rendered = await render_draft(
                self.db, organization_id, draft, candidate_values(candidate, campaign.campaign_name, page_url(token)), allowed=allowed_for_key(get_def(KEY)), strict=True,
            )
        except (MissingPlaceholders, ValueError) as exc:
            recipient.status, recipient.error = "failed", str(exc)[:500]
            return "failed"
        html, text = with_unsubscribe(rendered.html, rendered.text, page_url(token))

        key = f"pxm:{recipient.id}"
        done = (
            await self.db.execute(select(EmailSendRecord.id).where(EmailSendRecord.organization_id == organization_id, EmailSendRecord.idempotency_key == key, EmailSendRecord.status == SendStatus.SENT.value))
        ).first()
        if done:  # an earlier attempt did go out and was recorded; never send it a second time
            recipient.status, recipient.sent_at, recipient.error = "sent", datetime.now(timezone.utc), None
            return "sent"
        set_send_meta(
            SendMeta(
                organization_id=organization_id, key=KEY, module="pentrix", template_id=template.id, version_id=version.id, source=rendered.source,
                idempotency_key=key, sent_by_user_id=campaign.created_by_user_id, reply_to=rendered.reply_to, from_name=rendered.from_name,
                headers={"List-Unsubscribe": f"<{one_click_url(token)}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
            )
        )
        sent = await email_service.send(recipient.email, rendered.subject, text, html, rendered.attachments or None)
        if sent:
            recipient.status, recipient.sent_at, recipient.error = "sent", datetime.now(timezone.utc), None
            return "sent"
        recipient.error = "The mail server did not accept the message."
        if recipient.attempts >= MAX_ATTEMPTS:
            recipient.status = "failed"
            return "failed"
        recipient.status = "queued"  # tried again on a later run
        return "queued"

    async def finish(self) -> int:
        """Mark campaigns whose messages have all reached an end as completed."""
        R, C = PentrixMarketingRecipient, PentrixMarketingCampaign
        open_ = select(R.id).where(R.campaign_id == C.id, R.status.in_(("queued", "sending")))
        result = await self.db.execute(update(C).where(C.status == "sending", ~open_.exists()).values(status="completed", completed_at=datetime.now(timezone.utc)))
        await self.db.flush()
        return result.rowcount or 0

    # ------------------------------------------------------------------ unsubscribing

    async def unsubscribe(self, token: str) -> dict:
        """Someone used an unsubscribe link. It takes effect here immediately; Pentrix is then told (and again later if that fails)."""
        claims = read_token(token)
        if claims is None:
            raise ValidationError("This unsubscribe link is not valid.")
        org, user_id, email = claims["organization_id"], claims["pentrix_user_id"], claims["email"]
        row = (await self.db.execute(select(PentrixMarketingSuppression).where(PentrixMarketingSuppression.organization_id == org, PentrixMarketingSuppression.email == email))).scalar_one_or_none()
        if row is None:
            try:
                async with self.db.begin_nested():
                    row = PentrixMarketingSuppression(organization_id=org, email=email, pentrix_user_id=user_id, source="unsubscribe_link", pentrix_synced=False)
                    self.db.add(row)
                    await self.db.flush()
            except IntegrityError:  # clicked twice at once: the other click made it
                row = (await self.db.execute(select(PentrixMarketingSuppression).where(PentrixMarketingSuppression.organization_id == org, PentrixMarketingSuppression.email == email))).scalar_one()
        await self.db.execute(
            update(PentrixCandidate).where(PentrixCandidate.organization_id == org, PentrixCandidate.pentrix_user_id == user_id).values(marketing_opt_in=False)
        )
        await self.db.execute(
            update(PentrixMarketingRecipient).where(PentrixMarketingRecipient.pentrix_user_id == user_id, PentrixMarketingRecipient.status == "queued")
            .values(status="skipped", error=REASON_LABEL["unsubscribed"])
        )
        await self.tell_pentrix(row)
        return {"email": mask(email), "unsubscribed": True}

    def check_token(self, token: str) -> dict:
        claims = read_token(token)
        if claims is None:
            raise ValidationError("This unsubscribe link is not valid.")
        return {"email": mask(claims["email"])}

    async def tell_pentrix(self, row: PentrixMarketingSuppression) -> bool:
        if row.pentrix_synced or not row.pentrix_user_id or not PentrixClient.configured():
            return row.pentrix_synced
        try:
            await self.client.unsubscribe_candidate(row.pentrix_user_id, "unsubscribe_link", None)
        except Exception as exc:  # noqa: BLE001 - the unsubscribe stands here regardless; it is passed on again later
            logger.warning("pentrix_unsubscribe_not_passed_on", error=str(exc)[:200])
            return False
        row.pentrix_synced = True
        await self.db.flush()
        return True

    async def retry_unsynced(self, limit: int = 50) -> int:
        rows = (await self.db.execute(select(PentrixMarketingSuppression).where(PentrixMarketingSuppression.pentrix_synced.is_(False)).limit(limit))).scalars().all()
        return sum([1 for row in rows if await self.tell_pentrix(row)])


__all__ = ["PentrixMarketingService", "Resolution", "KEY", "sign_token", "read_token"]
