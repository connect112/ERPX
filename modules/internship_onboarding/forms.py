"""
Checking a student's answers against the administrator's form. Pure. Nothing an administrator writes is ever executed:
the only "logic" is a field being visible when another field equals a fixed value.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from modules.internship_onboarding.config import FormField

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")
_PHONE = re.compile(r"^\+?[0-9 ()-]{7,20}$")
MAX_TEXT = 5000


def visible(field: FormField, answers: dict) -> bool:
    if field.visible_if is None:
        return True
    return answers.get(field.visible_if.field) == field.visible_if.equals


def _check(field: FormField, value) -> str | None:
    t = field.type
    if t in ("checkbox", "declaration"):
        if not isinstance(value, bool):
            return "Choose yes or no."
        return None
    if t == "multi_select":
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            return "Choose from the list."
        if any(v not in field.options for v in value):
            return "Choose from the list."
        return None
    if not isinstance(value, str):
        return "Enter text."
    value = value.strip()
    if len(value) > MAX_TEXT:
        return "This is too long."
    if field.min_length is not None and len(value) < field.min_length:
        return f"Enter at least {field.min_length} characters."
    if field.max_length is not None and len(value) > field.max_length:
        return f"Enter at most {field.max_length} characters."
    if t == "email" and not _EMAIL.match(value):
        return "Enter a valid email address."
    if t == "phone" and not _PHONE.match(value):
        return "Enter a valid phone number."
    if t in ("dropdown", "radio") and value not in field.options:
        return "Choose from the list."
    if t == "number":
        try:
            number = Decimal(value)
        except InvalidOperation:
            return "Enter a number."
        if not number.is_finite():
            return "Enter a number."
        if field.min_value is not None and number < field.min_value:
            return f"Enter {field.min_value} or more."
        if field.max_value is not None and number > field.max_value:
            return f"Enter {field.max_value} or less."
    if t == "date":
        try:
            date.fromisoformat(value)
        except ValueError:
            return "Enter a date (YYYY-MM-DD)."
    return None


def _empty(value) -> bool:
    return value is None or value == "" or value == [] or value is False


def clean(fields: list[FormField], answers: dict, *, complete: bool) -> tuple[dict, dict[str, str]]:
    """(kept answers, errors by field key). Unknown keys and answers to hidden or read-only fields are dropped.
    ``complete`` also requires every visible required field (a draft may be partial)."""
    by_key = {f.key: f for f in fields}
    kept: dict = {}
    errors: dict[str, str] = {}
    for key, value in (answers or {}).items():
        field = by_key.get(key)
        if field is None or not field.editable:
            continue
        if _empty(value) and field.type not in ("checkbox",):
            continue
        problem = _check(field, value)
        if problem:
            errors[key] = problem
        else:
            kept[key] = value.strip() if isinstance(value, str) else value
    for field in fields:
        if not visible(field, kept):
            kept.pop(field.key, None)
            errors.pop(field.key, None)
            continue
        if complete and field.required and _empty(kept.get(field.key)):
            errors.setdefault(field.key, "Please confirm this." if field.type == "declaration" else "This is required.")
    return kept, errors
