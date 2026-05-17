"""Unit tests for personalscraper.indexer.db.

Covers PRAGMA configuration, writer-lock lifecycle, stale-lock recovery,
live-lock blocking, malformed-DB quarantine, disk-full pre-checks, and the
mid-scan disk-full WAL checkpoint flow.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer._disk_guard import handle_disk_full
from personalscraper.indexer.db import (
    IndexerCorruptError,
    IndexerDiskFullError,
    IndexerLockError,
    check_free_space,
    indexer_lock,
    open_db,
)

# ---------------------------------------------------------------------------
# PRAGMA assertions
# ---------------------------------------------------------------------------


class TestOpenDbPragmas:
    """open_db sets all required PRAGMAs on a fresh file-based DB."""

    def test_wal_mode(self, tmp_path: Path) -> None:
        """journal_mode is set to WAL."""
        db_path = tmp_path / "test.db"
        conn = open_db(db_path, event_bus=EventBus())
        row = conn.execute("PRAGMA journal_mode").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "wal"

    def test_synchronous_normal(self, tmp_path: Path) -> None:
        """Synchronous is 1 (NORMAL)."""
        db_path = tmp_path / "test.db"
        conn = open_db(db_path, event_bus=EventBus())
        row = conn.execute("PRAGMA synchronous").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 1  # 1 = NORMAL

    def test_temp_store_memory(self, tmp_path: Path) -> None:
        """temp_store is 2 (MEMORY)."""
        db_path = tmp_path / "test.db"
        conn = open_db(db_path, event_bus=EventBus())
        row = conn.execute("PRAGMA temp_store").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 2  # 2 = MEMORY

    def test_cache_size(self, tmp_path: Path) -> None:
        """cache_size is -65536 (64 MB in kibibytes)."""
        db_path = tmp_path / "test.db"
        conn = open_db(db_path, event_bus=EventBus())
        row = conn.execute("PRAGMA cache_size").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == -65536

    def test_mmap_size(self, tmp_path: Path) -> None:
        """mmap_size is 268435456 (256 MB)."""
        db_path = tmp_path / "test.db"
        conn = open_db(db_path, event_bus=EventBus())
        row = conn.execute("PRAGMA mmap_size").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 268435456

    def test_wal_autocheckpoint(self, tmp_path: Path) -> None:
        """wal_autocheckpoint is 1000."""
        db_path = tmp_path / "test.db"
        conn = open_db(db_path, event_bus=EventBus())
        row = conn.execute("PRAGMA wal_autocheckpoint").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 1000

    def test_busy_timeout(self, tmp_path: Path) -> None:
        """busy_timeout is 5000 ms."""
        db_path = tmp_path / "test.db"
        conn = open_db(db_path, event_bus=EventBus())
        row = conn.execute("PRAGMA busy_timeout").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 5000

    def test_foreign_keys_on(self, tmp_path: Path) -> None:
        """foreign_keys is ON (1)."""
        db_path = tmp_path / "test.db"
        conn = open_db(db_path, event_bus=EventBus())
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 1


# ---------------------------------------------------------------------------
# Writer lock — normal lifecycle
# ---------------------------------------------------------------------------


class TestIndexerLockLifecycle:
    """Verify lock acquire / release and lockfile cleanup."""

    def test_lock_acquired_and_released(self, tmp_path: Path) -> None:
        """Lock is held inside the context and both lock files removed after exit."""
        db_path = tmp_path / "library.db"
        lock_path = Path(str(db_path) + ".lock")
        meta_path = Path(str(db_path) + ".lock.json")

        with indexer_lock(db_path):
            # FileLock file and metadata sidecar must exist while held
            assert lock_path.exists()
            assert meta_path.exists()

        assert not lock_path.exists()
        assert not meta_path.exists()

    def test_lockfile_contains_pid_and_hostname(self, tmp_path: Path) -> None:
        """Metadata sidecar JSON contains current pid and hostname."""
        db_path = tmp_path / "library.db"
        meta_path = Path(str(db_path) + ".lock.json")

        with indexer_lock(db_path):
            data = json.loads(meta_path.read_text())
            assert data["pid"] == os.getpid()
            assert "hostname" in data
            assert "started_at" in data


# ---------------------------------------------------------------------------
# Stale lock recovery
# ---------------------------------------------------------------------------


class TestStaleLockRecovery:
    """A lockfile referencing a dead PID should be recovered transparently."""

    def test_stale_lock_recovered(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """When lockfile PID is dead (os.kill raises OSError), lock is broken and acquired."""
        import logging

        db_path = tmp_path / "library.db"
        lock_path = Path(str(db_path) + ".lock")
        meta_path = Path(str(db_path) + ".lock.json")

        dead_pid = 99999
        # Write stale metadata sidecar (simulates a previous holder that crashed)
        meta_path.write_text(json.dumps({"pid": dead_pid, "started_at": 0.0, "hostname": "test"}))
        # Write the FileLock file too so FileLock sees it as held
        lock_path.touch()

        with caplog.at_level(logging.WARNING):
            with patch("os.kill", side_effect=OSError("no such process")):
                with indexer_lock(db_path, timeout=0.1):
                    pass  # Should succeed after stale recovery

        assert not lock_path.exists()
        assert not meta_path.exists()

        # structlog passes a dict as record.msg; check the "event" key
        def _has_structlog_event(event: str) -> bool:
            for rec in caplog.records:
                msg = rec.msg
                if isinstance(msg, dict) and msg.get("event") == event:
                    return True
                # Fallback: formatted string may contain the event name
                if isinstance(msg, str) and event in msg:
                    return True
            return False

        assert _has_structlog_event("indexer.lock.stale_recovered"), (
            f"Expected 'indexer.lock.stale_recovered' in caplog; got: {[r.msg for r in caplog.records]}"
        )


# ---------------------------------------------------------------------------
# Live lock blocks
# ---------------------------------------------------------------------------


class TestLiveLockBlocking:
    """A lockfile referencing a live PID must raise IndexerLockError."""

    def test_live_lock_raises(self, tmp_path: Path) -> None:
        """IndexerLockError raised when lock is held by a live process."""
        db_path = tmp_path / "library.db"
        lock_path = Path(str(db_path) + ".lock")
        meta_path = Path(str(db_path) + ".lock.json")

        live_pid = os.getpid()  # current process — definitely alive
        # Write metadata sidecar with live PID
        meta_path.write_text(json.dumps({"pid": live_pid, "started_at": 0.0, "hostname": "test"}))

        # Use FileLock to hold the OS-level lock, then attempt a second acquire
        from filelock import FileLock as _FL

        outer = _FL(str(lock_path))
        outer.acquire()
        try:
            with pytest.raises(IndexerLockError) as exc_info:
                with indexer_lock(db_path, timeout=0.1):
                    pass
            assert exc_info.value.pid == live_pid
        finally:
            outer.release()
            for p in (lock_path, meta_path):
                p.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Malformed DB quarantine
# ---------------------------------------------------------------------------


class TestMalformedDbQuarantine:
    """A corrupt DB file is quarantined and IndexerCorruptError is raised."""

    def test_corrupt_db_quarantined(self, tmp_path: Path) -> None:
        """Garbage bytes in a .db file trigger quarantine and IndexerCorruptError."""
        db_path = tmp_path / "library.db"
        # Write a SQLite header magic followed by garbage to trigger malformed error
        db_path.write_bytes(b"SQLite format 3\x00" + b"\xff" * 100)

        with pytest.raises(IndexerCorruptError) as exc_info:
            open_db(db_path, event_bus=EventBus())

        assert exc_info.value.db_path == db_path
        quarantine = exc_info.value.quarantine_path
        assert quarantine.exists(), "Quarantine file must exist"
        assert ".corrupt-" in quarantine.name

    def test_corrupt_db_not_reopened_without_rebuild(self, tmp_path: Path) -> None:
        """open_db does not create a fresh DB after quarantine unless rebuild=True."""
        db_path = tmp_path / "library.db"
        db_path.write_bytes(b"SQLite format 3\x00" + b"\xff" * 100)

        with pytest.raises(IndexerCorruptError):
            open_db(db_path, event_bus=EventBus())

        # db_path has been renamed; no fresh DB should exist yet
        assert not db_path.exists()

    def test_corrupt_db_rebuild_creates_fresh_db(self, tmp_path: Path) -> None:
        """With rebuild=True, a fresh DB is opened after quarantine."""
        db_path = tmp_path / "library.db"
        db_path.write_bytes(b"SQLite format 3\x00" + b"\xff" * 100)

        conn = open_db(db_path, rebuild=True, event_bus=EventBus())
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            assert row is not None
            assert row[0] == "ok"
        finally:
            conn.close()

        # Quarantine file must still exist
        quarantine_files = list(tmp_path.glob("library.db.corrupt-*"))
        assert len(quarantine_files) == 1


# ---------------------------------------------------------------------------
# Disk-full pre-check
# ---------------------------------------------------------------------------


class TestDiskFullPreCheck:
    """check_free_space raises IndexerDiskFullError when free space is insufficient."""

    def test_insufficient_free_space(self, tmp_path: Path) -> None:
        """Mock statvfs returning tiny free space raises IndexerDiskFullError."""
        db_path = tmp_path / "library.db"

        fake_stat = MagicMock()
        fake_stat.f_frsize = 4096
        fake_stat.f_bavail = 1  # 4096 bytes free

        expected_growth = 10_000  # requires 20_000 bytes → fail

        with patch("os.statvfs", return_value=fake_stat):
            with pytest.raises(IndexerDiskFullError) as exc_info:
                check_free_space(db_path, expected_growth, event_bus=EventBus())

        assert exc_info.value.free_bytes == 4096
        assert exc_info.value.required_bytes == 20_000

    def test_open_db_calls_check_free_space_when_growth_given(self, tmp_path: Path) -> None:
        """open_db raises IndexerDiskFullError before opening SQLite when space is low."""
        db_path = tmp_path / "library.db"

        fake_stat = MagicMock()
        fake_stat.f_frsize = 4096
        fake_stat.f_bavail = 1  # 4096 bytes free

        with patch("os.statvfs", return_value=fake_stat):
            with pytest.raises(IndexerDiskFullError):
                open_db(db_path, expected_growth_bytes=100_000, event_bus=EventBus())

        # The DB file must NOT have been created
        assert not db_path.exists()


# ---------------------------------------------------------------------------
# Mid-scan disk-full: wal_checkpoint(TRUNCATE) invoked
# ---------------------------------------------------------------------------


class TestHandleDiskFull:
    """handle_disk_full issues PRAGMA wal_checkpoint(TRUNCATE) on disk-full errors."""

    def test_checkpoint_called_and_disk_full_raised(self, tmp_path: Path) -> None:
        """wal_checkpoint(TRUNCATE) runs and IndexerDiskFullError is raised.

        sqlite3.Connection is an immutable C type whose methods cannot be
        patched on instances or the class.  We pass a MagicMock as the
        connection so we can record ``execute`` and ``commit`` calls while
        still verifying the control flow of ``handle_disk_full``.
        """
        mock_conn = MagicMock(spec=sqlite3.Connection)

        exc = sqlite3.OperationalError("database or disk is full")
        with pytest.raises(IndexerDiskFullError):
            handle_disk_full(mock_conn, exc, event_bus=EventBus())

        # Verify that PRAGMA wal_checkpoint(TRUNCATE) was called.
        # call_args_list entries are call objects; extract first positional arg.
        sql_calls = [str(c.args[0]).upper() for c in mock_conn.execute.call_args_list if c.args]
        assert any("WAL_CHECKPOINT" in s for s in sql_calls), f"Expected WAL_CHECKPOINT call; got: {sql_calls}"
        # Verify commit was attempted
        mock_conn.commit.assert_called_once()

    def test_non_disk_full_error_returns_none(self, tmp_path: Path) -> None:
        """Other OperationalErrors return None silently."""
        db_path = tmp_path / "library.db"
        conn = open_db(db_path, event_bus=EventBus())

        exc = sqlite3.OperationalError("no such table: foo")
        result = handle_disk_full(conn, exc, event_bus=EventBus())
        conn.close()

        assert result is None

    def test_disk_io_error_signal_triggers(self, tmp_path: Path) -> None:
        """'disk I/O error' message also triggers checkpoint + IndexerDiskFullError."""
        db_path = tmp_path / "library.db"
        conn = open_db(db_path, event_bus=EventBus())

        exc = sqlite3.OperationalError("disk I/O error")
        with pytest.raises(IndexerDiskFullError):
            handle_disk_full(conn, exc, event_bus=EventBus())

        conn.close()


# ---------------------------------------------------------------------------
# macFUSE-NTFS rejection (macOS only)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific mount detection")
class TestMacFuseNtfsRejection:
    """open_db rejects paths on macFUSE-NTFS mounts."""

    def test_ntfs_mount_raises_invalid_path_error(self, tmp_path: Path) -> None:
        """Mocked mount output with NTFS type causes IndexerInvalidPathError."""
        from personalscraper.indexer.db import IndexerInvalidPathError

        db_path = tmp_path / "library.db"

        fake_mount_output = f"/dev/disk2s1 on {tmp_path} (ufsd_NTFS, local, noatime)\n"

        with patch(
            "subprocess.run",
            return_value=MagicMock(stdout=fake_mount_output, returncode=0),
        ):
            with pytest.raises(IndexerInvalidPathError) as exc_info:
                open_db(db_path, event_bus=EventBus())

        assert str(tmp_path) in str(exc_info.value.mount_point)
