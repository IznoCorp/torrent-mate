"""Tests for personalscraper.indexer.scanner.

Covers the skeleton walk introduced in sub-phase 2.4:
- ``ScanMode`` enum — all four members declared.
- ``ScanRunResult`` dataclass — fields present and typed.
- ``EXCLUDED_NAMES`` — set membership.
- ``_should_exclude`` — exact-match and ``"._"`` prefix exclusion.
- ``scan`` — end-to-end walk via pyfakefs with mocked ``guard_disk_mounted``:
  - Files and directories are visited and recorded.
  - Hidden / system names are excluded.
  - Symlinks are recorded with ``oshash=""`` (deferred sentinel).
  - ``path.dir_mtime_ns`` is written through for each visited directory.
  - ``scan_run`` status is ``'ok'`` on success.
  - Disks that raise ``DiskUnmountedError`` are skipped; scan still finishes ``'ok'``.
  - ``indexer.scan.disk_skipped`` warning is emitted for skipped disks.

Sub-phase 2.5 additions:
- Full-mode fingerprinting: ``oshash`` populated for video files; ``""`` for non-video.
- Symlinks always receive ``oshash=""`` regardless of extension.
- ``media_file.size_bytes`` and ``media_file.mtime_ns`` populated from stat.
- ``filter_disks`` helper: label matching, unknown label raises ``IndexerConfigError``.

Note on ``release_id`` / FK constraints:
    ``media_file.release_id`` is a NOT NULL FK to ``media_release``.  The skeleton
    scanner uses ``release_id=0`` as a deferred sentinel (release linkage is wired
    in the scraper phase, not the walk phase).  All test connections therefore run
    with ``PRAGMA foreign_keys=OFF`` so that FK integrity tests do not fire on the
    sentinel value.  FK enforcement is deliberately re-enabled in other test
    modules that exercise the repo layer directly.

Note on pyfakefs + sqlite3:
    pyfakefs intercepts all filesystem I/O including ``sqlite3.connect`` and file
    reads inside ``apply_migrations``.  To work around this each integration test
    calls ``fs.pause()`` to temporarily restore the real filesystem while building
    the in-memory DB, then calls ``fs.resume()`` before constructing the fake
    directory tree that the scanner walks.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.merkle import DiskUnmountedError
from personalscraper.indexer.repos import disk_repo, log_repo
from personalscraper.indexer.scanner import (
    EXCLUDED_NAMES,
    IndexerConfigError,
    ScanMode,
    ScanRunResult,
    _should_exclude,
    filter_disks,
    scan,
)
from personalscraper.indexer.schema import DiskRow

if TYPE_CHECKING:
    from pyfakefs.fake_filesystem import FakeFilesystem

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"


def _make_conn_real() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema but FK checks OFF.

    Must be called while the real filesystem is active (i.e. outside pyfakefs or
    after ``fs.pause()``).  ``apply_migrations`` reads SQL files from disk, so it
    requires the real filesystem to be in effect.

    FK checks are disabled because the scanner skeleton uses ``release_id=0`` as a
    deferred sentinel — see module docstring.

    Returns:
        Open :class:`sqlite3.Connection` with the full migration chain applied.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    # FK OFF: scanner skeleton uses release_id=0 sentinel (not a real FK target).
    conn.execute("PRAGMA foreign_keys=OFF")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection, mount_path: str) -> DiskRow:
    """Insert a minimal disk row and return the resulting :class:`DiskRow` with its PK.

    Args:
        conn: Open SQLite connection.
        mount_path: Absolute path of the fake mount point.

    Returns:
        :class:`DiskRow` with the PK assigned by SQLite.
    """
    now = int(time.time())
    row = DiskRow(
        id=0,
        uuid=f"test-uuid-{mount_path}",
        label=mount_path.split("/")[-1],
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


# ---------------------------------------------------------------------------
# Unit tests — ScanMode / ScanRunResult / EXCLUDED_NAMES / _should_exclude
# (No filesystem access — no pyfakefs needed.)
# ---------------------------------------------------------------------------


class TestScanMode:
    """Tests for the :class:`ScanMode` enum."""

    def test_all_four_members_declared(self) -> None:
        """quick, incremental, enrich, full must all be present."""
        members = {m.value for m in ScanMode}
        assert members == {"quick", "incremental", "enrich", "full"}

    def test_members_are_strings(self) -> None:
        """ScanMode members behave as plain strings (str, Enum pattern)."""
        assert isinstance(ScanMode.quick, str)
        assert ScanMode.full == "full"


class TestScanRunResult:
    """Tests for the :class:`ScanRunResult` dataclass."""

    def test_fields_and_defaults(self) -> None:
        """All required fields are settable; error defaults to None."""
        r = ScanRunResult(scan_run_id=1, files_visited=5, dirs_visited=2, status="ok")
        assert r.scan_run_id == 1
        assert r.files_visited == 5
        assert r.dirs_visited == 2
        assert r.status == "ok"
        assert r.error is None

    def test_error_field_settable(self) -> None:
        """Error field accepts a non-None string."""
        r = ScanRunResult(scan_run_id=2, files_visited=0, dirs_visited=0, status="failed", error="boom")
        assert r.error == "boom"


class TestExcludedNames:
    """Tests for :data:`EXCLUDED_NAMES` and :func:`_should_exclude`."""

    def test_excluded_names_is_frozenset(self) -> None:
        """EXCLUDED_NAMES must be a frozenset."""
        assert isinstance(EXCLUDED_NAMES, frozenset)

    def test_known_system_names_in_excluded(self) -> None:
        """Well-known macOS/Windows artefacts are in EXCLUDED_NAMES."""
        for name in (".fseventsd", "$Recycle.Bin", ".Spotlight-V100", ".Trashes", ".DS_Store"):
            assert name in EXCLUDED_NAMES, f"{name!r} missing from EXCLUDED_NAMES"

    def test_should_exclude_exact_match(self) -> None:
        """_should_exclude returns True for names in EXCLUDED_NAMES."""
        assert _should_exclude(".fseventsd") is True
        assert _should_exclude("$Recycle.Bin") is True
        assert _should_exclude(".DS_Store") is True

    def test_should_exclude_resource_fork_prefix(self) -> None:
        """_should_exclude returns True for names starting with '._'."""
        assert _should_exclude("._foo.mkv") is True
        assert _should_exclude("._") is True

    def test_should_not_exclude_regular_names(self) -> None:
        """_should_exclude returns False for regular file/directory names."""
        assert _should_exclude("movie.mkv") is False
        assert _should_exclude("001-MOVIES") is False
        assert _should_exclude(".hidden_but_not_resource_fork") is False


# ---------------------------------------------------------------------------
# Integration tests — scan() with pyfakefs
#
# Pattern: each test receives the ``fs`` pyfakefs fixture.  The DB is created
# while the real FS is in effect (fs.pause() / fs.resume()), then the fake
# directory tree is built, then scan() is called.
# ---------------------------------------------------------------------------


class TestScanWalksFilesAndDirs:
    """scan() visits files and directories and records them in the DB."""

    def test_scan_walks_files_and_dirs(self, fs: "FakeFilesystem") -> None:
        """Fake FS with 2 files in 1 dir under mount root → files_visited=2, dirs_visited≥1."""
        # Build the DB while the real FS is accessible for apply_migrations.
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/TestDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/Movies").mkdir()
        Path(f"{mount}/Movies/film1.mkv").write_text("data1")
        Path(f"{mount}/Movies/film2.mkv").write_text("data2")

        # Insert disk row while DB is live.
        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

        assert result.status == "ok"
        assert result.files_visited == 2
        assert result.dirs_visited >= 1  # at minimum the "Movies" subdir + disk root


class TestScanExcludesHiddenSystemNames:
    """scan() skips EXCLUDED_NAMES and '._' resource-fork prefix entries."""

    def test_scan_excludes_hidden_system_names(self, fs: "FakeFilesystem") -> None:
        """Hidden/system files and dirs must not appear in media_file."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ExclDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        # Should be excluded
        Path(f"{mount}/.DS_Store").write_text("junk")
        Path(f"{mount}/._shadow.mkv").write_text("rsrc")
        Path(f"{mount}/.fseventsd").mkdir()
        Path(f"{mount}/$Recycle.Bin").mkdir()
        # Should be included
        Path(f"{mount}/real_movie.mkv").write_text("content")

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

        assert result.status == "ok"
        assert result.files_visited == 1, "only real_movie.mkv must be visited"
        # Verify media_file table contains only the real file.
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename FROM media_file").fetchall()
        filenames = {r["filename"] for r in rows}
        assert ".DS_Store" not in filenames
        assert "._shadow.mkv" not in filenames
        assert "real_movie.mkv" in filenames


class TestScanRecordsSymlinks:
    """scan() records symlinks with oshash='' (deferred sentinel, never fingerprinted)."""

    def test_scan_records_symlinks_with_empty_oshash(self, fs: "FakeFilesystem") -> None:
        """Symlink is recorded in media_file with oshash='' (NOT NULL sentinel)."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/SymDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        # Create a real file and a symlink pointing to it.
        Path(f"{mount}/original.mkv").write_text("data")
        Path(f"{mount}/link.mkv").symlink_to(f"{mount}/original.mkv")

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

        assert result.status == "ok"
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, oshash FROM media_file").fetchall()
        filenames = {r["filename"]: r["oshash"] for r in rows}
        # Symlink must be recorded.
        assert "link.mkv" in filenames, f"link.mkv not found in {list(filenames)}"
        # oshash must be the deferred empty-string sentinel (column is NOT NULL).
        assert filenames["link.mkv"] == ""


class TestScanUpdatesDirMtimeNs:
    """scan() writes dir_mtime_ns into the path table for each visited directory."""

    def test_scan_updates_dir_mtime_ns_for_each_directory(self, fs: "FakeFilesystem") -> None:
        """Two subdirectories → both path rows have non-None dir_mtime_ns after scan."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/MtimeDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/dirA").mkdir()
        Path(f"{mount}/dirA/file1.mkv").write_text("a")
        Path(f"{mount}/dirB").mkdir()
        Path(f"{mount}/dirB/file2.mkv").write_text("b")

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

        assert result.status == "ok"
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT rel_path, dir_mtime_ns FROM path WHERE disk_id = ? AND dir_mtime_ns IS NOT NULL",
            (disk.id,),
        ).fetchall()
        rel_paths = {r["rel_path"] for r in rows}
        # Both directories must have a path row with dir_mtime_ns set.
        assert "dirA" in rel_paths, f"dirA missing from path rows: {rel_paths}"
        assert "dirB" in rel_paths, f"dirB missing from path rows: {rel_paths}"
        for r in rows:
            assert r["dir_mtime_ns"] > 0, f"dir_mtime_ns=0 for {r['rel_path']!r}"


class TestScanRunStatus:
    """scan_run lifecycle — status transitions."""

    def test_scan_run_status_ok_on_success(self, fs: "FakeFilesystem") -> None:
        """Successful scan → scan_run.status='ok' and finished_at NOT NULL."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/OkDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/film.mkv").write_text("ok")

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

        assert result.status == "ok"
        run_row = log_repo.get_scan_run_by_id(conn, result.scan_run_id)
        assert run_row is not None
        assert run_row.status == "ok"
        assert run_row.finished_at is not None

    def test_scan_run_status_ok_when_disk_unmounted(self, fs: "FakeFilesystem") -> None:
        """DiskUnmountedError causes disk to be skipped; scan_run.status still 'ok'."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/UnmountedDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, side_effect=DiskUnmountedError("test-uuid")):
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

        # Disk-guard failure is a skip, not an abort — scan_run must finish 'ok'.
        assert result.status == "ok"
        assert result.files_visited == 0
        run_row = log_repo.get_scan_run_by_id(conn, result.scan_run_id)
        assert run_row is not None
        assert run_row.status == "ok"


class TestScanSkippedDiskLogsWarning:
    """scan() emits indexer.scan.disk_skipped when a disk is skipped."""

    def test_scan_skipped_disk_logs_warning(
        self,
        fs: "FakeFilesystem",
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """indexer.scan.disk_skipped warning is emitted for a DiskUnmountedError."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/SkipDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)

        disk = _insert_disk(conn, mount)

        with caplog.at_level(logging.WARNING, logger="indexer.scan"):
            with patch(_GUARD_PATCH, side_effect=DiskUnmountedError("skip-uuid")):
                scan([disk], ScanMode.full, generation=1, conn=conn)

        # structlog forwards to stdlib logging; check the rendered warning text.
        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("disk_skipped" in t for t in warning_texts), (
            f"Expected 'disk_skipped' in warning records, got: {warning_texts}"
        )


# ---------------------------------------------------------------------------
# Sub-phase 2.5 tests — full-mode fingerprinting and filter_disks
# ---------------------------------------------------------------------------


class TestFullModeFingerprints:
    """scan() in full mode computes oshash for video files; '' for non-video."""

    def test_full_mode_fingerprints_files(self, fs: "FakeFilesystem") -> None:
        """Video .mkv files get a non-empty oshash; a .txt file gets ''."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/FingerprintDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        # Two video files — each needs enough content for oshash to produce a
        # distinct non-zero result.  65 536 bytes is the OSHash chunk size; use
        # a small but non-empty payload so pyfakefs can serve the read.
        Path(f"{mount}/film1.mkv").write_bytes(b"A" * 200)
        Path(f"{mount}/film2.mkv").write_bytes(b"B" * 200)
        # Non-video file — should get oshash="" (not applicable, not a video).
        Path(f"{mount}/readme.txt").write_text("notes")

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

        assert result.status == "ok"
        assert result.files_visited == 3

        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, oshash FROM media_file").fetchall()
        by_name = {r["filename"]: r["oshash"] for r in rows}

        # Video files must have a non-empty hex oshash.
        assert by_name["film1.mkv"] != "", "film1.mkv oshash must be non-empty"
        assert len(by_name["film1.mkv"]) == 16, "oshash must be 16 hex chars"
        assert by_name["film2.mkv"] != "", "film2.mkv oshash must be non-empty"
        # Non-video file must keep the empty sentinel.
        assert by_name["readme.txt"] == "", "readme.txt oshash must be empty string"

    def test_full_mode_skips_oshash_for_symlinks(self, fs: "FakeFilesystem") -> None:
        """Symlink pointing to a .mkv always gets oshash='' (never fingerprinted)."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/SymlinkDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/original.mkv").write_bytes(b"C" * 200)
        # Symlink — should be recorded but never oshashed.
        Path(f"{mount}/link.mkv").symlink_to(f"{mount}/original.mkv")

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

        assert result.status == "ok"
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, oshash FROM media_file").fetchall()
        by_name = {r["filename"]: r["oshash"] for r in rows}

        assert "link.mkv" in by_name, f"link.mkv not found in {list(by_name)}"
        assert by_name["link.mkv"] == "", "symlink oshash must be '' regardless of extension"

    def test_full_mode_writes_size_and_mtime(self, fs: "FakeFilesystem") -> None:
        """Full-mode scan populates size_bytes and mtime_ns for every file."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/SizeMtimeDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        content = b"X" * 512
        Path(f"{mount}/movie.mkv").write_bytes(content)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

        assert result.status == "ok"
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT size_bytes, mtime_ns FROM media_file WHERE filename = 'movie.mkv'").fetchone()
        assert row is not None
        assert row["size_bytes"] == 512, f"Expected 512, got {row['size_bytes']}"
        assert row["mtime_ns"] > 0, f"mtime_ns must be positive, got {row['mtime_ns']}"


class TestFilterDisks:
    """Tests for the filter_disks() helper."""

    def _make_disk(self, label: str) -> DiskRow:
        """Return a minimal DiskRow with the given label (no real DB needed).

        Args:
            label: Disk label string.

        Returns:
            :class:`DiskRow` instance with id=0 and the given label.
        """
        return DiskRow(
            id=0,
            uuid=f"uuid-{label}",
            label=label,
            mount_path=f"/mnt/{label}",
            last_seen_at=None,
            merkle_root=None,
            is_mounted=1,
            unreachable_strikes=0,
        )

    def test_filter_disks_by_label_matches_one(self) -> None:
        """filter_disks(['A','B','C'], 'B') returns only the B disk."""
        disks = [self._make_disk("A"), self._make_disk("B"), self._make_disk("C")]
        result = filter_disks(disks, "B")
        assert len(result) == 1
        assert result[0].label == "B"

    def test_filter_disks_by_label_unknown_raises(self) -> None:
        """filter_disks(disks, 'Z') raises IndexerConfigError when 'Z' is not present."""
        disks = [self._make_disk("A"), self._make_disk("B"), self._make_disk("C")]
        with pytest.raises(IndexerConfigError, match="no disk with label 'Z'"):
            filter_disks(disks, "Z")

    def test_filter_disks_no_filter_returns_all(self) -> None:
        """filter_disks(disks, None) returns all disks unchanged."""
        disks = [self._make_disk("A"), self._make_disk("B"), self._make_disk("C")]
        result = filter_disks(disks, None)
        assert len(result) == 3
        assert [d.label for d in result] == ["A", "B", "C"]
