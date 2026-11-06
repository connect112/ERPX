"""
ops/cashfree-production/cashfreectl.sh, run against temporary files with FAKE keys only. Covers: secrets never printed, keys and the live
confirmation refused without a real terminal, atomic replacement with mode 600, no temporary copy left after a failure or a kill,
symbolic links / hard links / writable folders refused, and one run at a time.

The "typed at a terminal" cases load the script's functions and replace only its terminal check; every other line is the real code.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "ops" / "cashfree-production" / "cashfreectl.sh"
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="bash is needed to run the script")

FAKE_ID, FAKE_SECRET = "FAKEAPPID.live-1", "FAKE_secret-value.2"
START = "SMTP_PASSWORD=keep-me\nCASHFREE_ENABLED=false\nOTHER=1\n"


def sh(command: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, "-c", command], capture_output=True, text=True, timeout=60, **kw)


class Result:
    def __init__(self, done: subprocess.CompletedProcess):
        self.returncode = done.returncode
        self.stdout = done.stdout.decode("utf-8", "replace")
        self.stderr = done.stderr.decode("utf-8", "replace")


def run(env_file: Path, *args: str, stdin: str = "", terminal: bool = False, prelude: str = "") -> Result:
    env = {**os.environ, "ENV_FILE": env_file.as_posix()}
    if terminal:  # load the real functions, replace only the terminal check
        cmd = [BASH, "-c", f'source "$1"; have_terminal() {{ return 0; }}; {prelude}\nshift; main "$@"', "_", SCRIPT.as_posix(), *args]
    else:
        cmd = [BASH, SCRIPT.as_posix(), *args]
    # bytes in and out: what is typed must arrive with plain line ends on every platform
    return Result(subprocess.run(cmd, input=stdin.encode("utf-8"), capture_output=True, env=env, timeout=60))


@pytest.fixture
def env_file(tmp_path):
    folder = tmp_path / "erpx"
    folder.mkdir()
    assert sh(f'chmod 700 "{folder.as_posix()}"').returncode == 0
    path = folder / ".env"
    path.write_text(START, encoding="utf-8", newline="\n")
    assert sh(f'chmod 644 "{path.as_posix()}"').returncode == 0
    return path


def mode_of(path: Path) -> str:
    return sh(f'stat -c %a "{path.as_posix()}"').stdout.strip()


def expect_mode_600(path: Path) -> None:
    """The file must end up 600. Windows-based shells may ignore chmod, so check first that this platform honours it (Linux, macOS do)."""
    probe = path.parent.parent / "mode-probe"
    probe.write_text("x", encoding="utf-8")
    try:
        sh(f'chmod 644 "{probe.as_posix()}"; chmod 600 "{probe.as_posix()}"')
        honoured = mode_of(probe) == "600"
    finally:
        probe.unlink()
    if honoured:
        assert mode_of(path) == "600"


def leftovers(folder: Path) -> list[str]:
    """Anything in the folder besides the .env itself: a temporary copy or a lock."""
    return sorted(p.name for p in folder.iterdir() if p.name != ".env")


def lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


# ------------------------------------------------------------ terminal rule


def test_keys_are_refused_without_a_terminal_and_nothing_changes(env_file):
    done = run(env_file, "keys", stdin=f"{FAKE_ID}\n{FAKE_SECRET}\n{FAKE_SECRET}\n")
    assert done.returncode == 2 and "interactive terminal" in done.stderr
    assert env_file.read_text(encoding="utf-8") == START and leftovers(env_file.parent) == []
    assert FAKE_SECRET not in done.stdout + done.stderr


def test_the_live_confirmation_is_refused_without_a_terminal(env_file):
    done = run(env_file, "switches", "on", stdin="I AUTHORIZE LIVE PAYMENTS\n")
    assert done.returncode == 2 and "interactive terminal" in done.stderr
    assert env_file.read_text(encoding="utf-8") == START


def test_switching_off_needs_no_terminal(env_file):
    done = run(env_file, "switches", "off")
    assert done.returncode == 0
    assert {"CASHFREE_ENABLED=false", "CASHFREE_ALLOW_PRODUCTION=false", "CASHFREE_ENV=sandbox", "SMTP_PASSWORD=keep-me"} <= set(lines(env_file))
    assert leftovers(env_file.parent) == []


# ------------------------------------------------------------ secrets, permissions, atomic replacement


def test_keys_are_stored_without_ever_being_printed_and_the_file_ends_up_600(env_file):
    done = run(env_file, "keys", stdin=f"{FAKE_ID}\n{FAKE_SECRET}\n{FAKE_SECRET}\n", terminal=True)
    assert done.returncode == 0, done.stderr
    assert FAKE_ID not in done.stdout + done.stderr and FAKE_SECRET not in done.stdout + done.stderr
    assert f"CASHFREE_APP_ID={FAKE_ID}" in lines(env_file) and f"CASHFREE_SECRET_KEY={FAKE_SECRET}" in lines(env_file)
    assert "SMTP_PASSWORD=keep-me" in lines(env_file) and "OTHER=1" in lines(env_file)
    assert leftovers(env_file.parent) == []
    expect_mode_600(env_file)
    status = run(env_file, "status")
    assert status.returncode == 0 and "<set, hidden>" in status.stdout and FAKE_SECRET not in status.stdout + status.stderr and FAKE_ID not in status.stdout


@pytest.mark.parametrize(
    "typed, why",
    [(f"{FAKE_ID}\nabc\nabd\n", "differ"), (f"{FAKE_ID}\nbad$secret\nbad$secret\n", "not a letter"), ("\nabc\nabc\n", "both values")],
)
def test_bad_input_is_refused_and_changes_nothing(env_file, typed, why):
    done = run(env_file, "keys", stdin=typed, terminal=True)
    assert done.returncode == 1 and why in done.stderr
    assert env_file.read_text(encoding="utf-8") == START and leftovers(env_file.parent) == []


def test_the_live_switches_need_the_typed_phrase_and_the_keys_first(env_file):
    assert "store the keys first" in run(env_file, "switches", "on", stdin="I AUTHORIZE LIVE PAYMENTS\n", terminal=True).stderr
    run(env_file, "keys", stdin=f"{FAKE_ID}\n{FAKE_SECRET}\n{FAKE_SECRET}\n", terminal=True)
    wrong = run(env_file, "switches", "on", stdin="yes\n", terminal=True)
    assert wrong.returncode == 1 and "CASHFREE_ENABLED=true" not in lines(env_file)
    right = run(env_file, "switches", "on", stdin="I AUTHORIZE LIVE PAYMENTS\n", terminal=True)
    assert right.returncode == 0
    assert {"CASHFREE_ENABLED=true", "CASHFREE_ENV=production", "CASHFREE_ALLOW_PRODUCTION=true", "CASHFREE_API_VERSION=2025-01-01"} <= set(lines(env_file))
    assert FAKE_SECRET not in right.stdout + right.stderr
    expect_mode_600(env_file)


def test_a_run_cut_short_part_way_never_leaves_live_payments_on(env_file):
    run(env_file, "keys", stdin=f"{FAKE_ID}\n{FAKE_SECRET}\n{FAKE_SECRET}\n", terminal=True)
    # the fourth replacement (ENABLED, which is written last) fails
    prelude = 'n=0; mv() { n=$((n+1)); if [ "$n" -eq 4 ]; then return 1; fi; command mv "$@"; }'
    done = run(env_file, "switches", "on", stdin="I AUTHORIZE LIVE PAYMENTS\n", terminal=True, prelude=prelude)
    assert done.returncode != 0
    assert "CASHFREE_ENABLED=true" not in lines(env_file) and "CASHFREE_ENABLED=false" in lines(env_file)
    assert leftovers(env_file.parent) == []  # no temporary copy, no lock


def test_a_kill_part_way_leaves_the_file_whole_and_no_temporary_copy(env_file):
    before = env_file.read_text(encoding="utf-8")
    prelude = "mv() { kill -TERM $$; sleep 2; }"  # the run is terminated just before the replacement
    done = run(env_file, "switches", "off", terminal=True, prelude=prelude)
    assert done.returncode == 143
    assert env_file.read_text(encoding="utf-8") == before and leftovers(env_file.parent) == []


# ------------------------------------------------------------ the file itself


def test_a_symbolic_link_is_refused_for_changes_but_status_may_read_it(env_file):
    link = env_file.parent / "link.env"
    made = sh(f'ln -s "{env_file.as_posix()}" "{link.as_posix()}" && test -L "{link.as_posix()}"')
    if made.returncode != 0:
        pytest.skip("symbolic links are not available here")
    done = run(link, "switches", "off")
    assert done.returncode == 1 and "symbolic link" in done.stderr
    assert env_file.read_text(encoding="utf-8") == START and sh(f'test -L "{link.as_posix()}"').returncode == 0
    status = run(link, "status")
    assert status.returncode == 0 and "symbolic link" in status.stdout


def test_a_hard_linked_file_is_refused(env_file):
    twin = env_file.parent / "twin.env"
    made = sh(f'ln "{env_file.as_posix()}" "{twin.as_posix()}" && test "$(stat -c %h "{env_file.as_posix()}")" = 2')
    if made.returncode != 0:
        pytest.skip("hard links are not reported here")
    done = run(env_file, "switches", "off")
    assert done.returncode == 1 and "hard links" in done.stderr and env_file.read_text(encoding="utf-8") == START


def stat_says(**answers: str) -> str:
    """A stand-in for `stat -c <format>` that reports chosen modes / link counts, so the rules are tested the same on every platform."""
    return 'stat() { case "$2" in %a) echo "${FOLDER_MODE:-700}";; %h) echo "${LINKS:-1}";; *) command stat "$@";; esac; }; ' + "".join(f'{k}={v}; ' for k, v in answers.items())


@pytest.mark.parametrize("mode, allowed", [("700", True), ("755", True), ("775", False), ("777", False), ("1777", True), ("702", False)])
def test_a_folder_other_users_can_write_to_is_refused(env_file, mode, allowed):
    prelude = stat_says(FOLDER_MODE=mode)
    done = run(env_file, "switches", "off", terminal=True, prelude=prelude)
    if allowed:
        assert done.returncode == 0, done.stderr
    else:
        assert done.returncode == 1 and "can be written to by other users" in done.stderr and env_file.read_text(encoding="utf-8") == START


def test_a_file_with_several_hard_links_is_refused_whatever_the_platform(env_file):
    done = run(env_file, "switches", "off", terminal=True, prelude=stat_says(LINKS="2"))
    assert done.returncode == 1 and "2 hard links" in done.stderr and env_file.read_text(encoding="utf-8") == START


# ------------------------------------------------------------ one run at a time


def test_a_second_run_is_refused_while_another_is_alive_and_does_not_disturb_its_lock(env_file):
    holder = subprocess.Popen([BASH, "-c", "echo $$; sleep 30"], stdout=subprocess.PIPE, text=True)
    try:
        pid = holder.stdout.readline().strip()
        lock = Path(str(env_file) + ".cashfreectl.lock")
        lock.mkdir()
        (lock / "pid").write_text(pid + "\n", encoding="utf-8")
        done = run(env_file, "switches", "off")
        assert done.returncode == 1 and "another cashfreectl run is in progress" in done.stderr
        assert env_file.read_text(encoding="utf-8") == START
        assert lock.is_dir() and (lock / "pid").read_text(encoding="utf-8").strip() == pid  # the other run's lock is untouched
    finally:
        holder.kill()
        holder.wait()


def test_a_lock_left_by_a_dead_run_is_cleared(env_file):
    dead = subprocess.run([BASH, "-c", "echo $$"], capture_output=True, text=True).stdout.strip()
    lock = Path(str(env_file) + ".cashfreectl.lock")
    lock.mkdir()
    (lock / "pid").write_text(dead + "\n", encoding="utf-8")
    done = run(env_file, "switches", "off")
    assert done.returncode == 0 and "no longer running" in done.stderr
    assert leftovers(env_file.parent) == []


def test_several_runs_at_once_never_corrupt_the_file(env_file):
    procs = [
        subprocess.Popen([BASH, SCRIPT.as_posix(), "switches", "off"], env={**os.environ, "ENV_FILE": env_file.as_posix()}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(8)
    ]
    codes = []
    for p in procs:
        p.communicate(timeout=60)
        codes.append(p.returncode)
    assert set(codes) <= {0, 1} and 0 in codes
    content = lines(env_file)
    assert content.count("SMTP_PASSWORD=keep-me") == 1 and content.count("OTHER=1") == 1
    for name in ("CASHFREE_ENABLED=false", "CASHFREE_ALLOW_PRODUCTION=false", "CASHFREE_ENV=sandbox"):
        assert content.count(name) == 1
    assert leftovers(env_file.parent) == []
