"""The web app's navigation tests use a copy of the system roles' permissions (apps/web/src/components/navigation/role-permissions.fixture.json).
This fails when the backend's roles change and the copy does not, so the role-visibility tests never describe roles that no longer exist.

Regenerate: python -c "..." as in the fixture's own history, or simply copy SYSTEM_ROLES (slug -> sorted permission codes; administrator = every
default permission except the platform-only ones) into the file's "roles" object.
"""

import json
from pathlib import Path

from modules.authorization import service as roles_service

FIXTURE = Path(__file__).resolve().parents[2] / "apps/web/src/components/navigation/role-permissions.fixture.json"


def test_the_navigation_role_fixture_matches_the_backends_system_roles():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))["roles"]
    live = {slug: sorted(codes) for _, slug, _, codes in roles_service.SYSTEM_ROLES if slug != "super_admin"}
    live["administrator"] = sorted(code for code, _, _ in roles_service.DEFAULT_PERMISSIONS if code not in roles_service._PLATFORM_ONLY_PERMISSIONS)
    assert fixture == live
