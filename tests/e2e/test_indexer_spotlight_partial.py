"""E2E test: Spotlight partial/timeout → dir-mtime walk fallback (sub-phase 4.8).

When ``mdutil -s`` returns "Indexing enabled but rebuilding" or raises a
:class:`subprocess.TimeoutExpired`, the scanner must:

* Log ``indexer.spotlight.unavailable`` at INFO level (with a ``reason`` field).
* Fall back to the standard dir-mtime walk (full or incremental mode).
* Complete the scan successfully with all files indexed.

Two sub-cases are covered:

1. ``mdutil -s`` returns "Indexing enabled but rebuilding" (index not usable yet).
2. ``mdutil -s`` raises :class:`subprocess.TimeoutExpired` (probe hangs).
"""

from __future__ import annotations

import logging
import sqlite3
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.schema import DiskRow

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"
_MDUTIL_PATCH = "personalscraper.indexer.scanner._spotlight.subprocess.run"
_FSTYPE_PATCH = "personalscraper.indexer.scanner._spotlight.detect_fs_type"
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


def _make_mdutil_result(stdout: str) -> SimpleNamespace:
    """Build a fake subprocess.CompletedProcess with *stdout*.

    Args:
        stdout: Text to return as the process stdout.

    Returns:
        :class:`SimpleNamespace` mimicking :class:`subprocess.CompletedProcess`.
    """
    return SimpleNamespace(stdout=stdout, stderr="", returncode=0)


def _build_disk_tree(mount: str) -> None:
    """Create a minimal two-file directory tree under *mount*.

    Args:
        mount: Absolute path of the root directory to populate.
    """
    base = Path(mount) / "movies" / "Film B (2021)"
    base.mkdir(parents=True, exist_ok=True)
    (base / "FilmB.mkv").write_bytes(b"W" * 300)
    (base / "FilmB.nfo").write_bytes(b"<nfo/>")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSpotlightPartial:
    """Spotlight partial/timeout cases fall back to dir-mtime walk."""

    def test_spotlight_rebuilding_fallback(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Mdutil reports 'Indexing enabled but rebuilding' → unavailable logged, walk runs.

        Scenario:
        1. Create a temporary directory with two media files.
        2. Mock ``detect_fs_type`` to return "apfs" so the probe is attempted.
        3. Mock ``mdutil -s`` to return "Indexing enabled but rebuilding".
        4. Run ``scan()`` with ``spotlight_enabled=True``.
        5. Assert:
           - Scan status is 'ok'.
           - All files indexed (dir-mtime walk ran).
           - ``indexer.spotlight.unavailable`` is in caplog.
        """
        conn = _open_db()

        mount = str(tmp_path / "DiskRebuilding")
        Path(mount).mkdir(parents=True, exist_ok=True)
        _build_disk_tree(mount)

        disk = _insert_disk(conn, "DiskRebuilding", mount)

        _mdutil_rebuilding = _make_mdutil_result("Indexing enabled but rebuilding")

        with (
            caplog.at_level(logging.INFO, logger="indexer.spotlight"),
            patch(_GUARD_PATCH, return_value=None),
            patch(_PLATFORM_PATCH, return_value="Darwin"),
            patch(_FSTYPE_PATCH, return_value="apfs"),
            patch(_MDUTIL_PATCH, return_value=_mdutil_rebuilding),
        ):
            result = scan(
                [disk],
                mode=ScanMode.full,
                generation=1,
                conn=conn,
                spotlight_enabled=True,
            )

        assert result.status == "ok", f"Expected status='ok', got {result.status!r}"
        assert result.files_visited == 2, f"Expected 2 files_visited, got {result.files_visited}"

        info_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
        assert any("spotlight.unavailable" in t for t in info_texts), (
            f"Expected 'indexer.spotlight.unavailable' in INFO records; got: {info_texts}"
        )

        count = conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0]
        assert count == 2, f"Expected 2 media_file rows (dir-mtime walk), got {count}"

        conn.close()

    def test_spotlight_timeout_fallback(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Mdutil raises TimeoutExpired → unavailable logged with reason='mdutil_timeout', walk runs.

        Scenario:
        1. Create a temporary directory with two media files.
        2. Mock ``detect_fs_type`` to return "apfs" so the probe is attempted.
        3. Mock ``subprocess.run`` to raise :class:`subprocess.TimeoutExpired`.
        4. Run ``scan()`` with ``spotlight_enabled=True``.
        5. Assert:
           - Scan status is 'ok'.
           - All files indexed (dir-mtime walk ran).
           - ``indexer.spotlight.unavailable`` is in caplog.
        """
        conn = _open_db()

        mount = str(tmp_path / "DiskTimeout")
        Path(mount).mkdir(parents=True, exist_ok=True)
        _build_disk_tree(mount)

        disk = _insert_disk(conn, "DiskTimeout", mount)

        def _timeout_side_effect(*_args: object, **_kwargs: object) -> None:
            raise subprocess.TimeoutExpired(cmd=["mdutil", "-s", mount], timeout=10)

        with (
            caplog.at_level(logging.INFO, logger="indexer.spotlight"),
            patch(_GUARD_PATCH, return_value=None),
            patch(_PLATFORM_PATCH, return_value="Darwin"),
            patch(_FSTYPE_PATCH, return_value="apfs"),
            patch(_MDUTIL_PATCH, side_effect=_timeout_side_effect),
        ):
            result = scan(
                [disk],
                mode=ScanMode.full,
                generation=1,
                conn=conn,
                spotlight_enabled=True,
            )

        assert result.status == "ok", f"Expected status='ok', got {result.status!r}"
        assert result.files_visited == 2, f"Expected 2 files_visited, got {result.files_visited}"

        info_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
        assert any("spotlight.unavailable" in t for t in info_texts), (
            f"Expected 'indexer.spotlight.unavailable' in INFO records; got: {info_texts}"
        )

        count = conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0]
        assert count == 2, f"Expected 2 media_file rows (dir-mtime walk), got {count}"

        conn.close()
