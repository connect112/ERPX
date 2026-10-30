"""
The registry of everything the Storage Manager can see, and the rules for each source.

Allowlist, not denylist: a new table that stores files is invisible until it is added here, and nothing is deletable
unless it is an unreferenced object in object storage (see service.analyze). Every identifier below is a constant from
this file, never user input, which is why the service can build its SQL from them.
"""

from dataclasses import dataclass

TRASH_PREFIX = ".trash/"
# Object-storage prefixes that are never deletable, whatever the database says about them.
PROTECTED_PREFIXES = ("backups/",)
LARGE_FILE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class ObjectSource:
    """A table whose rows point at objects in MinIO."""

    key: str
    label: str
    module: str
    table: str
    key_col: str
    name_col: str
    size_col: str
    type_col: str | None
    org_col: str | None
    owner_col: str | None
    status_col: str | None = None
    protected_reason: str | None = None


@dataclass(frozen=True)
class DatabaseSource:
    """A table that keeps file content inside the database (a bytea column). Browse and preview only."""

    key: str
    label: str
    module: str
    table: str
    name_expr: str
    size_expr: str
    type_expr: str
    data_col: str
    org_col: str | None
    owner_col: str | None
    where: str = "true"
    protected_reason: str = "Stored inside a business record. Deleting the file would damage the record."


OBJECT_SOURCES: tuple[ObjectSource, ...] = (
    ObjectSource("documents", "Documents", "documents", "documents", "storage_key", "filename", "size_bytes",
                 "content_type", "organization_id", "uploaded_by_user_id", status_col="status"),
    ObjectSource("media", "Media library", "media", "media_assets", "storage_key", "filename", "size_bytes",
                 "content_type", "organization_id", "uploaded_by_user_id", status_col="status"),
    ObjectSource("internship_files", "Internship files", "internship_learning", "internship_files", "object_key",
                 "filename", "size_bytes", "content_type", "organization_id", "uploaded_by_user_id"),
    ObjectSource("social_assets", "Social media assets", "social_media", "social_assets", "storage_key", "filename",
                 "bytes_size", "content_type", "organization_id", "uploaded_by_user_id"),
    ObjectSource("bulk_exports", "Bulk download ZIPs", "bulk_exports", "bulk_export_jobs", "storage_key",
                 "zip_filename", "size_bytes", None, "organization_id", "requested_by_user_id",
                 protected_reason="A prepared bulk download. It is removed automatically when it expires."),
    ObjectSource("backups", "In-app database backups", "backups", "backup_jobs", "storage_key",
                 "storage_key", "size_bytes", None, None, None,
                 protected_reason="A database backup. Backups are never deleted from here."),
)

DATABASE_SOURCES: tuple[DatabaseSource, ...] = (
    DatabaseSource("offer_letters", "Generated offer letters", "our_internships", "offer_letters",
                   "coalesce(filename, 'offer-letter.pdf')", "coalesce(pdf_size, 0)", "'application/pdf'", "pdf_data",
                   "organization_id", None, where="pdf_data is not null"),
    DatabaseSource("offer_letter_assets", "Offer-letter logos and signatures", "our_internships",
                   "offer_letter_assets", "filename", "size_bytes", "content_type", "data",
                   "organization_id", "uploaded_by_user_id"),
    DatabaseSource("offer_templates", "Offer-letter templates", "our_internships", "our_internships",
                   "coalesce(offer_template_filename, 'offer-template')", "coalesce(offer_template_size, 0)",
                   "'application/octet-stream'", "offer_template_data", "organization_id", "created_by_user_id",
                   where="offer_template_data is not null"),
    DatabaseSource("institution_mous", "Institution MoU files", "institutions", "institutions",
                   "coalesce(mou_filename, 'mou')", "coalesce(mou_size_bytes, 0)",
                   "coalesce(mou_content_type, 'application/octet-stream')", "mou_data", "organization_id",
                   "created_by_user_id", where="mou_data is not null"),
    DatabaseSource("email_assets", "Email Studio images", "email_studio", "email_studio_assets", "filename",
                   "size_bytes", "content_type", "data", "organization_id", "uploaded_by_user_id"),
    DatabaseSource("hackathon_reports", "Hackathon team reports", "hackathons", "hackathon_team_reports", "filename",
                   "size_bytes", "content_type", "data", None, None),
    DatabaseSource("hackathon_task_reports", "Hackathon task reports", "hackathons", "hackathon_task_submissions",
                   "coalesce(report_filename, 'report')", "coalesce(report_size_bytes, 0)",
                   "coalesce(report_content_type, 'application/octet-stream')", "report_data", None, None,
                   where="report_data is not null"),
    DatabaseSource("workshop_certificate_templates", "Workshop certificate templates", "workshop_exams",
                   "workshop_exam_certificate_templates", "'certificate-template'", "octet_length(data)",
                   "content_type", "data", None, None),
)

OBJECT_SOURCES_BY_KEY = {s.key: s for s in OBJECT_SOURCES}
DATABASE_SOURCES_BY_KEY = {s.key: s for s in DATABASE_SOURCES}


def is_protected_key(key: str) -> bool:
    return key.startswith(PROTECTED_PREFIXES)


# Content types that are safe to show inline in the browser. SVG and HTML are deliberately absent: both can run script.
PREVIEWABLE = {
    "image": {"image/png", "image/jpeg", "image/gif", "image/webp"},
    "pdf": {"application/pdf"},
    "video": {"video/mp4", "video/webm"},
    "text": {"text/plain", "text/csv", "application/json"},
}


def preview_kind(content_type: str | None) -> str | None:
    base = (content_type or "").split(";")[0].strip().lower()
    for kind, types in PREVIEWABLE.items():
        if base in types:
            return kind
    return None


def type_group(content_type: str | None) -> str:
    base = (content_type or "").split(";")[0].strip().lower()
    if base.startswith("image/"):
        return "image"
    if base.startswith("video/"):
        return "video"
    if base.startswith("audio/"):
        return "audio"
    if base == "application/pdf":
        return "pdf"
    if base.startswith("text/") or base in ("application/json", "application/xml"):
        return "text"
    if "word" in base or "officedocument" in base or "excel" in base or "powerpoint" in base:
        return "office"
    if "zip" in base or "tar" in base or "gzip" in base:
        return "archive"
    if base in ("application/sql", "application/x-sql"):
        return "database"
    return "other"
