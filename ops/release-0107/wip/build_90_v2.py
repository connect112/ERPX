"""Fills wip/90_rollback_code_only.v2.template.sh: embeds sql/rollback_hold.sql, sql/rollback_release.sql and rollback_guard/results_routes.py and
computes the two sha256 values. Writes wip/90_rollback_code_only.v2.sh (generated, not committed) and checks that bash can parse it.
Usage: python ops/release-0107/wip/build_90_v2.py"""
import hashlib
import pathlib
import re
import subprocess
import sys

pack = pathlib.Path(__file__).resolve().parents[1]
wip = pack / "wip"
guard = (pack / "rollback_guard" / "results_routes.py").read_bytes()
text = (wip / "90_rollback_code_only.v2.template.sh").read_text(encoding="utf8")
replaces = re.search(rb'REPLACES_SHA256 = "([0-9a-f]{64})"', guard).group(1).decode()
text = text.replace("@@REPLACES_SHA256@@", replaces).replace("@@GUARD_SHA256@@", hashlib.sha256(guard).hexdigest())
for key, name in (("@@SQL_HOLD@@", "rollback_hold.sql"), ("@@SQL_RELEASE@@", "rollback_release.sql")):
    text = text.replace(key, (pack / "sql" / name).read_text(encoding="utf8").rstrip("\n"))
text = text.replace("@@GUARD_PY@@", guard.decode("utf8").rstrip("\n"))
assert "@@" not in text, "an unfilled placeholder is left"
out = wip / "90_rollback_code_only.v2.sh"
out.write_bytes(text.replace("\r\n", "\n").encode("utf8"))
done = subprocess.run(["bash", "-n", str(out)], capture_output=True, text=True)
print("generated", out, "bash -n:", "ok" if done.returncode == 0 else done.stderr)
sys.exit(done.returncode)
