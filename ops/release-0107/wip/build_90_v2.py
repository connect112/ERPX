"""Fills wip/90_rollback_code_only.v2.template.sh: embeds sql/rollback_hold.sql, sql/rollback_release.sql, rollback_guard/results_routes.py and rollback_guard/progress_routes.py and
computes the two sha256 values. Writes ../90_rollback_code_only.sh (the committed rollback script, generated) or the path given as argument, and checks that bash can parse it.
Usage: python ops/release-0107/wip/build_90_v2.py [output-path]"""
import hashlib
import pathlib
import re
import subprocess
import sys

pack = pathlib.Path(__file__).resolve().parents[1]
wip = pack / "wip"
guard = (pack / "rollback_guard" / "results_routes.py").read_bytes().replace(b"\r\n", b"\n")   # hash the LF form: the same on Windows (autocrlf) and Linux
text = (wip / "90_rollback_code_only.v2.template.sh").read_text(encoding="utf8")
replaces = re.search(rb'REPLACES_SHA256 = "([0-9a-f]{64})"', guard).group(1).decode()
pguard = (pack / "rollback_guard" / "progress_routes.py").read_bytes().replace(b"\r\n", b"\n")
p_replaces = re.search(rb'REPLACES_SHA256 = "([0-9a-f]{64})"', pguard).group(1).decode()
text = text.replace("@@REPLACES_SHA256@@", replaces).replace("@@GUARD_SHA256@@", hashlib.sha256(guard).hexdigest())
text = text.replace("@@P_REPLACES_SHA256@@", p_replaces).replace("@@P_GUARD_SHA256@@", hashlib.sha256(pguard).hexdigest())
text = text.replace("@@PROGRESS_PY@@", pguard.decode("utf8").rstrip("\n"))
for key, name in (("@@SQL_HOLD@@", "rollback_hold.sql"), ("@@SQL_RELEASE@@", "rollback_release.sql")):
    text = text.replace(key, (pack / "sql" / name).read_text(encoding="utf8").rstrip("\n"))
text = text.replace("@@GUARD_PY@@", guard.decode("utf8").rstrip("\n"))
assert "@@" not in text, "an unfilled placeholder is left"
out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pack / "90_rollback_code_only.sh"
out.write_bytes(text.replace("\r\n", "\n").encode("utf8"))
done = subprocess.run(["bash", "-n", str(out)], capture_output=True, text=True)
print("generated", out, "bash -n:", "ok" if done.returncode == 0 else done.stderr)
sys.exit(done.returncode)
