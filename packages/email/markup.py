"""
The small, safe format email templates are written in.

Admins edit plain text, not HTML, so a template can never carry scripts or break the layout:

    # A heading
    A paragraph. Blank lines start a new paragraph; **bold** works; so do [links](https://example.com).
    [A button](https://example.com)      <- a line holding only a link becomes a button
    > A small grey note

`{{name}}` placeholders are filled in when the email is sent. Everything is escaped, values included
(a name or announcement can't inject markup), and links only keep http, https and mailto addresses.
"""

import html
import re
from urllib.parse import urlparse

VAR = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
_TOKEN = re.compile(r"\x00(\d+)\x00")
_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_SOLE_LINK = re.compile(r"^\[([^\]\n]+)\]\(([^)\s]+)\)$")

_ALLOWED_SCHEMES = {"http", "https", "mailto"}
_WRAPPER = '<div style="font-family:sans-serif;max-width:480px;margin:0 auto">{}</div>'
_BUTTON = (
    '<p><a href="{href}" style="background:{color};color:#fff;padding:10px 20px;'
    'border-radius:6px;text-decoration:none;display:inline-block">{label}</a></p>'
)
_NOTE = '<p style="color:#6b7280;font-size:13px">{}</p>'


def variables_in(*texts: str) -> set[str]:
    """Every {{placeholder}} name used in these texts."""
    return {m.group(1) for text in texts for m in VAR.finditer(text or "")}


def render_subject(subject: str, values: dict[str, object]) -> str:
    """The subject line with placeholders filled in (one line, no markup)."""
    filled = VAR.sub(lambda m: str(values.get(m.group(1), "")), subject or "")
    return " ".join(filled.split())


def _safe_url(url: str) -> str:
    try:
        scheme = urlparse(url.strip()).scheme.lower()
    except ValueError:
        return "#"
    return url.strip() if scheme in _ALLOWED_SCHEMES else "#"


def _tokenise(text: str, values: dict[str, object]) -> tuple[str, list[str]]:
    """Swap placeholders for opaque markers, so values are never parsed as formatting."""
    tokens: list[str] = []

    def take(match: re.Match) -> str:
        tokens.append(str(values.get(match.group(1), "")))
        return f"\x00{len(tokens) - 1}\x00"

    return VAR.sub(take, text), tokens


def _inline_html(text: str, values: dict[str, object]) -> str:
    text, tokens = _tokenise(text, values)
    text = html.escape(text, quote=False)

    def link(match: re.Match) -> str:
        # The typed part of the address was escaped with the rest of the text; undo that before escaping it
        # once for the attribute (values are still raw here, so they are not touched).
        url = _TOKEN.sub(lambda m: tokens[int(m.group(1))], html.unescape(match.group(2)))
        return f'<a href="{html.escape(_safe_url(url), quote=True)}">{match.group(1)}</a>'

    text = _LINK.sub(link, text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _TOKEN.sub(lambda m: html.escape(tokens[int(m.group(1))], quote=False).replace("\n", "<br>"), text)
    return text.replace("\n", "<br>")


def _inline_text(text: str, values: dict[str, object]) -> str:
    text, tokens = _tokenise(text, values)

    def link(match: re.Match) -> str:
        url = _TOKEN.sub(lambda m: tokens[int(m.group(1))], match.group(2))
        return f"{match.group(1)} ({_safe_url(url)})"

    text = _LINK.sub(link, text)
    text = _BOLD.sub(r"\1", text)
    return _TOKEN.sub(lambda m: tokens[int(m.group(1))], text)


def _blocks(body: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", body.replace("\r\n", "\n").replace("\r", "\n")) if block.strip()]


def render_body(body: str, values: dict[str, object], button_color: str = "#2563eb") -> tuple[str, str]:
    """(html, plain text) for a template body with its placeholders filled in."""
    html_parts: list[str] = []
    text_parts: list[str] = []
    for block in _blocks(body):
        lines = block.split("\n")
        if len(lines) == 1 and block.startswith("# "):
            title = block[2:].strip()
            html_parts.append(f"<h2>{_inline_html(title, values)}</h2>")
            text_parts.append(_inline_text(title, values))
        elif block.startswith("> "):
            note = "\n".join(line[2:] if line.startswith("> ") else line.lstrip(">").lstrip() for line in lines)
            html_parts.append(_NOTE.format(_inline_html(note, values)))
            text_parts.append(_inline_text(note, values))
        elif _SOLE_LINK.match(block):
            match = _SOLE_LINK.match(block)
            assert match is not None
            tokenised, tokens = _tokenise(match.group(2), values)
            url = _TOKEN.sub(lambda m: tokens[int(m.group(1))], tokenised)
            html_parts.append(
                _BUTTON.format(
                    href=html.escape(_safe_url(url), quote=True),
                    color=button_color,
                    label=_inline_html(match.group(1), values),
                )
            )
            text_parts.append(f"{_inline_text(match.group(1), values)}: {_safe_url(url)}")
        else:
            html_parts.append(f"<p>{_inline_html(block, values)}</p>")
            text_parts.append(_inline_text(block, values))
    return _WRAPPER.format("".join(html_parts)), "\n\n".join(text_parts)
