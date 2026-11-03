"""The read-only backup inventory (ops/inventory/backup_inventory.py) must read the same facts from a header that PostgreSQL's own
pg_restore reports, for archives made by pg_dump 16, 17 and 18. Header-only: nothing is restored."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

from app.core.config import settings
from tests.integration.test_restore_client_compat import _make_archive, _need, _seed_widgets, _tool, _use_clients

pytestmark = pytest.mark.integration

_SPEC = importlib.util.spec_from_file_location(
    "backup_inventory", Path(__file__).resolve().parents[2] / "ops" / "inventory" / "backup_inventory.py"
)
inventory = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(inventory)


@pytest.mark.parametrize("dump_v, archive_version", [(16, "1.15"), (17, "1.16"), (18, "1.16")])
async def test_the_inventory_reads_the_same_header_as_pg_restore(dump_v, archive_version, tmp_path, monkeypatch):
    dirs = _need(dump_v)
    _use_clients(monkeypatch, dirs, dump=dump_v, restore=dump_v)
    archive = await _make_archive(tmp_path, _seed_widgets)

    row = inventory.from_files([str(archive)])[0]

    listing = subprocess.run([_tool(dirs[dump_v], "pg_restore"), "--list", str(archive)], capture_output=True, text=True).stdout
    assert f"Dumped by pg_dump version: {row['dumped_by']}" in listing
    assert f"Dumped from database version: {row['dumped_from']}" in listing
    assert row["format"] == "custom" and row["archive_version"].startswith(archive_version)
    assert row["compression"] in {"gzip", "none"} and f"pg_restore {dump_v}+" in row["restore_hint"]
    if dump_v > inventory.major(row["dumped_from"]):
        assert "SET transaction_timeout" in row["restore_hint"]


async def test_plain_dumps_and_junk_are_classified(tmp_path, monkeypatch):
    dirs = _need(18)
    _use_clients(monkeypatch, dirs, dump=18, restore=18)
    plain = await _make_archive(tmp_path, _seed_widgets, "p.sql", compressed=False)
    junk = tmp_path / "junk.bin"
    junk.write_bytes(b"not a dump" * 100)
    rows = {r["name"]: r for r in inventory.from_files([str(plain), str(junk)])}
    assert rows["p.sql"]["format"] == "plain" and rows["p.sql"]["has_transaction_timeout_header"] is True
    assert rows["junk.bin"]["format"] == "unknown" and "Not a recognised" in rows["junk.bin"]["restore_hint"]


def test_a_truncated_header_is_reported_not_crashed(tmp_path):
    cut = tmp_path / "x.dump"
    cut.write_bytes(b"PGDMP" + b"\x01\x0e\x00\x04\x08\x01")  # the file ends inside the header
    row = inventory.from_files([str(cut)])[0]
    assert row["format"] == "unknown" and "unrecognised" in row["note"] and row["size_bytes"] == cut.stat().st_size


def test_only_a_header_sized_prefix_is_ever_read(tmp_path, monkeypatch):
    big = tmp_path / "big.dump"
    big.write_bytes(b"PGDMP" + b"\x01\x0e\x00\x04\x08\x01" + b"\x00" * 3_000_000)
    seen = []
    real_open = open

    def spy(path, mode="r", *a, **k):
        handle = real_open(path, mode, *a, **k)
        original_read = handle.read
        handle.read = lambda n=-1: (seen.append(n), original_read(n))[1]
        return handle

    monkeypatch.setattr("builtins.open", spy)
    inventory.from_files([str(big)])
    assert seen == [inventory.HEADER_BYTES]
