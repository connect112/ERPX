"""
Documents students uploaded during internship onboarding (the current version of each), copied byte for byte. Needs the
internship's view access and ``our_internships.onboarding.review``, the same as opening one of them for review.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from modules.authentication.models import User
from modules.bulk_exports.sources.base import DocumentSource, ExportItem, FilterOption, Placeholder, Scope, matches

_EXT = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}

_PLACEHOLDERS = (
    Placeholder("student_name", "Student name", "Asha Rao"),
    Placeholder("email", "Email", "asha@example.com"),
    Placeholder("application_reference", "Application reference", "ERPX-INT-2026-000001"),
    Placeholder("document", "Document", "College ID card"),
    Placeholder("version", "Version", "2"),
    Placeholder("review_status", "Review status", "verified"),
    Placeholder("program_name", "Internship", "Cloud Internship 2026"),
)


class OnboardingDocumentsSource(DocumentSource):
    key = "onboarding_documents"
    label = "Internship onboarding documents"
    module = "internship_onboarding"
    document_type = "Onboarding document"
    scope_kind = "internship"
    extension = None
    status_options = (FilterOption("submitted", "Waiting for review"), FilterOption("verified", "Verified"), FilterOption("rejected", "Changes requested"))
    base_placeholders = _PLACEHOLDERS
    presets = (
        ("Reference, student, document", "{{application_reference}}_{{student_name}}_{{document}}"),
        ("Student and document", "{{student_name}}_{{document}}"),
    )
    folder_presets = (("By student", "{{student_name}}"), ("By document", "{{document}}"))

    async def open_scope(self, db: AsyncSession, user: User, organization_id: uuid.UUID, scope_id: uuid.UUID | None) -> Scope:
        from modules.internship_onboarding.service import REVIEW, config_of, require
        from modules.our_internships.access import assert_internship_access
        from modules.our_internships.models import OurInternship

        if scope_id is None:
            raise NotFoundError("Internship", "")
        internship = (
            await db.execute(select(OurInternship).where(OurInternship.id == scope_id, OurInternship.organization_id == organization_id))
        ).scalar_one_or_none()
        if internship is None:
            raise NotFoundError("Internship", scope_id)
        await assert_internship_access(db, user, internship.id, "view")
        await require(db, user, REVIEW)
        _, config = await config_of(db, internship)
        return Scope(id=internship.id, label=internship.title, organization_id=organization_id,
                     extra={"internship": internship, "labels": {d.key: d.label for d in config.documents}})  # fmt: skip

    async def query(self, db: AsyncSession, scope: Scope, search: str | None, status: str | None) -> list[ExportItem]:
        from modules.institutions.models import InstitutionStudent
        from modules.internship_onboarding.models import OnboardingApplication, OnboardingDocument
        from modules.our_internships.models import InternshipSelection

        rows = await db.execute(
            select(OnboardingDocument, OnboardingApplication.reference, InstitutionStudent.name, InstitutionStudent.email)
            .join(OnboardingApplication, OnboardingApplication.id == OnboardingDocument.application_id)
            .join(InternshipSelection, InternshipSelection.id == OnboardingApplication.selection_id)
            .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
            .where(
                OnboardingApplication.internship_id == scope.id,
                OnboardingDocument.organization_id == scope.organization_id,
                OnboardingDocument.status != "superseded",
                OnboardingDocument.removed_at.is_(None),
            )
            .order_by(InstitutionStudent.name, OnboardingDocument.requirement_key)
        )  # fmt: skip
        labels = scope.extra["labels"]
        items = []
        for doc, reference, name, email in rows.all():
            label = labels.get(doc.requirement_key, doc.requirement_key)
            if (status and doc.status != status) or not matches(search, name, email, reference, label):
                continue
            items.append(ExportItem(
                id=doc.id, title=f"{name}: {label}", subtitle=f"{reference} · v{doc.version}", status=doc.status,
                values={"student_name": name, "email": email, "application_reference": reference, "document": label,
                        "version": doc.version, "review_status": doc.status, "program_name": scope.label},
                extension=_EXT.get(doc.content_type, "bin"), ref=doc,
            ))  # fmt: skip
        return items

    async def fetch(self, db: AsyncSession, scope: Scope, item: ExportItem) -> bytes:
        from packages.storage.client import get_storage_client

        doc = item.ref
        if doc is None or doc.organization_id != scope.organization_id:
            raise NotFoundError("Document", item.id)
        return await get_storage_client().read_bytes(doc.storage_key, max_bytes=20 * 1024 * 1024)
