"""
Tests for the SSM deletion document that removes the four approved October 2026 dumps (ops/offsite-backup/ssm).

Every decision runs against a fake MinIO. Nothing here touches AWS, a server, or a database.
"""

import base64
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

SSM = Path(__file__).resolve().parents[2] / "ops" / "offsite-backup" / "ssm"
spec = importlib.util.spec_from_file_location("delete_old_dumps", SSM / "delete_old_dumps.py")
dod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dod)


class FakeStore:
    def __init__(self, files, versioning="", sticky=()):
        self.files = dict(files)            # key -> (size, sha256)
        self._versioning = versioning
        self.removed = []
        self.sticky = set(sticky)           # keys the "delete" call silently fails to remove

    def versioning(self):
        return self._versioning

    def size(self, key):
        return self.files[key][0] if key in self.files else None

    def sha256(self, key):
        return self.files[key][1]

    def remove(self, key):
        self.removed.append(key)
        if key not in self.sticky:
            self.files.pop(key, None)


NEWEST = [
    {"id": "898b4191-b61a-4010-8429-0fa0ff1a6a31", "status": "completed", "size_bytes": 1229163940,
     "storage_key": "backups/898b4191-b61a-4010-8429-0fa0ff1a6a31.sql", "started_at": "2026-10-30 02:00:00.03+00"},
    {"id": "4b7c7480-a1c6-47cf-aa11-fc4949bd06b3", "status": "completed", "size_bytes": 1227196088,
     "storage_key": "backups/4b7c7480-a1c6-47cf-aa11-fc4949bd06b3.sql", "started_at": "2026-10-29 02:00:00.03+00"},
    {"id": "24f415e1-97c5-4e92-bc88-4f874f9b5028", "status": "completed", "size_bytes": 1207981695,
     "storage_key": "backups/24f415e1-97c5-4e92-bc88-4f874f9b5028.sql", "started_at": "2026-10-28 02:00:00.06+00"},
]


def good_rows():
    return [
        {"id": job_id, "status": "completed", "size_bytes": size, "sha256": sha, "storage_key": key,
         "started_at": f"{day} 02:00:00+00"}
        for job_id, key, size, sha, day in dod.APPROVED
    ]


def good_store(**kwargs):
    files = {key: (size, sha) for _, key, size, sha, _ in dod.APPROVED}
    for row in NEWEST:
        files[row["storage_key"]] = (row["size_bytes"], "x" * 64)
    return FakeStore(files, **kwargs)


def newest():
    return [dict(r) for r in NEWEST]


# ---- what is approved ------------------------------------------------------------------------------------------

def test_exactly_the_four_approved_backups_are_listed():
    assert [a[0] for a in dod.APPROVED] == [
        "60b5ddc6-ab6d-4dcb-a36b-9085908d5589", "6d502c1b-d465-4690-848e-6b161f0099a1",
        "6b693aff-1ca9-4d19-851d-1e585c63b0de", "aec2d1b7-6673-4674-86c9-1832afe0db6b",
    ]
    assert [a[4] for a in dod.APPROVED] == ["2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11"]
    assert sum(a[2] for a in dod.APPROVED) == 4_770_955_666
    for job_id, key, _, sha, _ in dod.APPROVED:
        assert key == f"backups/{job_id}.sql" and re.fullmatch(r"[0-9a-f]{64}", sha)


def test_the_newest_backups_are_not_in_the_approved_list():
    approved_ids = {a[0] for a in dod.APPROVED}
    assert not approved_ids & {r["id"] for r in NEWEST}


# ---- checks: everything passes ---------------------------------------------------------------------------------

def test_all_checks_pass_for_the_approved_state():
    problems, actions = dod.check(good_rows(), newest(), good_store())
    assert problems == []
    assert [(a["state"], a["id"]) for a in actions] == [("delete", a[0]) for a in dod.APPROVED]


# ---- checks: every failure aborts, and nothing is offered for deletion -----------------------------------------

def abort(rows=None, new=None, store=None):
    problems, actions = dod.check(rows if rows is not None else good_rows(), new if new is not None else newest(),
                                  store or good_store())
    assert problems, "expected the check to find a problem"
    assert actions == [], "a failed check must never hand out anything to delete"
    return " | ".join(problems)


def test_versioned_bucket_aborts():
    assert "versioning" in abort(store=good_store(versioning="Enabled"))
    assert "versioning" in abort(store=good_store(versioning="Suspended"))


def test_recomputed_checksum_that_differs_aborts():
    store = good_store()
    key = dod.APPROVED[2][1]
    store.files[key] = (dod.APPROVED[2][2], "0" * 64)
    assert "recomputed sha256" in abort(store=store)


def test_file_size_that_differs_aborts():
    store = good_store()
    key = dod.APPROVED[0][1]
    store.files[key] = (dod.APPROVED[0][2] + 1, dod.APPROVED[0][3])
    assert "not the approved" in abort(store=store)


def test_record_that_differs_from_the_approved_values_aborts():
    rows = good_rows()
    rows[1]["sha256"] = "f" * 64
    assert "recorded sha256" in abort(rows=rows)
    rows = good_rows()
    rows[0]["size_bytes"] += 5
    assert "recorded size" in abort(rows=rows)
    rows = good_rows()
    rows[3]["status"] = "failed"
    assert "status" in abort(rows=rows)
    rows = good_rows()
    rows[2]["storage_key"] = "backups/someone-else.sql"
    assert "record points at" in abort(rows=rows)


def test_missing_record_aborts():
    assert "no record found" in abort(rows=good_rows()[:3])


def test_unexpected_extra_record_aborts():
    rows = good_rows() + [{"id": "00000000-0000-0000-0000-000000000000", "status": "completed", "size_bytes": 1,
                           "sha256": "a" * 64, "storage_key": "backups/x.sql", "started_at": "2026-10-12 02:00:00+00"}]
    assert "unexpected records" in abort(rows=rows)


def test_a_file_that_exists_but_whose_record_no_longer_points_at_it_aborts():
    rows = good_rows()
    rows[0]["storage_key"] = None
    assert "no longer points" in abort(rows=rows)


def test_the_newest_backups_are_protected():
    new = newest()
    new[0] = {**new[0], "id": dod.APPROVED[0][0]}                       # one of the four among the newest
    assert "one of the four" in abort(new=new)
    assert "newer than the approved" in abort(new=[{**newest()[0], "started_at": "2026-10-11 02:00:00+00"}] + newest()[1:])
    assert "expected the 3 newest" in abort(new=newest()[:2])


def test_a_newest_backup_whose_file_is_missing_or_wrong_size_aborts():
    store = good_store()
    del store.files[NEWEST[1]["storage_key"]]
    assert "is missing" in abort(store=store)
    store = good_store()
    store.files[NEWEST[2]["storage_key"]] = (1, "x" * 64)
    assert "bytes but the record says" in abort(store=store)
    new = newest()
    new[0]["status"] = "failed"
    assert "not a completed backup" in abort(new=new)


def test_problems_are_all_reported_not_just_the_first():
    rows = good_rows()
    rows[0]["sha256"] = "f" * 64
    rows[1]["size_bytes"] += 1
    text = abort(rows=rows, store=good_store(versioning="Enabled"))
    assert text.count("|") >= 2


# ---- applying --------------------------------------------------------------------------------------------------

def test_verify_mode_never_removes_anything():
    store = good_store()
    _, actions = dod.check(good_rows(), newest(), store)
    assert dod.apply(actions, store, delete=False, today="2026-10-30") == []
    assert store.removed == []


def test_delete_mode_removes_only_the_four_approved_keys_in_order():
    store = good_store()
    _, actions = dod.check(good_rows(), newest(), store)
    sql = dod.apply(actions, store, delete=True, today="2026-10-30")
    assert store.removed == [a[1] for a in dod.APPROVED]
    for row in NEWEST:
        assert row["storage_key"] in store.files            # the newest three are untouched
    assert len(sql) == 4
    for statement, (job_id, key, _, sha, _) in zip(sql, dod.APPROVED):
        assert f"where id = '{job_id}'" in statement and f"sha256 = '{sha}'" in statement
        assert f"storage_key = '{key}'" in statement and "set storage_key = null" in statement
        assert "delete" not in statement.lower().replace("file removed", "")   # records are updated, never deleted


def test_deletion_stops_if_an_object_is_still_there_afterwards():
    store = good_store(sticky={dod.APPROVED[0][1]})
    _, actions = dod.check(good_rows(), newest(), store)
    with pytest.raises(RuntimeError, match="still there"):
        dod.apply(actions, store, delete=True, today="2026-10-30")
    assert store.removed == [dod.APPROVED[0][1]]            # it did not carry on to the others


def test_a_key_outside_the_approved_list_is_never_passed_to_delete():
    store = good_store()
    bad = [{"id": "x", "key": NEWEST[0]["storage_key"], "sha256": "a" * 64, "state": "delete"}]
    with pytest.raises(AssertionError):
        dod.apply(bad, store, delete=True, today="2026-10-30")
    assert store.removed == []


def test_running_again_after_a_full_run_changes_nothing():
    store = good_store()
    rows = good_rows()
    _, actions = dod.check(rows, newest(), store)
    dod.apply(actions, store, delete=True, today="2026-10-30")
    for row in rows:                                         # what the database update does
        row["storage_key"] = None
    problems, again = dod.check(rows, newest(), store)
    assert problems == [] and {a["state"] for a in again} == {"done"}
    store.removed.clear()
    assert dod.apply(again, store, delete=True, today="2026-10-30") == [] and store.removed == []


def test_a_half_finished_run_is_completed_by_updating_the_record_only():
    store = good_store()
    del store.files[dod.APPROVED[0][1]]                      # the file went, the record still points at it
    problems, actions = dod.check(good_rows(), newest(), store)
    assert problems == [] and actions[0]["state"] == "record_only"
    store.removed.clear()
    sql = dod.apply(actions, store, delete=True, today="2026-10-30")
    assert len(sql) == 4 and dod.APPROVED[0][1] not in store.removed


# ---- the SSM document ------------------------------------------------------------------------------------------

DOC = json.loads((SSM / "pentrix-op-delete-old-dumps.json").read_text(encoding="utf-8"))
COMMANDS = DOC["mainSteps"][0]["inputs"]["runCommand"]


def test_the_document_defaults_to_verify_and_restricts_its_parameters():
    params = DOC["parameters"]
    assert params["Mode"]["default"] == "verify" and params["Mode"]["allowedValues"] == ["verify", "delete"]
    assert re.fullmatch(params["Confirm"]["allowedPattern"], "DELETE-4-OLD-DUMPS")
    assert not re.fullmatch(params["Confirm"]["allowedPattern"], "x; rm -rf /")


def test_delete_mode_needs_the_confirmation_phrase():
    joined = "\n".join(COMMANDS)
    assert 'CONFIRM" != "DELETE-4-OLD-DUMPS"' in joined and "exit 3" in joined


def test_the_document_embeds_exactly_the_reviewed_code():
    payload = re.search(r"printf '%s' '([A-Za-z0-9+/=]+)'", "\n".join(COMMANDS)).group(1)
    assert base64.b64decode(payload).decode() == (SSM / "delete_old_dumps.py").read_text(encoding="utf-8").replace("\r\n", "\n")


def test_the_committed_document_is_what_the_generator_produces():
    before = (SSM / "pentrix-op-delete-old-dumps.json").read_text(encoding="utf-8")
    subprocess.run(["python", str(SSM / "build_delete_doc.py")], check=True, capture_output=True)
    assert (SSM / "pentrix-op-delete-old-dumps.json").read_text(encoding="utf-8") == before


def test_the_document_only_names_the_four_approved_ids():
    joined = "\n".join(COMMANDS)
    ids = re.search(r"where id::text in \(([^)]*)\)", joined).group(1)
    assert ids == ",".join(f"'{a[0]}'" for a in dod.APPROVED)


def test_the_document_checks_the_offsite_backup_before_anything_else_is_touched():
    joined = "\n".join(COMMANDS)
    assert joined.index("gate 1") < joined.index("gate 2") < joined.index("gate 3")
    assert "last_status.json" in joined and "SHA256SUMS" in joined and "100800" in joined


def test_the_document_has_no_commands_that_could_harm_anything_else():
    joined = "\n".join(COMMANDS)
    for word in ("rm -rf", "docker rm", "docker stop", "docker restart", "systemctl", "delete from", "drop ", "truncate",
                 "mc rm", "aws s3 rm", "aws s3api delete"):
        assert word not in joined, word


def test_only_the_two_parameters_are_substituted_by_ssm():
    placeholders = {m for c in COMMANDS for m in re.findall(r"\{\{[^}]*\}\}", c)}
    assert placeholders == {"{{ Mode }}", "{{ Confirm }}"}
    assert len(json.dumps(DOC)) < 60_000                     # SSM's document limit is 64 KB


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not installed")
@pytest.mark.parametrize("mode,confirm", [("verify", ""), ("delete", "DELETE-4-OLD-DUMPS")])
def test_the_document_is_valid_shell_in_both_modes(mode, confirm):
    body = "\n".join(COMMANDS).replace("{{ Mode }}", mode).replace("{{ Confirm }}", confirm)
    script = Path(tempfile.mkdtemp()) / "doc.sh"
    script.write_text(body + "\n")
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
