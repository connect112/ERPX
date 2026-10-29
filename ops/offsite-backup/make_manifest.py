"""Turn the psql output of counts.sql (`alembic=<rev>` then `<table>=<rows>` lines) into manifest.json on stdout.

Usage: make_manifest.py <stamp> <name>=<counts-file> [<name>=<counts-file> ...]
Written for the host's Python 3.9: no new-style type syntax.
"""
import json
import sys
from datetime import datetime, timezone


def parse_counts(text):
    alembic, tables = None, {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key == "alembic":
            alembic = value
        else:
            tables[key] = int(value)
    return {"alembic": alembic, "table_count": len(tables), "rows": tables}


def build(stamp, databases):
    return {
        "stamp": stamp,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Counts are read a minute or two after the dump's snapshot, so busy tables (audit_logs, task queues) can be a
        # few rows ahead of the dump. restore_verify.sh allows for that; it does not allow a missing table.
        "note": "row counts are taken just after the dump, not from the same snapshot",
        "databases": databases,
    }


def main(argv):
    stamp, pairs = argv[1], argv[2:]
    databases = {}
    for pair in pairs:
        name, _, path = pair.partition("=")
        with open(path, encoding="utf-8") as handle:
            databases[name] = parse_counts(handle.read())
    json.dump(build(stamp, databases), sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv)
