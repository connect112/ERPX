"""
Certificate ID patterns.

An organiser writes the ID format as text with a few special tokens in braces; everything else is fixed text:

    GIR-DSO-{YYYY}-{#4}        ->  GIR-DSO-2026-0001, GIR-DSO-2026-0002, ...   (numbers in order)
    GIR{A6}                    ->  GIRK7M4QX                                   (6 random letters/digits)
    DSO-{L3}-{1000-9999}       ->  DSO-XQP-4821                                (3 random letters, a number in a range)

Tokens:
    {YYYY} {YY} {MM}   the year (4 or 2 digits) or month when the certificate is issued
    {#N}               the next number in order, zero-padded to N digits (it starts at the exam's "start number"
                       and carries on after the last one issued)
    {AN}               N random capital letters and digits (look-alikes such as 0/O and 1/I left out)
    {LN}               N random capital letters
    {DN}               N random digits
    {FROM-TO}          a random whole number from FROM to TO, e.g. {1000-9999}

Fixed text may use letters, digits, "-" and "_" (the ID is used in a web address, so no spaces, slashes or dots).
"""

import re
import secrets
from dataclasses import dataclass
from datetime import datetime

MAX_PATTERN_LENGTH = 80
MAX_ID_LENGTH = 40
# An ID must be able to tell at least this many certificates apart.
MIN_COMBINATIONS = 1000

_ALNUM = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_LETTERS = "ABCDEFGHJKMNPQRSTUVWXYZ"
_DIGITS = "0123456789"
_FIXED_OK = re.compile(r"^[A-Za-z0-9_-]*$")
_TOKEN = re.compile(r"\{([^{}]*)\}")
_RANGE = re.compile(r"^(\d{1,9})-(\d{1,9})$")
_COUNTED = re.compile(r"^([AaLlDd#])(\d{1,2})$")


class PatternError(ValueError):
    """The ID pattern can't be used; the message says what to change."""


@dataclass(frozen=True)
class Part:
    kind: str  # fixed | year4 | year2 | month | seq | alnum | letters | digits | range
    text: str = ""
    count: int = 0
    low: int = 0
    high: int = 0

    def max_length(self) -> int:
        if self.kind == "fixed":
            return len(self.text)
        if self.kind == "year4":
            return 4
        if self.kind in ("year2", "month"):
            return 2
        if self.kind == "range":
            return len(str(self.high))
        return self.count

    def combinations(self) -> int:
        if self.kind in ("seq", "digits"):
            return 10**self.count
        if self.kind == "alnum":
            return len(_ALNUM) ** self.count
        if self.kind == "letters":
            return len(_LETTERS) ** self.count
        if self.kind == "range":
            return self.high - self.low + 1
        return 1


def parse(pattern: str) -> list[Part]:
    """The pattern as parts, or a PatternError saying what is wrong with it."""
    text = pattern.strip()
    if not text:
        raise PatternError("Enter a format for the certificate ID.")
    if len(text) > MAX_PATTERN_LENGTH:
        raise PatternError(f"The format can be at most {MAX_PATTERN_LENGTH} characters.")
    parts: list[Part] = []
    position = 0
    for match in _TOKEN.finditer(text):
        _add_fixed(parts, text[position : match.start()])
        parts.append(_token(match.group(1)))
        position = match.end()
    _add_fixed(parts, text[position:])

    variable = [p for p in parts if p.kind not in ("fixed", "year4", "year2", "month")]
    if not variable:
        raise PatternError(
            "Add something that changes from one certificate to the next: {#4} for numbers in order, "
            "{A6} for random letters and digits, {D4} for random digits, or {1000-9999} for a number in a range."
        )
    total = 1
    for part in parts:
        total *= part.combinations()
    if total < MIN_COMBINATIONS:
        raise PatternError("That format can only make a few IDs. Add more digits or random characters.")
    if sum(p.max_length() for p in parts) > MAX_ID_LENGTH:
        raise PatternError(f"IDs made from this format would be longer than {MAX_ID_LENGTH} characters.")
    return parts


def _add_fixed(parts: list[Part], text: str) -> None:
    if not text:
        return
    if "{" in text or "}" in text:
        raise PatternError("Every { needs a matching } (for example {YYYY} or {#4}).")
    if not _FIXED_OK.match(text):
        raise PatternError(
            f'"{text}" has a character that can\'t be used. Fixed text can only have letters, digits, - and _.'
        )
    parts.append(Part("fixed", text=text))


def _token(raw: str) -> Part:
    name = raw.strip()
    upper = name.upper()
    if upper == "YYYY":
        return Part("year4")
    if upper == "YY":
        return Part("year2")
    if upper == "MM":
        return Part("month")
    ranged = _RANGE.match(name)
    if ranged:
        low, high = int(ranged.group(1)), int(ranged.group(2))
        if high < low:
            raise PatternError(f"{{{name}}}: the second number must be larger than the first.")
        if high == low:
            raise PatternError(f"{{{name}}}: pick a range, not a single number.")
        return Part("range", low=low, high=high)
    counted = _COUNTED.match(name)
    if counted:
        kind = {"#": "seq", "A": "alnum", "L": "letters", "D": "digits"}[counted.group(1).upper()]
        count = int(counted.group(2))
        limit = 12 if kind == "seq" else 20
        if not 1 <= count <= limit:
            raise PatternError(f"{{{name}}}: use between 1 and {limit} characters.")
        return Part(kind, count=count)
    raise PatternError(
        f"{{{name}}} isn't a known token. Use {{YYYY}}, {{YY}}, {{MM}}, {{#4}} (numbers in order), "
        "{A6} (random letters and digits), {L3} (random letters), {D4} (random digits) or {1000-9999} (a number in a range)."
    )


def uses_sequence(parts: list[Part]) -> bool:
    return any(p.kind == "seq" for p in parts)


def render(parts: list[Part], now: datetime, sequence: int | None = None) -> str:
    out: list[str] = []
    for part in parts:
        if part.kind == "fixed":
            out.append(part.text)
        elif part.kind == "year4":
            out.append(f"{now.year:04d}")
        elif part.kind == "year2":
            out.append(f"{now.year % 100:02d}")
        elif part.kind == "month":
            out.append(f"{now.month:02d}")
        elif part.kind == "seq":
            out.append(str(sequence if sequence is not None else 1).zfill(part.count))
        elif part.kind == "alnum":
            out.append("".join(secrets.choice(_ALNUM) for _ in range(part.count)))
        elif part.kind == "letters":
            out.append("".join(secrets.choice(_LETTERS) for _ in range(part.count)))
        elif part.kind == "digits":
            out.append("".join(secrets.choice(_DIGITS) for _ in range(part.count)))
        elif part.kind == "range":
            out.append(str(part.low + secrets.randbelow(part.high - part.low + 1)))
    return "".join(out)


def examples(pattern: str, start: int, now: datetime, how_many: int = 3) -> list[str]:
    """What the next few IDs would look like (numbers in order carry on from `start`)."""
    parts = parse(pattern)
    return [render(parts, now, start + i) for i in range(how_many)]
