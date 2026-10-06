"""Tests for `scripts/start-preprod.sh`, the PM2 step of a staging deploy.

The real script runs in a copy of the repository's `scripts/` with a FAKE `pm2` first on
`PATH` (it logs its arguments and answers `jlist` from a file) and a stub precondition
check (it prints what the test says is missing). Nothing reaches the machine's PM2.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.indexer.test_ecosystem import _PREPROD_APP_NAMES

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "start-preprod.sh"
WEB = "torrentmate-web-staging"

_FAKE_PM2 = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$PM2_LOG"
if [ "$1" = "jlist" ]; then cat "$PM2_JLIST"; exit 0; fi
if [ "$1" = "startOrRestart" ] && [ -n "${PM2_FAIL_START:-}" ]; then
  echo "[PM2][ERROR] File ecosystem.config.js malformated" >&2
  exit 1
fi
exit 0
"""

# Stands in for scripts/preprod_preconditions.py: prints the lines PREPROD_MISSING holds.
_STUB_CHECK = """import os, sys
missing = [line for line in os.environ.get("PREPROD_MISSING", "").split("|") if line]
for line in missing:
    print(line)
sys.exit(1 if missing else 0)
"""


def _jlist(web_env: dict[str, str] | None) -> str:
    """Render what `pm2 jlist` prints.

    Args:
        web_env: The stored env of the staging web; ``None`` when it is not registered.

    Returns:
        The JSON list of processes.
    """
    apps = [{"name": "torrentmate-web", "pm2_env": {"env": {"PERSONALSCRAPER_CONFIG": "/x"}}}]
    if web_env is not None:
        apps.append({"name": WEB, "pm2_env": {"env": web_env}})
    return json.dumps(apps)


def _run(
    tmp_path: Path,
    *,
    missing: tuple[str, ...] = (),
    web_env: dict[str, str] | None = None,
    fail_start: bool = False,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run the real script against a fake pm2 and a stub precondition check.

    Args:
        tmp_path: Pytest tmp_path fixture value.
        missing: The preconditions the stub reports missing.
        web_env: The staging web's stored env in `pm2 jlist`; ``None`` when unregistered.
        fail_start: Make `pm2 startOrRestart` fail.

    Returns:
        The completed run and the pm2 command lines it issued, in order.
    """
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "scripts" / SCRIPT.name)
    (repo / "scripts" / "preprod_preconditions.py").write_text(_STUB_CHECK, encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    pm2 = bin_dir / "pm2"
    pm2.write_text(_FAKE_PM2, encoding="utf-8")
    pm2.chmod(0o755)
    jlist = tmp_path / "jlist.json"
    jlist.write_text(_jlist(web_env), encoding="utf-8")
    log = tmp_path / "pm2.log"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path / "home"),
        "PM2_LOG": str(log),
        "PM2_JLIST": str(jlist),
        "PREPROD_MISSING": "|".join(missing),
    }
    if fail_start:
        env["PM2_FAIL_START"] = "1"
    done = subprocess.run(
        ["bash", str(repo / "scripts" / SCRIPT.name), sys.executable],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return done, calls


def _started(calls: list[str]) -> set[str]:
    """Read the app names the run passed to `pm2 startOrRestart ... --only`.

    Args:
        calls: The pm2 command lines of a run.

    Returns:
        The app names started or restarted.
    """
    starts = [c for c in calls if c.startswith("startOrRestart ")]
    assert len(starts) == 1, calls
    words = starts[0].split()
    return set(words[words.index("--only") + 1].split(","))


def test_every_preprod_app_starts_when_the_preprod_is_set_up(tmp_path: Path) -> None:
    """Every precondition holds: the web and every preprod job start, nothing of prod's."""
    done, calls = _run(tmp_path)
    assert done.returncode == 0, done.stderr
    assert _started(calls) == _PREPROD_APP_NAMES
    assert "--update-env" in next(c for c in calls if c.startswith("startOrRestart "))


@pytest.mark.parametrize(
    "missing",
    [
        "the preprod overlay /h/.torrentmate/config-staging does not exist",
        "the preprod secrets file /h/.torrentmate/.env-staging does not exist",
        "the preprod overlay /h/c does not load in 'staging': /h/d/.tm-environment names 'dev'",
        "sandbox root /Volumes/Disk3/tm-preprod has no .tm-preprod-root marker",
    ],
)
def test_a_missing_precondition_starts_the_web_alone_and_says_which(tmp_path: Path, missing: str) -> None:
    """A precondition missing: only the web restarts, and the deploy says loudly which.

    Args:
        tmp_path: Pytest tmp_path fixture value.
        missing: The precondition the check reports missing.
    """
    done, calls = _run(tmp_path, missing=(missing,))
    assert done.returncode == 0, done.stderr
    assert _started(calls) == {WEB}
    assert missing in done.stderr
    assert "NOT STARTED" in done.stderr


def test_a_failed_start_is_reported_with_pm2s_own_words(tmp_path: Path) -> None:
    """`pm2 startOrRestart` failing is reported with its output, never swallowed."""
    done, _ = _run(tmp_path, fail_start=True)
    assert "malformated" in done.stderr
    assert "startOrRestart" in done.stderr


def test_a_stored_read_only_role_deletes_the_web_before_it_starts(tmp_path: Path) -> None:
    """The web's stored env still carries PERSONALSCRAPER_WEB_ROLE: it is deleted, then started.

    PM2 merges the file's env into the stored one on `--update-env`, so a key the file no
    longer sets survives a restart; only a delete clears it.
    """
    done, calls = _run(tmp_path, web_env={"PERSONALSCRAPER_WEB_ROLE": "staging", "PERSONALSCRAPER_CONFIG": "/x"})
    assert done.returncode == 0, done.stderr
    assert f"delete {WEB}" in calls
    assert calls.index(f"delete {WEB}") < next(i for i, c in enumerate(calls) if c.startswith("startOrRestart "))
    assert "PERSONALSCRAPER_WEB_ROLE" in done.stdout + done.stderr


@pytest.mark.parametrize("web_env", [None, {"PERSONALSCRAPER_ENV": "staging"}])
def test_a_web_without_the_role_is_never_deleted(tmp_path: Path, web_env: dict[str, str] | None) -> None:
    """An unregistered web, or one already re-pointed, is restarted in place — never deleted.

    Args:
        tmp_path: Pytest tmp_path fixture value.
        web_env: The web's stored env; ``None`` when it is not registered.
    """
    done, calls = _run(tmp_path, web_env=web_env)
    assert done.returncode == 0, done.stderr
    assert not [c for c in calls if c.startswith("delete")]


def test_the_staging_deploy_runs_this_step_with_its_venv() -> None:
    """`deploy-staging.sh` hands the PM2 step to this script, with the staging venv's python."""
    text = (ROOT / "scripts" / "deploy-staging.sh").read_text(encoding="utf-8")
    assert 'scripts/start-preprod.sh "$VENV/bin/python"' in text
    assert "pm2 startOrRestart" not in text
