"""E2E test: Spotlight unavailable → dir-mtime walk fallback (sub-phase 4.8).

When ``mdutil -s`` reports "Indexing disabled", the scanner must:

* Log ``indexer.spotlight.unavailable`` at INFO level.
* Fall back to the standard dir-mtime walk (full or incremental mode).
* Complete the scan successfully with all files indexed.

This test mocks ``mdutil -s`` to return "Indexing disabled" and asserts that
the scan completes normally using the dir-mtime walk.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.schema import DiskRow

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"
_MDUTIL_PATCH = "personalscraper.indexer.scanner._spotlight.subprocess.run"
_PLATFORM_PATCH = "personalscraper.indexer.scanner._spotlight.platform.system"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema applied.

    Returns:
        Open :class:`sqlite3.Connection` with FK enforcement and migrations.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection, label: str, mount_path: str) -> DiskRow:
    """Insert a minimal disk row and return the populated :class:`DiskRow`.

    Args:
        conn: Open SQLite connection.
        label: Human-readable disk label.
        mount_path: Absolute path of the disk mount point.

    Returns:
        :class:`DiskRow` with the PK assigned by SQLite.
    """
    now = int(time.time())
    row = DiskRow(
        id=0,
        uuid=f"test-uuid-{label}",
        label=label,
        mount_path=mount_path,
        last_seen_at=now,
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )
    disk_id = disk_repo.insert(conn, row)
    return DiskRow(
        id=disk_id,
        uuid=row.uuid,
        label=row.label,
        mount_path=row.mount_path,
        last_seen_at=row.last_seen_at,
        merkle_root=row.merkle_root,
        is_mounted=row.is_mounted,
        unreachable_strikes=row.unreachable_strikes,
    )


def _make_mdutil_result(stdout: str) -> object:
    """Build a fake subprocess.CompletedProcess with *stdout*.

    Args:
        stdout: Text to return as the process stdout.

    Returns:
        A simple namespace mimicking :class:`subprocess.CompletedProcess`.
    """
    from types import SimpleNamespace

    return SimpleNamespace(stdout=stdout, stderr="", returncode=0)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestSpotlightUnavailable:
    """Spotlight disabled → dir-mtime walk runs; unavailable event logged."""

    def test_spotlight_unavailable_fallback(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Mdutil reports 'Indexing disabled' → scan falls back to dir-mtime walk.

        Scenario:
        1. Create a real temporary directory with two media files.
        2. Insert a disk row pointing to that directory.
        3. Mock ``mdutil -s`` to return "Indexing disabled".
        4. Mock ``mount`` (called by _check_mount_flags / detect_fs_type) to
           return no output (no-op — the spotlight probe will get fs_type=None
           which already skips the APFS path; the key assertion is unavailable
           is logged by probe_spotlight directly when called from try_attach).
        5. Run ``scan()`` with ``spotlight_enabled=True`` and ``staging_dir``
           pointing to the tmp dir.
        6. Assert:
           - Scan status is 'ok'.
           - All files indexed (dir-mtime walk ran).
           - ``indexer.spotlight.unavailable`` is in caplog.
        """
        conn = _open_db()

        mount = str(tmp_path / "DiskSpotlight")
        Path(mount).mkdir(parents=True, exist_ok=True)

        # Create a couple of media files on the fake disk.
        (Path(mount) / "movies" / "Film A (2020)").mkdir(parents=True, exist_ok=True)
        (Path(mount) / "movies" / "Film A (2020)" / "FilmA.mkv").write_bytes(b"V" * 300)
        (Path(mount) / "movies" / "Film A (2020)" / "FilmA.nfo").write_bytes(b"<nfo/>")

        disk = _insert_disk(conn, "DiskSpotlight", mount)

        # Mock ``mount`` to return empty output (fs_type detection returns None →
        # SpotlightChangeDetector.try_attach falls through to probe_spotlight via
        # the not-APFS branch only when spotlight_enabled=True and fs_type is unknown).
        # To trigger probe_spotlight directly (which logs unavailable), we set
        # fs_type_fn to return "apfs" so the code reaches the mdutil call, which
        # we mock to return "Indexing disabled".
        _mdutil_disabled = _make_mdutil_result("Indexing disabled")

        with (
            caplog.at_level(logging.INFO, logger="indexer.spotlight"),
            patch(_GUARD_PATCH, return_value=None),
            patch(_PLATFORM_PATCH, return_value="Darwin"),
            patch(
                "personalscraper.indexer.scanner._spotlight.detect_fs_type",
                return_value="apfs",
            ),
            patch(_MDUTIL_PATCH, return_value=_mdutil_disabled),
        ):
            result = scan(
                [disk],
                mode=ScanMode.full,
                generation=1,
                conn=conn,
                staging_dir=mount,
                spotlight_enabled=True,
                event_bus=EventBus(),
            )

        # Scan must complete cleanly via dir-mtime walk.
        assert result.status == "ok", f"Expected status='ok', got {result.status!r}"
        assert result.files_visited == 2, f"Expected 2 files_visited, got {result.files_visited}"

        # ``indexer.spotlight.unavailable`` must have been logged.
        info_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
        assert any("spotlight.unavailable" in t for t in info_texts), (
            f"Expected 'indexer.spotlight.unavailable' in INFO records; got: {info_texts}"
        )

        # Verify all media_file rows exist (dir-mtime walk ran correctly).
        count = conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0]
        assert count == 2, f"Expected 2 media_file rows (dir-mtime walk), got {count}"

        conn.close()
