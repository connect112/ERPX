"""
Years of experience a job asks for, read from its title and description.

Job ads say it in many ways ("3-5 years", "5+ years of experience", "minimum 2 years", "freshers welcome"). A number is
only taken when the words "experience" / "exp" appear close by, so "founded 25+ years ago" is not mistaken for it. When the
text says nothing, the title is used as a rough guide (Senior, Junior, Intern...) and the result is marked as an estimate.
"""

import re

MAX_YEARS = 40
OPEN_ENDED = 99  # "no upper limit" when comparing ranges

_YEARS = r"(?:years?|yrs?)\b"
_RANGE = re.compile(rf"(?<![\d.])(\d{{1,2}})\s*(?:-|–|—|to)\s*(\d{{1,2}})\s*\+?\s*{_YEARS}", re.I)
_PLUS = re.compile(rf"(?<![\d.])(\d{{1,2}})\s*\+\s*{_YEARS}", re.I)
_MIN = re.compile(rf"\b(?:minimum(?:\s+of)?|min\.?|at\s*least|over|more\s+than)\s+(\d{{1,2}})\s*{_YEARS}", re.I)
_SINGLE = re.compile(
    rf"(?<![\d.])(\d{{1,2}})\s*{_YEARS}(?:\s+of)?\s+(?:(?:relevant|hands-on|professional|work|industry|total|overall|proven|practical|real-world)\s+)*experience",
    re.I,
)
_EXPERIENCE_WORD = re.compile(r"experience|\bexp\b|experienced", re.I)
_FRESHER_TEXT = re.compile(r"\b(freshers?|no experience (?:is )?(?:required|needed)|entry[- ]level|0\s*years?)\b", re.I)

_TITLE_GUIDE: list[tuple[re.Pattern, tuple[int, int | None]]] = [
    (re.compile(r"\b(intern|internship|trainee|apprentice|fresher|graduate|campus)\b", re.I), (0, 1)),
    (re.compile(r"\b(junior|jr\.?|entry[- ]level)\b", re.I), (0, 2)),
    (re.compile(r"\b(manager|director|vp|head of|head,|chief)\b", re.I), (8, None)),
    (re.compile(r"\b(lead|principal|staff|architect)\b", re.I), (8, None)),
    (re.compile(r"\b(senior|sr\.?)\b", re.I), (5, None)),
]


def _near_experience(text: str, start: int, end: int) -> bool:
    return bool(_EXPERIENCE_WORD.search(text[max(0, start - 70) : end + 70]))


def _sane(low: int, high: int | None) -> bool:
    return 0 <= low <= MAX_YEARS and (high is None or low <= high <= MAX_YEARS)


def from_text(text: str) -> tuple[int, int | None] | None:
    """(minimum years, maximum years or None for "and more") when the text states it."""
    for pattern, ranged in ((_RANGE, True), (_PLUS, False), (_MIN, False), (_SINGLE, False)):
        for match in pattern.finditer(text):
            if pattern is not _SINGLE and not _near_experience(text, match.start(), match.end()):
                continue
            low = int(match.group(1))
            high = int(match.group(2)) if ranged else None
            if _sane(low, high):
                return low, high
    if _FRESHER_TEXT.search(text):
        return 0, 1
    return None


def from_title(title: str, job_type: str | None) -> tuple[int, int | None] | None:
    if job_type and "intern" in job_type.lower():
        return 0, 1
    for pattern, years in _TITLE_GUIDE:
        if pattern.search(title):
            return years
    return None


def extract_experience(title: str, summary: str | None, job_type: str | None = None) -> tuple[int | None, int | None, bool]:
    """(min, max, estimated). `estimated` is True when it only comes from the title; (None, None, False) = not stated."""
    stated = from_text(f"{title}. {summary or ''}")
    if stated is not None:
        return stated[0], stated[1], False
    guess = from_title(title, job_type)
    if guess is not None:
        return guess[0], guess[1], True
    return None, None, False


# Filter choices: the job's range must overlap the chosen one. "unknown" = nothing stated or guessed.
BUCKETS: dict[str, tuple[int, int]] = {"0-3": (0, 3), "1-5": (1, 5), "3-7": (3, 7), "7+": (7, OPEN_ENDED)}
