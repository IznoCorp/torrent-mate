"""Tests for the ``health-check`` command helpers.

Covers the three anomaly detectors: daemon liveness (the pid=None phantom from
#216), recent log errors (with the benign-event allowlist + the lookback
window), and a stuck pipeline lock.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.commands import health_check as hc


class TestCheckDaemons:
    """_check_daemons flags a required daemon that is not truly running."""

    def _jlist(self, watch: dict) -> MagicMock:
        proc = MagicMock()
        proc.stdout = json.dumps([{"name": "personalscraper-watch", **watch}])
        return proc

    def test_healthy_daemon_no_anomaly(self) -> None:
        """Watch online with a real pid → no anomaly."""
        with patch("subprocess.run", return_value=self._jlist({"pid": 1234, "pm2_env": {"status": "online"}})):
            assert hc._check_daemons() == []

    def test_phantom_pid_none_flagged(self) -> None:
        """The #216 failure — online but pid=None → anomaly."""
        with patch("subprocess.run", return_value=self._jlist({"pid": None, "pm2_env": {"status": "online"}})):
            out = hc._check_daemons()
        assert len(out) == 1 and "pid=None" in out[0]

    def test_missing_daemon_flagged(self) -> None:
        """A required daemon absent from PM2 → anomaly."""
        proc = MagicMock()
        proc.stdout = "[]"
        with patch("subprocess.run", return_value=proc):
            out = hc._check_daemons()
        assert len(out) == 1 and "not registered" in out[0]

    def test_pm2_failure_reported_not_raised(self) -> None:
        """A pm2 invocation failure is reported, never raised."""
        with patch("subprocess.run", side_effect=OSError("no pm2")):
            out = hc._check_daemons()
        assert len(out) == 1 and "pm2 jlist failed" in out[0]


class TestCheckRecentErrors:
    """_check_recent_errors scans for recent error lines, skipping benign ones."""

    def _write_log(self, tmp_path: Path, lines: list[dict]) -> Path:
        p = tmp_path / "personalscraper.json"
        p.write_text("\n".join(json.dumps(x) for x in lines))
        return p

    def test_recent_error_flagged(self, tmp_path: Path) -> None:
        """An error line inside the window is reported."""
        from datetime import datetime

        now = datetime.now().isoformat()
        log = self._write_log(tmp_path, [{"level": "error", "event": "cli.failed.run", "timestamp": now}])
        with patch.object(hc, "LOGS_DIR", tmp_path):
            _ = log
            out = hc._check_recent_errors(90)
        assert any("cli.failed.run" in o for o in out)

    def test_benign_event_ignored(self, tmp_path: Path) -> None:
        """A benign event (macFUSE spotlight) is not an anomaly."""
        from datetime import datetime

        now = datetime.now().isoformat()
        self._write_log(
            tmp_path,
            [{"level": "error", "event": "indexer.spotlight.flag_ignored_macfuse", "timestamp": now}],
        )
        with patch.object(hc, "LOGS_DIR", tmp_path):
            assert hc._check_recent_errors(90) == []

    def test_old_error_outside_window_ignored(self, tmp_path: Path) -> None:
        """An error older than the lookback window is ignored."""
        from datetime import datetime, timedelta

        old = (datetime.now() - timedelta(hours=5)).isoformat()
        self._write_log(tmp_path, [{"level": "error", "event": "cli.failed.run", "timestamp": old}])
        with patch.object(hc, "LOGS_DIR", tmp_path):
            assert hc._check_recent_errors(90) == []

    def test_no_log_file_no_anomaly(self, tmp_path: Path) -> None:
        """No log file → no anomaly (fresh install)."""
        with patch.object(hc, "LOGS_DIR", tmp_path / "absent"):
            assert hc._check_recent_errors(90) == []


class TestCheckStuckLock:
    """_check_stuck_lock flags a held lock older than a run should take."""

    def test_held_and_old_flagged(self, tmp_path: Path) -> None:
        """A held lock older than max_run_minutes → anomaly."""
        import os
        import time

        lock = tmp_path / "pipeline.lock"
        lock.write_text("x")
        old = time.time() - 2 * 3600  # 2h ago
        os.utime(lock, (old, old))
        state = MagicMock()
        state.config.paths.data_dir = str(tmp_path)
        with patch("personalscraper.lock.is_lock_held", return_value=True):
            out = hc._check_stuck_lock(state, 60)
        assert len(out) == 1 and "stuck" in out[0]

    def test_not_held_no_anomaly(self, tmp_path: Path) -> None:
        """A lock file present but not held → no anomaly (stale, handled elsewhere)."""
        lock = tmp_path / "pipeline.lock"
        lock.write_text("x")
        state = MagicMock()
        state.config.paths.data_dir = str(tmp_path)
        with patch("personalscraper.lock.is_lock_held", return_value=False):
            assert hc._check_stuck_lock(state, 60) == []
