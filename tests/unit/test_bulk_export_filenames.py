"""File and folder names inside a bulk-download ZIP (modules/bulk_exports/filenames.py). No database."""

import pytest

from modules.bulk_exports import filenames as fn

ALLOWED = {"student_name", "certificate_id", "registration_id", "document_type", "program_name", "batch_name", "index"}
ROW = {
    "student_name": "Asha Rao",
    "certificate_id": "WS-2026-0042",
    "registration_id": "REG/77",
    "document_type": "Certificate",
    "program_name": "Cloud Basics",
    "batch_name": "B1",
}


def name(template: str, values: dict | None = None, extension: str = "pdf") -> str:
    parsed = fn.parse(template, ALLOWED)
    fn.check_extension(parsed, extension)
    return fn.file_name(parsed, ROW if values is None else values, extension, "Certificate_001")[0]


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{student_name}}{{certificate_id}}.pdf", "Asha RaoWS-2026-0042.pdf"),
        ("{{student_name}}_{{certificate_id}}.pdf", "Asha Rao_WS-2026-0042.pdf"),
        ("{{ student_name }}_{{certificate_id}}", "Asha Rao_WS-2026-0042.pdf"),  # spaces inside braces, no extension
        ("{{registration_id}}{{student_name}}{{document_type}}.pdf", "REG 77Asha RaoCertificate.pdf"),
        ("{{program_name}}{{batch_name}}_{{student_name}}.pdf", "Cloud BasicsB1_Asha Rao.pdf"),
        ("{{student_name}}.PDF", "Asha Rao.pdf"),  # extension compared without case, written as the real one
    ],
)
def test_the_examples_from_the_request_render(template, expected):
    assert name(template) == expected


def test_unknown_placeholders_are_refused_by_name():
    with pytest.raises(fn.TemplateError, match=r"\{\{roll_no\}\}"):
        fn.parse("{{student_name}}_{{roll_no}}.pdf", ALLOWED)


@pytest.mark.parametrize("template", ["{{student_name}", "{student_name}}.pdf", "{{student_name}}{.pdf", "{{Student Name}}"])
def test_malformed_placeholders_are_refused(template):
    with pytest.raises(fn.TemplateError):
        fn.parse(template, ALLOWED)


@pytest.mark.parametrize("template", ["", "   "])
def test_an_empty_template_is_refused(template):
    with pytest.raises(fn.TemplateError):
        fn.parse(template, ALLOWED)


def test_a_too_long_template_is_refused():
    with pytest.raises(fn.TemplateError):
        fn.parse("x" * (fn.MAX_TEMPLATE_LENGTH + 1), ALLOWED)


@pytest.mark.parametrize("template", ["{{student_name}}.exe", "{{student_name}}.pdf.exe", "{{student_name}}.docx"])
def test_any_extension_other_than_the_real_one_is_refused(template):
    parsed = fn.parse(template, ALLOWED)
    with pytest.raises(fn.TemplateError, match="cannot end in"):
        fn.check_extension(parsed, "pdf")


def test_files_that_keep_their_own_extension_refuse_a_typed_one():
    with pytest.raises(fn.TemplateError, match="Leave the extension off"):
        fn.check_extension(fn.parse("{{student_name}}.pdf", ALLOWED), None)
    assert name("{{student_name}}", extension="docx") == "Asha Rao.docx"


@pytest.mark.parametrize("template", ["../{{student_name}}.pdf", "a/{{student_name}}.pdf", "a\\{{student_name}}.pdf", "x:{{student_name}}"])
def test_a_file_name_template_cannot_contain_path_characters(template):
    with pytest.raises(fn.TemplateError):
        fn.parse(template, ALLOWED)


@pytest.mark.parametrize(
    "evil",
    ["../../etc/passwd", "..\\..\\windows", "/abs/path", "a/b", 'q"u<o>t|e?*', "line\nbreak\ttab\x00nul"],
)
def test_values_can_never_create_folders_or_unsafe_characters(evil):
    out = name("{{student_name}}_{{certificate_id}}.pdf", {**ROW, "student_name": evil})
    assert "/" not in out and "\\" not in out and ".." not in out
    assert not any(c in out for c in '<>:"|?*\x00\n\t')
    assert out.endswith("_WS-2026-0042.pdf")


def test_missing_values_leave_no_gaps():
    values = {**ROW, "registration_id": None, "batch_name": ""}
    assert name("{{registration_id}}_{{student_name}}_{{certificate_id}}.pdf", values) == "Asha Rao_WS-2026-0042.pdf"
    assert name("{{program_name}}_{{batch_name}}_{{student_name}}.pdf", values) == "Cloud Basics_Asha Rao.pdf"
    assert name("{{student_name}} - {{batch_name}}.pdf", values) == "Asha Rao.pdf"


def test_missing_values_are_reported():
    parsed = fn.parse("{{registration_id}}_{{student_name}}", ALLOWED)
    _, missing = fn.file_name(parsed, {**ROW, "registration_id": ""}, "pdf", "x")
    assert missing == ["registration_id"]


def test_a_name_with_nothing_left_falls_back_to_the_document_number():
    assert name("{{registration_id}}.pdf", {"registration_id": None}) == "Certificate_001.pdf"


def test_reserved_windows_names_are_made_safe():
    assert name("{{student_name}}", {"student_name": "CON"}) == "_CON.pdf"


def test_long_names_are_shortened_and_keep_the_extension():
    out = name("{{student_name}}", {"student_name": "A" * 500})
    assert out.endswith(".pdf") and len(out) <= fn.MAX_NAME_LENGTH + 4


def test_unicode_names_are_kept():
    assert name("{{student_name}}", {"student_name": "Śrīnivāsa ராமன்"}).startswith("Śrīnivāsa")


def test_duplicate_names_get_a_number_ignoring_case():
    names = fn.UniqueNames()
    assert names.claim("", "Asha.pdf") == "Asha.pdf"
    assert names.claim("", "asha.pdf") == "asha_2.pdf"
    assert names.claim("", "Asha.pdf") == "Asha_3.pdf"
    assert names.claim("Other", "Asha.pdf") == "Other/Asha.pdf"  # another folder is another name
    assert names.renamed == 2


def test_paths_never_exceed_the_limit():
    names = fn.UniqueNames()
    folder = "/".join(["F" * fn.MAX_NAME_LENGTH] * 2)
    path = names.claim(folder, "N" * fn.MAX_NAME_LENGTH + ".pdf")
    assert len(path) <= fn.MAX_PATH_LENGTH and path.endswith(".pdf")
    again = names.claim(folder, "N" * fn.MAX_NAME_LENGTH + ".pdf")
    assert again != path and len(again) <= fn.MAX_PATH_LENGTH


def test_folders_are_plain_names_without_traversal():
    parsed = fn.parse("{{program_name}}/{{batch_name}}", ALLOWED, allow_slash=True)
    assert fn.folder_path(parsed, ROW)[0] == "Cloud Basics/B1"
    assert fn.folder_path(parsed, {**ROW, "program_name": "../..", "batch_name": "/etc"})[0] == "etc"
    assert fn.folder_path(parsed, {"program_name": "", "batch_name": ""})[0] == ""


def test_folder_depth_is_capped():
    parsed = fn.parse("a/b/c/d/e", ALLOWED, allow_slash=True)
    assert fn.folder_path(parsed, {})[0] == "a/b/c"


def test_zip_names_always_end_in_zip():
    parsed = fn.parse("{{program_name}}_certificates", ALLOWED, what="ZIP name")
    assert fn.zip_name(parsed, ROW) == "Cloud Basics_certificates.zip"
    assert fn.zip_name(fn.parse("{{program_name}}", ALLOWED), {}) == "documents.zip"


@pytest.mark.parametrize(
    ("label", "key"),
    [("Registration No.", "registration_no"), ("Roll Number", "roll_number"), ("  ", ""), ("12th Mark", "f_12th_mark"), ("Café", "cafe")],
)
def test_field_labels_become_placeholder_keys(label, key):
    assert fn.to_key(label) == key
