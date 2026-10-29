"""
The audit trail must never keep the bytes of a stored file.

`hackathon_task_submissions.report_data` (PDF reports) used to be written into `audit_logs.changes` as the repr of
the bytes on every create and update — about 270 MB of duplicated PDFs that also went into every database backup.
These tests pin the replacement: a small marker holding the size and a short fingerprint, for every model.
"""

import json

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select

from modules.audit.hooks import _binary_marker, _serialize
from modules.audit.models import AuditAction, AuditLog
from modules.institutions.models import Institution

pytestmark = pytest.mark.api

PDF = b"%PDF-1.7\n" + bytes(range(256)) * 4000  # about 1 MB, every byte value present


def test_binary_marker_has_size_and_fingerprint_but_not_the_content():
    marker = _binary_marker(PDF)
    assert marker.startswith(f"<binary {len(PDF)} bytes sha256:")
    assert len(marker) < 80
    assert "%PDF" not in marker


def test_marker_differs_when_the_file_differs_and_matches_when_it_does_not():
    assert _binary_marker(PDF) == _binary_marker(bytes(PDF))
    assert _binary_marker(PDF) != _binary_marker(PDF + b"!")


@pytest.mark.parametrize("wrap", [bytes, bytearray, memoryview])
def test_every_bytes_like_value_is_serialized_as_a_marker(wrap):
    assert _serialize(wrap(PDF)).startswith("<binary ")


def test_ordinary_values_are_serialized_as_before():
    assert _serialize("text") == "text"
    assert _serialize(5) == 5
    assert _serialize(None) is None


async def _audit_rows(db_session, institution_id, action):
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "institutions", AuditLog.entity_id == institution_id, AuditLog.action == action
        )
    )
    return result.scalars().all()


def _institution(organization, **overrides) -> Institution:
    return Institution(
        organization_id=organization.id, name="Audit probe", location="Chennai", faculty_name="Dr Probe", **overrides
    )


async def test_creating_a_row_with_a_file_audits_a_marker_not_the_bytes(db_session, organization):
    institution = _institution(organization, mou_data=PDF, mou_size_bytes=len(PDF))
    db_session.add(institution)
    await db_session.flush()

    (row,) = await _audit_rows(db_session, institution.id, AuditAction.CREATE)
    assert row.changes["mou_data"].startswith(f"<binary {len(PDF)} bytes sha256:")
    assert row.changes["mou_size_bytes"] == len(PDF)  # the plain size column is still audited
    assert len(json.dumps(row.changes)) < 2_000


async def test_replacing_a_file_audits_markers_for_old_and_new(db_session, organization):
    institution = _institution(organization, mou_data=PDF)
    db_session.add(institution)
    await db_session.flush()

    replacement = PDF + b"replacement"
    institution.mou_data = replacement
    await db_session.flush()

    (row,) = await _audit_rows(db_session, institution.id, AuditAction.UPDATE)
    change = row.changes["mou_data"]
    assert change["new"] == _binary_marker(replacement)
    assert change["old"] != change["new"]
    assert len(json.dumps(row.changes)) < 2_000


async def test_deleting_a_row_does_not_load_its_deferred_file_just_to_audit_it(db_session, organization):
    institution = _institution(organization, mou_data=PDF)
    db_session.add(institution)
    await db_session.flush()
    institution_id = institution.id
    db_session.expunge(institution)

    reloaded = (await db_session.execute(select(Institution).where(Institution.id == institution_id))).scalar_one()
    assert "mou_data" in sa_inspect(reloaded).unloaded  # deferred: the file was not fetched

    await db_session.delete(reloaded)
    await db_session.flush()  # used to need a synchronous load of the whole file inside the flush

    (row,) = await _audit_rows(db_session, institution_id, AuditAction.DELETE)
    assert row.changes["mou_data"] == "<binary, not loaded>"
    assert row.changes["name"] == "Audit probe"
