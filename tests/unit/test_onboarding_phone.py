"""The mobile number a student gives for payments: Indian mobile numbers in the form Cashfree is handed (ten digits)."""

import pytest

from modules.internship_onboarding.phone import mask, normalize_mobile
from modules.internship_onboarding.providers.cashfree import _phone

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "typed",
    ["9876543210", "98765 43210", "98765-43210", "(98765) 43210", "+91 98765 43210", "+919876543210", "919876543210", "09876543210", "  98765   43210 "],
)
def test_every_usual_way_of_typing_an_indian_mobile_number_gives_the_same_ten_digits(typed):
    assert normalize_mobile(typed) == "9876543210"


@pytest.mark.parametrize(
    "typed",
    ["", None, "12345", "987654321", "98765432101", "5876543210", "0123456789", "+44 7911 123456", "+1 415 555 0132", "9876 54321O", "abcdefghij", "98765/43210", "<script>", "+91", "91 98765"],
)
def test_anything_else_is_refused(typed):
    assert normalize_mobile(typed) is None


def test_what_is_stored_is_exactly_what_the_cashfree_integration_accepts():
    for typed in ("+91 81234 56789", "8123456789", "081234 56789"):
        assert _phone(normalize_mobile(typed)) == "8123456789"


def test_a_number_is_only_ever_shown_as_its_last_four_digits():
    assert mask("9876543210") == "••••••3210" and "9876" not in mask("9876543210")
    assert mask(None) == mask("12") == "••••••"
