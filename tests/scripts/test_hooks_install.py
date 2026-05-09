"""Tests for hooks/install.sh."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "hooks" / "install.sh"


def _fake_crontab(tmp_path: Path) -> Path:
    """Create a fake crontab command that stores its state in tmp_path."""
    state = tmp_path / "crontab.txt"
    script = tmp_path / "crontab"
    quoted_state = shlex.quote(str(state))
    script.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
state={quoted_state}
if [ "${{1:-}}" = "-l" ]; then
  if [ -f "$state" ]; then
    cat "$state"
    exit 0
  fi
  exit 1
fi
cp "$1" "$state"
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_install_help_lists_cron_option() -> None:
    """The installer exposes the optional cron installation flag."""
    result = subprocess.run(
        [str(INSTALL), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--install-cron" in result.stdout


def test_install_cron_is_idempotent_and_preserves_existing_entries(tmp_path: Path) -> None:
    """--install-cron replaces only the managed block and preserves user cron lines."""
    crontab = _fake_crontab(tmp_path)
    state = tmp_path / "crontab.txt"
    state.write_text("15 3 * * * echo keep-me\n", encoding="utf-8")

    env = os.environ.copy()
    env["PERSONALSCRAPER_CRONTAB_CMD"] = str(crontab)

    for _ in range(2):
        result = subprocess.run(
            [str(INSTALL), "--install-cron"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    content = state.read_text(encoding="utf-8")
    assert "15 3 * * * echo keep-me" in content
    assert content.count("# personalscraper coverage audit begin") == 1
    assert content.count("# personalscraper coverage audit end") == 1
    assert "scripts/coverage_audit_report.sh" in content
