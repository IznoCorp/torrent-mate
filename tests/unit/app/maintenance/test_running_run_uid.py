"""``running_run_uid`` / ``running_run``: the live run the duplicate guard sees, read for a caller that joins it."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.errors import AppConflict
from personalscraper.app.maintenance import service as maintenance_service
from personalscraper.app.maintenance.registry import REGISTRY, MaintenanceAction, canonical_options_json
from personalscraper.app.maintenance.service import LaunchedRun, launch_action, running_run, running_run_uid
from personalscraper.indexer.db import apply_migrations

_MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "personalscraper" / "indexer" / "migrations"
_UID = "c" * 32
_OPTIONS = {"item_id": 7}


@pytest.fixture
def action() -> MaintenanceAction:
    """The per-medium rescrape, the action the library joins.

    Returns:
        The registry action.
    """
    (found,) = [a for a in REGISTRY if a.id == "library-rescrape-item"]
    return found


@pytest.fixture
def db_path(tmp_path: Path, action: MaintenanceAction) -> Iterator[Path]:
    """A migrated ``library.db`` holding one reserved ``running`` run of the action.

    Args:
        tmp_path: Pytest's temporary directory.
        action: The action the run is of.

    Yields:
        The database's path.
    """
    path = tmp_path / "library.db"
    conn = sqlite3.connect(path, isolation_level=None)
    apply_migrations(conn, _MIGRATIONS_DIR)
    conn.close()
    maintenance_service._reserve_run_row(
        path,
        run_uid=_UID,
        action=action,
        command=action.id,
        options_json=canonical_options_json(_OPTIONS),
        dry_run=False,
    )
    yield path


def _set_pid(db_path: Path, pid: int | None) -> None:
    """Give the reserved run another pid.

    Args:
        db_path: ``library.db``.
        pid: The pid, or ``None`` for a row that never claimed one.
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE pipeline_run SET pid=? WHERE run_uid=?", (pid, _UID))


def test_a_live_run_is_named(db_path: Path, action: MaintenanceAction) -> None:
    """A running row whose pid lives: its uid."""
    assert running_run_uid(action, _OPTIONS, db_path=db_path) == _UID


def test_an_absent_database_names_none(tmp_path: Path, action: MaintenanceAction) -> None:
    """No ``library.db``: no run, and no database is created by the read."""
    assert running_run_uid(action, _OPTIONS, db_path=tmp_path / "library.db") is None
    assert not (tmp_path / "library.db").exists()


def test_a_dead_pid_names_none(db_path: Path, action: MaintenanceAction, monkeypatch: pytest.MonkeyPatch) -> None:
    """A running row whose process is gone is stale: none."""

    def gone(pid: int, signal: int) -> None:
        """Answer as for a process that no longer exists."""
        raise ProcessLookupError(pid)

    monkeypatch.setattr(maintenance_service.os, "kill", gone)

    assert running_run_uid(action, _OPTIONS, db_path=db_path) is None


def test_a_null_pid_names_none(db_path: Path, action: MaintenanceAction) -> None:
    """A running row that never claimed a pid is stale: none."""
    _set_pid(db_path, None)

    assert running_run_uid(action, _OPTIONS, db_path=db_path) is None


def test_a_pid_of_another_user_is_alive_and_still_refuses_a_second_launch(
    db_path: Path, action: MaintenanceAction, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``os.kill`` refused for permission: the process lives, its uid is named and the guard still refuses."""
    _set_pid(db_path, os.getpid())

    def foreign(pid: int, signal: int) -> None:
        """Answer as for a process another user owns."""
        raise PermissionError(pid)

    monkeypatch.setattr(maintenance_service.os, "kill", foreign)
    monkeypatch.setattr(maintenance_service, "_spawn_runner", lambda *args: pytest.fail("nothing may spawn"))

    assert running_run_uid(action, _OPTIONS, db_path=db_path) == _UID
    with pytest.raises(AppConflict):
        launch_action(action, _OPTIONS, db_path=db_path, data_dir=db_path.parent)


@pytest.mark.parametrize(("status", "queued"), [("waiting_pipeline_lock", True), ("done", False)])
def test_the_run_s_own_queue_step_says_whether_it_waits(
    db_path: Path, action: MaintenanceAction, status: str, queued: bool
) -> None:
    """Once the runner wrote its ``queue`` step, its last status answers, whoever holds the lock."""
    steps = [{"name": "queue", "started_at": 1.0, "ended_at": 1.0, "status": status}]
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE pipeline_run SET steps_json=? WHERE run_uid=?", (json.dumps(steps), _UID))
    (db_path.parent / "pipeline.lock").write_text(str(os.getppid()))

    assert running_run(action, _OPTIONS, db_path=db_path, data_dir=db_path.parent) == LaunchedRun(
        run_uid=_UID, queued=queued
    )
