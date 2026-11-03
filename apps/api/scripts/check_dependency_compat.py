#!/usr/bin/env python
"""Fail loudly when the installed Celery / Kombu / redis-py stack cannot work together.

Why this exists: requirements.txt pins celery and redis but Kombu (Celery's messaging layer) used to float. Celery 5.4.0 accepts any
kombu from 5.3.4 up to (not including) 6.0, so a fresh image build picked up kombu 5.7.0, which needs redis-py >= 6.1.0, and every
Celery worker and Beat container died at start-up with

    kombu.exceptions.VersionMismatch: Redis transport requires redis-py versions 6.1.0 or later. You have 5.0.8

while the API stayed healthy (it does not open a Kombu Redis connection until it publishes a task). `pip check` does not see this,
because the requirement lives in a Kombu *extra* (kombu[redis]) that nothing asked for.

Two checks:
  1. offline, always: every requirement the installed celery / kombu / amqp / billiard / vine declare (including kombu's and celery's
     "redis" extras) is satisfied by what is installed;
  2. optional, --broker URL: open a real Kombu connection to the broker. This runs Kombu's own runtime guards, so it is the same test
     a worker performs when it starts.

Run it after `pip install -r requirements.txt` (the API Dockerfile does, and CI does), or inside a built image:
    python scripts/check_dependency_compat.py [--broker redis://redis:6379/1]
Exit status 0 = compatible, 1 = a problem (each one is printed), 2 = the check itself could not run.
"""

from __future__ import annotations

import argparse
import sys
from importlib import metadata

try:  # packaging is normally installed; every virtualenv also carries pip's vendored copy
    from packaging.requirements import Requirement
except ImportError:  # pragma: no cover
    from pip._vendor.packaging.requirements import Requirement  # type: ignore[no-redef]

# The messaging stack and the Redis client it talks through.
STACK = ("celery", "kombu", "amqp", "billiard", "vine", "redis")
# (distribution, extra) pairs whose declared requirements must also hold, because the worker uses them even though nothing in
# requirements.txt asks for the extra by name.
EXTRAS = (("celery", "redis"), ("kombu", "redis"))


def installed_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def problems_for(requires: list[str] | None, owner: str, extra: str | None, versions: dict[str, str | None]) -> list[str]:
    """Requirements in `requires` (a distribution's Requires-Dist lines) that the `versions` do not satisfy.

    With extra=None only unconditional requirements count; with an extra, only the ones that belong to that extra.
    """
    found = []
    for line in requires or []:
        req = Requirement(line)
        if req.name.lower() not in {n.lower() for n in STACK}:
            continue
        marker_env = {"extra": extra} if extra else {"extra": ""}
        if req.marker is not None and not req.marker.evaluate(marker_env):
            continue
        if extra and (req.marker is None or "extra" not in str(req.marker)):
            continue  # an unconditional requirement is checked on its own pass
        have = versions.get(req.name.lower()) or versions.get(req.name)
        label = f"{owner}[{extra}]" if extra else owner
        if have is None:
            found.append(f"{label} needs {req.name}{req.specifier}, which is not installed")
        elif not req.specifier.contains(have, prereleases=True):
            found.append(f"{label} needs {req.name}{req.specifier}, but {req.name} {have} is installed")
    return found


def installed_problems() -> tuple[list[str], dict[str, str | None]]:
    versions = {name: installed_version(name) for name in STACK}
    found: list[str] = []
    for name in STACK:
        if versions[name] is None:
            found.append(f"{name} is not installed")
    if found:
        return found, versions
    for name in ("celery", "kombu", "amqp", "billiard", "vine"):
        found += problems_for(metadata.requires(name), name, None, versions)
    for name, extra in EXTRAS:
        found += problems_for(metadata.requires(name), name, extra, versions)
    return found, versions


def broker_problems(url: str) -> list[str]:
    try:
        import kombu
    except ImportError as exc:  # pragma: no cover
        return [f"kombu cannot be imported: {exc}"]
    connection = kombu.Connection(url, connect_timeout=5)
    try:
        connection.ensure_connection(max_retries=2, interval_start=0.5, interval_step=0.5)
        connection.default_channel  # noqa: B018  # creating the channel runs Kombu's Redis client guard
    except Exception as exc:  # noqa: BLE001  # report whatever Kombu / redis-py raised, by its full name
        return [f"opening a Kombu connection to the broker failed: {type(exc).__module__}.{type(exc).__name__}: {exc}"]
    finally:
        try:
            connection.release()
        except Exception:  # noqa: BLE001  # nothing useful to report about closing a broken connection
            pass
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--broker", help="also open a real Kombu connection to this broker URL (e.g. redis://localhost:6379/1)")
    args = parser.parse_args(argv)

    try:
        found, versions = installed_problems()
    except Exception as exc:  # noqa: BLE001
        print(f"dependency check could not run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print("messaging stack: " + ", ".join(f"{n} {versions[n] or '(missing)'}" for n in STACK))
    if args.broker:
        found += broker_problems(args.broker)
    if found:
        print("INCOMPATIBLE dependencies:")
        for item in found:
            print(f"  - {item}")
        print("Fix the pins in apps/api/requirements.txt so these versions agree (kombu, in particular, must match redis-py).")
        return 1
    print("dependency check passed" + (" (including a real broker connection)" if args.broker else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
