"""Lock-file discipline of ``core.sqlite._lock.db_lock``.

The flock file is never unlinked (a second writer would lock a fresh inode while the first
still holds the old one); a pid probe denied with ``PermissionError`` means the holder is
alive, only ``ProcessLookupError`` means gone.
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

from personalscraper.core.sqlite._lock import db_lock
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


class TestPidProbe:
    """Only ``ProcessLookupError`` reads as a dead holder."""

    def test_permission_error_means_alive(self, tmp_path: Path) -> None:
        """A denied probe is a live holder: the lock is refused, naming that pid."""
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

    def test_process_lookup_error_means_gone(self, tmp_path: Path) -> None:
        """A sidecar naming a vanished pid is recovered; the flock file stays."""
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
