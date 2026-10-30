"""
File and folder names inside a bulk-download ZIP, built from an administrator's template.

A template is plain text with placeholders in double braces, e.g. ``{{student_name}}_{{certificate_id}}.pdf``. Pure
functions, no database: a source supplies the values for each document, this module turns them into names that are safe
on Windows, macOS and Linux and inside a ZIP, and never collide.

Rules (each one is a test in tests/unit/test_bulk_export_filenames.py):

* Only placeholders the source offers are allowed; anything else is refused before the export starts.
* A value cannot break out of its name: slashes, ``..``, control and reserved characters are removed from values, and a
  folder template can never produce an absolute path or a parent-directory step.
* The extension is the document's real one. A template may end in that extension or leave it off; any other extension
  is refused, so a PDF can never be saved as ``.exe``.
* A missing value leaves no gap: doubled or dangling separators are tidied away, and an empty name falls back to the
  document type plus its number.
* Two documents never get the same path: later ones get ``_2``, ``_3`` (compared case-insensitively, as Windows does).
"""

import re
import unicodedata
from dataclasses import dataclass, field

PLACEHOLDER = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
_KEY = re.compile(r"^[a-z][a-z0-9_]{0,59}$")
_EXTENSION = re.compile(r"\.([A-Za-z][A-Za-z0-9]{0,7})$")
# Never allowed in a name on Windows, or meaningful to a shell or a ZIP tool.
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_SEPARATORS = "_-. "
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}

MAX_TEMPLATE_LENGTH = 200
MAX_NAME_LENGTH = 120  # one file or folder name, before the extension
MAX_FOLDER_DEPTH = 3
MAX_PATH_LENGTH = 240


class TemplateError(ValueError):
    """The template cannot be used. The message is shown to the administrator as it is."""


@dataclass(frozen=True)
class ParsedTemplate:
    text: str  # the template without any extension
    keys: tuple[str, ...]
    extension: str | None  # what the administrator typed, lower case without the dot


def to_key(label: str) -> str:
    """A placeholder key from a free-text field label: "Registration No." -> "registration_no"."""
    plain = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii").lower()
    key = re.sub(r"[^a-z0-9]+", "_", plain).strip("_")
    if not key:
        return ""
    if not key[0].isalpha():
        key = f"f_{key}"
    return key[:60]


def _check_braces(template: str) -> None:
    rest = PLACEHOLDER.sub("", template)
    if "{" in rest or "}" in rest:
        raise TemplateError("Every placeholder needs two braces on each side, like {{student_name}}.")


def parse(template: str, allowed: set[str], *, what: str = "file name", allow_slash: bool = False) -> ParsedTemplate:
    template = (template or "").strip()
    if not template:
        raise TemplateError(f"Enter a {what} format.")
    if len(template) > MAX_TEMPLATE_LENGTH:
        raise TemplateError(f"The {what} format is too long (at most {MAX_TEMPLATE_LENGTH} characters).")
    _check_braces(template)
    keys = tuple(m.group(1) for m in PLACEHOLDER.finditer(template))
    bad = [k for k in keys if not _KEY.match(k)]
    if bad:
        raise TemplateError(f"Placeholders use lower-case letters, digits and underscores only: {', '.join(bad)}.")
    unknown = sorted({k for k in keys if k not in allowed})
    if unknown:
        raise TemplateError(
            "Unknown placeholder" + ("s" if len(unknown) > 1 else "") + ": "
            + ", ".join("{{" + k + "}}" for k in unknown) + ". Pick one from the list."
        )
    literal = PLACEHOLDER.sub("", template)
    if not allow_slash and ("/" in literal or "\\" in literal):
        raise TemplateError(f"A {what} cannot contain / or \\. Use the folder setting to put files in folders.")
    if allow_slash and "\\" in literal:
        raise TemplateError("Use / to separate folders.")
    if re.search(r'[<>:"|?*\x00-\x1f]', literal):
        raise TemplateError(f'A {what} cannot contain any of < > : " | ? *')
    extension = None
    match = _EXTENSION.search(template)
    if match and not PLACEHOLDER.search(template[match.start():]):
        extension = match.group(1).lower()
        template = template[: match.start()]
    return ParsedTemplate(text=template, keys=keys, extension=extension)


def check_extension(parsed: ParsedTemplate, real_extension: str | None) -> None:
    """The typed extension must be the document's own. ``real_extension`` None means each file keeps its own."""
    if parsed.extension is None:
        return
    if real_extension is None:
        raise TemplateError("Leave the extension off: every file keeps its own (.pdf, .docx, ...).")
    if parsed.extension != real_extension.lower():
        raise TemplateError(f'These documents are .{real_extension} files; the name cannot end in ".{parsed.extension}".')


def clean_value(value: object) -> str:
    """One placeholder value made safe to sit inside a name."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    text = _UNSAFE.sub(" ", text)
    text = " ".join(text.split())
    return text.replace("..", ".")


def _tidy(name: str) -> str:
    """Remove the gaps a missing value leaves: "Asha__7" -> "Asha_7", "Asha_-_7" -> "Asha_7", "Asha_" -> "Asha".
    A deliberate " - " between two values is kept."""
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"([_\-.])(?:\s*[_\-.])+", r"\1", name)
    name = name.strip(_SEPARATORS)
    if name.split(".")[0].lower() in _RESERVED:
        name = f"_{name}"
    return name


def _truncate(name: str, limit: int) -> str:
    if len(name) <= limit:
        return name
    return name[:limit].rstrip(_SEPARATORS)


def render(parsed: ParsedTemplate, values: dict[str, object]) -> tuple[str, list[str]]:
    """The rendered text and the placeholders that had no value."""
    missing: list[str] = []

    def replace(match: re.Match) -> str:
        key = match.group(1)
        value = clean_value(values.get(key))
        if not value:
            missing.append(key)
        return value

    return PLACEHOLDER.sub(replace, parsed.text), missing


def file_name(parsed: ParsedTemplate, values: dict[str, object], extension: str, fallback: str) -> tuple[str, list[str]]:
    text, missing = render(parsed, values)
    base = _truncate(_tidy(text), MAX_NAME_LENGTH) or _tidy(clean_value(fallback)) or "document"
    ext = re.sub(r"[^a-z0-9]", "", (extension or "").lower())[:8]
    return (f"{base}.{ext}" if ext else base), missing


def folder_path(parsed: ParsedTemplate | None, values: dict[str, object]) -> tuple[str, list[str]]:
    """Folders for one file: at most MAX_FOLDER_DEPTH levels, every level a plain name (no "", ".", "..")."""
    if parsed is None:
        return "", []
    missing: list[str] = []
    parts: list[str] = []
    for segment in parsed.text.split("/"):
        rendered, gone = render(ParsedTemplate(text=segment, keys=(), extension=None), values)
        missing.extend(gone)
        clean = _truncate(_tidy(rendered), MAX_NAME_LENGTH)
        if clean and clean not in (".", ".."):
            parts.append(clean)
    return "/".join(parts[:MAX_FOLDER_DEPTH]), missing


def zip_name(parsed: ParsedTemplate, values: dict[str, object]) -> str:
    text, _ = render(parsed, values)
    return f"{_truncate(_tidy(text), MAX_NAME_LENGTH) or 'documents'}.zip"


@dataclass
class UniqueNames:
    """Hands out paths that are unique inside one ZIP, ignoring case."""

    taken: set[str] = field(default_factory=set)
    renamed: int = 0  # how many names needed a number to stay unique

    def claim(self, folder: str, name: str) -> str:
        # leave room for a file name of a useful length whatever the folders are
        if len(folder) > MAX_PATH_LENGTH - 40:
            folder = folder[: MAX_PATH_LENGTH - 40].rstrip(_SEPARATORS + "/")
        stem, dot, ext = name.rpartition(".")
        if not dot:
            stem, ext = name, ""
        candidate = name
        number = 1
        while True:
            path = f"{folder}/{candidate}" if folder else candidate
            if len(path) > MAX_PATH_LENGTH:
                room = max(8, len(stem) - (len(path) - MAX_PATH_LENGTH))
                stem = stem[:room].rstrip(_SEPARATORS)
                candidate = f"{stem}{'_' + str(number) if number > 1 else ''}{'.' + ext if ext else ''}"
                continue
            if path.lower() not in self.taken:
                self.taken.add(path.lower())
                self.renamed += number > 1
                return path
            number += 1
            candidate = f"{stem}_{number}{'.' + ext if ext else ''}"
