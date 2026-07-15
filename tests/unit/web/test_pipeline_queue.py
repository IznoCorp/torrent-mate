"""Unit tests for the queued pipeline launch (``web/pipeline_queue.py``, §6).

``POST /api/pipeline/run`` queues visibly when a maintenance run holds the
lock: an atomically reserved ``pipeline-queue`` row plus a detached waiter
that hands over to ``spawn_pipeline_run`` once the lock frees.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from personalscraper.web.pipeline_queue import (
    PIPELINE_QUEUE_COMMAND,
    _canonical_options,
    main,
    reserve_queued_pipeline_run,
)


def _create_db(db_path: Path) -> None:
    """Create a minimal ``pipeline_run`` table mirroring migrations 011+012.

    Args:
        db_path: Where to create the SQLite file.
    """
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE pipeline_run (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_uid      TEXT UNIQUE NOT NULL,
            trigger      TEXT,
            dry_run      INTEGER NOT NULL DEFAULT 0,
            started_at   REAL NOT NULL,
            ended_at     REAL,
            outcome      TEXT,
            steps_json   TEXT,
            error        TEXT,
            pid          INTEGER,
            kind         TEXT NOT NULL DEFAULT 'pipeline',
            command      TEXT,
            options_json TEXT,
            output_tail  TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def _rows(db_path: Path) -> list[dict[str, object]]:
    """Return all ``pipeline_run`` rows as dicts.

    Args:
        db_path: The SQLite file to read.

    Returns:
        One dict per row.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM pipeline_run").fetchall()]
    conn.close()
    return rows


class TestReserve:
    """Atomic reservation of the queue row."""

    def test_reserves_row_and_spawns_waiter(self, tmp_path: Path) -> None:
        """A fresh reserve inserts the running queue row and spawns the waiter."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)

        with patch("personalscraper.web.pipeline_queue.subprocess.Popen") as mock_popen:
            mock_popen.return_value.pid = 4242
            run_uid = reserve_queued_pipeline_run(db_path, trigger_reason="web", dry_run=False)

        rows = _rows(db_path)
        assert len(rows) == 1
        row = rows[0]
        assert row["run_uid"] == run_uid
        assert row["kind"] == "maintenance"
        assert row["command"] == PIPELINE_QUEUE_COMMAND
        assert row["outcome"] == "running"
        assert row["options_json"] == _canonical_options("web", False)
        assert row["pid"] == 4242
        argv = mock_popen.call_args[0][0]
        assert argv[-2:] == ["-m", "personalscraper.web.pipeline_queue"]
        env = mock_popen.call_args.kwargs["env"]
        assert env["PERSONALSCRAPER_RUN_UID"] == run_uid
        assert env["PERSONALSCRAPER_PQ_DRY_RUN"] == "0"

    def test_duplicate_live_queue_row_returns_409(self, tmp_path: Path) -> None:
        """A live identical queued launch refuses with the French duplicate detail."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO pipeline_run (run_uid, trigger, dry_run, started_at, outcome, "
            "steps_json, pid, kind, command, options_json) "
            "VALUES ('queued1', 'web', 0, 1000.0, 'running', '[]', ?, 'maintenance', ?, ?)",
            (os.getpid(), PIPELINE_QUEUE_COMMAND, _canonical_options("web", False)),
        )
        conn.commit()
        conn.close()

        with (
            patch("personalscraper.web.pipeline_queue.subprocess.Popen") as mock_popen,
            pytest.raises(HTTPException) as exc_info,
        ):
            reserve_queued_pipeline_run(db_path, trigger_reason="web", dry_run=False)
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Un lancement du pipeline est déjà en file d'attente (doublon)."
        mock_popen.assert_not_called()
        assert len(_rows(db_path)) == 1

    def test_stale_dead_pid_row_is_ignored(self, tmp_path: Path) -> None:
        """A queued row with a dead pid is stale — a new reserve proceeds."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO pipeline_run (run_uid, trigger, dry_run, started_at, outcome, "
            "steps_json, pid, kind, command, options_json) "
            "VALUES ('stale1', 'web', 0, 1000.0, 'running', '[]', 99999, 'maintenance', ?, ?)",
            (PIPELINE_QUEUE_COMMAND, _canonical_options("web", False)),
        )
        conn.commit()
        conn.close()

        with patch("personalscraper.web.pipeline_queue.subprocess.Popen") as mock_popen:
            mock_popen.return_value.pid = 4242
            run_uid = reserve_queued_pipeline_run(db_path, trigger_reason="web", dry_run=False)
        assert run_uid
        assert len(_rows(db_path)) == 2

    def test_db_error_fails_closed_409(self, tmp_path: Path) -> None:
        """A missing table fails closed with the French cannot-verify detail."""
        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE unrelated (x INTEGER)")
        conn.commit()
        conn.close()

        with pytest.raises(HTTPException) as exc_info:
            reserve_queued_pipeline_run(db_path, trigger_reason="web", dry_run=False)
        assert exc_info.value.status_code == 409
        assert "vérifier" in exc_info.value.detail


class TestWaiterMain:
    """The detached waiter hands over to the single trigger authority."""

    def _env(self, monkeypatch: pytest.MonkeyPatch, run_uid: str) -> None:
        """Set the waiter's mandatory env vars.

        Args:
            monkeypatch: The pytest monkeypatch fixture.
            run_uid: The reserved queue row uid.
        """
        monkeypatch.setenv("PERSONALSCRAPER_RUN_UID", run_uid)
        monkeypatch.setenv("PERSONALSCRAPER_PQ_TRIGGER_REASON", "web")
        monkeypatch.setenv("PERSONALSCRAPER_PQ_DRY_RUN", "0")

    def _config(self, tmp_path: Path, db_path: Path) -> MagicMock:
        """Build a minimal config double for the waiter.

        Args:
            tmp_path: The test's temp dir (data_dir).
            db_path: The library DB path.

        Returns:
            A config-shaped MagicMock.
        """
        config = MagicMock()
        config.indexer.db_path = db_path
        config.paths.data_dir = tmp_path
        return config

    def test_hands_over_when_lock_free(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Lock free → spawn_pipeline_run called, queue row finalized success."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO pipeline_run (run_uid, trigger, dry_run, started_at, outcome, "
            "steps_json, pid, kind, command, options_json) "
            "VALUES ('qrow1', 'web', 0, 1000.0, 'running', '[]', 1, 'maintenance', ?, ?)",
            (PIPELINE_QUEUE_COMMAND, _canonical_options("web", False)),
        )
        conn.commit()
        conn.close()
        self._env(monkeypatch, "qrow1")

        with (
            patch("personalscraper.web.pipeline_queue.load_config", return_value=self._config(tmp_path, db_path)),
            patch("personalscraper.web.pipeline_queue.is_lock_held", return_value=False),
            patch(
                "personalscraper.web.pipeline_trigger.spawn_pipeline_run",
                return_value="realrun1",
            ) as mock_spawn,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 0
        mock_spawn.assert_called_once_with(tmp_path, trigger_reason="web", dry_run=False)
        row = _rows(db_path)[0]
        assert row["outcome"] == "success"
        assert "realrun1" in str(row["output_tail"])

    def test_lost_race_requeues_then_hands_over(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Spawn returns None once (lost race) → paced re-queue → hand-over."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO pipeline_run (run_uid, trigger, dry_run, started_at, outcome, "
            "steps_json, pid, kind, command, options_json) "
            "VALUES ('qrow2', 'web', 0, 1000.0, 'running', '[]', 1, 'maintenance', ?, ?)",
            (PIPELINE_QUEUE_COMMAND, _canonical_options("web", False)),
        )
        conn.commit()
        conn.close()
        self._env(monkeypatch, "qrow2")

        with (
            patch("personalscraper.web.pipeline_queue.load_config", return_value=self._config(tmp_path, db_path)),
            patch("personalscraper.web.pipeline_queue.is_lock_held", return_value=False),
            patch("personalscraper.web.pipeline_queue.time.sleep"),
            patch(
                "personalscraper.web.pipeline_trigger.spawn_pipeline_run",
                side_effect=[None, "realrun2"],
            ) as mock_spawn,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 0
        assert mock_spawn.call_count == 2
        assert _rows(db_path)[0]["outcome"] == "success"
