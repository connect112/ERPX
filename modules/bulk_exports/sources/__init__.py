"""
Every module whose documents can be bulk-downloaded. Adding a module is adding a ``DocumentSource`` here; the job,
the ZIP, the file names, the screens and the clean-up are shared.
"""

from modules.bulk_exports.sources.base import DocumentSource
from modules.bulk_exports.sources.certificates import ExamCertificatesSource, InternshipCertificatesSource
from modules.bulk_exports.sources.documents import DocumentsSource
from modules.bulk_exports.sources.offer_letters import OfferLettersSource
from modules.bulk_exports.sources.onboarding import OnboardingDocumentsSource
from modules.bulk_exports.sources.payslips import PayslipsSource

SOURCES: dict[str, DocumentSource] = {
    s.key: s
    for s in (
        ExamCertificatesSource(),
        InternshipCertificatesSource(),
        OfferLettersSource(),
        PayslipsSource(),
        DocumentsSource(),
        OnboardingDocumentsSource(),
    )
}


def get_source(key: str) -> DocumentSource:
    from app.core.exceptions import NotFoundError

    source = SOURCES.get(key)
    if source is None:
        raise NotFoundError("Document type", key)
    return source
