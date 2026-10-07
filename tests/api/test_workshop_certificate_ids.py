"""
Customisable certificate IDs (fixed text + random / in-order / ranged parts) and the script-font + gradient
name styling on uploaded certificate designs.
"""

import io
import re
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from modules.workshop_exams import certificate_ids
from modules.workshop_exams.certificate_ids import PatternError
from modules.workshop_exams.certificate_template import (
    CertificateLayout,
    build_templated_certificate_pdf,
    normalize_template,
)
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee
from modules.workshop_exams.service import WorkshopExamService

_BASE = "/api/v1/workshop-exams"
_PUBLIC = "/api/v1/public/workshop-exams"
_NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)
_QUESTIONS = [{"text": "2 + 2?", "options": ["3", "4"], "correct_indices": [1], "marks": 1}]


# ---------------- the pattern language ----------------


def test_numbers_in_order_start_where_asked_and_are_zero_padded():
    assert certificate_ids.examples("GIR-DSO-{YYYY}-{#4}", 1, _NOW, 3) == [
        "GIR-DSO-2026-0001",
        "GIR-DSO-2026-0002",
        "GIR-DSO-2026-0003",
    ]
    assert certificate_ids.examples("C{YY}{MM}-{#3}", 250, _NOW, 2) == ["C2610-250", "C2610-251"]


def test_random_parts_follow_the_requested_shape():
    for _ in range(50):
        assert re.fullmatch(r"GIR[A-HJKMNP-Z2-9]{6}", certificate_ids.examples("GIR{A6}", 1, _NOW, 1)[0])
        assert re.fullmatch(r"DSO-[A-HJKMNP-Z]{3}-\d{4}", certificate_ids.examples("DSO-{L3}-{D4}", 1, _NOW, 1)[0])
        number = int(certificate_ids.examples("X{1000-9999}", 1, _NOW, 1)[0][1:])
        assert 1000 <= number <= 9999


@pytest.mark.parametrize(
    "pattern, message",
    [
        ("", "Enter a format"),
        ("GIR-2026", "changes from one certificate"),
        ("GIR-{YYYY}", "changes from one certificate"),  # the year alone doesn't tell certificates apart
        ("GIR {#4}", "can't be used"),  # a space
        ("GIR/{#4}", "can't be used"),
        ("GIR{#4", "matching }"),
        ("GIR{#4}}", "matching }"),
        ("GIR-{XYZ}", "isn't a known token"),
        ("GIR-{5000-100}", "second number must be larger"),
        ("GIR-{7-7}", "pick a range"),
        ("GIR-{#0}", "between 1 and"),
        ("GIR-{D2}", "only make a few IDs"),
        ("{A20}{A20}{A5}", "longer than"),
        ("x" * 81, "at most 80"),
    ],
)
def test_unusable_formats_say_what_to_change(pattern, message):
    with pytest.raises(PatternError, match=message):
        certificate_ids.parse(pattern)


# ---------------- script fonts and gradient on the certificate ----------------


def _design():
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (1600, 1131), (250, 250, 250)).save(out, format="PNG")
    return out.getvalue()


def _pdf(layout, number="GIR-0001", name="Asha Rao"):
    jpeg, w, h = normalize_template(_design())
    return build_templated_certificate_pdf(
        template_jpeg=jpeg,
        width_px=w,
        height_px=h,
        layout=layout,
        attendee_name=name,
        certificate_number=number,
        verify_url="https://example.invalid/v",
    )


@pytest.fixture
def readable_pdfs(monkeypatch):
    from reportlab import rl_config

    monkeypatch.setattr(rl_config, "pageCompression", 0)
    monkeypatch.setattr(rl_config, "useA85", 0)


@pytest.mark.parametrize(
    "font, embedded",
    [
        ("great_vibes", b"GreatVibes"),
        ("allura", b"Allura"),
        ("alex_brush", b"AlexBrush"),
        ("pinyon_script", b"PinyonScript"),
        ("parisienne", b"Parisienne"),
    ],
)
def test_every_script_font_is_embedded_in_the_certificate(font, embedded, readable_pdfs):
    pdf = _pdf(CertificateLayout(font=font))
    assert pdf.startswith(b"%PDF") and embedded in pdf


def test_a_second_colour_paints_the_name_as_a_gradient_but_one_colour_stays_flat(readable_pdfs):
    flat = _pdf(CertificateLayout(color="#1e3a8a"))
    same = _pdf(CertificateLayout(color="#1e3a8a", color_end="#1E3A8A"))
    graded = _pdf(CertificateLayout(color="#1e3a8a", color_end="#38bdf8", font="great_vibes"))
    assert b"/ShadingType 2" not in flat and b"/ShadingType 2" not in same
    assert b"/ShadingType 2" in graded and b"7 Tr" in graded


def test_the_certificate_id_is_printed_only_when_switched_on(readable_pdfs):
    off = _pdf(CertificateLayout(), number="GIR-ONLY-7")
    on = _pdf(CertificateLayout(show_id=True), number="GIR-ONLY-7")
    assert b"GIR-ONLY-7" not in off
    assert b"GIR-ONLY-7" in on


def test_layout_rejects_unknown_fonts_and_bad_colours():
    for bad in ({"font": "comic_sans"}, {"id_font": "nope"}, {"color_end": "blue"}, {"id_color": "#12"}):
        with pytest.raises(ValueError):
            CertificateLayout(**bad)


# ---------------- per exam, through the API ----------------


async def _exam(client, auth_headers, **fields):
    created = await client.post(_BASE, json={"title": "Workshop MCQ", "duration_minutes": 30}, headers=auth_headers)
    exam = created.json()
    await client.post(f"{_BASE}/{exam['id']}/questions", json={"questions": _QUESTIONS}, headers=auth_headers)
    if fields:
        patched = await client.patch(f"{_BASE}/{exam['id']}", json=fields, headers=auth_headers)
        assert patched.status_code == 200, patched.text
        exam = patched.json()
    return exam


async def _row(db_session, exam):
    return (await db_session.execute(select(WorkshopExam).where(WorkshopExam.id == uuid.UUID(exam["id"])))).scalar_one()


async def test_the_id_format_is_saved_validated_and_can_be_cleared(client, auth_headers):
    exam = await _exam(client, auth_headers)
    assert exam["certificate_id_pattern"] is None and exam["certificate_id_start"] == 1
    url = f"{_BASE}/{exam['id']}"
    ok = await client.patch(
        url, json={"certificate_id_pattern": " GIR-{YYYY}-{#4} ", "certificate_id_start": 101}, headers=auth_headers
    )
    assert ok.status_code == 200
    assert ok.json()["certificate_id_pattern"] == "GIR-{YYYY}-{#4}" and ok.json()["certificate_id_start"] == 101
    bad = await client.patch(url, json={"certificate_id_pattern": "GIR 2026"}, headers=auth_headers)
    assert bad.status_code == 422
    assert (await client.get(url, headers=auth_headers)).json()["certificate_id_pattern"] == "GIR-{YYYY}-{#4}"
    cleared = await client.patch(url, json={"certificate_id_pattern": ""}, headers=auth_headers)
    assert cleared.json()["certificate_id_pattern"] is None


async def test_id_preview_shows_examples_and_explains_a_bad_format(client, auth_headers):
    exam = await _exam(client, auth_headers)
    url = f"{_BASE}/{exam['id']}/certificate/id-preview"
    ok = await client.post(url, json={"pattern": "GIR-{#3}-{L2}", "start": 7}, headers=auth_headers)
    assert ok.status_code == 200
    shown = ok.json()["examples"]
    assert len(shown) == 4 and shown[0].startswith("GIR-007-") and shown[3].startswith("GIR-010-")
    bad = await client.post(url, json={"pattern": "GIR-{Q}"}, headers=auth_headers)
    assert bad.status_code == 422 and "known token" in bad.text
    assert (await client.post(url, json={"pattern": "GIR-{#3}"})).status_code in (401, 403)


async def test_certificates_get_ids_in_the_exams_format_and_numbers_carry_on_in_order(client, db_session, auth_headers):
    exam = await _exam(client, auth_headers, certificate_id_pattern="GIR-DSO-{YYYY}-{#4}", certificate_id_start=25)
    people = [{"name": f"Student {i}", "email": f"s{i}@example.com"} for i in range(3)]
    await client.post(f"{_BASE}/{exam['id']}/attendees", json={"attendees": people}, headers=auth_headers)
    opened = await client.post(f"{_BASE}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)
    assert opened.status_code == 200
    rows = (
        await db_session.execute(
            select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"]))
        )
    ).scalars().all()
    for row in rows:
        start = (await client.post(f"{_PUBLIC}/{row.access_token}/start")).json()
        await client.post(
            f"{_PUBLIC}/{row.access_token}/submit", json={"answers": {start["questions"][0]["id"]: [1]}}
        )
    sent = await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)
    assert sent.status_code == 200, sent.text
    for row in rows:
        await db_session.refresh(row)
    year = datetime.now(timezone.utc).year
    assert sorted(r.certificate_number for r in rows) == [f"GIR-DSO-{year}-{n:04d}" for n in (25, 26, 27)]
    # Once certificates are out the format is frozen.
    late = await client.patch(
        f"{_BASE}/{exam['id']}", json={"certificate_id_pattern": "OTHER-{#4}"}, headers=auth_headers
    )
    assert late.status_code == 422 and "already been sent" in late.text


async def test_two_exams_with_the_same_format_never_hand_out_the_same_id(client, db_session, auth_headers):
    first = await _exam(client, auth_headers, certificate_id_pattern="SAME-{#3}")
    second = await _exam(client, auth_headers, certificate_id_pattern="SAME-{#3}")
    service = WorkshopExamService(db_session)
    seen = set()
    for exam_json in (first, second, first, second):
        exam = await _row(db_session, exam_json)
        number = await service._new_certificate_number(exam)
        db_session.add(
            WorkshopExamAttendee(
                exam_id=exam.id,
                name="A",
                email=f"{uuid.uuid4().hex[:8]}@example.com",
                access_token=uuid.uuid4().hex,
                certificate_number=number,
            )
        )
        await db_session.flush()
        assert number not in seen
        seen.add(number)
    assert len(seen) == 4


async def test_without_a_format_ids_keep_the_original_style(client, db_session, auth_headers):
    exam = await _exam(client, auth_headers)
    number = await WorkshopExamService(db_session)._new_certificate_number(await _row(db_session, exam))
    assert re.fullmatch(r"WS-\d{4}-[0-9A-F]{8}", number)


async def test_the_preview_pdf_shows_an_id_in_the_chosen_format(client, auth_headers, readable_pdfs):
    exam = await _exam(client, auth_headers, certificate_id_pattern="PREV-{#2}-{D3}")
    await client.put(
        f"{_BASE}/{exam['id']}/certificate/template",
        files={"file": ("d.png", _design(), "image/png")},
        headers=auth_headers,
    )
    layout = CertificateLayout(show_id=True, font="allura", color_end="#38bdf8").model_dump()
    pdf = await client.post(
        f"{_BASE}/{exam['id']}/certificate/preview", json={"layout": layout, "id_start": 9}, headers=auth_headers
    )
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert re.search(rb"PREV-09-\d{3}", pdf.content)
