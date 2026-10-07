"""Link names (slugs) for the public leaderboard."""

import re


def clean_slug(value: str) -> str:
    """What an organiser typed, as a link name: lower case, spaces and underscores become hyphens,
    anything else odd is dropped, repeated hyphens collapse."""
    text = re.sub(r"[\s_]+", "-", value.strip().lower())
    text = re.sub(r"[^a-z0-9-]", "", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


def slugify_title(title: str) -> str:
    """A starting link name from a hackathon's title."""
    return clean_slug(title)[:40].strip("-") or "leaderboard"
