"""Tests for the design-host staleness check in scripts/autodeploy-poll.sh.

The defect these exist for: `torrentmate-design` reads its MARKUP from the
source on every request and loads its PYTHON once, at boot. Renaming the login
form's fields therefore changed what the form sent without changing what the
running process read, and the operator was locked out with nothing in the logs.
Nothing could catch it — the rule suite starts `serve.py` fresh on a scratch
port, so a stale daemon is invisible to it by construction.

The poller is driven through `--design-only`, with `pm2` stubbed on PATH: the
stub answers `jlist` from a file the test writes and records every `restart`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

_POLLER = Path(__file__).resolve().parents[2] / "scripts" / "autodeploy-poll.sh"

_STUB = """#!/usr/bin/env bash
case "$1" in
  jlist) cat "$TM_TEST_JLIST" ;;
  restart) printf '%s\\n' "$2" >> "$TM_TEST_RESTARTS" ;;
esac
exit 0
"""


def _stub_pm2(tmp_path: Path) -> Path:
    """Writes an executable `pm2` stub and returns the directory holding it."""
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir(exist_ok=True)
    pm2 = stub_dir / "pm2"
    pm2.write_text(_STUB, encoding="utf-8")
    pm2.chmod(0o755)
    return stub_dir


def _listing(script: Path, started_ms: int, status: str = "online") -> list[dict]:
    """Builds a `pm2 jlist` payload for the design app."""
    return [
        {"name": "torrentmate-web", "pm2_env": {"status": "online"}},
        {
            "name": "torrentmate-design",
            "pm2_env": {
                "status": status,
                "pm_exec_path": str(script),
                "pm_uptime": started_ms,
            },
        },
    ]


def _run(tmp_path: Path, jlist: object) -> tuple[int, list[str], str]:
    """Runs the poller's design check and returns (code, restarts, output)."""
    jlist_file = tmp_path / "jlist.json"
    jlist_file.write_text(jlist if isinstance(jlist, str) else json.dumps(jlist), encoding="utf-8")
    restarts = tmp_path / "restarts.txt"
    env = {
        **os.environ,
        "PATH": f"{_stub_pm2(tmp_path)}{os.pathsep}{os.environ['PATH']}",
        "TM_TEST_JLIST": str(jlist_file),
        "TM_TEST_RESTARTS": str(restarts),
    }
    done = subprocess.run(
        ["bash", str(_POLLER), "--design-only"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    recorded = restarts.read_text(encoding="utf-8").split() if restarts.exists() else []
    return done.returncode, recorded, done.stdout + done.stderr


def _served(tmp_path: Path, age_seconds: int) -> Path:
    """Writes a stand-in `serve.py` whose mtime is `age_seconds` in the past."""
    script = tmp_path / "serve.py"
    script.write_text("# stand-in\n", encoding="utf-8")
    when = time.time() - age_seconds
    os.utime(script, (when, when))
    return script


def test_restarts_when_the_script_changed_after_boot(tmp_path: Path) -> None:
    """The defect itself: serve.py edited while the process kept running."""
    script = _served(tmp_path, age_seconds=10)
    booted_ms = int((time.time() - 3600) * 1000)
    code, restarts, output = _run(tmp_path, _listing(script, booted_ms))
    assert code == 0, output
    assert restarts == ["torrentmate-design"], output


def test_leaves_a_process_newer_than_its_script_alone(tmp_path: Path) -> None:
    """A process booted after the last edit is current — restarting it is noise."""
    script = _served(tmp_path, age_seconds=3600)
    booted_ms = int((time.time() - 10) * 1000)
    code, restarts, output = _run(tmp_path, _listing(script, booted_ms))
    assert code == 0, output
    assert restarts == [], output


def test_does_not_restart_twice_for_one_edit(tmp_path: Path) -> None:
    """After a restart the process is newer than the file, so the loop settles.

    A check that restarted on equality would fire on every pass forever, which
    is worse than the defect it fixes.
    """
    script = _served(tmp_path, age_seconds=0)
    restarted_ms = int(time.time() * 1000)
    code, restarts, output = _run(tmp_path, _listing(script, restarted_ms))
    assert code == 0, output
    assert restarts == [], output


def test_ignores_a_stopped_app(tmp_path: Path) -> None:
    """A stopped app is the operator's decision; the poller does not undo it."""
    script = _served(tmp_path, age_seconds=10)
    booted_ms = int((time.time() - 3600) * 1000)
    code, restarts, output = _run(tmp_path, _listing(script, booted_ms, status="stopped"))
    assert code == 0, output
    assert restarts == [], output


def test_survives_unusable_pm2_output(tmp_path: Path) -> None:
    """Garbage from `pm2 jlist` is fail-soft, exactly like every other pass."""
    code, restarts, output = _run(tmp_path, "not json at all")
    assert code == 0, output
    assert restarts == [], output


def test_survives_a_missing_script(tmp_path: Path) -> None:
    """A path pm2 reports but the filesystem does not have is named, not fatal."""
    booted_ms = int((time.time() - 3600) * 1000)
    code, restarts, output = _run(tmp_path, _listing(tmp_path / "gone.py", booted_ms))
    assert code == 0, output
    assert restarts == [], output


def test_survives_pm2_being_absent(tmp_path: Path) -> None:
    """No pm2 on PATH at all — the poller must not die on the design check."""
    bare = tmp_path / "bare"
    bare.mkdir()
    for tool in ("bash", "python3", "stat", "cat", "date", "printf"):
        found = shutil.which(tool)
        if found:
            (bare / tool).symlink_to(found)
    done = subprocess.run(
        ["bash", str(_POLLER), "--design-only"],
        env={"PATH": str(bare), "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stdout + done.stderr
