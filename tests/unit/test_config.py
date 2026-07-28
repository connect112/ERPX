"""
Unit tests for Settings' production-safety validation — the fix for the
Production Hardening Audit's one Critical finding: the app must refuse to
start in production with the default (source-visible) JWT signing secret,
or with any secret too short to be a real key.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

pytestmark = pytest.mark.unit


def test_default_jwt_secret_is_fine_outside_production():
    settings = Settings(ENVIRONMENT="development", JWT_SECRET_KEY="change_me_in_production_min_32_chars")
    assert settings.JWT_SECRET_KEY == "change_me_in_production_min_32_chars"


def test_python_default_placeholder_rejected_in_production():
    with pytest.raises(ValidationError, match="placeholder value"):
        Settings(ENVIRONMENT="production", JWT_SECRET_KEY="change_me_in_production_min_32_chars")


def test_env_file_style_placeholder_rejected_in_production():
    # .env ships its own, differently-worded placeholder
    # ("change_me_to_a_random_64_char_secret_in_production") which is both
    # a different string than the Python field default AND long enough to
    # slip past a naive length-only check — this is the specific case that
    # caught an early version of this validator during development.
    with pytest.raises(ValidationError, match="placeholder value"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="change_me_to_a_random_64_char_secret_in_production",
        )


def test_short_custom_secret_rejected_in_production():
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(ENVIRONMENT="production", JWT_SECRET_KEY="too_short")


def test_real_secret_accepted_in_production():
    real_secret = "a" * 64
    settings = Settings(ENVIRONMENT="production", JWT_SECRET_KEY=real_secret)
    assert settings.JWT_SECRET_KEY == real_secret


def test_environment_is_case_insensitive_for_the_production_check():
    with pytest.raises(ValidationError, match="placeholder value"):
        Settings(ENVIRONMENT="Production", JWT_SECRET_KEY="change_me_in_production_min_32_chars")
