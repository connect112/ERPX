"""Celery task module for internship onboarding (autodiscovered). The tasks live beside the code they use."""

from modules.internship_onboarding.emails import send_invitation_task  # noqa: F401
