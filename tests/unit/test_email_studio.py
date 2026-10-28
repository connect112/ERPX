"""
Email Studio's pure parts: making designed or imported HTML safe, filling placeholders so values cannot add markup, the editor
document check, the plain-text twin, and the approved React Email templates that ship with the API.
"""

import pytest

from modules.email_studio.code_templates import CodeTemplateError, list_code_templates, load_code_template
from modules.email_studio.placeholders import (
    component_misuse,
    fill_html,
    fill_props,
    fill_subject,
    fill_text,
    missing,
    placeholders_in,
    props_in,
    safe_url,
    unsupported,
)
from modules.email_studio.sanitize import html_to_text, sanitize_document, sanitize_fragment, validate_editor_json
from packages.email.registry import get_def

HOSTILE = (
    '<!DOCTYPE html><html><head><style>*{display:none}</style><script>alert(1)</script></head>'
    '<body style="background-color:#eee;position:fixed;behavior:url(x)"><table width="100%" onclick="evil()"><tr>'
    '<td style="color:red;background-image:url(javascript:alert(1));expression:1">'
    '<h1 onmouseover="x()">Hi {{student_name}}</h1>'
    '<a href="{{reset_url}}">Go</a><a href="javascript:alert(1)">bad</a><a href="data:text/html;base64,AAAA">bad2</a>'
    '<img src="data:image/png;base64,AAA" onerror="x()"><img src="https://cdn.example.com/a.png" width="10">'
    '<iframe src="https://evil.example"></iframe><form action="https://evil.example"><input name="x"></form>'
    "<svg onload=\"x()\"></svg><p>{{signature}}</p><!-- secret --></td></tr></table></body></html>"
)


# ------------------------------------------------------------------ sanitising


def test_scripts_handlers_frames_forms_and_unsafe_links_are_removed_and_placeholders_kept():
    out = sanitize_document(HOSTILE, "Title", "Preview text")
    lowered = out.lower()
    for bad in ("<script", "onclick", "onmouseover", "onerror", "onload", "<iframe", "<form", "<input", "<svg", "javascript:", "data:text", "data:image", "secret", "evil", "position:fixed", "behavior", "expression"):
        assert bad not in lowered, bad
    assert 'href="{{reset_url}}"' in out and "{{student_name}}" in out and "{{signature}}" in out
    assert 'src="https://cdn.example.com/a.png"' in out
    assert 'rel="noopener noreferrer"' in out
    assert out.startswith("<!DOCTYPE html") and "<body style=\"background-color:#eee\">" in out  # the page wrapper is ours


def test_only_safe_css_survives_and_urls_in_css_must_be_https():
    ok = sanitize_fragment('<p style="color:#111;font-size:14px;padding:4px 8px;background:url(https://a.example/b.png)">x</p>')
    assert "color:#111" in ok and "padding:4px 8px" in ok and "url(https://a.example/b.png)" in ok
    bad = sanitize_fragment('<p style="color:red;background:url(http://a.example/b.png);position:absolute;left:0">x</p>')
    assert "color:red" in bad and "http://a.example" not in bad and "position" not in bad
    assert "display" not in sanitize_fragment('<p style="display:flex">x</p>')


def test_a_document_that_is_too_big_is_refused():
    with pytest.raises(ValueError, match="too large"):
        sanitize_document("<p>" + "x" * 700_000 + "</p>")


def test_the_plain_text_twin_keeps_links_and_paragraphs():
    text = html_to_text('<html><body><h1>Hello</h1><p>Open <a href="https://x.example/a">the page</a> now.</p><p>Bye&nbsp;now</p></body></html>')
    assert text == "Hello\nOpen the page (https://x.example/a) now.\nBye now"


# ------------------------------------------------------------------ the editor's saved document


def good_doc():
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hi", "marks": [{"type": "link", "attrs": {"href": "{{reset_url}}"}}]}]}]}


def test_a_valid_editor_document_is_accepted_and_bad_ones_are_refused():
    assert validate_editor_json(good_doc())["type"] == "doc"
    for bad in ("text", {"type": "paragraph"}, {"type": "doc", "content": "x"}, {"type": "doc", "content": [{"nope": 1}]}):
        with pytest.raises(ValueError):
            validate_editor_json(bad)
    evil = good_doc()
    evil["content"][0]["content"][0]["marks"][0]["attrs"]["href"] = "javascript:alert(1)"
    with pytest.raises(ValueError, match="unsafe link"):
        validate_editor_json(evil)
    evil = {"type": "doc", "content": [{"type": "button", "attrs": {"href": " JavaScript:alert(1)"}}]}
    with pytest.raises(ValueError, match="unsafe link"):
        validate_editor_json(evil)


def test_a_deeply_nested_or_huge_document_is_refused():
    node: dict = {"type": "paragraph"}
    for _ in range(60):
        node = {"type": "blockquote", "content": [node]}
    with pytest.raises(ValueError, match="nested too deeply"):
        validate_editor_json({"type": "doc", "content": [node]})
    with pytest.raises(ValueError, match="too many blocks"):
        validate_editor_json({"type": "doc", "content": [{"type": "paragraph"}] * 9000})


# ------------------------------------------------------------------ placeholders


def test_values_are_escaped_for_where_they_land():
    html = '<h1>Hi {{name}}</h1><a href="{{url}}" title="{{name}}">go</a><img src="{{logo}}" alt="{{name}}">'
    out = fill_html(html, {"name": '<script>"x"</script>', "url": "https://ok.example/a?b=1&c=2", "logo": "https://img.example/l.png"})
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert 'href="https://ok.example/a?b=1&amp;c=2"' in out and 'src="https://img.example/l.png"' in out
    assert 'title="&lt;script&gt;&quot;x&quot;&lt;/script&gt;"' in out


def test_a_link_or_image_value_must_be_a_safe_address():
    html = '<a href="{{u}}">x</a><img src="{{u}}">'
    for evil in ("javascript:alert(1)", "data:text/html,x", " vbscript:x", "//evil.example/x"):
        out = fill_html(html, {"u": evil})
        assert 'href=""' in out and 'src=""' in out, evil
    assert 'href="mailto:a@b.example"' in fill_html(html, {"u": "mailto:a@b.example"})
    assert 'src=""' in fill_html(html, {"u": "mailto:a@b.example"})  # an image must be http(s)
    assert safe_url("tel:+911234567890") == "tel:+911234567890" and safe_url("ftp://x") == ""


def test_newlines_in_a_value_become_line_breaks_not_markup():
    assert fill_html("<p>{{v}}</p>", {"v": "a\nb<i>"}) == "<p>a<br />b&lt;i&gt;</p>"


def test_the_subject_is_one_line_with_nothing_that_could_add_a_header():
    out = fill_subject("Hi {{n}} - offer", {"n": "Asha\r\nBcc: evil@example.com\x00"})
    assert "\r" not in out and "\n" not in out and "\x00" not in out
    assert out == "Hi Asha Bcc: evil@example.com - offer"


def test_placeholders_are_found_checked_and_missing_ones_listed():
    assert placeholders_in("Hi {{ a }} {{b}} {{a}}", None, "{{c}}") == ["a", "b", "c"]
    assert props_in("{{prop:heading}} {{x}} {{prop:heading}}") == ["heading"]
    assert missing(["a", "b", "signature", "c"], {"a": "x", "c": ""}, required=("c",)) == ["b", "c"]
    assert unsupported(["a", "zzz", "signature"], {"a"}) == ["zzz"]
    assert fill_text("{{a}}-{{b}}", {"a": "1"}) == "1-"


def test_a_component_block_replaces_its_own_paragraph_and_only_once():
    html = "<p style='x'>{{signature}}</p><p>text</p>"
    assert fill_html(html, {}, {"signature": "<table>SIG</table>"}) == "<table>SIG</table><p>text</p>"
    assert component_misuse("{{signature}} {{brand_footer}} {{signature}}") == ["{{signature}} is used 2 times; use it once."]
    assert component_misuse("{{signature}}") == []


def test_properties_are_escaped_and_nested_placeholders_are_left_for_later():
    html = '<p>{{prop:heading}}</p><a href="{{prop:url}}">{{prop:text}}</a>'
    out = fill_props(html, {"heading": "Welcome, {{full_name}}", "url": "javascript:x", "text": "<b>go</b>"})
    assert "{{full_name}}" in out and 'href=""' in out and "&lt;b&gt;" in out


# ------------------------------------------------------------------ the approved templates that ship with the API


def test_every_approved_template_is_complete_safe_and_consistent():
    templates = list_code_templates()
    assert {t.key for t in templates} >= {"account_verification", "password_reset", "internship_offer", "internship_welcome", "certificate_distribution"}
    for t in templates:
        lowered = t.html.lower()
        assert "<script" not in lowered and "javascript:" not in lowered, t.key
        declared = {p.name for p in t.props}
        assert set(props_in(t.html)) <= declared, f"{t.key}: a property is used but not declared"
        assert {p.name for p in t.props if p.required} <= set(props_in(t.html)), t.key
        assert set(t.default_props()) == declared
        suggested = get_def(t.suggested_for) if t.suggested_for else None
        if suggested is not None:  # what it uses must be what that ERPX email can supply, and the link it needs must be there
            used = set(placeholders_in(fill_props(t.html, t.default_props()), t.subject)) - {"signature", "brand_header", "brand_footer", "company_name"}
            allowed = {v.name for v in suggested.variables}
            assert used <= allowed, f"{t.key} uses {sorted(used - allowed)} which {suggested.key} does not supply"
            for name in suggested.required:
                assert name in used, f"{t.key} must keep {{{{{name}}}}}"


def test_an_unknown_approved_template_is_refused():
    with pytest.raises(CodeTemplateError):
        load_code_template("../../etc/passwd")
    with pytest.raises(CodeTemplateError):
        load_code_template("nope")
