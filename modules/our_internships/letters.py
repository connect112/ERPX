"""
The offer letter generator: saved settings and images, the checks before generating, generating each student's letter, approving,
and releasing (emailing) the approved ones.

Generating and releasing are separate steps on purpose: a letter is never emailed just because it was made.
"""

import hashlib
import io
import json
import re
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.exceptions import NotFoundError, ServiceUnavailableError, ValidationError
from modules.institutions.models import Institution, InstitutionStudent
from modules.our_internships.letter_config import (
    ASSET_KINDS,
    ASSET_LABELS,
    LetterConfig,
    code_defaults,
    config_hash,
    deep_merge,
    difference,
    effective,
    fill,
    program_problems,
    unprintable,
)
from modules.our_internships.letter_models import (
    DeliveryStatus,
    LetterStatus,
    OfferLetter,
    OfferLetterAsset,
    OfferLetterDelivery,
    OfferLetterEvent,
    OfferLetterSetting,
)
from modules.our_internships.letter_pdf import Asset, AssetError, StudentFacts, build_letter_pdf, letter_values, validate_asset
from modules.our_internships.models import InternshipSelection, OfferStatus, OurInternship, OurInternshipStatus
from packages.email.service import EmailAttachment, email_service

SAMPLE_FACTS = StudentFacts("Asha Rao", "Sri Venkateswara College", "Tirupati, Andhra Pradesh", "asha.rao@example.com")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_BATCH = 1000
STUCK_AFTER = timedelta(minutes=15)  # a letter still waiting after this long lost its background task


def letter_date_text(config: LetterConfig, when: datetime | None = None) -> str:
    day = config.content.letter_date or (when or datetime.now(timezone.utc)).date()
    return f"{day.day} {day.strftime('%B %Y')}"


def registration_id(details: dict[str, Any] | None) -> str:
    """The student's registration or roll number from whatever columns their list had, when there is one."""
    for key, value in (details or {}).items():
        name = str(key).lower()
        if ("regist" in name or "roll" in name or name in ("reg no", "reg. no", "regno", "usn", "enrollment", "enrolment")) and value:
            return " ".join(str(value).split())[:60]
    return ""


def facts_of(student: InstitutionStudent, institution: Institution) -> StudentFacts:
    return StudentFacts(
        name=" ".join(student.name.split()),
        institution=" ".join(institution.name.split()),
        location=" ".join((institution.location or "").split()),
        email=(student.email or "").strip(),
        registration_id=registration_id(student.details),
    )


def student_issues(facts: StudentFacts) -> list[str]:
    """What is missing or cannot be printed for this student. Nothing is ever invented to fill a gap."""
    issues: list[str] = []
    for label, value in (("student name", facts.name), ("institution name", facts.institution), ("institution location", facts.location)):
        if not value.strip():
            issues.append(f"The {label} is missing.")
        elif unprintable(value):
            issues.append(f"The {label} has characters the letter font cannot print: {' '.join(unprintable(value))}")
    if not facts.email.strip():
        issues.append("The student's email address is missing.")
    elif not _EMAIL.match(facts.email.strip()):
        issues.append("The student's email address is not valid.")
    return issues


def letter_filename(name: str, internship_id: uuid.UUID, version: int) -> str:
    """OfferLetter_StudentName_InternshipID.pdf with anything unsafe taken out of the name."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    safe = re.sub(r"[^A-Za-z0-9]+", "", ascii_name.title().replace(" ", "")) or "Student"
    suffix = f"_v{version}" if version > 1 else ""
    return f"OfferLetter_{safe[:60]}_{internship_id.hex[:8].upper()}{suffix}.pdf"


def student_hash(settings_hash: str, facts: StudentFacts, reference: str) -> str:
    payload = json.dumps([settings_hash, facts.__dict__, reference], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class Loaded:
    config: LetterConfig
    default_config: LetterConfig
    override: dict[str, Any]
    assets: dict[str, Asset]
    asset_info: dict[str, dict[str, Any]]
    approved_hash: str | None
    approved_at: datetime | None
    settings_hash: str


class LetterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ settings

    async def _setting(self, organization_id: uuid.UUID, internship_id: uuid.UUID | None) -> OfferLetterSetting | None:
        query = select(OfferLetterSetting).where(OfferLetterSetting.organization_id == organization_id)
        query = query.where(OfferLetterSetting.internship_id.is_(None) if internship_id is None else OfferLetterSetting.internship_id == internship_id)
        return (await self.db.execute(query)).scalar_one_or_none()

    async def load(self, internship: OurInternship) -> Loaded:
        org_row = await self._setting(internship.organization_id, None)
        own_row = await self._setting(internship.organization_id, internship.id)
        default_config = effective(org_row.config if org_row else None, None)
        config = effective(org_row.config if org_row else None, own_row.config if own_row else None)
        rows = (
            await self.db.execute(
                select(OfferLetterAsset)
                .options(undefer(OfferLetterAsset.data))
                .where(
                    OfferLetterAsset.organization_id == internship.organization_id,
                    (OfferLetterAsset.internship_id.is_(None)) | (OfferLetterAsset.internship_id == internship.id),
                )
            )
        ).scalars().all()
        chosen: dict[str, OfferLetterAsset] = {}
        for row in rows:  # this internship's own image wins over the organisation's
            if row.kind not in chosen or row.internship_id is not None:
                chosen[row.kind] = row
        assets = {k: Asset(k, r.content_type, r.data) for k, r in chosen.items()}
        info = {
            k: {
                "kind": k,
                "label": ASSET_LABELS[k],
                "source": "internship" if r.internship_id else "defaults",
                "filename": r.filename,
                "content_type": r.content_type,
                "size_bytes": r.size_bytes,
                "updated_at": r.updated_at,
            }
            for k, r in chosen.items()
        }
        hashes = {k: r.sha256 for k, r in chosen.items()}
        # the approval lives with the internship's own row when it has one, otherwise with the organisation's
        holder = own_row if own_row and own_row.approved_hash else org_row
        approved_hash = holder.approved_hash if holder else None
        return Loaded(
            config=config,
            default_config=default_config,
            override=own_row.config if own_row else {},
            assets=assets,
            asset_info=info,
            approved_hash=approved_hash,
            approved_at=holder.approved_at if holder else None,
            settings_hash=config_hash(config, hashes),
        )

    async def save_config(self, internship: OurInternship, config: LetterConfig, scope: str, user_id: uuid.UUID) -> None:
        full = config.model_dump(mode="json")
        if scope == "defaults":
            row = await self._setting(internship.organization_id, None)
            if row is None:
                row = OfferLetterSetting(organization_id=internship.organization_id, internship_id=None, config={})
                self.db.add(row)
            row.config = difference(code_defaults(), full)
            row.updated_by_user_id = user_id
            await self.log(internship, user_id, "defaults_saved", "Saved the organisation's offer letter defaults")
        else:
            org_row = await self._setting(internship.organization_id, None)
            base = deep_merge(code_defaults(), org_row.config if org_row else {})
            row = await self._setting(internship.organization_id, internship.id)
            if row is None:
                row = OfferLetterSetting(organization_id=internship.organization_id, internship_id=internship.id, config={})
                self.db.add(row)
            row.config = difference(base, full)
            row.updated_by_user_id = user_id
            await self.log(internship, user_id, "config_saved", "Saved this internship's offer letter settings")
        await self.db.flush()

    async def clear_override(self, internship: OurInternship, user_id: uuid.UUID) -> None:
        row = await self._setting(internship.organization_id, internship.id)
        if row is not None:
            row.config = {}
            await self.log(internship, user_id, "config_reset", "Went back to the organisation's defaults")
            await self.db.flush()

    async def _asset_row(self, internship: OurInternship, kind: str, scope: str) -> OfferLetterAsset | None:
        query = select(OfferLetterAsset).where(OfferLetterAsset.organization_id == internship.organization_id, OfferLetterAsset.kind == kind)
        query = query.where(OfferLetterAsset.internship_id.is_(None) if scope == "defaults" else OfferLetterAsset.internship_id == internship.id)
        return (await self.db.execute(query)).scalar_one_or_none()

    async def put_asset(self, internship: OurInternship, kind: str, scope: str, filename: str, data: bytes, user_id: uuid.UUID) -> None:
        if kind not in ASSET_KINDS:
            raise ValidationError("Unknown image type.")
        try:
            content_type = validate_asset(kind, data)
        except AssetError as exc:
            raise ValidationError(str(exc)) from exc
        row = await self._asset_row(internship, kind, scope)
        if row is None:
            row = OfferLetterAsset(organization_id=internship.organization_id, internship_id=None if scope == "defaults" else internship.id, kind=kind)
            self.db.add(row)
        row.filename = " ".join(filename.split())[:255] or kind
        row.content_type = content_type
        row.size_bytes = len(data)
        row.sha256 = hashlib.sha256(data).hexdigest()
        row.data = data
        row.uploaded_by_user_id = user_id
        await self.log(internship, user_id, f"{kind}_uploaded", f"{ASSET_LABELS[kind]} uploaded ({'for all internships' if scope == 'defaults' else 'for this internship'})")
        await self.db.flush()

    async def remove_asset(self, internship: OurInternship, kind: str, scope: str, user_id: uuid.UUID) -> None:
        row = await self._asset_row(internship, kind, scope)
        if row is None:
            raise NotFoundError("Image", kind)
        await self.db.delete(row)
        await self.log(internship, user_id, f"{kind}_removed", f"{ASSET_LABELS[kind]} removed")
        await self.db.flush()

    async def asset_bytes(self, internship: OurInternship, kind: str) -> tuple[bytes, str]:
        loaded = await self.load(internship)
        asset = loaded.assets.get(kind)
        if asset is None:
            raise NotFoundError("Image", kind)
        return asset.data, asset.content_type

    # ------------------------------------------------------------------ design approval

    def design_state(self, loaded: Loaded) -> str:
        if not loaded.approved_hash:
            return "not_approved"
        return "approved" if loaded.approved_hash == loaded.settings_hash else "changed"

    def problems(self, internship: OurInternship, loaded: Loaded) -> list[str]:
        return program_problems(loaded.config, internship.title)

    async def approve_design(self, internship: OurInternship, user_id: uuid.UUID) -> None:
        loaded = await self.load(internship)
        problems = self.problems(internship, loaded)
        if problems:
            raise ValidationError("Finish the settings first: " + " ".join(problems))
        row = await self._setting(internship.organization_id, internship.id)
        if row is None:
            row = OfferLetterSetting(organization_id=internship.organization_id, internship_id=internship.id, config={})
            self.db.add(row)
        row.approved_hash = loaded.settings_hash
        row.approved_at = datetime.now(timezone.utc)
        row.approved_by_user_id = user_id
        await self.log(internship, user_id, "design_approved", "Approved the offer letter design")
        await self.db.flush()

    # ------------------------------------------------------------------ the selected students

    async def selected(self, internship: OurInternship, student_ids: list[uuid.UUID] | None = None):
        query = (
            select(InternshipSelection, InstitutionStudent, Institution)
            .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
            .join(Institution, Institution.id == InstitutionStudent.institution_id)
            .where(InternshipSelection.internship_id == internship.id)
            .order_by(func.lower(InstitutionStudent.name), InstitutionStudent.id)
        )
        if student_ids is not None:
            query = query.where(InternshipSelection.student_id.in_(student_ids))
        return list((await self.db.execute(query)).all())

    async def current_letters(self, internship: OurInternship) -> dict[uuid.UUID, OfferLetter]:
        rows = (
            await self.db.execute(select(OfferLetter).where(OfferLetter.internship_id == internship.id, OfferLetter.is_current.is_(True)))
        ).scalars().all()
        return {r.selection_id: r for r in rows if r.selection_id is not None}

    async def rows(self, internship: OurInternship) -> list[dict[str, Any]]:
        """Every selected student with their checks and their current letter, for the dashboard."""
        loaded = await self.load(internship)
        letters = await self.current_letters(internship)
        out: list[dict[str, Any]] = []
        for selection, student, institution in await self.selected(internship):
            facts = facts_of(student, institution)
            issues = student_issues(facts)
            letter = letters.get(selection.id)
            reference = (letter.reference if letter else selection.offer_reference) or ""
            stale = bool(
                letter
                and letter.status in (LetterStatus.READY.value, LetterStatus.APPROVED.value, LetterStatus.RELEASED.value)
                and letter.data_hash != student_hash(loaded.settings_hash, facts, reference)
            )
            out.append(
                {
                    "student_id": student.id,
                    "selection_id": selection.id,
                    "name": facts.name,
                    "email": facts.email,
                    "institution": facts.institution,
                    "location": facts.location,
                    "issues": issues,
                    "letter": letter,
                    "outdated": stale,
                }
            )
        return out

    # ------------------------------------------------------------------ audit

    async def log(self, internship: OurInternship, user_id: uuid.UUID | None, action: str, detail: str | None = None, letter_id: uuid.UUID | None = None) -> None:
        self.db.add(
            OfferLetterEvent(organization_id=internship.organization_id, internship_id=internship.id, letter_id=letter_id, actor_user_id=user_id, action=action, detail=(detail or "")[:2000] or None)
        )

    async def events(self, internship: OurInternship, limit: int = 100) -> list[OfferLetterEvent]:
        return list(
            (
                await self.db.execute(
                    select(OfferLetterEvent).where(OfferLetterEvent.internship_id == internship.id).order_by(OfferLetterEvent.created_at.desc(), OfferLetterEvent.id).limit(limit)
                )
            ).scalars().all()
        )

    # ------------------------------------------------------------------ references

    async def _references(self, internship: OurInternship) -> tuple[set[str], int]:
        rows = (await self.db.execute(select(InternshipSelection.offer_reference).where(InternshipSelection.internship_id == internship.id))).scalars().all()
        taken = {r for r in rows if r}
        return taken, len(taken)

    # ------------------------------------------------------------------ generating

    async def prepare(
        self, internship: OurInternship, user_id: uuid.UUID, student_ids: list[uuid.UUID] | None, regenerate: bool
    ) -> dict[str, Any]:
        """Decide who gets a (new) letter and create their rows as pending. Nothing is rendered here.

        The internship row is locked first, so two requests at once cannot hand out the same reference twice or make two
        letters for one student.
        """
        await self.db.execute(select(OurInternship.id).where(OurInternship.id == internship.id).with_for_update())
        loaded = await self.load(internship)
        problems = self.problems(internship, loaded)
        if problems:
            raise ValidationError("Finish the settings before generating: " + " ".join(problems))
        state = self.design_state(loaded)
        if state != "approved":
            raise ValidationError(
                "Approve the letter design first." if state == "not_approved" else "The settings changed after the design was approved. Preview and approve the design again."
            )
        rows = await self.selected(internship, student_ids)
        if student_ids is not None and len({s.id for _, s, _ in rows}) != len(set(student_ids)):
            raise ValidationError("Only students on the selected list can have an offer letter.")
        if not rows:
            raise ValidationError("Select at least one student first.")
        if len(rows) > MAX_BATCH:
            raise ValidationError(f"Generate at most {MAX_BATCH} letters at a time.")
        existing = await self.current_letters(internship)
        taken, count = await self._references(internship)
        year = datetime.now(timezone.utc).year
        created: list[uuid.UUID] = []
        skipped = 0
        in_progress = 0
        blocked: list[dict[str, Any]] = []
        for selection, student, institution in rows:
            facts = facts_of(student, institution)
            issues = student_issues(facts)
            if issues:
                blocked.append({"student_id": student.id, "name": facts.name or student.email, "issues": issues})
                continue
            current = existing.get(selection.id)
            if current is not None:
                waiting = current.status in (LetterStatus.PENDING.value, LetterStatus.GENERATING.value)
                if waiting and datetime.now(timezone.utc) - current.updated_at < STUCK_AFTER:
                    in_progress += 1
                    continue
                if waiting or current.status == LetterStatus.FAILED.value:  # a letter stuck for long (a lost task) is tried again
                    current.status = LetterStatus.PENDING.value
                    current.error = None
                    current.student_name, current.student_email, current.institution_name = facts.name, facts.email, facts.institution
                    created.append(current.id)
                    continue
                outdated = current.data_hash != student_hash(loaded.settings_hash, facts, current.reference)
                # regenerating is a deliberate act: named students are redone, and with no names only the outdated ones
                if not regenerate or (student_ids is None and not outdated):
                    skipped += 1
                    continue
                current.is_current = False  # kept for the record
                await self.db.flush()
                version = current.version + 1
                ref = current.reference
            else:
                version = 1
                if not selection.offer_reference:
                    while True:
                        count += 1
                        candidate = f"OFR-{year}-{internship.id.hex[:4].upper()}-{count:03d}"
                        if candidate not in taken:
                            break
                    taken.add(candidate)
                    selection.offer_reference = candidate
                ref = selection.offer_reference
            letter = OfferLetter(
                organization_id=internship.organization_id,
                internship_id=internship.id,
                selection_id=selection.id,
                student_id=student.id,
                version=version,
                is_current=True,
                reference=ref,
                student_name=facts.name,
                student_email=facts.email,
                institution_name=facts.institution,
                status=LetterStatus.PENDING.value,
                generated_by_user_id=user_id,
            )
            self.db.add(letter)
            await self.db.flush()
            created.append(letter.id)
        if created:
            await self.log(
                internship, user_id, "regenerated" if regenerate else "generation_requested", f"{len(created)} letter{'s' if len(created) != 1 else ''} queued"
            )
        await self.db.flush()
        return {"letter_ids": created, "already_generated": skipped, "in_progress": in_progress, "blocked": blocked}

    async def generate_one(self, letter_id: uuid.UUID) -> bool:
        """Make one letter's PDF. True when there is nothing more to do for it. One student's failure is recorded on that
        student's letter and never stops the others."""
        letter = (await self.db.execute(select(OfferLetter).where(OfferLetter.id == letter_id).with_for_update())).scalar_one_or_none()
        if letter is None or letter.status not in (LetterStatus.PENDING.value, LetterStatus.GENERATING.value):
            return True
        internship = (await self.db.execute(select(OurInternship).where(OurInternship.id == letter.internship_id))).scalar_one()
        try:
            row = (await self.selected(internship, [letter.student_id]))[0] if letter.student_id else None
            if row is None:
                raise ValueError("The student is no longer on the selected list.")
            _, student, institution = row
            facts = facts_of(student, institution)
            issues = student_issues(facts)
            if issues:
                raise ValueError("Missing or unusable details: " + " ".join(issues))
            loaded = await self.load(internship)
            problems = self.problems(internship, loaded)
            if problems:
                raise ValueError("The letter settings are incomplete: " + " ".join(problems))
            when = datetime.now(timezone.utc)
            pdf, pages = build_letter_pdf(
                loaded.config, facts, loaded.assets, internship.title, letter.reference, letter_date_text(loaded.config, when),
                title=f"Internship offer letter - {facts.name}",
            )
            letter.student_name, letter.student_email, letter.institution_name = facts.name, facts.email, facts.institution
            letter.pdf_data = pdf
            letter.pdf_size = len(pdf)
            letter.page_count = pages
            letter.filename = letter_filename(facts.name, internship.id, letter.version)
            letter.data_hash = student_hash(loaded.settings_hash, facts, letter.reference)
            letter.status = LetterStatus.READY.value
            letter.error = None
            letter.generated_at = when
        except Exception as exc:  # noqa: BLE001 - one bad letter is recorded and the rest go on
            letter.status = LetterStatus.FAILED.value
            letter.error = f"{type(exc).__name__}: {exc}"[:500] if not isinstance(exc, ValueError) else str(exc)[:500]
        await self.db.flush()
        return True

    async def fail_unqueued(self, letter_ids: list[uuid.UUID]) -> None:
        """The message broker was unreachable: mark these as failed with the reason, so pressing Generate again retries them
        (otherwise they would wait for a background task that was never started)."""
        await self.db.execute(
            update(OfferLetter)
            .where(OfferLetter.id.in_(letter_ids), OfferLetter.status == LetterStatus.PENDING.value)
            .values(status=LetterStatus.FAILED.value, error="The letter could not be queued. Press Generate again.")
        )
        await self.db.flush()

    async def mark_generating(self, letter_ids: list[uuid.UUID]) -> None:
        await self.db.execute(
            update(OfferLetter).where(OfferLetter.id.in_(letter_ids), OfferLetter.status == LetterStatus.PENDING.value).values(status=LetterStatus.GENERATING.value)
        )
        await self.db.flush()

    # ------------------------------------------------------------------ previews

    async def preview(self, internship: OurInternship, student_id: uuid.UUID | None, draft: LetterConfig | None) -> tuple[bytes, int, bool]:
        """(PDF, pages, is_sample). Uses the unsaved draft settings when given, so the preview shows what is on screen."""
        loaded = await self.load(internship)
        config = draft or loaded.config
        facts, reference, sample = SAMPLE_FACTS, f"OFR-{datetime.now(timezone.utc).year}-{internship.id.hex[:4].upper()}-000", True
        if student_id is not None:
            rows = await self.selected(internship, [student_id])
            if not rows:
                raise NotFoundError("Selected student", student_id)
            selection, student, institution = rows[0]
            facts, sample = facts_of(student, institution), False
            reference = selection.offer_reference or reference
        bad = student_issues(facts)
        if bad:
            raise ValidationError("This student's letter cannot be made yet: " + " ".join(bad))
        pdf, pages = build_letter_pdf(config, facts, loaded.assets, internship.title, reference, letter_date_text(config), title="Offer letter preview")
        return pdf, pages, sample

    # ------------------------------------------------------------------ approving

    async def approve_letters(self, internship: OurInternship, user_id: uuid.UUID, letter_ids: list[uuid.UUID] | None) -> dict[str, int]:
        rows = {r["selection_id"]: r for r in await self.rows(internship)}
        approved = skipped = 0
        for row in rows.values():
            letter: OfferLetter | None = row["letter"]
            if letter is None or (letter_ids is not None and letter.id not in letter_ids):
                continue
            if letter.status != LetterStatus.READY.value or row["outdated"]:
                skipped += 1
                continue
            letter.status = LetterStatus.APPROVED.value
            letter.approved_at = datetime.now(timezone.utc)
            letter.approved_by_user_id = user_id
            await self.log(internship, user_id, "letter_approved", f"Approved the letter for {letter.student_name}", letter.id)
            approved += 1
        await self.db.flush()
        return {"approved": approved, "skipped": skipped}

    # ------------------------------------------------------------------ releasing

    async def release(self, internship: OurInternship, user_id: uuid.UUID, letter_ids: list[uuid.UUID], resend: bool) -> dict[str, Any]:
        """Mark the chosen letters as queued for emailing. Only letters the admin approved can be released."""
        if not letter_ids:
            raise ValidationError("Choose at least one letter to release.")
        await self.db.execute(select(OurInternship.id).where(OurInternship.id == internship.id).with_for_update())
        rows = {r["letter"].id: r for r in await self.rows(internship) if r["letter"] is not None}
        unknown = [i for i in letter_ids if i not in rows]
        if unknown:
            raise ValidationError("Only the current letters of this internship can be released.")
        queued: list[uuid.UUID] = []
        skipped: list[dict[str, str]] = []
        selections = {s.id: s for s, _, _ in await self.selected(internship)}
        for letter_id in dict.fromkeys(letter_ids):
            row = rows[letter_id]
            letter: OfferLetter = row["letter"]
            who = letter.student_name

            def skip(reason: str) -> None:
                skipped.append({"letter_id": str(letter.id), "name": who, "reason": reason})

            if row["issues"]:
                skip("Details are missing: " + " ".join(row["issues"]))
            elif row["outdated"]:
                skip("The letter is outdated. Regenerate and approve it first.")
            elif letter.status == LetterStatus.RELEASED.value and not resend:
                skip("Already sent.")
            elif letter.delivery_status == DeliveryStatus.QUEUED.value and not resend:
                skip("Already on its way.")
            elif letter.status not in (LetterStatus.APPROVED.value, LetterStatus.RELEASED.value):
                skip("Approve the letter first.")
            else:
                letter.delivery_status = DeliveryStatus.QUEUED.value
                letter.delivery_attempts = 0
                letter.delivery_error = None
                letter.released_by_user_id = user_id
                selection = selections.get(letter.selection_id)
                if selection is not None:
                    selection.offer_reference = letter.reference
                    selection.offer_status = OfferStatus.QUEUED
                    selection.offer_attempts = 0
                    selection.offer_error = None
                queued.append(letter.id)
        if queued:
            internship.status = OurInternshipStatus.OFFERS_RELEASED
            internship.offers_released_at = internship.offers_released_at or datetime.now(timezone.utc)
            await self.log(internship, user_id, "release_requested", f"{len(queued)} letter{'s' if len(queued) != 1 else ''} queued for emailing")
        await self.db.flush()
        return {"queued": queued, "skipped": skipped}

    async def revert_queue(self, letter_ids: list[uuid.UUID]) -> None:
        """The message broker was unreachable: put these back, so pressing Release again retries them."""
        letters = (await self.db.execute(select(OfferLetter).where(OfferLetter.id.in_(letter_ids)))).scalars().all()
        for letter in letters:
            if letter.delivery_status == DeliveryStatus.QUEUED.value:
                letter.delivery_status = DeliveryStatus.SENT.value if letter.status == LetterStatus.RELEASED.value else DeliveryStatus.NONE.value
                selection = await self.db.get(InternshipSelection, letter.selection_id) if letter.selection_id else None
                if selection is not None and selection.offer_status == OfferStatus.QUEUED:
                    selection.offer_status = OfferStatus.SENT if letter.status == LetterStatus.RELEASED.value else OfferStatus.NOT_SENT
        await self.db.flush()

    # ------------------------------------------------------------------ the email

    def email_values(self, config: LetterConfig, facts: StudentFacts, internship_title: str, reference: str, when: datetime | None = None) -> dict[str, str]:
        return letter_values(config, facts, internship_title, reference, letter_date_text(config, when))

    def render_email(self, config: LetterConfig, values: dict[str, str]) -> tuple[str, str, str]:
        from html import escape

        subject = " ".join(fill(config.email.subject, values).split())
        text = fill(config.email.body, values).strip()
        paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        body = "".join(f"<p style=\"margin:0 0 14px\">{escape(p.strip()).replace(chr(10), '<br>')}</p>" for p in paragraphs)
        html = f"<div style=\"font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.55;color:#1f2937\">{body}</div>"
        return subject, text, html

    async def render_offer_email(self, internship: OurInternship, config: LetterConfig, values: dict[str, str]) -> tuple[str, str, str, Any]:
        """(subject, text, html, note for the send history). A published Email Studio template that an administrator assigned to the
        offer email is used; otherwise the email written in the letter settings, as before. A studio template that needs a value this
        student does not have raises MissingPlaceholders, so the letter is reported as not sent rather than sent wrongly."""
        from modules.email_studio.engine import render_assigned
        from modules.email_studio.service import allowed_for_key
        from packages.email.history import SendMeta
        from packages.email.registry import get_def

        definition = get_def("internship_offer_letter")
        merged: dict[str, object] = {**values, "full_name": values.get("student_name", "")}
        rendered = await render_assigned(
            self.db, internship.organization_id, "internship_offer_letter", merged,
            allowed=allowed_for_key(definition), required=definition.required if definition else (),
        )
        if rendered is not None:
            note = SendMeta(
                organization_id=internship.organization_id, key="internship_offer_letter", module="Internships", template_id=rendered.template_id,
                version_id=rendered.version_id, source=rendered.source, reply_to=rendered.reply_to, from_name=rendered.from_name,
                extra_attachments=rendered.attachments, requires=rendered.requires,
            )
            return rendered.subject, rendered.text, rendered.html, note
        subject, text, html = self.render_email(config, values)
        return subject, text, html, SendMeta(organization_id=internship.organization_id, key="internship_offer_letter", module="Internships", source="letter_settings")

    async def email_preview(self, internship: OurInternship, student_id: uuid.UUID | None) -> dict[str, Any]:
        loaded = await self.load(internship)
        facts, reference, filename = SAMPLE_FACTS, "OFR-0000-0000-000", "OfferLetter_Sample.pdf"
        if student_id is not None:
            rows = await self.selected(internship, [student_id])
            if not rows:
                raise NotFoundError("Selected student", student_id)
            selection, student, institution = rows[0]
            facts = facts_of(student, institution)
            reference = selection.offer_reference or reference
            letter = (await self.current_letters(internship)).get(selection.id)
            filename = letter.filename if letter and letter.filename else letter_filename(facts.name, internship.id, 1)
        from modules.email_studio.engine import MissingPlaceholders

        try:
            subject, text, _, _ = await self.render_offer_email(internship, loaded.config, self.email_values(loaded.config, facts, internship.title, reference))
        except MissingPlaceholders as exc:
            return {"to": facts.email, "subject": "(cannot be made)", "body": f"The email template needs a value this student does not have. {exc}", "attachment": filename}
        return {"to": facts.email, "subject": subject, "body": text, "attachment": filename}

    async def send_test(self, internship: OurInternship, to_email: str) -> None:
        loaded = await self.load(internship)
        pdf, _, _ = await self.preview(internship, None, None)
        values = self.email_values(loaded.config, SAMPLE_FACTS, internship.title, "OFR-TEST-000")
        subject, text, html, _ = await self.render_offer_email(internship, loaded.config, values)
        sent = await email_service.send(
            to_email, "[Test] " + subject, text, html,
            attachments=[EmailAttachment(filename="OfferLetter_Sample.pdf", content=pdf, mime_type="application/pdf")],
        )
        if not sent:
            raise ServiceUnavailableError("The test email could not be sent. Check the email (SMTP) settings.")

    # ------------------------------------------------------------------ files

    async def letter_pdf(self, internship: OurInternship, letter_id: uuid.UUID) -> OfferLetter:
        letter = (
            await self.db.execute(
                select(OfferLetter).options(undefer(OfferLetter.pdf_data)).where(OfferLetter.id == letter_id, OfferLetter.internship_id == internship.id)
            )
        ).scalar_one_or_none()
        if letter is None or not letter.pdf_data:
            raise NotFoundError("Offer letter", letter_id)
        return letter

    async def versions(self, internship: OurInternship, student_id: uuid.UUID) -> list[OfferLetter]:
        return list(
            (
                await self.db.execute(
                    select(OfferLetter).where(OfferLetter.internship_id == internship.id, OfferLetter.student_id == student_id).order_by(OfferLetter.version.desc())
                )
            ).scalars().all()
        )

    async def zip_letters(self, internship: OurInternship, letter_ids: list[uuid.UUID] | None) -> bytes:
        query = (
            select(OfferLetter)
            .options(undefer(OfferLetter.pdf_data))
            .where(
                OfferLetter.internship_id == internship.id,
                OfferLetter.is_current.is_(True),
                OfferLetter.status.in_([LetterStatus.READY.value, LetterStatus.APPROVED.value, LetterStatus.RELEASED.value]),
            )
            .order_by(OfferLetter.student_name, OfferLetter.id)
        )
        if letter_ids:
            query = query.where(OfferLetter.id.in_(letter_ids))
        letters = (await self.db.execute(query)).scalars().all()
        if not letters:
            raise ValidationError("There are no generated letters to download.")
        out = io.BytesIO()
        used: set[str] = set()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            for letter in letters:
                name = letter.filename or letter_filename(letter.student_name, internship.id, letter.version)
                if name in used:  # two students with the same name
                    name = name[:-4] + "_" + letter.reference.rsplit("-", 1)[-1] + ".pdf"
                used.add(name)
                archive.writestr(name, letter.pdf_data)
        return out.getvalue()

    async def deliveries(self, internship: OurInternship, limit: int = 300) -> list[tuple[OfferLetterDelivery, OfferLetter]]:
        rows = (
            await self.db.execute(
                select(OfferLetterDelivery, OfferLetter)
                .join(OfferLetter, OfferLetter.id == OfferLetterDelivery.letter_id)
                .where(OfferLetter.internship_id == internship.id)
                .order_by(OfferLetterDelivery.created_at.desc(), OfferLetterDelivery.attempt.desc(), OfferLetterDelivery.id)
                .limit(limit)
            )
        ).all()
        return [(d, letter) for d, letter in rows]

    async def counts(self, internship: OurInternship) -> dict[str, int]:
        rows = (
            await self.db.execute(
                select(OfferLetter.status, func.count()).where(OfferLetter.internship_id == internship.id, OfferLetter.is_current.is_(True)).group_by(OfferLetter.status)
            )
        ).all()
        counts = {s.value: 0 for s in LetterStatus}
        for status, count in rows:
            counts[status] = count
        return counts

