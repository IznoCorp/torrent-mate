"""Lock-file discipline of ``core.sqlite._lock.db_lock``.

The flock file is never unlinked (a second writer would lock a fresh inode while the first
still holds the old one); a held flock is always a refusal, whatever its sidecar says, and a
stale sidecar is judged only once the flock is held.
"""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.core.sqlite._lock import _read_pid, db_lock
from personalscraper.core.sqlite.errors import SqliteLockError
from personalscraper.indexer.scanner._checkpoint import _check_crash_resume

_DEAD_PID = 99999


def _paths(db_path: Path) -> tuple[Path, Path]:
    """Return the flock file and the metadata sidecar of ``db_path``."""
    return Path(str(db_path) + ".lock"), Path(str(db_path) + ".lock.json")


@contextmanager
def _foreign_holder(lock_path: Path) -> Iterator[None]:
    """Hold the flock the way another process would, without ever unlinking the file."""
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        yield
    finally:
        os.close(fd)


def _write_meta(meta_path: Path, pid: int) -> None:
    """Write a metadata sidecar naming ``pid`` as the holder."""
    meta_path.write_text(json.dumps({"pid": pid, "started_at": 0.0, "hostname": "test"}))


class TestFlockFileNeverUnlinked:
    """The flock file outlives every release and every recovery path."""

    def test_flock_file_persists_after_release(self, tmp_path: Path) -> None:
        """A clean exit removes the sidecar but leaves the flock file in place."""
        lock_path, meta_path = _paths(tmp_path / "library.db")

        with db_lock(tmp_path / "library.db"):
            assert lock_path.exists()

        assert lock_path.exists()
        assert not meta_path.exists()

    def test_stale_sidecar_does_not_unlink_a_held_flock(self, tmp_path: Path) -> None:
        """A holds the flock under a sidecar naming a dead pid: B is still refused."""
        db_path = tmp_path / "library.db"
        lock_path, meta_path = _paths(db_path)
        with _foreign_holder(lock_path):
            _write_meta(meta_path, _DEAD_PID)
            with pytest.raises(SqliteLockError):
                with db_lock(db_path, timeout=0.1):
                    pass

    def test_unreadable_holder_does_not_unlink_a_held_flock(self, tmp_path: Path) -> None:
        """A holds the flock before writing its sidecar: B is refused, not handed a new inode."""
        db_path = tmp_path / "library.db"
        lock_path, _ = _paths(db_path)
        with _foreign_holder(lock_path):
            with pytest.raises(SqliteLockError):
                with db_lock(db_path, timeout=0.1):
                    pass
            assert lock_path.exists()

    def test_flock_keeps_its_inode_across_acquisitions(self, tmp_path: Path) -> None:
        """Two successive holders lock the same inode."""
        db_path = tmp_path / "library.db"
        lock_path, _ = _paths(db_path)

        with db_lock(db_path):
            first = os.stat(lock_path).st_ino
        with db_lock(db_path):
            second = os.stat(lock_path).st_ino

        assert first == second


class TestStaleSidecarOrdering:
    """The stale sidecar is judged only once the flock is held."""

    def test_contender_never_removes_a_live_holders_sidecar(self, tmp_path: Path) -> None:
        """C reads a dead pid, then D takes the flock and writes its sidecar: D's sidecar survives."""
        db_path = tmp_path / "library.db"
        lock_path, meta_path = _paths(db_path)
        lock_path.touch()
        _write_meta(meta_path, _DEAD_PID)
        real_read_pid = _read_pid
        state: dict[str, int | None] = {"d_fd": None}

        def read_then_let_d_in(path: Path) -> int | None:
            pid = real_read_pid(path)
            if state["d_fd"] is None:
                # D slips in right after C's first read of the sidecar.
                fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    os.close(fd)  # C already holds the flock: D cannot slip in
                    state["d_fd"] = -1
                else:
                    state["d_fd"] = fd
                    _write_meta(meta_path, os.getppid())
            return pid

        try:
            with patch("personalscraper.core.sqlite._lock._read_pid", side_effect=read_then_let_d_in):
                try:
                    with db_lock(db_path, timeout=0):
                        pass
                except SqliteLockError:
                    pass
            if state["d_fd"] not in (None, -1):
                assert json.loads(meta_path.read_text())["pid"] == os.getppid()
        finally:
            if state["d_fd"] not in (None, -1):
                os.close(state["d_fd"])

    def test_stale_sidecar_over_a_free_flock_is_recovered(self, tmp_path: Path) -> None:
        """A crashed holder left its sidecar; the flock is free: acquired and the recovery is logged."""
        db_path = tmp_path / "library.db"
        lock_path, meta_path = _paths(db_path)
        lock_path.touch()
        _write_meta(meta_path, _DEAD_PID)

        with patch("personalscraper.core.sqlite._lock.log") as log:
            with db_lock(db_path):
                assert json.loads(meta_path.read_text())["pid"] == os.getpid()

        log.warning.assert_called_once_with("core.sqlite.lock.stale_recovered", stale_pid=_DEAD_PID)

    def test_refused_contender_does_not_log_a_recovery(self, tmp_path: Path) -> None:
        """While the flock is held, a dead-pid sidecar is no recovery: refusal, nothing logged."""
        db_path = tmp_path / "library.db"
        lock_path, meta_path = _paths(db_path)
        with _foreign_holder(lock_path):
            _write_meta(meta_path, _DEAD_PID)
            with patch("personalscraper.core.sqlite._lock.log") as log:
                with pytest.raises(SqliteLockError):
                    with db_lock(db_path, timeout=0):
                        pass
        log.warning.assert_not_called()


class TestPidProbe:
    """A held flock is a live holder, whatever a pid probe would say."""

    def test_permission_error_means_alive(self, tmp_path: Path) -> None:
        """A held flock is refused even when the pid probe is denied, naming the sidecar pid."""
        db_path = tmp_path / "library.db"
        lock_path, meta_path = _paths(db_path)
        with _foreign_holder(lock_path):
            _write_meta(meta_path, _DEAD_PID)
            seen: list[int] = []

            def factory(pid: int) -> BaseException:
                seen.append(pid)
                return SqliteLockError(f"held by {pid}")

            with patch("os.kill", side_effect=PermissionError("denied")):
                with pytest.raises(SqliteLockError):
                    with db_lock(db_path, timeout=0.1, error_factory=factory):
                        pass
            assert seen == [_DEAD_PID]
            assert meta_path.exists()

    def test_free_flock_over_vanished_pid_is_recovered(self, tmp_path: Path) -> None:
        """A sidecar naming a vanished pid over a free flock is recovered; the flock file stays."""
        db_path = tmp_path / "library.db"
        lock_path, meta_path = _paths(db_path)
        lock_path.touch()
        _write_meta(meta_path, _DEAD_PID)

        with patch("os.kill", side_effect=ProcessLookupError()):
            with db_lock(db_path, timeout=0.1):
                assert json.loads(meta_path.read_text())["pid"] == os.getpid()

        assert lock_path.exists()
        assert not meta_path.exists()


class TestPersistingFlockFileIsFree:
    """An empty, unlocked flock file reads as free."""

    def test_existing_unlocked_flock_file_is_acquired(self, tmp_path: Path) -> None:
        """Acquiring over a leftover flock file with no sidecar succeeds."""
        db_path = tmp_path / "library.db"
        lock_path, _ = _paths(db_path)
        lock_path.touch()

        with db_lock(db_path):
            pass

        assert lock_path.exists()

    def test_crash_resume_reads_a_released_lock_as_free(self, tmp_path: Path) -> None:
        """After a release the flock file persists; the scan still resumes (no live holder)."""
        db_path = tmp_path / "library.db"
        with db_lock(db_path):
            pass
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE scan_run (id INTEGER, started_at REAL, last_path TEXT, status TEXT)")
        conn.execute("INSERT INTO scan_run VALUES (1, 0.0, '/media/x', 'running')")

        assert _check_crash_resume(conn, db_path) == "/media/x"
