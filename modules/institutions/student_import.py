"""
Reading a student registration list: an Excel file, a CSV/text file, or text pasted into a box.

The lists people actually bring are messy: a header row or none, columns in any order, tabs or commas, a registration form
export with fifteen columns of which we want three. So the reader is forgiving about layout and strict about what it
accepts as a student: every row needs a name and a valid email, and a row that does not is reported back with its line
number rather than silently dropped.

Pure functions, no database: ``parse_students`` turns the input into rows and problems, and the service decides what to do
with them.
"""

import csv
import io
import re
from dataclasses import dataclass, field

from email_validator import EmailNotValidError, validate_email

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000

_EXCEL = (".xlsx", ".xlsm")
_TEXT = (".csv", ".txt", ".tsv", "")

_EMAIL_IN_TEXT = re.compile(r"[^\s,;|<>()\[\]\"']+@[^\s,;|<>()\[\]\"']+")

# Header words (lower-cased, punctuation removed) that identify the three columns we always want.
_NAME_HEADERS = {"name", "studentname", "fullname", "candidatename", "participantname", "student", "participant"}
_EMAIL_HEADERS = {"email", "emailid", "emailaddress", "mail", "mailid", "studentemail", "collegeemail", "personalemail"}
_PHONE_HEADERS = {
    "phone",
    "phoneno",
    "phonenumber",
    "mobile",
    "mobileno",
    "mobilenumber",
    "contact",
    "contactno",
    "contactnumber",
    "whatsapp",
    "whatsappnumber",
}


class StudentListError(ValueError):
    """The input could not be read at all (wrong file type, too big, empty). Shown to the admin as is."""


@dataclass
class ParsedStudent:
    row: int
    name: str
    email: str
    phone: str | None = None
    details: dict[str, str] = field(default_factory=dict)


@dataclass
class RowProblem:
    row: int
    reason: str
    raw: str


@dataclass
class ParsedList:
    students: list[ParsedStudent] = field(default_factory=list)
    problems: list[RowProblem] = field(default_factory=list)


def _key(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", header.lower())


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(str(value).split())


def _valid_email(raw: str) -> str | None:
    try:
        return validate_email(raw.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return None


def _looks_like_phone(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return 8 <= len(digits) <= 15 and re.fullmatch(r"[+\d][\d\s\-()]*", value) is not None


def _excel_rows(data: bytes) -> list[list[str]]:
    try:
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # a corrupt or password-protected file raises many different errors
        raise StudentListError("That Excel file could not be read. Save it as .xlsx (or CSV) and try again.") from exc
    try:
        sheet = workbook.worksheets[0] if workbook.worksheets else None
        if sheet is None:
            raise StudentListError("That Excel file has no sheets.")
        rows: list[list[str]] = []
        for values in sheet.iter_rows(values_only=True):
            if len(rows) > MAX_ROWS + 1:
                break
            rows.append([_clean(v) for v in values])
        return rows
    finally:
        workbook.close()


def _text_rows(text: str) -> list[list[str]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        return []
    sample = "\n".join(lines[:20])
    delimiter = None
    for candidate in ("\t", "|", ";", ","):
        if candidate in sample:
            delimiter = candidate
            break
    if delimiter is None:
        # "Asha Rao asha@example.com 9876543210": no separator at all. Treat each line as one cell and let the
        # per-row logic pull the email out of it.
        return [[line.strip()] for line in lines]
    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter, skipinitialspace=True)
    return [[_clean(cell) for cell in row] for row in reader if any(cell.strip() for cell in row)]


def _header_map(first_row: list[str]) -> dict[int, str] | None:
    """If the first row is a header, map column index -> 'name' | 'email' | 'phone' | <the header text>."""
    keys = [_key(c) for c in first_row]
    if not any(k in _EMAIL_HEADERS for k in keys):
        return None
    if any("@" in c for c in first_row):  # an actual email in the first row means there is no header
        return None
    mapping: dict[int, str] = {}
    seen: set[str] = set()
    for index, (cell, key) in enumerate(zip(first_row, keys)):
        if not cell:
            continue
        if key in _EMAIL_HEADERS and "email" not in seen:
            mapping[index] = "email"
            seen.add("email")
        elif key in _NAME_HEADERS and "name" not in seen:
            mapping[index] = "name"
            seen.add("name")
        elif key in _PHONE_HEADERS and "phone" not in seen:
            mapping[index] = "phone"
            seen.add("phone")
        else:
            mapping[index] = cell[:60]
    return mapping


def _row_from_header(cells: list[str], mapping: dict[int, str]) -> tuple[str, str, str | None, dict[str, str]]:
    name = email = ""
    phone: str | None = None
    details: dict[str, str] = {}
    for index, label in mapping.items():
        value = cells[index] if index < len(cells) else ""
        if label == "name":
            name = value
        elif label == "email":
            email = value
        elif label == "phone":
            phone = value or None
        elif value:
            details[label] = value[:255]
    return name, email, phone, details


def _row_without_header(cells: list[str]) -> tuple[str, str, str | None, dict[str, str]]:
    """No header: find the email by its @, the phone by its digits, and call the first remaining text the name."""
    name = email = ""
    phone: str | None = None
    rest: list[str] = []
    for cell in cells:
        if not cell:
            continue
        match = _EMAIL_IN_TEXT.search(cell)
        if match and not email:
            email = match.group(0).strip(".")
            # what is left around the address, minus the brackets of "Name <a@b.com>"
            leftover = re.sub(r"[<>()\[\]]", " ", cell[: match.start()] + " " + cell[match.end() :])
            leftover = " ".join(leftover.split()).strip(" ,;|-")
            if leftover:
                rest.append(leftover)
        elif phone is None and _looks_like_phone(cell):
            phone = cell
        else:
            rest.append(cell)
    # a phone number hiding in the leftover text of a one-cell line ("Asha Rao 9876543210")
    if phone is None:
        for i, cell in enumerate(rest):
            found = re.search(r"(?<!\d)(\+?\d[\d\s\-]{7,16}\d)(?!\d)", cell)
            if found and _looks_like_phone(found.group(1)):
                phone = found.group(1).strip()
                rest[i] = (cell[: found.start()] + " " + cell[found.end() :]).strip(" ,;|-")
                break
    rest = [r for r in rest if r]
    if rest:
        name = rest[0]
    return name, email, phone, {}


def parse_students(*, filename: str | None = None, data: bytes | None = None, text: str | None = None) -> ParsedList:
    """Read a list of students from an uploaded file (``filename`` + ``data``) or from pasted ``text``."""
    if data is not None:
        if len(data) > MAX_UPLOAD_BYTES:
            raise StudentListError("That file is too large (the limit is 5 MB).")
        suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if filename and "." in filename else ""
        if suffix in _EXCEL:
            rows = _excel_rows(data)
        elif suffix in _TEXT:
            try:
                rows = _text_rows(data.decode("utf-8-sig"))
            except UnicodeDecodeError:
                rows = _text_rows(data.decode("latin-1"))
        elif suffix == ".xls":
            raise StudentListError("Old .xls files are not supported. Save the sheet as .xlsx or CSV and upload that.")
        else:
            raise StudentListError("Please upload an Excel (.xlsx), CSV or text file.")
    elif text is not None:
        if len(text) > MAX_UPLOAD_BYTES:
            raise StudentListError("That text is too long.")
        rows = _text_rows(text)
    else:
        raise StudentListError("Choose a file or paste the student list.")

    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        raise StudentListError("No students were found in that list.")

    mapping = _header_map(rows[0])
    body = rows[1:] if mapping is not None else rows
    first_row_number = 2 if mapping is not None else 1
    if len(body) > MAX_ROWS:
        raise StudentListError(f"That list has more than {MAX_ROWS} students. Please upload it in parts.")

    result = ParsedList()
    for offset, cells in enumerate(body):
        number = first_row_number + offset
        raw = ", ".join(c for c in cells if c)[:200]
        name, email, phone, details = (
            _row_from_header(cells, mapping) if mapping is not None else _row_without_header(cells)
        )
        name = " ".join(name.split())
        if not email:
            result.problems.append(RowProblem(number, "No email address.", raw))
            continue
        normalized = _valid_email(email)
        if normalized is None:
            result.problems.append(RowProblem(number, f"“{email[:80]}” is not a valid email address.", raw))
            continue
        if not name:
            result.problems.append(RowProblem(number, "No name.", raw))
            continue
        if len(name) > 255:
            result.problems.append(RowProblem(number, "The name is too long.", raw))
            continue
        result.students.append(
            ParsedStudent(row=number, name=name, email=normalized, phone=(phone or None) and phone[:50], details=details)
        )
    return result
