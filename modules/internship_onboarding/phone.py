"""
The mobile number a student gives for payments: Indian mobile numbers, in the form the Cashfree integration needs.

Pure functions, no database. Cashfree is handed exactly ten digits (``providers/cashfree.py`` strips ``+91``/``91`` and refuses
anything else), so that is the form stored here. A number is never written to a log: ``mask`` is what events and messages show.
"""

import re

# digits, spaces, hyphens and brackets, with an optional leading "+" (no letters or other symbols)
_TYPED = re.compile(r"^\+?[0-9(][0-9 ()\-]{6,18}$")
_MOBILE = re.compile(r"^[6-9][0-9]{9}$")  # Indian mobile numbers start with 6, 7, 8 or 9

INVALID = "Enter a valid 10-digit Indian mobile number (for example 98765 43210). A +91 prefix is fine."


def normalize_mobile(raw: object) -> str | None:
    """The ten digits of an Indian mobile number as typed (``+91 98765-43210``, ``098765 43210``...), or None when it is not one."""
    text = " ".join(str(raw or "").split())
    if not _TYPED.match(text):
        return None
    digits = re.sub(r"\D", "", text)
    if text.startswith("+") and not digits.startswith("91"):
        return None  # a +country code other than India
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]  # the trunk prefix some people type before a mobile number
    return digits if _MOBILE.match(digits) else None


def mask(number: str | None) -> str:
    """What may appear in a log, an event or an audit entry: the last four digits only."""
    digits = re.sub(r"\D", "", number or "")
    return f"{'•' * 6}{digits[-4:]}" if len(digits) >= 4 else "•" * 6
