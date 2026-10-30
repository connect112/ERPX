"""
Tests for the SSM archive document (ops/offsite-backup/ssm): compression, manifest, the verification marker, cost, lifecycle
safety, and that the deletion document refuses to run without a verified archive. No AWS, server or database.
"""

import base64
import gzip
import hashlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

SSM = Path(__file__).resolve().parents[2] / "ops" / "offsite-backup" / "ssm"
OPS = SSM.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dod = _load("delete_old_dumps", SSM / "delete_old_dumps.py")
builder = _load("build_archive_doc", SSM / "build_archive_doc.py")


def container_namespace():
    """The code exactly as the container runs it: the deletion helpers followed by the archive module."""
    source = builder.joined_python((SSM / "delete_old_dumps.py").read_text(), (SSM / "archive_old_dumps.py").read_text())
    namespace = {"__name__": "container"}
    exec(compile(source, "container", "exec"), namespace)
    return namespace


NS = container_namespace()


def synthetic_dumps():
    """Four fake dumps, and an APPROVED table that describes them."""
    data = {}
    approved = []
    for i, day in enumerate(("2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11")):
        job_id = f"0000000{i}-0000-0000-0000-000000000000"
        blob = (f"-- PostgreSQL database dump {i}\nINSERT INTO t VALUES ({i}, 'row');\n".encode()) * 5000
        key = f"backups/{job_id}.sql"
        data[key] = blob
        approved.append((job_id, key, len(blob), hashlib.sha256(blob).hexdigest(), day))
    return data, tuple(approved)


class FakeMinio:
    def __init__(self, data):
        self.data = data

    def chunks(self, key, offset=0, length=0):
        blob = self.data[key][offset:offset + length] if length else self.data[key][offset:]
        for start in range(0, len(blob), 1000):
            yield blob[start:start + 1000]


@pytest.fixture
def world(monkeypatch):
    data, approved = synthetic_dumps()
    monkeypatch.setitem(NS, "APPROVED", approved)
    return data, approved


# ---- compression -----------------------------------------------------------------------------------------------

def test_compress_round_trips_and_reports_both_checksums(world):
    data, approved = world
    key = approved[0][1]
    out = io.BytesIO()
    meta = NS["compress"](FakeMinio(data).chunks(key), out)
    assert gzip.decompress(out.getvalue()) == data[key]
    assert meta["original_sha256"] == hashlib.sha256(data[key]).hexdigest() == approved[0][3]
    assert meta["original_size"] == len(data[key])
    assert meta["gz_sha256"] == hashlib.sha256(out.getvalue()).hexdigest() and meta["gz_size"] == len(out.getvalue())
    assert meta["gz_size"] < meta["original_size"] / 5          # SQL text compresses well


def test_compression_is_repeatable_so_a_rerun_gives_the_same_archive(world):
    data, approved = world
    a, b = io.BytesIO(), io.BytesIO()
    NS["compress"](FakeMinio(data).chunks(approved[1][1]), a)
    NS["compress"](FakeMinio(data).chunks(approved[1][1]), b)
    assert a.getvalue() == b.getvalue()


def test_sampling_stops_at_the_limit(world):
    data, approved = world
    meta = NS["compress"](FakeMinio(data).chunks(approved[0][1]), io.BytesIO(), limit=5000)
    assert 5000 <= meta["original_size"] < 8000


def test_estimate_gives_a_size_and_a_cost_under_the_budget(world):
    data, approved = world
    rows, total = NS["estimate"](FakeMinio(data))
    assert len(rows) == 4 and all(0 < r["ratio"] < 0.2 for r in rows)
    assert total == sum(r["estimated_gz_size"] for r in rows) and total < sum(a[2] for a in approved)
    assert NS["monthly_cost"](1024 ** 3) == pytest.approx(0.023)
    # the real figures: even with no compression at all, four dumps of 4.77 GB cost about US$0.10 a month
    assert NS["monthly_cost"](4_770_955_666) == pytest.approx(0.102, abs=0.005)


# ---- manifest and marker ---------------------------------------------------------------------------------------

def metas_for(data, approved):
    result = {}
    for job_id, key, *_ in approved:
        out = io.BytesIO()
        result[job_id] = NS["compress"](FakeMinio(data).chunks(key), out)
    return result


def db_rows(approved):
    return [{"id": a[0], "status": "completed", "size_bytes": a[2], "sha256": a[3], "storage_key": a[1],
             "started_at": f"{a[4]} 02:00:00+00"} for a in approved]


def test_manifest_records_everything_needed_to_recover_each_dump(world):
    data, approved = world
    manifest = NS["build_manifest"](db_rows(approved), metas_for(data, approved), "2026-10-30T05:00:00+00:00")
    assert len(manifest["files"]) == 4 and "Permanent" in manifest["retention"]
    for entry, (job_id, key, size, sha, day) in zip(manifest["files"], approved):
        assert entry["job_id"] == job_id and entry["original_filename"] == f"{job_id}.sql" and entry["backup_date"] == day
        assert entry["original_size_bytes"] == size and entry["original_sha256"] == sha and entry["original_object_key"] == key
        assert entry["archive_object_key"] == f"archive/inapp-dumps-2026-10-08-to-11/{day}_{job_id}.sql.gz"
        assert entry["archive_s3_uri"] == "s3://pentrix-erpx-backups-373384939117/" + entry["archive_object_key"]
        assert entry["archive_size_bytes"] > 0 and len(entry["archive_sha256"]) == 64
        assert entry["backup_record_when_archived"]["sha256"] == sha        # the database record is kept in the manifest
    assert any("gunzip" in step for step in manifest["how_to_restore"])


def test_manifest_refuses_bytes_that_are_not_the_approved_original(world):
    data, approved = world
    metas = metas_for(data, approved)
    metas[approved[2][0]]["original_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="not the approved original"):
        NS["build_manifest"](db_rows(approved), metas, "now")


def good_results(approved):
    return {a[0]: {"archive_size_ok": True, "archive_sha256_ok": True, "original_sha256_ok": True,
                   "archive_size": 100, "archive_sha256": "a" * 64} for a in approved}


def test_marker_says_verified_only_when_every_check_passed_for_every_dump(world):
    _, approved = world
    assert NS["build_marker"](good_results(approved), "now")["all_verified"] is True
    for field in ("archive_size_ok", "archive_sha256_ok", "original_sha256_ok"):
        results = good_results(approved)
        results[approved[1][0]][field] = False
        marker = NS["build_marker"](results, "now")
        assert marker["all_verified"] is False and [f["verified"] for f in marker["files"]] == [True, False, True, True]
    missing = good_results(approved)
    del missing[approved[3][0]]
    assert NS["build_marker"](missing, "now")["all_verified"] is False


# ---- the container's entry points ------------------------------------------------------------------------------

def run_main(monkeypatch, mode, data, approved, rows=None, argv=()):
    monkeypatch.setenv("MODE", mode)
    newest = [{"id": f"n{i}", "status": "completed", "size_bytes": 10, "storage_key": f"backups/n{i}.sql",
               "started_at": f"2026-10-{28 + i} 02:00:00+00"} for i in range(3)]
    monkeypatch.setenv("DATA_JSON", json.dumps({"rows": rows if rows is not None else db_rows(approved), "newest": newest}))

    class Store(FakeMinio):
        def versioning(self): return ""
        def size(self, key): return len(self.data[key]) if key in self.data else None
        def sha256(self, key): return hashlib.sha256(self.data[key]).hexdigest()

    store_data = dict(data, **{f"backups/n{i}.sql": b"x" * 10 for i in range(3)})
    monkeypatch.setitem(NS, "MinioStore", lambda: Store(store_data))
    monkeypatch.setattr("sys.argv", ["container", *argv])
    return NS["main"]()


def test_plan_mode_prints_the_estimate_and_the_exact_keys_and_changes_nothing(world, monkeypatch, capsys):
    data, approved = world
    assert run_main(monkeypatch, "plan", data, approved) == 0
    out = capsys.readouterr().out
    assert "all gates passed" in out and "estimated archive size" in out and "US$" in out
    for job_id, _, _, _, day in approved:
        assert f"archive/inapp-dumps-2026-10-08-to-11/{day}_{job_id}.sql.gz" in out
    assert "VERIFIED.json" in out


def test_plan_mode_aborts_when_a_gate_fails(world, monkeypatch, capsys):
    data, approved = world
    rows = db_rows(approved)
    rows[0]["sha256"] = "f" * 64
    assert run_main(monkeypatch, "plan", data, approved, rows=rows) == 2
    assert "ABORT" in capsys.readouterr().out


def test_stream_mode_writes_the_gzip_and_reports_checksums(world, monkeypatch, capsysbinary):
    data, approved = world
    assert run_main(monkeypatch, "stream", data, approved, argv=(approved[0][1],)) == 0
    captured = capsysbinary.readouterr()
    assert gzip.decompress(captured.out) == data[approved[0][1]]
    meta = json.loads(captured.err.decode().split("META|")[1])
    assert meta["original_sha256"] == approved[0][3] and meta["gz_sha256"] == hashlib.sha256(captured.out).hexdigest()


def test_stream_mode_refuses_a_key_that_is_not_approved(world, monkeypatch, capsysbinary):
    data, approved = world
    assert run_main(monkeypatch, "stream", data, approved, argv=("backups/n0.sql",)) == 2
    assert capsysbinary.readouterr().out == b""


def test_stream_mode_fails_if_the_bytes_are_not_the_approved_original(world, monkeypatch, capsysbinary):
    data, approved = world
    data[approved[0][1]] = data[approved[0][1]] + b"tampered"
    assert run_main(monkeypatch, "stream", data, approved, argv=(approved[0][1],)) == 5


# ---- lifecycle: the archive can not expire ---------------------------------------------------------------------

def test_no_lifecycle_rule_can_expire_anything_under_the_archive_prefix():
    prefix = NS["S3_PREFIX"]
    rules = json.loads((OPS / "aws" / "lifecycle.json").read_text())["Rules"]
    for rule in rules:
        rule_prefix = rule["Filter"]["Prefix"]
        expires = "Days" in rule.get("Expiration", {}) or "NoncurrentVersionExpiration" in rule
        if expires:
            assert not prefix.startswith(rule_prefix), f"rule {rule['ID']} would expire the archive"
    assert not any(prefix.startswith(p) for p in ("daily/", "weekly/", "monthly/"))


def test_the_instance_role_still_cannot_delete_or_change_lifecycle():
    policy = json.loads((OPS / "aws" / "iam-policy-instance-role.json").read_text())
    denied = {a for s in policy["Statement"] if s["Effect"] == "Deny" for a in s["Action"]}
    assert {"s3:DeleteObject", "s3:DeleteObjectVersion", "s3:PutLifecycleConfiguration"} <= denied


# ---- the SSM documents -----------------------------------------------------------------------------------------

ARCHIVE_DOC = json.loads((SSM / "pentrix-op-archive-old-dumps.json").read_text())
ARCHIVE_COMMANDS = ARCHIVE_DOC["mainSteps"][0]["inputs"]["runCommand"]
DELETE_DOC = json.loads((SSM / "pentrix-op-delete-old-dumps.json").read_text())
DELETE_COMMANDS = DELETE_DOC["mainSteps"][0]["inputs"]["runCommand"]


def test_the_archive_document_defaults_to_plan_and_restricts_its_parameters():
    params = ARCHIVE_DOC["parameters"]
    assert params["Mode"]["default"] == "plan" and params["Mode"]["allowedValues"] == ["plan", "archive", "verify"]
    assert re.fullmatch(params["Confirm"]["allowedPattern"], "ARCHIVE-4-OLD-DUMPS")
    assert not re.fullmatch(params["Confirm"]["allowedPattern"], "$(rm -rf /)")
    host = (SSM / "archive_host.sh").read_text()
    assert 'CONFIRM" != "ARCHIVE-4-OLD-DUMPS"' in host and "exit 3" in host


def test_the_archive_document_embeds_exactly_the_reviewed_code():
    joined = "\n".join(ARCHIVE_COMMANDS)
    py, sh = re.findall(r"printf '%s' '([A-Za-z0-9+/=]+)'", joined)
    assert base64.b64decode(py).decode() == (SSM / "archive_container.py").read_text()
    assert base64.b64decode(sh).decode() == (SSM / "archive_host.sh").read_text()


def test_the_committed_archive_files_are_what_the_generator_produces():
    names = ["archive_host.sh", "archive_container.py", "pentrix-op-archive-old-dumps.json"]
    before = {n: (SSM / n).read_bytes() for n in names}
    subprocess.run(["python", str(SSM / "build_archive_doc.py")], check=True, capture_output=True)
    assert {n: (SSM / n).read_bytes() for n in names} == before


def test_the_host_script_lists_exactly_the_four_approved_dumps():
    host = (SSM / "archive_host.sh").read_text()
    entries = re.findall(r'^  "([^"]+)"$', host, re.M)
    assert entries == [f"{a[0]}|{a[1]}|{a[4]}|{a[3]}" for a in dod.APPROVED]


def test_the_archive_never_deletes_anything():
    host = (SSM / "archive_host.sh").read_text()
    container = (SSM / "archive_old_dumps.py").read_text()
    for word in ("s3 rm", "delete-object", "remove(", "remove_object", "docker rm", "docker stop", "systemctl", "drop ", "truncate"):
        assert word not in host and word not in container, word
    assert "rm -rf" not in host.replace('rm -rf "$WORK"', "")           # only its own temp folder


def test_the_archive_document_only_uses_its_two_ssm_parameters_and_fits():
    placeholders = {m for c in ARCHIVE_COMMANDS for m in re.findall(r"\{\{[^}]*\}\}", c)}
    assert placeholders == {"{{ Mode }}", "{{ Confirm }}"} and len(json.dumps(ARCHIVE_DOC)) < 60_000


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not installed")
def test_the_host_script_and_both_modes_of_the_document_are_valid_shell():
    assert subprocess.run(["bash", "-n", str(SSM / "archive_host.sh")], capture_output=True).returncode == 0
    for mode, confirm in (("plan", ""), ("archive", "ARCHIVE-4-OLD-DUMPS"), ("verify", "")):
        body = "\n".join(ARCHIVE_COMMANDS).replace("{{ Mode }}", mode).replace("{{ Confirm }}", confirm)
        script = Path(tempfile.mkdtemp()) / "doc.sh"
        script.write_text(body + "\n")
        assert subprocess.run(["bash", "-n", str(script)], capture_output=True).returncode == 0


# ---- the deletion document needs the verified archive ----------------------------------------------------------

def test_the_deletion_document_refuses_to_run_without_a_verified_archive():
    joined = "\n".join(DELETE_COMMANDS)
    assert joined.index("gate 1:") < joined.index("gate 1b") < joined.index("gate 2")
    gate = next(c for c in DELETE_COMMANDS if "VERIFIED.json" in c)
    assert "exit 4" in gate and "archive/inapp-dumps-2026-10-08-to-11/VERIFIED.json" in gate
    code = gate.split("python3 -c '")[1].rsplit("' ", 1)[0]
    for job_id, key, size, sha, day in dod.APPROVED:
        assert job_id in code and sha in code and f"{day}_{job_id}.sql.gz" in code


def run_gate(marker, sizes):
    """Run the deletion document's real gate code against a marker, with `aws s3api head-object` replaced by `sizes`."""
    gate = next(c for c in DELETE_COMMANDS if "VERIFIED.json" in c)
    code = gate.split("python3 -c '")[1].rsplit("' ", 1)[0]
    code = code.replace('subprocess.run(["aws","s3api","head-object","--bucket","pentrix-erpx-backups-373384939117","--key",key,'
                        '"--query","ContentLength","--output","text"],capture_output=True,text=True,check=True)',
                        "type('R',(),{'stdout':str(SIZES[key])})()")
    result = subprocess.run(["python", "-c", f"SIZES={sizes!r}\n{code}"], input=json.dumps(marker), capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def real_marker(**changes):
    files = [{"job_id": a[0], "archive_object_key": f"archive/inapp-dumps-2026-10-08-to-11/{a[4]}_{a[0]}.sql.gz",
              "original_sha256": a[3], "verified": True, "archive_size_bytes": 1000 + i}
             for i, a in enumerate(dod.APPROVED)]
    marker = {"all_verified": True, "files": files}
    marker.update(changes)
    return marker, {f["archive_object_key"]: f["archive_size_bytes"] for f in files}


def test_the_deletion_gate_accepts_a_complete_verified_marker():
    marker, sizes = real_marker()
    code, out = run_gate(marker, sizes)
    assert code == 0 and "archive verified for 4 dumps" in out


def test_the_deletion_gate_rejects_anything_less():
    marker, sizes = real_marker(all_verified=False)
    assert run_gate(marker, sizes)[0] != 0
    marker, sizes = real_marker()
    marker["files"][2]["verified"] = False
    assert run_gate(marker, sizes)[0] != 0
    marker, sizes = real_marker()
    marker["files"][0]["original_sha256"] = "0" * 64                  # a marker for different content
    assert run_gate(marker, sizes)[0] != 0
    marker, sizes = real_marker()
    assert run_gate({**marker, "files": marker["files"][:3]}, sizes)[0] != 0       # one dump missing
    marker, sizes = real_marker()
    sizes[marker["files"][1]["archive_object_key"]] += 1               # the S3 object is not the verified size
    assert run_gate(marker, sizes)[0] != 0
