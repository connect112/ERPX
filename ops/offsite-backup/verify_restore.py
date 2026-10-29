"""Compare a restored database with the backup's manifest.json. Used by restore_verify.sh; pure logic, unit-tested.

Usage: verify_restore.py <manifest.json> <database-name> <counts-of-restored-db.txt>
Exit 0 when the restore matches, 1 when it does not (every problem is printed).

The manifest's counts were read a minute or two after the dump's snapshot, so a busy table can differ by a few rows
either way. A table may differ by max(25 rows, 2%); a missing table, a different migration version, or a table that
is empty in the restore but not in the manifest is always a failure.
"""
import json
import sys

ABSOLUTE_SLACK = 25
RELATIVE_SLACK = 0.02


def parse_counts(text):
    alembic, rows = None, {}
    for line in text.splitlines():
        key, sep, value = line.strip().partition("=")
        if not sep:
            continue
        if key == "alembic":
            alembic = value
        else:
            rows[key] = int(value)
    return alembic, rows


def compare(expected, alembic, rows):
    """expected: one database's entry from the manifest ({alembic, rows}). Returns a list of problems."""
    problems = []
    if alembic != expected["alembic"]:
        problems.append(f"migration version: backup says {expected['alembic']}, restored database has {alembic}")
    for table in sorted(set(expected["rows"]) - set(rows)):
        problems.append(f"table missing from the restore: {table}")
    for table in sorted(set(rows) - set(expected["rows"])):
        problems.append(f"table in the restore but not in the manifest: {table}")
    for table, want in sorted(expected["rows"].items()):
        if table not in rows:
            continue
        got = rows[table]
        if want > 0 and got == 0:
            problems.append(f"{table}: manifest has {want} rows, restore has none")
        elif abs(got - want) > max(ABSOLUTE_SLACK, int(want * RELATIVE_SLACK)):
            problems.append(f"{table}: manifest {want} rows, restore {got} rows")
    return problems


def main(argv):
    manifest_path, name, counts_path = argv[1:4]
    with open(manifest_path, encoding="utf-8") as handle:
        expected = json.load(handle)["databases"][name]
    with open(counts_path, encoding="utf-8") as handle:
        alembic, rows = parse_counts(handle.read())
    problems = compare(expected, alembic, rows)
    for problem in problems:
        print("MISMATCH", name, problem)
    print(f"{name}: migration {alembic}, {len(rows)} tables,",
          "restore matches the manifest" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
