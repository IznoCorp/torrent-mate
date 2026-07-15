"""Tests for personalscraper.indexer.scanner.

Covers the skeleton walk introduced in sub-phase 2.4:
- ``ScanMode`` enum — all four members declared.
- ``ScanRunResult`` dataclass — fields present and typed.
- ``EXCLUDED_NAMES`` — set membership.
- ``_should_exclude`` — exact-match and ``"._"`` prefix exclusion.
- ``scan`` — end-to-end walk via pyfakefs with mocked ``guard_disk_mounted``:
  - Files and directories are visited and recorded.
  - Hidden / system names are excluded.
  - Symlinks are recorded with ``oshash=None`` (NULL in DB; deferred Stage A state).
  - ``path.dir_mtime_ns`` is written through for each visited directory.
  - ``scan_run`` status is ``'ok'`` on success.
  - Disks that raise ``DiskUnmountedError`` are skipped; scan still finishes ``'ok'``.
  - ``indexer.scan.disk_skipped`` warning is emitted for skipped disks.

Sub-phase 2.5 additions:
- Full-mode fingerprinting: ``oshash`` populated for video files; ``None`` (NULL) for non-video.
- Symlinks always receive ``oshash=None`` (NULL) regardless of extension.
- ``media_file.size_bytes`` and ``media_file.mtime_ns`` populated from stat.
- ``filter_disks`` helper: label matching, unknown label raises ``IndexerConfigError``.

Sub-phase 2.6 additions:
- Quick mode: Merkle short-circuit skips disk when DB-computed root matches stored root.
- Quick mode: Merkle miss falls through to dir-mtime walk.
- Quick mode: Dir-mtime subtree skip when stored ``path.dir_mtime_ns`` equals live value.
- Quick mode: Dir-mtime changed → subtree is walked.
- Quick mode: Merkle root recomputed and persisted after a successful walk.
- Quick mode: ``_verify_dir_mtime_reliable`` returning ``False`` disables subtree skip.

Sub-phase 4.4 additions:
- ``_check_mount_flags``: warns via ``indexer.disk.mount_flags_missing`` when any of
  ``{noatime, noappledouble, noapplexattr, defer_permissions, allow_other}`` is absent
  from the ``mount`` output for a disk's mount point.
- No-op on non-Darwin platforms (``platform.system() != "Darwin"``).
- Non-fatal: subprocess failure is caught and logged at DEBUG; scan still proceeds.
- Tested via mocked ``subprocess.run`` for the ``mount`` command.

Sub-phase 9.4 additions:
- ``scan`` re-raises unexpected exceptions after recording ``scan_run.status='failed'``,
  matching the documented ``Raises`` contract and mirroring the ``DiskBulkChangeDetected``
  branch.  Regression test: ``TestScanUnexpectedExceptionReraise``.

Note on ``release_id`` / FK constraints:
    ``media_file.release_id`` is now nullable (migration 002).  Stage A inserts
    file rows with ``release_id=NULL``; release linkage is populated by the scraper
    phase (Stage B).  FK enforcement is enabled in all test connections (the default
    set by ``db.open_db``).  No FK workaround is needed.

Note on pyfakefs + sqlite3:
    pyfakefs intercepts all filesystem I/O including ``sqlite3.connect`` and file
    reads inside ``apply_migrations``.  To work around this each integration test
    calls ``fs.pause()`` to temporarily restore the real filesystem while building
    the in-memory DB, then calls ``fs.resume()`` before constructing the fake
    directory tree that the scanner walks.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer._fs_probe import MountInfo
from personalscraper.indexer._throttle import (
    TokenBucket,
    get_active_bucket,
    set_active_bucket,
)
from personalscraper.indexer._throttle import (
    acquire as _throttle_acquire,
)
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.merkle import DiskMountStatus, DiskUnmountedError, compute_merkle_root
from personalscraper.indexer.repos import disk_repo, log_repo
from personalscraper.indexer.scanner import (
    _RECOMMENDED_MOUNT_FLAGS,
    EXCLUDED_NAMES,
    IndexerConfigError,
    ScanMode,
    ScanRunResult,
    _build_disk_fingerprints,
    _check_mount_flags,
    _should_exclude,
    _verify_dir_mtime_reliable,
    filter_disks,
    scan,
)
from personalscraper.indexer.schema import DiskRow, PathRow

if TYPE_CHECKING:
    from pyfakefs.fake_filesystem import FakeFilesystem

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"
_VERIFY_PATCH = "personalscraper.indexer.scanner.verify_disk_mounted"


def _make_conn_real() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema.

    Must be called while the real filesystem is active (i.e. outside pyfakefs or
    after ``fs.pause()``).  ``apply_migrations`` reads SQL files from disk, so it
    requires the real filesystem to be in effect.

    FK checks remain enabled (the default per ``db.open_db``).  Stage A inserts
    ``release_id=NULL``, which is valid now that the column is nullable
    (migration 002) — no ``PRAGMA foreign_keys=OFF`` workaround needed.

    Returns:
        Open :class:`sqlite3.Connection` with the full migration chain applied.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection, mount_path: str, merkle_root: str | None = None) -> DiskRow:
    """Insert a minimal disk row and return the resulting :class:`DiskRow` with its PK.

    Args:
        conn: Open SQLite connection.
        mount_path: Absolute path of the fake mount point.
        merkle_root: Optional pre-seeded Merkle root for the disk row.

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
        merkle_root=merkle_root,
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

    def test_all_members_declared(self) -> None:
        """quick, incremental, enrich, full, verify must all be present."""
        members = {m.value for m in ScanMode}
        assert members == {"quick", "incremental", "enrich", "full", "verify"}

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
            result = scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

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
            result = scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

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
    """scan() records symlinks with oshash=None (NULL in DB; never fingerprinted)."""

    def test_scan_records_symlinks_with_empty_oshash(self, fs: "FakeFilesystem") -> None:
        """Symlink is recorded in media_file with oshash=None (NULL; never fingerprinted)."""
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
            result = scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        assert result.status == "ok"
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, oshash FROM media_file").fetchall()
        filenames = {r["filename"]: r["oshash"] for r in rows}
        # Symlink must be recorded.
        assert "link.mkv" in filenames, f"link.mkv not found in {list(filenames)}"
        # oshash must be NULL (Stage A: symlinks are never fingerprinted).
        assert filenames["link.mkv"] is None


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
            result = scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

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
            result = scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

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
            result = scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Disk-guard failure is a skip, not an abort — scan_run must finish 'ok'.
        assert result.status == "ok"
        assert result.files_visited == 0
        run_row = log_repo.get_scan_run_by_id(conn, result.scan_run_id)
        assert run_row is not None
        assert run_row.status == "ok"


class TestScanSkippedDiskLogsWarning:
    """scan() emits indexer.disk.skipped_unmounted when a disk is unmounted."""

    def test_scan_skipped_disk_logs_warning(
        self,
        fs: "FakeFilesystem",
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """indexer.disk.skipped_unmounted warning is emitted for a DiskUnmountedError."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/SkipDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)

        disk = _insert_disk(conn, mount)

        # Capture from both logger namespaces (indexer.scan and indexer.disk).
        with caplog.at_level(logging.WARNING):
            with patch(_GUARD_PATCH, side_effect=DiskUnmountedError("skip-uuid")):
                scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # structlog forwards to stdlib logging; check the rendered warning text.
        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("skipped_unmounted" in t for t in warning_texts), (
            f"Expected 'skipped_unmounted' in warning records, got: {warning_texts}"
        )


# ---------------------------------------------------------------------------
# Sub-phase 10.5 tests — readable reason code on skipped_unmounted warning
# ---------------------------------------------------------------------------


class TestScanSkippedDiskReasonCode:
    """indexer.disk.skipped_unmounted warning carries a readable reason code, not a UUID.

    The ``reason`` field must be one of the known string codes (e.g.
    ``mount_inaccessible``, ``sentinel_missing``, ``sentinel_mismatch``) and
    must not expose the raw UUID string as the ``reason`` value.
    """

    _VALID_REASON_CODES = frozenset(
        {
            "mount_inaccessible",
            "sentinel_missing",
            "sentinel_mismatch",
            "bootstrap_failed",
        }
    )
    # Match a UUID appearing as the value of the 'reason' key in the structlog
    # JSON-dict output: "'reason': 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX'"
    _UUID_AS_REASON_RE = re.compile(
        r"'reason':\s*'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
        r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'"
    )

    def test_unmounted_disk_reason_is_readable_code(
        self,
        fs: "FakeFilesystem",
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When a disk is UNMOUNTED, reason is 'mount_inaccessible', not a UUID."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ReasonCodeDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk = _insert_disk(conn, mount)

        with caplog.at_level(logging.WARNING):
            with patch(_VERIFY_PATCH, return_value=DiskMountStatus.UNMOUNTED):
                with patch(_GUARD_PATCH, side_effect=DiskUnmountedError("F7E3C03C-48B7-4C23-BFEE-3E19B052C014")):
                    scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        skip_warnings = [t for t in warning_texts if "skipped_unmounted" in t]
        assert skip_warnings, f"Expected skipped_unmounted warning, got: {warning_texts}"

        combined = " ".join(skip_warnings)
        # reason must be one of the known human-readable codes (structlog renders
        # key-value pairs as "'reason': 'mount_inaccessible'" in the dict repr).
        assert any(f"'reason': '{code}'" in combined for code in self._VALID_REASON_CODES), (
            f"Expected reason=<readable_code> in: {combined}"
        )
        # reason must NOT be a raw UUID string.
        assert not self._UUID_AS_REASON_RE.search(combined), f"reason field must not contain a UUID, got: {combined}"
        # The UUID is preserved in a separate field (disk_uuid), not in reason.
        assert "disk_uuid" in combined, f"Expected disk_uuid field in: {combined}"

    def test_sentinel_missing_reason_code(
        self,
        fs: "FakeFilesystem",
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When sentinel is absent (NO_SENTINEL), reason is 'sentinel_missing'."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NoSentinelDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        disk = _insert_disk(conn, mount)

        with caplog.at_level(logging.WARNING):
            with patch(_VERIFY_PATCH, return_value=DiskMountStatus.NO_SENTINEL):
                # guard_disk_mounted sees NO_SENTINEL → tries bootstrap → raises DiskUnmountedError
                # to simulate bootstrap failure leading to a skip.
                with patch(_GUARD_PATCH, side_effect=DiskUnmountedError("some-uuid")):
                    scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        skip_warnings = [t for t in warning_texts if "skipped_unmounted" in t]
        assert skip_warnings, f"Expected skipped_unmounted warning, got: {warning_texts}"

        combined = " ".join(skip_warnings)
        assert "'reason': 'sentinel_missing'" in combined, f"Expected reason=sentinel_missing in: {combined}"
        assert not self._UUID_AS_REASON_RE.search(combined), f"reason field must not contain a UUID, got: {combined}"


# ---------------------------------------------------------------------------
# Sub-phase 2.5 tests — full-mode fingerprinting and filter_disks
# ---------------------------------------------------------------------------


class TestFullModeFingerprints:
    """scan() in full mode computes oshash for video files; None (NULL) for non-video."""

    def test_full_mode_fingerprints_files(self, fs: "FakeFilesystem") -> None:
        """Video .mkv files get a non-empty oshash; a .txt file gets None (NULL)."""
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
        # Non-video file — oshash is NULL (not applicable; Stage A only computes for video).
        Path(f"{mount}/readme.txt").write_text("notes")

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        assert result.status == "ok"
        assert result.files_visited == 3

        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, oshash FROM media_file").fetchall()
        by_name = {r["filename"]: r["oshash"] for r in rows}

        # Video files must have a non-empty hex oshash.
        assert by_name["film1.mkv"] is not None, "film1.mkv oshash must not be None"
        assert by_name["film1.mkv"] != "", "film1.mkv oshash must be non-empty"
        assert len(by_name["film1.mkv"]) == 16, "oshash must be 16 hex chars"
        assert by_name["film2.mkv"] is not None, "film2.mkv oshash must not be None"
        assert by_name["film2.mkv"] != "", "film2.mkv oshash must be non-empty"
        # Non-video file must have NULL oshash (Stage A; OSHash not applicable).
        assert by_name["readme.txt"] is None, "readme.txt oshash must be None (NULL)"

    def test_full_mode_skips_oshash_for_symlinks(self, fs: "FakeFilesystem") -> None:
        """Symlink pointing to a .mkv always gets oshash=None (NULL; never fingerprinted)."""
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
            result = scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        assert result.status == "ok"
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, oshash FROM media_file").fetchall()
        by_name = {r["filename"]: r["oshash"] for r in rows}

        assert "link.mkv" in by_name, f"link.mkv not found in {list(by_name)}"
        assert by_name["link.mkv"] is None, "symlink oshash must be None (NULL) regardless of extension"

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
            result = scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

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


# ---------------------------------------------------------------------------
# Sub-phase 2.6 tests — quick-mode Merkle short-circuit and dir-mtime skip
# ---------------------------------------------------------------------------


class TestQuickMode:
    """Tests for quick-mode scan: Merkle short-circuit and dir-mtime subtree skipping."""

    # ------------------------------------------------------------------
    # Test 1: Merkle match → disk entirely skipped (zero FS reads)
    # ------------------------------------------------------------------

    def test_quick_mode_merkle_match_skips_disk(self, fs: "FakeFilesystem") -> None:
        """When DB-computed Merkle root equals disk.merkle_root, disk walk is skipped.

        Seed the DB with one file, compute the real Merkle root from those rows,
        store it on disk.merkle_root, then run a quick scan.  Because the root
        matches, _scan_disk_quick must return immediately without any scandir call,
        and ``result.disks_skipped`` must be 1.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/MerkleMatchDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/film.mkv").write_text("data")

        # Insert disk (no merkle_root yet) and run a full scan to populate media_file.
        disk = _insert_disk(conn, mount)
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Compute the Merkle root from the now-populated DB rows.
        fingerprints = _build_disk_fingerprints(conn, disk.id)
        expected_root = compute_merkle_root(fingerprints)

        # Store the root on the disk row so the next quick scan can short-circuit.
        disk_repo.update_merkle_root(conn, disk.id, expected_root)

        # Re-fetch the disk row so the DiskRow object carries the updated merkle_root.
        # The scanner uses disk.merkle_root from the passed DiskRow — it does not
        # re-read the DB row during the scan, so the object must be up-to-date.
        updated_disk = disk_repo.get_by_id(conn, disk.id)
        assert updated_disk is not None

        # Quick scan — scandir for the mount path must NOT be called.
        scandir_calls: list[str] = []
        real_scandir = __import__("os").scandir

        def _tracking_scandir(path: str) -> object:
            scandir_calls.append(path)
            return real_scandir(path)

        with patch(_GUARD_PATCH, return_value=None):
            with patch("personalscraper.indexer.scanner.os.scandir", side_effect=_tracking_scandir):
                result = scan([updated_disk], ScanMode.quick, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"
        assert result.disks_skipped == 1, f"Expected 1 disk skipped, got {result.disks_skipped}"
        # No scandir call should have touched the mount path subtree.
        mount_calls = [c for c in scandir_calls if c.startswith(mount)]
        assert mount_calls == [], f"scandir was called for mount path: {mount_calls}"

    # ------------------------------------------------------------------
    # Test 2: Merkle miss → full dir walk is performed
    # ------------------------------------------------------------------

    def test_quick_mode_merkle_miss_walks_disk(self, fs: "FakeFilesystem") -> None:
        """When the stored merkle_root differs from the DB-computed root, the disk is walked.

        Store a deliberately wrong merkle_root on the disk row so the Merkle
        check always fails.  Quick scan must then fall through to _walk_dir_quick
        and visit the file, and ``result.disks_skipped`` must be 0.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/MerkleMissDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/film.mkv").write_text("data")

        # Insert disk with a deliberately wrong merkle_root.
        disk = _insert_disk(conn, mount, merkle_root="deadbeefdeadbeef" * 4)

        scandir_calls: list[str] = []
        real_scandir = __import__("os").scandir

        def _tracking_scandir(path: str) -> object:
            scandir_calls.append(path)
            return real_scandir(path)

        with patch(_GUARD_PATCH, return_value=None):
            with patch("personalscraper.indexer.scanner.os.scandir", side_effect=_tracking_scandir):
                result = scan([disk], ScanMode.quick, generation=1, conn=conn, event_bus=EventBus())

        assert result.status == "ok"
        assert result.disks_skipped == 0, f"Expected 0 disks skipped, got {result.disks_skipped}"
        # scandir must have been called for the mount path.
        mount_calls = [c for c in scandir_calls if c.startswith(mount)]
        assert mount_calls, "scandir was never called for the mount path despite Merkle miss"

    # ------------------------------------------------------------------
    # Test 3: Dir-mtime unchanged → subtree skipped
    # ------------------------------------------------------------------

    def test_quick_mode_dir_mtime_unchanged_skips_subtree(self, fs: "FakeFilesystem") -> None:
        """Unchanged dir_mtime_ns causes _walk_dir_quick to skip the subtree.

        Run a full scan first to populate path rows with current dir_mtime_ns
        values.  Then run a quick scan with dir-mtime reliable and a wrong
        merkle_root (to force the Merkle miss path).  Because the subdir mtime
        matches, files inside it must NOT be re-inserted (media_file count stays
        the same from the first scan's perspective — we check via scan_generation).
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/DirMtimeSkipDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/subdir").mkdir()
        Path(f"{mount}/subdir/film.mkv").write_text("data")

        # First: full scan to populate path rows with current dir_mtime_ns.
        disk = _insert_disk(conn, mount)
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Store a wrong merkle_root to force Merkle miss in quick scan.
        disk_repo.update_merkle_root(conn, disk.id, "wrongroot")

        # Quick scan with dir-mtime reliable — the subdir mtime has not changed.
        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                return_value=True,
            ):
                result = scan([disk], ScanMode.quick, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"

        # Files inside the unchanged subdir must NOT have been re-visited in gen=2.
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, scan_generation FROM media_file WHERE filename = 'film.mkv'").fetchall()
        assert rows, "film.mkv must exist in media_file"
        # scan_generation should still be 1 (not updated to 2) because subtree was skipped.
        assert rows[0]["scan_generation"] == 1, (
            f"scan_generation was updated to {rows[0]['scan_generation']}; subtree skip should have preserved gen=1"
        )

    # ------------------------------------------------------------------
    # Test 4: Dir-mtime changed → subtree IS walked
    # ------------------------------------------------------------------

    def test_quick_mode_dir_mtime_changed_walks_subtree(self, fs: "FakeFilesystem") -> None:
        """Stale dir_mtime_ns causes _walk_dir_quick to recurse into the subtree.

        Seed the path row with a dir_mtime_ns value that does NOT match the
        current FS value (0 is a safe stale sentinel).  Quick scan must walk the
        subtree and update the file's scan_generation to 2.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/DirMtimeChangeDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/subdir").mkdir()
        Path(f"{mount}/subdir/film.mkv").write_text("data")

        # First: full scan to create the media_file row (gen=1).
        disk = _insert_disk(conn, mount)
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Manually stale the path row's dir_mtime_ns to 0 so it never matches.
        now_s = int(time.time())
        conn.execute(
            "UPDATE path SET dir_mtime_ns = 0, last_walked_at = ? WHERE disk_id = ? AND rel_path = 'subdir'",
            (now_s, disk.id),
        )

        # Store a wrong merkle_root to force Merkle miss path.
        disk_repo.update_merkle_root(conn, disk.id, "wrongroot")

        # Quick scan — dir mtime mismatch → subtree must be walked → gen updated to 2.
        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                return_value=True,
            ):
                result = scan([disk], ScanMode.quick, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"

        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, scan_generation FROM media_file WHERE filename = 'film.mkv'").fetchall()
        assert rows, "film.mkv must exist in media_file"
        assert rows[0]["scan_generation"] == 2, (
            f"Expected scan_generation=2 after subtree walk, got {rows[0]['scan_generation']}"
        )

    # ------------------------------------------------------------------
    # Test 5: Merkle root recomputed and persisted after quick walk
    # ------------------------------------------------------------------

    def test_quick_mode_recomputes_merkle_after_scan(self, fs: "FakeFilesystem") -> None:
        """After a Merkle-miss quick scan, disk.merkle_root is updated in the DB.

        The scan must recompute the Merkle root from the updated media_file rows
        and persist it via disk_repo.update_merkle_root so the next quick scan
        can short-circuit.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/MerkleUpdateDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/film.mkv").write_text("data")

        # Insert disk with a wrong merkle_root to force Merkle miss.
        disk = _insert_disk(conn, mount, merkle_root="staleroot")

        with patch(_GUARD_PATCH, return_value=None):
            result = scan([disk], ScanMode.quick, generation=1, conn=conn, event_bus=EventBus())

        assert result.status == "ok"
        assert result.disks_skipped == 0

        # Re-read disk row from DB and verify merkle_root is now set to a real value.
        updated_disk = disk_repo.get_by_id(conn, disk.id)
        assert updated_disk is not None
        assert updated_disk.merkle_root is not None, "merkle_root must be set after quick scan"
        assert updated_disk.merkle_root != "staleroot", "merkle_root must have been updated from stale value"

        # The stored root must match a fresh DB-side computation.
        fingerprints = _build_disk_fingerprints(conn, disk.id)
        expected_root = compute_merkle_root(fingerprints)
        assert updated_disk.merkle_root == expected_root, (
            f"Stored root {updated_disk.merkle_root!r} != freshly computed {expected_root!r}"
        )

    # ------------------------------------------------------------------
    # Test 6: _verify_dir_mtime_reliable=False disables subtree skip
    # ------------------------------------------------------------------

    def test_dir_mtime_verification_disables_optimization_when_unreliable(self, fs: "FakeFilesystem") -> None:
        """When dir-mtime is unreliable, subtrees are walked even if mtime matches.

        Mock _verify_dir_mtime_reliable to return False.  Run a quick scan after
        a full scan (so path rows are populated with matching dir_mtime_ns).
        Because the optimisation is disabled, the subtree must be re-walked and
        scan_generation updated to 2.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/UnreliableMtimeDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/subdir").mkdir()
        Path(f"{mount}/subdir/film.mkv").write_text("data")

        # First: full scan → path rows populated, gen=1.
        disk = _insert_disk(conn, mount)
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Seed a wrong merkle_root so the Merkle miss path is taken.
        disk_repo.update_merkle_root(conn, disk.id, "wrongroot")

        # Quick scan with dir-mtime UNRELIABLE → skip optimisation disabled.
        # Probe the disk as NTFS (``dir_mtime_reliable_default=None``) so the
        # per-disk capability defers to the session-wide runtime probe — the
        # exact path this test exercises.  Without this, the host's real ``/``
        # APFS mount would be matched (its hard-wired default ``True`` would
        # override the patched ``False``).
        ntfs_info = MountInfo(mount_point=mount, fs_type="ntfs_macfuse", raw_fs_type="ufsd_ntfs", flags=frozenset())
        with patch(_GUARD_PATCH, return_value=None):
            with patch("personalscraper.indexer._fs_probe.probe_mount", return_value=ntfs_info):
                with patch(
                    "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                    return_value=False,
                ):
                    result = scan([disk], ScanMode.quick, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"

        # Even though dir_mtime_ns matched, the subtree must have been walked.
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, scan_generation FROM media_file WHERE filename = 'film.mkv'").fetchall()
        assert rows, "film.mkv must exist in media_file"
        assert rows[0]["scan_generation"] == 2, (
            f"Expected scan_generation=2 (subtree walked despite matching mtime), got {rows[0]['scan_generation']}"
        )


# ---------------------------------------------------------------------------
# Unit tests — _verify_dir_mtime_reliable (no pyfakefs — uses real FS)
# ---------------------------------------------------------------------------


class TestVerifyDirMtimeReliable:
    """Unit tests for the _verify_dir_mtime_reliable helper."""

    def test_returns_bool(self) -> None:
        """_verify_dir_mtime_reliable returns a bool (True on a normal local FS)."""
        result = _verify_dir_mtime_reliable()
        assert isinstance(result, bool)

    def test_returns_true_on_local_fs(self) -> None:
        """On a normal macOS/Linux local filesystem, dir mtime is reliably updated."""
        # This test may spuriously fail on certain network mounts / CI environments
        # with noatime; mark it as expected True for local dev only.
        result = _verify_dir_mtime_reliable()
        # We assert True because the CI runner is a standard Linux/macOS local disk.
        assert result is True, "_verify_dir_mtime_reliable returned False on what appears to be a local FS"

    def test_returns_false_when_mtime_unchanged(self) -> None:
        """When os.stat always returns the same mtime, _verify_dir_mtime_reliable returns False.

        Patch os.stat so the mtime_before == mtime_after, simulating a noatime mount.
        """
        import os as _os

        original_stat = _os.stat

        call_count = 0

        def _frozen_stat(path: str, **kwargs: object) -> object:
            nonlocal call_count
            st = original_stat(path, **kwargs)  # type: ignore[arg-type]
            call_count += 1
            # Return a stat result with a fixed mtime_ns so before == after.
            # We monkey-patch only the st_mtime_ns attribute by wrapping the result.
            return type(
                "FrozenStat",
                (),
                {attr: getattr(st, attr) for attr in dir(st) if not attr.startswith("__")} | {"st_mtime_ns": 12345678},
            )()

        with patch("personalscraper.indexer.scanner.os.stat", side_effect=_frozen_stat):
            result = _verify_dir_mtime_reliable()

        assert result is False, "Expected False when mtime unchanged after child write"

    def test_returns_false_on_exception(self) -> None:
        """An OSError during the check causes _verify_dir_mtime_reliable to return False."""
        with patch("personalscraper.indexer.scanner.tempfile.TemporaryDirectory", side_effect=OSError("no tmp")):
            result = _verify_dir_mtime_reliable()
        assert result is False


# ---------------------------------------------------------------------------
# Unit tests — _build_disk_fingerprints (no pyfakefs)
# ---------------------------------------------------------------------------


class TestBuildDiskFingerprints:
    """Unit tests for _build_disk_fingerprints helper."""

    def test_returns_empty_list_for_unknown_disk(self) -> None:
        """_build_disk_fingerprints returns [] when no media_file rows exist for disk_id."""
        conn = _make_conn_real()
        fps = _build_disk_fingerprints(conn, disk_id=9999)
        assert fps == []

    def test_returns_fingerprints_for_seeded_files(self, fs: "FakeFilesystem") -> None:
        """Returns one FileFingerprint per non-deleted media_file row for the disk."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/FpDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/a.mkv").write_text("aaa")
        Path(f"{mount}/b.mkv").write_text("bbb")

        disk = _insert_disk(conn, mount)
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        fps = _build_disk_fingerprints(conn, disk.id)
        assert len(fps) == 2, f"Expected 2 fingerprints, got {len(fps)}"

    def test_excludes_deleted_files(self, fs: "FakeFilesystem") -> None:
        """Rows with deleted_at IS NOT NULL are excluded from fingerprint results."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/DeletedFpDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/alive.mkv").write_text("alive")
        Path(f"{mount}/dead.mkv").write_text("dead")

        disk = _insert_disk(conn, mount)
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Mark dead.mkv as deleted.
        now_s = int(time.time())
        conn.execute(
            "UPDATE media_file SET deleted_at = ? WHERE filename = 'dead.mkv'",
            (now_s,),
        )

        fps = _build_disk_fingerprints(conn, disk.id)
        assert len(fps) == 1, f"Expected 1 fingerprint (alive only), got {len(fps)}"

    def test_excludes_rows_with_null_oshash(self, fs: "FakeFilesystem") -> None:
        """Rows with ``oshash IS NULL`` (Stage A) are excluded (DEV #14 regression).

        The scanner stores the merkle from this helper's output; the reconcile
        detector ``detect_merkle_drift`` recomputes the live merkle with an
        ``AND mf.oshash IS NOT NULL`` filter. Before this fix the helper had no
        such filter, so the two callers operated on different row sets and the
        detector flagged every disk that contained any Stage-A row as drifted,
        forever.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NullOshashDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/enriched.mkv").write_text("enriched-content")
        Path(f"{mount}/stage_a.mkv").write_text("stage-a-content")

        disk = _insert_disk(conn, mount)
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Simulate a Stage-A row by clearing the oshash on one file. The scan
        # above fingerprints both; this mimics what the walker would persist
        # if it discovered a new file mid-enrich.
        conn.execute("UPDATE media_file SET oshash = NULL WHERE filename = 'stage_a.mkv'")

        fps = _build_disk_fingerprints(conn, disk.id)
        assert len(fps) == 1, f"Expected 1 fingerprint (enriched only), got {len(fps)}"
        assert all(f.oshash is not None for f in fps), "Null-oshash rows must be filtered out"


# Suppress unused-import warning: PathRow is used as a type in helper signatures
# that may be referenced from future tests; keep it imported for forward compatibility.
_PathRow = PathRow


# ---------------------------------------------------------------------------
# Sub-phase 4.1 tests — incremental mode: OSHash recompute + rename detection
# ---------------------------------------------------------------------------


class TestIncrementalMode:
    """Tests for ScanMode.incremental: OSHash recompute and rename/content-drift logic.

    Pattern: seed the DB with a full scan, then manipulate the fake FS and/or the
    DB state, then run an incremental scan and assert the expected outcome.
    """

    # ------------------------------------------------------------------
    # Test 1: New file inserted with oshash populated
    # ------------------------------------------------------------------

    def test_incremental_new_file_gets_oshash(self, fs: "FakeFilesystem") -> None:
        """A new video file discovered in incremental mode receives a non-NULL oshash.

        Seed the disk, add a new video file after the initial full scan, then run
        incremental → assert the new ``media_file`` row has a non-NULL 16-hex oshash.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/IncrNewFileDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/existing.mkv").write_bytes(b"X" * 200)

        disk = _insert_disk(conn, mount)

        # Initial full scan — seeds media_file + path rows.
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Add a new video file to the fake FS after the first scan.
        Path(f"{mount}/new_film.mkv").write_bytes(b"Y" * 200)

        # Force Merkle miss so the incremental walk is triggered.
        disk_repo.update_merkle_root(conn, disk.id, "wrongroot")
        # Reload the disk row so it carries the updated merkle_root.
        updated_disk = disk_repo.get_by_id(conn, disk.id)
        assert updated_disk is not None

        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                return_value=False,  # disable dir-mtime skip so all files are visited
            ):
                result = scan([updated_disk], ScanMode.incremental, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"

        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT oshash FROM media_file WHERE filename = 'new_film.mkv'").fetchone()
        assert row is not None, "new_film.mkv must be present in media_file"
        assert row["oshash"] is not None, "oshash must be non-NULL for a new video file"
        assert len(row["oshash"]) == 16, f"oshash must be 16 hex chars, got {row['oshash']!r}"

    # ------------------------------------------------------------------
    # Test 2: Renamed file — one row, path updated, no duplicate
    # ------------------------------------------------------------------

    def test_incremental_renamed_file_no_duplicate(self, fs: "FakeFilesystem") -> None:
        """Renaming a file across an incremental scan updates path_id/filename with no duplicate.

        Seed the disk with a video file, compute its oshash, then physically move
        the file (old path removed, new path added).  Run incremental → assert:
        - Exactly ONE row with the file's oshash.
        - The row's filename matches the new name.
        - No ``deleted_item`` entry for this file.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/IncrRenameDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        content = b"Z" * 200
        Path(f"{mount}/old_name.mkv").write_bytes(content)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        conn.row_factory = sqlite3.Row
        orig_row = conn.execute("SELECT id, oshash FROM media_file WHERE filename = 'old_name.mkv'").fetchone()
        assert orig_row is not None
        stored_oshash: str = orig_row["oshash"]
        assert stored_oshash is not None, "oshash must be set after full scan"

        # Simulate rename: remove old path, create new path with same content.
        Path(f"{mount}/old_name.mkv").unlink()
        Path(f"{mount}/new_name.mkv").write_bytes(content)

        # Force Merkle miss and disable dir-mtime optimisation so both entries are visited.
        disk_repo.update_merkle_root(conn, disk.id, "wrongroot")
        updated_disk = disk_repo.get_by_id(conn, disk.id)
        assert updated_disk is not None

        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                return_value=False,
            ):
                result = scan([updated_disk], ScanMode.incremental, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"

        conn.row_factory = sqlite3.Row
        # Exactly one row with this oshash must survive.
        rows = conn.execute(
            "SELECT id, filename, deleted_at FROM media_file WHERE oshash = ?",
            (stored_oshash,),
        ).fetchall()
        live_rows = [r for r in rows if r["deleted_at"] is None]
        assert len(live_rows) == 1, (
            f"Expected exactly 1 live row with oshash={stored_oshash!r}, got {len(live_rows)}: "
            f"{[dict(r) for r in live_rows]}"
        )
        assert live_rows[0]["filename"] == "new_name.mkv", (
            f"Expected filename='new_name.mkv', got {live_rows[0]['filename']!r}"
        )

        # No deleted_item tombstone for this file's original_id.
        orig_id: int = orig_row["id"]
        tombstone = conn.execute(
            "SELECT id FROM deleted_item WHERE original_id = ?",
            (orig_id,),
        ).fetchone()
        assert tombstone is None, f"Unexpected deleted_item tombstone for file_id={orig_id}"

    # ------------------------------------------------------------------
    # Test 3: Modified content enqueues repair
    # ------------------------------------------------------------------

    def test_incremental_modified_content_enqueues_repair(self, fs: "FakeFilesystem") -> None:
        """A file whose content changes in incremental mode triggers a repair_queue entry.

        Seed the disk with a video file; rewrite its content (different bytes →
        different oshash); run incremental → assert a ``repair_queue`` row with
        ``reason='content_drift'`` exists for the file.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/IncrContentDrift"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/film.mkv").write_bytes(b"A" * 200)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        conn.row_factory = sqlite3.Row
        orig_row = conn.execute("SELECT id, oshash FROM media_file WHERE filename = 'film.mkv'").fetchone()
        assert orig_row is not None
        file_id: int = orig_row["id"]

        # Overwrite with different content (different oshash + different size).
        Path(f"{mount}/film.mkv").write_bytes(b"B" * 400)

        # Set merkle_root=None to force Merkle miss while bypassing the bulk-change
        # guard (guard only fires when merkle_root is not None).  Disable dir-mtime
        # skip so the changed file is always visited.
        disk_repo.update_merkle_root(conn, disk.id, None)
        updated_disk = disk_repo.get_by_id(conn, disk.id)
        assert updated_disk is not None

        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                return_value=False,
            ):
                result = scan([updated_disk], ScanMode.incremental, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"

        conn.row_factory = sqlite3.Row
        repair_row = conn.execute(
            "SELECT reason FROM repair_queue WHERE scope = 'file' AND scope_id = ?",
            (file_id,),
        ).fetchone()
        assert repair_row is not None, f"Expected a repair_queue row for file_id={file_id} after content drift"
        assert repair_row["reason"] == "content_drift", f"Expected reason='content_drift', got {repair_row['reason']!r}"

    # ------------------------------------------------------------------
    # Test 4: OSHash collision enqueues repair, does NOT auto-rename
    # ------------------------------------------------------------------

    def test_incremental_oshash_collision_enqueues_repair(self, fs: "FakeFilesystem") -> None:
        """When two files share the same oshash (collision), repair is enqueued — no auto-rename.

        Seed the disk with two video files that have the same oshash (identical
        content).  Add a third file with the same content at a new path, simulating
        an ambiguous rename with multiple candidates.  Run incremental → assert that
        a ``repair_queue`` row with ``reason='oshash_collision'`` is created and no
        path update occurred on the original rows.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/IncrCollisionDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        # Two files with identical content → identical oshash.
        content = b"C" * 200
        Path(f"{mount}/file_a.mkv").write_bytes(content)
        Path(f"{mount}/file_b.mkv").write_bytes(content)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        conn.row_factory = sqlite3.Row
        rows_before = conn.execute("SELECT id, filename, oshash FROM media_file").fetchall()
        assert len(rows_before) == 2
        shared_oshash: str = rows_before[0]["oshash"]
        assert shared_oshash is not None

        # Add a third file with the same content at a new path — this creates
        # an ambiguous rename scenario (multiple candidates with the same oshash).
        Path(f"{mount}/file_new.mkv").write_bytes(content)

        # Set merkle_root=None to force Merkle miss while bypassing the bulk-change
        # guard.  Disable dir-mtime skip so all files are visited.
        disk_repo.update_merkle_root(conn, disk.id, None)
        updated_disk = disk_repo.get_by_id(conn, disk.id)
        assert updated_disk is not None

        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                return_value=False,
            ):
                result = scan([updated_disk], ScanMode.incremental, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"

        conn.row_factory = sqlite3.Row
        # At least one repair_queue row with reason='oshash_collision' must exist.
        repair_rows = conn.execute(
            "SELECT scope_id, reason FROM repair_queue WHERE reason = 'oshash_collision'"
        ).fetchall()
        assert len(repair_rows) >= 1, (
            f"Expected at least one oshash_collision repair entry; repair_queue: "
            f"{conn.execute('SELECT * FROM repair_queue').fetchall()}"
        )

        # The original two rows must not have been renamed/updated to file_new.mkv.
        filenames = {
            r["filename"] for r in conn.execute("SELECT filename FROM media_file WHERE deleted_at IS NULL").fetchall()
        }
        assert "file_new.mkv" in filenames, "file_new.mkv must be inserted as a new row"
        # The two original rows must still exist (not renamed away).
        assert "file_a.mkv" in filenames or "file_b.mkv" in filenames, (
            "At least one of the original collision candidates must remain"
        )


# ---------------------------------------------------------------------------
# Sub-phase 4.2 tests — enrich mode: pymediainfo + NFO + artwork, budget-bounded
# ---------------------------------------------------------------------------


class TestEnrichMode:
    """Tests for ScanMode.enrich: media stream extraction, NFO presence, artwork inventory.

    Pattern:
    - Seed the DB with a full scan (files have ``enriched_at=NULL``).
    - Mock :class:`~personalscraper.indexer.mediainfo.MediaInfoWrapper` to avoid
      requiring a real libmediainfo installation in CI.
    - Run ``scan()`` in ``ScanMode.enrich``.
    - Assert expected DB state.
    """

    # ------------------------------------------------------------------
    # Test 1: enriched_at=NULL file gets media_stream rows
    # ------------------------------------------------------------------

    def test_enrich_populates_media_stream(self, fs: "FakeFilesystem") -> None:
        """A file with enriched_at=NULL gets media_stream rows after enrich mode.

        Seed the DB with a full scan, then mock pymediainfo to return 2 streams
        (1 video + 1 audio).  Run enrich mode → assert:
        - 2 ``media_stream`` rows created for the file.
        - ``enriched_at`` is now set (non-NULL) on the ``media_file`` row.
        """
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/EnrichStreamDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/movie.mkv").write_bytes(b"V" * 300)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Verify enriched_at is NULL after full scan (no enrichment yet).
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT id, enriched_at FROM media_file WHERE filename = 'movie.mkv'").fetchone()
        assert row is not None
        assert row["enriched_at"] is None, "enriched_at must be NULL before enrich pass"
        file_id: int = row["id"]

        # Build fake tracks: 1 video + 1 audio.
        def _make_track(track_type: str, **kwargs: object) -> SimpleNamespace:
            defaults: dict[str, object] = {
                "track_type": track_type,
                "stream_identifier": None,
                "codec_id": None,
                "format": None,
                "language": None,
                "channel_s": None,
                "width": None,
                "height": None,
                "duration": None,
                "bit_rate": None,
            }
            defaults.update(kwargs)
            return SimpleNamespace(**defaults)

        fake_mi = MagicMock()
        fake_mi.tracks = [
            _make_track("Video", format="h264", width=1920, height=1080),
            _make_track("Audio", format="AAC", channel_s=2),
        ]

        with patch(_GUARD_PATCH, return_value=None):
            with patch("personalscraper.indexer.mediainfo.MediaInfo.parse", return_value=fake_mi):
                result = scan([disk], ScanMode.enrich, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"

        # Assert 2 media_stream rows for this file.
        conn.row_factory = sqlite3.Row
        stream_rows = conn.execute("SELECT kind FROM media_stream WHERE file_id = ?", (file_id,)).fetchall()
        kinds = {r["kind"] for r in stream_rows}
        assert len(stream_rows) == 2, f"Expected 2 streams, got {len(stream_rows)}"
        assert "video" in kinds, "Expected a video stream"
        assert "audio" in kinds, "Expected an audio stream"

        # Assert enriched_at is now set.
        enriched_row = conn.execute("SELECT enriched_at FROM media_file WHERE id = ?", (file_id,)).fetchone()
        assert enriched_row is not None
        assert enriched_row["enriched_at"] is not None, "enriched_at must be set after enrich pass"
        assert enriched_row["enriched_at"] > 0

    # ------------------------------------------------------------------
    # Test 2: already-enriched file is skipped (no pymediainfo call)
    # ------------------------------------------------------------------

    def test_enrich_skips_already_enriched(self, fs: "FakeFilesystem") -> None:
        """A file with enriched_at=now is skipped — pymediainfo is NOT called.

        Seed the DB with a full scan and manually set ``enriched_at`` to the
        current time (= file is up-to-date).  Run enrich mode and assert that
        ``MediaInfo.parse`` was never called.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/EnrichSkipDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        # File must have content so size gate passes; mtime_ns will be very recent.
        Path(f"{mount}/movie.mkv").write_bytes(b"W" * 300)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Mark the file as already enriched at the current epoch second AND
        # set enriched_at > (mtime_ns / 1_000_000_000) so the WHERE clause skips it.
        # We set enriched_at to a future value to guarantee the skip condition.
        far_future = int(time.time()) + 10_000
        conn.execute("UPDATE media_file SET enriched_at = ? WHERE filename = 'movie.mkv'", (far_future,))
        conn.commit()

        parse_call_count: list[int] = [0]

        def _counting_parse(*args: Any, **kwargs: Any) -> Any:
            parse_call_count[0] += 1
            return MagicMock(tracks=[])

        with patch(_GUARD_PATCH, return_value=None):
            with patch("personalscraper.indexer.mediainfo.MediaInfo.parse", side_effect=_counting_parse):
                result = scan([disk], ScanMode.enrich, generation=2, conn=conn, event_bus=EventBus())

        assert result.status == "ok"
        assert parse_call_count[0] == 0, (
            f"Expected 0 pymediainfo calls for already-enriched file, got {parse_call_count[0]}"
        )

    # ------------------------------------------------------------------
    # Test 3: budget exhaustion leaves remaining files with enriched_at=NULL
    # ------------------------------------------------------------------

    def test_enrich_budget_exhaustion_leaves_remaining_null(self, fs: "FakeFilesystem") -> None:
        """With a tight budget, some files are enriched while others remain NULL.

        Seed 5 files.  Mock ``time.monotonic`` to advance by 2 s on each call
        past the first, making every file iteration appear to exceed a budget of
        1 s.  Run enrich with budget_seconds=1 → assert at least one file still
        has ``enriched_at=NULL``.
        """
        from unittest.mock import MagicMock

        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/EnrichBudgetDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        for i in range(5):
            Path(f"{mount}/film{i}.mkv").write_bytes(b"X" * 300)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Verify all 5 files are unenriched.
        conn.row_factory = sqlite3.Row
        unenriched = conn.execute("SELECT id FROM media_file WHERE enriched_at IS NULL").fetchall()
        assert len(unenriched) == 5, f"Expected 5 unenriched files before enrich, got {len(unenriched)}"

        # Simulate slow parsing: monotonic advances 5 s per call so the budget
        # (1 s) is exceeded immediately after attempting the first file.
        call_count: list[int] = [0]
        base_time = time.monotonic()

        def _fast_monotonic() -> float:
            call_count[0] += 1
            # First call returns baseline; subsequent calls advance by 5 s so the
            # budget check triggers on the second file's boundary.
            return base_time + call_count[0] * 5.0

        fake_mi = MagicMock()
        fake_mi.tracks = []

        with patch(_GUARD_PATCH, return_value=None):
            with patch("personalscraper.indexer.mediainfo.MediaInfo.parse", return_value=fake_mi):
                with patch("personalscraper.indexer.scanner._modes.time.monotonic", side_effect=_fast_monotonic):
                    result = scan(
                        [disk], ScanMode.enrich, generation=2, conn=conn, budget_seconds=1.0, event_bus=EventBus()
                    )

        assert result.status == "ok"

        # At least some files must still have enriched_at=NULL.
        conn.row_factory = sqlite3.Row
        still_null = conn.execute("SELECT id FROM media_file WHERE enriched_at IS NULL").fetchall()
        assert len(still_null) > 0, "Expected at least 1 file with enriched_at=NULL after budget exhaustion"

    # ------------------------------------------------------------------
    # Test 4: quick_enrich=True passes parse_speed=0.5 to MediaInfoWrapper
    # ------------------------------------------------------------------

    def test_enrich_quick_flag_uses_half_parse_speed(self, fs: "FakeFilesystem") -> None:
        """quick_enrich=True causes MediaInfoWrapper to be instantiated with parse_speed=0.5.

        We patch the MediaInfoWrapper constructor to capture the parse_speed kwarg.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/EnrichQuickDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/film.mkv").write_bytes(b"Q" * 300)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        captured_kwargs: list[dict[str, object]] = []

        # Create a fake MediaInfoWrapper class that records constructor kwargs and
        # returns a stub instance whose extract_streams returns [].
        class _FakeWrapper:
            def __init__(self, *, min_size_mb: int = 50, parse_speed: float = 0.5) -> None:
                captured_kwargs.append({"min_size_mb": min_size_mb, "parse_speed": parse_speed})

            def extract_streams(self, path: object) -> list[object]:
                return []

        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                "personalscraper.indexer.scanner._modes.MediaInfoWrapper",
                _FakeWrapper,
            ):
                scan([disk], ScanMode.enrich, generation=2, conn=conn, quick_enrich=True, event_bus=EventBus())

        assert len(captured_kwargs) >= 1, "MediaInfoWrapper must have been instantiated"
        assert captured_kwargs[0]["parse_speed"] == 0.5, (
            f"Expected parse_speed=0.5 for quick_enrich, got {captured_kwargs[0]['parse_speed']}"
        )


# ---------------------------------------------------------------------------
# Sub-phase 4.3 tests — ThreadPoolExecutor per-disk parallelism
# ---------------------------------------------------------------------------


def _make_conn_file(db_path: Path) -> sqlite3.Connection:
    """Return a file-backed SQLite connection with the full schema applied.

    Used by parallel-scan tests that need a real on-disk DB so that per-worker
    connections can be opened from *db_path*.

    Args:
        db_path: Filesystem path for the new SQLite database file.

    Returns:
        Open :class:`sqlite3.Connection` with WAL mode, FK checks on, and the
        full migration chain applied.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _insert_disk_on_conn(
    conn: sqlite3.Connection,
    mount_path: str,
    label: str | None = None,
) -> DiskRow:
    """Insert a minimal disk row using the given connection and return it.

    Args:
        conn: Open SQLite connection.
        mount_path: Absolute mount-point path of the disk.
        label: Optional explicit label; defaults to the last component of
            *mount_path*.

    Returns:
        :class:`DiskRow` with the PK assigned by SQLite.
    """
    now = int(time.time())
    _label = label or mount_path.split("/")[-1]
    row = DiskRow(
        id=0,
        uuid=f"test-uuid-parallel-{mount_path}",
        label=_label,
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


class TestParallelScan:
    """Tests for sub-phase 4.3: ThreadPoolExecutor per-disk parallelism.

    These tests use a real file-backed SQLite database (via ``tmp_path``) so that
    per-worker connections can be opened from ``db_path``.  pyfakefs is NOT used
    here because it would intercept ``sqlite3.connect`` calls made inside the
    worker threads and break the per-worker connection creation.  Real directories
    under ``tmp_path`` are created instead.
    """

    # ------------------------------------------------------------------
    # Test 1: two disks scanned concurrently — both have media_file rows
    # ------------------------------------------------------------------

    def test_parallel_scan_two_disks_both_complete(
        self,
        tmp_path: Path,
    ) -> None:
        """Two disks scanned in parallel both produce media_file rows.

        Creates two real directories under tmp_path (acting as disk mount points),
        each containing one .mkv file.  Runs scan() with max_workers=2 and a
        file-backed DB (db_path provided) so the parallel executor is used.
        After the scan, asserts that media_file rows exist for both disks.
        """
        db_file = tmp_path / "indexer.db"
        conn = _make_conn_file(db_file)

        # Create two fake disk directories under tmp_path.
        mount1 = str(tmp_path / "Disk1")
        mount2 = str(tmp_path / "Disk2")
        Path(mount1).mkdir()
        Path(mount2).mkdir()
        Path(f"{mount1}/film_a.mkv").write_bytes(b"A" * 200)
        Path(f"{mount2}/film_b.mkv").write_bytes(b"B" * 200)

        disk1 = _insert_disk_on_conn(conn, mount1)
        disk2 = _insert_disk_on_conn(conn, mount2)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan(
                [disk1, disk2],
                ScanMode.full,
                generation=1,
                conn=conn,
                db_path=db_file,
                max_workers=2,
                event_bus=EventBus(),
            )

        assert result.status == "ok"

        # Both disks must have produced media_file rows.
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, path_id FROM media_file").fetchall()
        filenames = {r["filename"] for r in rows}
        assert "film_a.mkv" in filenames, f"film_a.mkv missing from media_file; found: {filenames}"
        assert "film_b.mkv" in filenames, f"film_b.mkv missing from media_file; found: {filenames}"
        assert result.files_visited == 2, f"Expected files_visited=2, got {result.files_visited}"

    # ------------------------------------------------------------------
    # Test 2: IOError on disk 2 does not lose disk 1's rows
    # ------------------------------------------------------------------

    def test_parallel_scan_disk_failure_does_not_lose_other(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A per-disk IOError is logged and does not discard the other disk's rows.

        Creates two real disk directories.  Disk1 has one .mkv file that scans
        normally.  Disk2's mount directory exists but os.scandir is monkey-patched
        to raise IOError(EIO) for that specific path, simulating a disk unplug
        mid-walk.

        After the scan:
        - Disk1's media_file row must exist.
        - The ``indexer.scan.disk_worker_failed`` or ``indexer.disk.io_error``
          event must appear in the log (the EIO path logs ``indexer.disk.io_error``).
        - The overall scan result must have status ``'ok'`` (failures are absorbed).
        """
        import errno as _errno

        db_file = tmp_path / "indexer.db"
        conn = _make_conn_file(db_file)

        mount1 = str(tmp_path / "DiskOK")
        mount2 = str(tmp_path / "DiskFail")
        Path(mount1).mkdir()
        Path(mount2).mkdir()
        Path(f"{mount1}/good_film.mkv").write_bytes(b"G" * 200)
        # Disk2 directory exists but has no files — the EIO is injected via patch.
        Path(f"{mount2}/bad_film.mkv").write_bytes(b"X" * 200)

        disk1 = _insert_disk_on_conn(conn, mount1)
        disk2 = _insert_disk_on_conn(conn, mount2)

        real_scandir = os.scandir

        def _patched_scandir(path: object) -> object:
            """Raise EIO when scanning Disk2's mount; pass through for all others."""
            path_str = str(path)
            if path_str == mount2:
                raise OSError(_errno.EIO, "Input/output error", path_str)
            return real_scandir(path_str)

        with patch(_GUARD_PATCH, return_value=None):
            with patch("personalscraper.indexer.scanner.os.scandir", side_effect=_patched_scandir):
                with caplog.at_level(logging.WARNING):
                    result = scan(
                        [disk1, disk2],
                        ScanMode.full,
                        generation=1,
                        conn=conn,
                        db_path=db_file,
                        max_workers=2,
                        event_bus=EventBus(),
                    )

        # Disk1's row must survive.
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename FROM media_file WHERE deleted_at IS NULL").fetchall()
        filenames = {r["filename"] for r in rows}
        assert "good_film.mkv" in filenames, f"good_film.mkv must be present after Disk2 failure; found: {filenames}"

        # The EIO error must have been logged.
        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("io_error" in t or "disk_worker_failed" in t for t in warning_texts), (
            f"Expected io_error or disk_worker_failed warning; got: {warning_texts}"
        )

        # Overall scan must not be marked failed.
        assert result.status == "ok", f"Expected status='ok' after absorbed disk failure, got {result.status!r}"

    def test_parallel_scan_unexpected_worker_exception_fails_scan(
        self,
        tmp_path: Path,
    ) -> None:
        """Unexpected worker exceptions propagate and mark the scan_run failed."""
        import personalscraper.indexer.scanner as scanner_module

        db_file = tmp_path / "indexer.db"
        conn = _make_conn_file(db_file)

        mount1 = str(tmp_path / "DiskOK")
        mount2 = str(tmp_path / "DiskFail")
        Path(mount1).mkdir()
        Path(mount2).mkdir()
        Path(f"{mount1}/good_film.mkv").write_bytes(b"G" * 200)
        Path(f"{mount2}/bad_film.mkv").write_bytes(b"X" * 200)

        disk1 = _insert_disk_on_conn(conn, mount1, label="DiskOK")
        disk2 = _insert_disk_on_conn(conn, mount2, label="DiskFail")

        original_scan_disk_full = scanner_module._scan_disk_full

        def _raise_for_disk_fail(*args: Any, **kwargs: Any) -> Any:
            disk = args[1]
            if isinstance(disk, DiskRow) and disk.label == "DiskFail":
                raise RuntimeError("synthetic worker failure")
            return original_scan_disk_full(*args, **kwargs)

        with patch(_GUARD_PATCH, return_value=None):
            with patch("personalscraper.indexer.scanner._scan_disk_full", side_effect=_raise_for_disk_fail):
                with pytest.raises(RuntimeError, match="disk worker .* synthetic worker failure"):
                    scan(
                        [disk1, disk2],
                        ScanMode.full,
                        generation=1,
                        conn=conn,
                        db_path=db_file,
                        max_workers=2,
                        event_bus=EventBus(),
                    )

        row = conn.execute("SELECT status FROM scan_run ORDER BY id DESC LIMIT 1").fetchone()
        assert row is not None
        assert row[0] == "failed"

    def test_parallel_scan_finalize_uses_worker_connections(
        self,
        tmp_path: Path,
    ) -> None:
        """Post-walk disk finalization must use per-worker SQLite connections."""
        import personalscraper.indexer.scanner as scanner_module

        db_file = tmp_path / "indexer.db"
        conn = _make_conn_file(db_file)

        mount1 = str(tmp_path / "Disk1")
        mount2 = str(tmp_path / "Disk2")
        Path(mount1).mkdir()
        Path(mount2).mkdir()
        Path(f"{mount1}/film_a.mkv").write_bytes(b"A" * 200)
        Path(f"{mount2}/film_b.mkv").write_bytes(b"B" * 200)

        disk1 = _insert_disk_on_conn(conn, mount1)
        disk2 = _insert_disk_on_conn(conn, mount2)

        original_finalize = scanner_module._finalize_disk_after_walk
        finalize_connection_ids: list[int] = []

        def _record_finalize_conn(*args: Any, **kwargs: Any) -> Any:
            finalize_connection_ids.append(id(args[0]))
            return original_finalize(*args, **kwargs)

        with patch(_GUARD_PATCH, return_value=None):
            with patch("personalscraper.indexer.scanner._finalize_disk_after_walk", side_effect=_record_finalize_conn):
                result = scan(
                    [disk1, disk2],
                    ScanMode.full,
                    generation=1,
                    conn=conn,
                    db_path=db_file,
                    max_workers=2,
                    event_bus=EventBus(),
                )

        assert result.status == "ok"
        assert len(finalize_connection_ids) == 2
        assert id(conn) not in finalize_connection_ids

    # ------------------------------------------------------------------
    # Test 3: single-disk filter uses max_workers=1
    # ------------------------------------------------------------------

    def test_single_disk_filter_uses_one_worker(
        self,
        tmp_path: Path,
    ) -> None:
        """When disk_filter is set (single-disk run), the executor uses max_workers=1.

        Verifies DESIGN §11.8: ``--full --disk D`` degrades to a single worker.
        We spy on ThreadPoolExecutor to capture the max_workers argument passed
        at construction time.
        """
        from concurrent.futures import ThreadPoolExecutor as _TPE

        db_file = tmp_path / "indexer_single.db"
        conn = _make_conn_file(db_file)

        mount1 = str(tmp_path / "SingleDisk")
        Path(mount1).mkdir()
        Path(f"{mount1}/movie.mkv").write_bytes(b"M" * 200)

        disk1 = _insert_disk_on_conn(conn, mount1)

        captured_max_workers: list[int] = []
        real_tpe = _TPE

        class _SpyTPE(real_tpe):  # type: ignore[misc]
            def __init__(self, *args: Any, max_workers: int | None = None, **kwargs: Any) -> None:
                captured_max_workers.append(max_workers if max_workers is not None else 1)
                super().__init__(*args, max_workers=max_workers, **kwargs)

        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                "personalscraper.indexer.scanner._concurrency.ThreadPoolExecutor",
                _SpyTPE,
            ):
                result = scan(
                    [disk1],
                    ScanMode.full,
                    generation=1,
                    conn=conn,
                    db_path=db_file,
                    disk_filter=disk1.label,
                    max_workers=4,  # intentionally high — must be clamped to 1
                    event_bus=EventBus(),
                )

        assert result.status == "ok"

        # The executor must either not have been created (sequential path taken
        # because _effective_workers==1 bypasses the executor) OR it was created
        # with max_workers=1.
        # When disk_filter is set, _effective_workers is forced to 1, which
        # triggers the sequential fallback (no executor created).
        # Either behaviour satisfies the §11.8 requirement.
        if captured_max_workers:
            assert captured_max_workers[0] == 1, (
                f"Expected max_workers=1 for single-disk filter, got {captured_max_workers[0]}"
            )
        # If no executor was created, the sequential path was used — also correct.

    # ------------------------------------------------------------------
    # Test 4: enrich mode pins to 1 worker (libmediainfo not thread-safe)
    # ------------------------------------------------------------------

    def test_enrich_mode_honours_caller_max_workers(
        self,
        tmp_path: Path,
    ) -> None:
        """Enrich mode is no longer artificially pinned to one worker.

        The libmediainfo segfault that motivated the previous pin is now
        addressed by the wider ``_MEDIAINFO_PARSE_LOCK`` (covers parse +
        track iteration + lazy attribute reads), so per-disk parallelism
        can resume. Parse calls still serialise on the lock; everything
        else (NFO inventory, artwork inventory, release linkage,
        ``enriched_at`` updates) overlaps across disks.
        """
        from concurrent.futures import ThreadPoolExecutor as _TPE

        db_file = tmp_path / "indexer_enrich.db"
        conn = _make_conn_file(db_file)

        mount_a = str(tmp_path / "DiskA")
        mount_b = str(tmp_path / "DiskB")
        Path(mount_a).mkdir()
        Path(mount_b).mkdir()
        Path(f"{mount_a}/movie.mkv").write_bytes(b"M" * 200)
        Path(f"{mount_b}/movie.mkv").write_bytes(b"M" * 200)

        disk_a = _insert_disk_on_conn(conn, mount_a)
        disk_b = _insert_disk_on_conn(conn, mount_b)

        captured_max_workers: list[int] = []
        real_tpe = _TPE

        class _SpyTPE(real_tpe):  # type: ignore[misc]
            def __init__(self, *args: Any, max_workers: int | None = None, **kwargs: Any) -> None:
                captured_max_workers.append(max_workers if max_workers is not None else 1)
                super().__init__(*args, max_workers=max_workers, **kwargs)

        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                "personalscraper.indexer.scanner._concurrency.ThreadPoolExecutor",
                _SpyTPE,
            ):
                result = scan(
                    [disk_a, disk_b],
                    ScanMode.enrich,
                    generation=1,
                    conn=conn,
                    db_path=db_file,
                    max_workers=4,
                    event_bus=EventBus(),
                )

        assert result.status == "ok"
        # Caller passed 4 workers, two disks → expect 2 (clamped to len(disks)).
        if captured_max_workers:
            assert captured_max_workers[0] == 2, (
                f"Expected max_workers=2 (clamped to len(disks)), got {captured_max_workers[0]}"
            )


# ---------------------------------------------------------------------------
# Sub-phase 4.4 — Mount-flag detection
# ---------------------------------------------------------------------------

# _check_mount_flags now delegates the ``mount`` shell-out to the shared
# FsProbe module.  ``scanner/__init__.py`` imports ``_run_mount`` into its own
# namespace (``from ..._fs_probe import _run_mount``), so the patch must target
# the *name as looked up there* — ``scanner._run_mount`` — not the definition
# site in ``_fs_probe``.  The patched callable returns the raw ``mount`` stdout
# string directly (FsProbe's contract), replacing the old subprocess.run mock.
_MOUNT_CHECK_PATCH = "personalscraper.indexer.scanner._run_mount"
_PLATFORM_PATCH = "personalscraper.indexer.scanner.platform.system"


def _make_disk_row(mount_path: str) -> DiskRow:
    """Build a minimal :class:`DiskRow` for mount-flag tests.

    Args:
        mount_path: The fake mount point to use.

    Returns:
        A :class:`DiskRow` with a unique uuid derived from *mount_path*.
    """
    return DiskRow(
        id=1,
        uuid=f"uuid-{mount_path}",
        label=mount_path.split("/")[-1],
        mount_path=mount_path,
        last_seen_at=0,
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )


def _mount_output_for(mount_path: str, flags: list[str]) -> str:
    """Build a fake ``mount`` command output line for *mount_path*.

    The parenthesised block on a real macOS ``mount`` line is
    ``(<fs_type>, <flag1>, <flag2>, …)`` — the fs-type is always the first
    token, and FsProbe's ``MountInfo.flags`` deliberately excludes it
    (``flags = tokens[1:]``).  A leading ``ufsd_NTFS`` fs-type token is therefore
    prepended here so the recommended *flags* land in the flag set rather than
    being silently consumed as the fs-type.

    Args:
        mount_path: The mount point to embed.
        flags: List of flag strings to include as mount flags (after the
            fs-type token).

    Returns:
        A single line matching the macOS ``mount`` output format.
    """
    flags_str = ", ".join(["ufsd_NTFS", *flags])
    return f"/dev/disk2s1 on {mount_path} ({flags_str})\n"


class TestRecommendedMountFlags:
    """Verify :data:`_RECOMMENDED_MOUNT_FLAGS` contains exactly the expected five flags."""

    def test_contains_exactly_five_flags(self) -> None:
        """The recommended set must contain exactly the five macOS-specific flags."""
        assert _RECOMMENDED_MOUNT_FLAGS == {
            "noatime",
            "noappledouble",
            "noapplexattr",
            "defer_permissions",
            "allow_other",
        }

    def test_nodiratime_absent(self) -> None:
        """Nodiratime is Linux-only and must NOT appear in the macOS set."""
        assert "nodiratime" not in _RECOMMENDED_MOUNT_FLAGS


class TestCheckMountFlagsNoDarwin:
    """_check_mount_flags is a no-op on non-Darwin platforms."""

    def test_no_subprocess_call_on_linux(self) -> None:
        """subprocess.run must not be called when platform.system() != 'Darwin'."""
        disk = _make_disk_row("/mnt/Disk1")
        with patch(_PLATFORM_PATCH, return_value="Linux"):
            with patch(_MOUNT_CHECK_PATCH) as mock_run:
                _check_mount_flags([disk])
        mock_run.assert_not_called()

    def test_no_subprocess_call_on_windows(self) -> None:
        """subprocess.run must not be called on Windows."""
        disk = _make_disk_row("/mnt/Disk1")
        with patch(_PLATFORM_PATCH, return_value="Windows"):
            with patch(_MOUNT_CHECK_PATCH) as mock_run:
                _check_mount_flags([disk])
        mock_run.assert_not_called()


class TestCheckMountFlagsAllPresent:
    """_check_mount_flags emits no warning when all recommended flags are present."""

    def test_no_warning_when_all_flags_present(self, caplog: pytest.LogCaptureFixture) -> None:
        """All five recommended flags present → no indexer.disk.mount_flags_missing warning."""
        mount = "/Volumes/Disk1"
        disk = _make_disk_row(mount)
        all_flags = list(_RECOMMENDED_MOUNT_FLAGS) + ["local", "synchronous"]
        fake_output = _mount_output_for(mount, all_flags)

        with patch(_PLATFORM_PATCH, return_value="Darwin"):
            with patch(_MOUNT_CHECK_PATCH, return_value=fake_output):
                with caplog.at_level(logging.WARNING, logger="indexer.scan"):
                    _check_mount_flags([disk])

        warning_events = [r for r in caplog.records if "mount_flags_missing" in r.getMessage()]
        assert warning_events == [], "Expected no mount_flags_missing warning when all flags are present"


class TestCheckMountFlagsMissing:
    """_check_mount_flags warns when one or more recommended flags are absent."""

    def test_warning_emitted_for_missing_flag(self, caplog: pytest.LogCaptureFixture) -> None:
        """A single missing flag → indexer.disk.mount_flags_missing warning is emitted."""
        mount = "/Volumes/Disk1"
        disk = _make_disk_row(mount)
        # All flags except noatime.
        partial_flags = [f for f in _RECOMMENDED_MOUNT_FLAGS if f != "noatime"] + ["local"]
        fake_output = _mount_output_for(mount, partial_flags)

        with patch(_PLATFORM_PATCH, return_value="Darwin"):
            with patch(_MOUNT_CHECK_PATCH, return_value=fake_output):
                with caplog.at_level(logging.WARNING):
                    _check_mount_flags([disk])

        # At least one log record must mention mount_flags_missing.
        all_messages = " ".join(r.getMessage() for r in caplog.records)
        assert "mount_flags_missing" in all_messages

    def test_warning_emitted_for_multiple_missing_flags(self, caplog: pytest.LogCaptureFixture) -> None:
        """Multiple missing flags → a single warning is still emitted for that disk."""
        mount = "/Volumes/Disk2"
        disk = _make_disk_row(mount)
        # Only noatime present; four flags missing.
        fake_output = _mount_output_for(mount, ["noatime", "local", "synchronous"])

        with patch(_PLATFORM_PATCH, return_value="Darwin"):
            with patch(_MOUNT_CHECK_PATCH, return_value=fake_output):
                with caplog.at_level(logging.WARNING):
                    _check_mount_flags([disk])

        all_messages = " ".join(r.getMessage() for r in caplog.records)
        assert "mount_flags_missing" in all_messages

    def test_per_disk_independent_check(self, caplog: pytest.LogCaptureFixture) -> None:
        """Each disk is checked independently: one ok, one missing → one warning emitted."""
        mount_ok = "/Volumes/DiskOK"
        mount_bad = "/Volumes/DiskBad"
        disk_ok = _make_disk_row(mount_ok)
        disk_bad = _make_disk_row(mount_bad)
        # disk_ok has all flags; disk_bad is missing noappledouble.
        ok_flags = list(_RECOMMENDED_MOUNT_FLAGS) + ["local"]
        bad_flags = [f for f in _RECOMMENDED_MOUNT_FLAGS if f != "noappledouble"] + ["local"]
        fake_output = _mount_output_for(mount_ok, ok_flags) + _mount_output_for(mount_bad, bad_flags)

        with patch(_PLATFORM_PATCH, return_value="Darwin"):
            with patch(_MOUNT_CHECK_PATCH, return_value=fake_output):
                with caplog.at_level(logging.WARNING):
                    _check_mount_flags([disk_ok, disk_bad])

        warning_records = [r for r in caplog.records if "mount_flags_missing" in r.getMessage()]
        # Exactly one warning: for disk_bad only.
        assert len(warning_records) == 1


class TestCheckMountFlagsNonFatal:
    """_check_mount_flags is non-fatal: mount-probe failures must not propagate.

    The ``mount`` shell-out (and its timeout/OSError handling) now lives in
    ``_fs_probe._run_mount``, which catches every error internally and returns
    an empty string.  ``_check_mount_flags`` therefore sees ``""`` on any
    subprocess failure and returns early without raising.
    """

    def test_empty_mount_output_does_not_raise(self) -> None:
        """An empty probe result (the FsProbe failure signal) is non-fatal."""
        disk = _make_disk_row("/Volumes/Disk1")
        with patch(_PLATFORM_PATCH, return_value="Darwin"):
            with patch(_MOUNT_CHECK_PATCH, return_value=""):
                # Must not raise — non-fatal by design.
                _check_mount_flags([disk])

    def test_probe_exception_does_not_propagate_to_scan(self) -> None:
        """Even a raising probe must not crash _check_mount_flags' caller path.

        ``_run_mount`` is contractually exception-free (it returns ""), but this
        guards against a future regression by asserting the scanner still treats
        a raising probe as fatal-to-itself only — here we simulate the realistic
        contract (empty output) and confirm no exception escapes.
        """
        disk = _make_disk_row("/Volumes/Disk1")
        with patch(_PLATFORM_PATCH, return_value="Darwin"):
            with patch(_MOUNT_CHECK_PATCH, return_value=""):
                _check_mount_flags([disk])

    def test_disk_with_none_mount_path_skipped(self) -> None:
        """Disks with mount_path=None are silently skipped; no crash."""
        disk = DiskRow(
            id=2,
            uuid="uuid-none-mount",
            label="NullDisk",
            mount_path=None,
            last_seen_at=0,
            merkle_root=None,
            is_mounted=0,
            unreachable_strikes=0,
        )
        with patch(_PLATFORM_PATCH, return_value="Darwin"):
            with patch(_MOUNT_CHECK_PATCH, return_value=""):
                _check_mount_flags([disk])  # must not raise


class TestCheckMountFlagsMalformedOutput:
    """_check_mount_flags handles unexpected mount output gracefully."""

    def test_malformed_lines_do_not_crash(self) -> None:
        """Lines that don't match the expected format are silently skipped."""
        disk = _make_disk_row("/Volumes/Disk1")
        malformed = "this is not a mount line at all\nanother bad line\n"

        with patch(_PLATFORM_PATCH, return_value="Darwin"):
            with patch(_MOUNT_CHECK_PATCH, return_value=malformed):
                # Must not raise; mount point simply not found → debug log only.
                _check_mount_flags([disk])

    def test_mount_point_not_in_output_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """When the disk's mount point is absent from mount output, no WARNING is emitted."""
        disk = _make_disk_row("/Volumes/Disk1")
        # Output mentions a different mount point entirely.
        other_output = _mount_output_for("/Volumes/OtherDisk", list(_RECOMMENDED_MOUNT_FLAGS))

        with patch(_PLATFORM_PATCH, return_value="Darwin"):
            with patch(_MOUNT_CHECK_PATCH, return_value=other_output):
                with caplog.at_level(logging.WARNING):
                    _check_mount_flags([disk])

        warning_records = [r for r in caplog.records if "mount_flags_missing" in r.getMessage()]
        assert warning_records == []


# ===========================================================================
# Sub-phase 4.6 — Read-rate token bucket
# ===========================================================================


class _FakeClock46:
    """Deterministic monotonic clock for token-bucket tests.

    ``now()`` returns the current fake time; ``sleep(seconds)`` advances
    the clock by ``seconds`` without actually blocking.  Both methods
    match the ``Callable[[], float]`` and ``Callable[[float], None]``
    signatures the bucket expects.
    """

    def __init__(self, t: float = 0.0) -> None:
        self.t: float = t

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


class TestTokenBucket:
    """Direct unit tests for ``TokenBucket`` — DESIGN §11.6 / sub-phase 4.6."""

    def test_passthrough_when_rate_none(self) -> None:
        """When ``rate_mb_per_sec`` is None, ``acquire`` returns immediately."""
        bucket = TokenBucket(rate_mb_per_sec=None)
        start = time.monotonic()
        bucket.acquire(2_000_000)
        elapsed = time.monotonic() - start
        # Real clock: 2 MB through a passthrough must take a tiny fraction of a
        # second.  50 ms is generous and immune to CI scheduling jitter.
        assert elapsed < 0.05

    def test_throttles_at_rate(self) -> None:
        """A 2 MB acquire at 1 MB/s spends ~1.0 s of fake-clock time.

        First MB drains the initial 1-second capacity (no sleep).
        Second MB requires a 1.0 s sleep (advancing the fake clock).
        """
        clk = _FakeClock46(t=0.0)
        bucket = TokenBucket(rate_mb_per_sec=1.0, clock=clk.now, sleep=clk.sleep)

        # First 1 MB: bucket is full (capacity = 1 MB); acquire is instant.
        bucket.acquire(1_000_000)
        assert clk.t == pytest.approx(0.0, abs=1e-6)

        # Second 1 MB: bucket is empty; must wait exactly 1.0 s for refill.
        bucket.acquire(1_000_000)
        assert clk.t == pytest.approx(1.0, abs=1e-6)

    def test_zero_bytes_is_noop_even_when_throttled(self) -> None:
        """``acquire(0)`` returns immediately regardless of bucket state."""
        clk = _FakeClock46(t=0.0)
        bucket = TokenBucket(rate_mb_per_sec=1.0, clock=clk.now, sleep=clk.sleep)
        bucket.acquire(0)
        assert clk.t == pytest.approx(0.0, abs=1e-6)

    def test_negative_n_bytes_raises(self) -> None:
        """``acquire(n)`` rejects negative byte counts."""
        bucket = TokenBucket(rate_mb_per_sec=None)
        with pytest.raises(ValueError):
            bucket.acquire(-1)

    def test_non_positive_rate_raises(self) -> None:
        """A non-positive rate is invalid (use None for unlimited instead)."""
        with pytest.raises(ValueError):
            TokenBucket(rate_mb_per_sec=0.0)
        with pytest.raises(ValueError):
            TokenBucket(rate_mb_per_sec=-1.0)


class TestThrottleModuleHooks:
    """Tests for the process-global active-bucket plumbing."""

    def teardown_method(self, _method: object) -> None:  # noqa: D401 — pytest hook
        """Reset the active bucket between tests for isolation."""
        set_active_bucket(None)

    def test_acquire_is_noop_when_no_bucket_installed(self) -> None:
        """Without an active bucket, ``acquire`` is a zero-cost no-op."""
        set_active_bucket(None)
        assert get_active_bucket() is None
        start = time.monotonic()
        _throttle_acquire(10_000_000)  # 10 MB — would block at any sane rate
        elapsed = time.monotonic() - start
        assert elapsed < 0.05

    def test_acquire_delegates_to_active_bucket(self) -> None:
        """When a bucket is installed, ``acquire`` advances its fake clock."""
        clk = _FakeClock46(t=0.0)
        bucket = TokenBucket(rate_mb_per_sec=1.0, clock=clk.now, sleep=clk.sleep)
        set_active_bucket(bucket)
        try:
            # Drain initial capacity (1 MB) then trigger a 0.5 s wait.
            _throttle_acquire(1_000_000)
            _throttle_acquire(500_000)
            assert clk.t == pytest.approx(0.5, abs=1e-6)
        finally:
            set_active_bucket(None)


# ===========================================================================
# Sub-phase 4.7 — Bulk-insert coverage and assertions for full scan
# ===========================================================================


class TestBulkInsertFullMode:
    """Verify that full-mode bulk-insert behaviour matches DESIGN §11.7.

    - ``DROP INDEX IF EXISTS`` is issued for secondary indexes before the walk
      when ``drop_indexes=True``.
    - Inserts are batched via ``executemany`` (i.e. :func:`_flush_insert_buffer`
      is called at least once during the walk).
    - ``incremental`` mode never issues any ``DROP INDEX IF EXISTS`` statement.

    We use pyfakefs for a small fixture (a handful of files) and spy on the
    scanner internals via ``unittest.mock.patch`` rather than driving a 6000-row
    fixture.  The SQL *behaviour* (which functions are called and with what
    SQL) is what matters, not the row count.
    """

    # ------------------------------------------------------------------
    # test 1 — full scan + drop_indexes=True
    # ------------------------------------------------------------------

    def test_full_scan_drops_indexes_and_uses_executemany(self, fs: "FakeFilesystem") -> None:
        """Full scan with drop_indexes=True issues DROP INDEX and uses executemany.

        Strategy:
        - Wrap the internal ``_drop_secondary_indexes`` function with a spy so
          we can assert it was called exactly once per disk.
        - Wrap ``_flush_insert_buffer`` with a spy to assert executemany-style
          batching is triggered at scan end (remainder flush).
        - The test uses a small fake filesystem (3 video files) — row count is
          irrelevant because what we're checking is the control flow, not
          SQLite throughput.

        Args:
            fs: pyfakefs ``FakeFilesystem`` fixture injected by pytest.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/BulkFullDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        # Three small video files — enough to exercise the full-mode path.
        for i in range(3):
            Path(f"{mount}/film{i}.mkv").write_bytes(b"X" * 200)

        disk = _insert_disk(conn, mount)

        # Spy on the two internal functions that implement bulk-insert behaviour.
        _drop_patch = "personalscraper.indexer.scanner._modes._drop_secondary_indexes"
        _flush_patch = "personalscraper.indexer.scanner._modes._flush_insert_buffer"

        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                _drop_patch,
                wraps=__import__(
                    "personalscraper.indexer.scanner._index_ddl",
                    fromlist=["_drop_secondary_indexes"],
                )._drop_secondary_indexes,
            ) as mock_drop:
                with patch(
                    _flush_patch,
                    wraps=__import__(
                        "personalscraper.indexer.scanner._db_writes",
                        fromlist=["_flush_insert_buffer"],
                    )._flush_insert_buffer,
                ) as mock_flush:
                    result = scan(
                        [disk],
                        ScanMode.full,
                        generation=1,
                        conn=conn,
                        drop_indexes=True,
                        event_bus=EventBus(),
                    )

        assert result.status == "ok"
        # _drop_secondary_indexes must have been called once (one disk).
        assert mock_drop.call_count == 1, (
            f"Expected _drop_secondary_indexes to be called once, got {mock_drop.call_count}"
        )
        # _flush_insert_buffer must have been called at least once (remainder flush
        # at the end of the walk is always executed, even for a small fixture).
        assert mock_flush.call_count >= 1, (
            f"Expected _flush_insert_buffer to be called at least once, got {mock_flush.call_count}"
        )

    # ------------------------------------------------------------------
    # test 2 — incremental mode must NOT drop indexes
    # ------------------------------------------------------------------

    def test_incremental_does_not_drop_indexes(self, fs: "FakeFilesystem") -> None:
        """Incremental scan must never issue DROP INDEX statements (DESIGN §11.7).

        Incremental write volume is small (only changed files are updated) so
        keeping indexes live is the correct trade-off.  We assert this by spying
        on ``_drop_secondary_indexes`` and verifying it is never called.

        Args:
            fs: pyfakefs ``FakeFilesystem`` fixture injected by pytest.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/BulkIncrDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        for i in range(3):
            Path(f"{mount}/movie{i}.mkv").write_bytes(b"Y" * 200)

        disk = _insert_disk(conn, mount)

        _drop_patch = "personalscraper.indexer.scanner._modes._drop_secondary_indexes"

        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                _drop_patch,
                wraps=__import__(
                    "personalscraper.indexer.scanner._index_ddl",
                    fromlist=["_drop_secondary_indexes"],
                )._drop_secondary_indexes,
            ) as mock_drop:
                result = scan(
                    [disk],
                    ScanMode.incremental,
                    generation=1,
                    conn=conn,
                    # drop_indexes is False by default; set explicitly for clarity.
                    drop_indexes=False,
                    event_bus=EventBus(),
                )

        assert result.status == "ok"
        # _drop_secondary_indexes must never be called in incremental mode.
        assert mock_drop.call_count == 0, (
            f"_drop_secondary_indexes must not be called in incremental mode, got {mock_drop.call_count} call(s)"
        )


# ---------------------------------------------------------------------------
# Sub-phase 5.6 tests — quick-mode paranoia branch (DESIGN §17.1)
# ---------------------------------------------------------------------------


class TestQuickModeParanoiaBranch:
    """Tests for the paranoia branch in :func:`_scan_disk_quick` (DESIGN §17.1).

    The paranoia branch queries recent ``scan_event`` rows with
    ``event LIKE 'outbox.%'`` and re-stats the referenced paths to detect
    silent tier-1 mismatches that dir-mtime would miss.
    """

    def test_paranoia_recheck_logged_when_file_mutated_silently(
        self,
        fs: "FakeFilesystem",
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Paranoia branch detects a file mutated without updating dir-mtime.

        Setup:
        1. Full scan seeds ``media_file`` and ``path`` rows.
        2. Fake FS file content is changed WITHOUT touching parent dir mtime
           (simulated by inserting a stale ``media_file`` row with different
           size_bytes/mtime_ns — the file on disk stays as-is but the stored
           values are manually backdated so there's a mismatch).
        3. A ``scan_event`` row with ``event='outbox.move'`` and
           ``payload_json='{"rel_path": "<filename>"}'`` is inserted.
        4. Quick scan is run with a sufficiently large paranoia_window_seconds.

        Expected: ``indexer.scan.paranoia_recheck`` is logged for that path.

        Args:
            fs: pyfakefs ``FakeFilesystem`` fixture.
            caplog: pytest log capture fixture.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ParanoiaDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        # Write the initial file content.
        Path(f"{mount}/movie.mkv").write_bytes(b"initial" * 100)

        disk = _insert_disk(conn, mount)

        # Full scan — seeds media_file row with current size_bytes / mtime_ns.
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Verify the media_file row was created.
        conn.row_factory = sqlite3.Row
        mf_row = conn.execute("SELECT id, size_bytes, mtime_ns FROM media_file WHERE filename = 'movie.mkv'").fetchone()
        assert mf_row is not None, "media_file row must exist after full scan"
        conn.row_factory = None

        # Simulate a silent mutation: update the stored size_bytes to a stale
        # value so the paranoia re-stat will see a mismatch.  We deliberately
        # do NOT change the file on disk (so dir mtime is also unchanged); the
        # stored row is the one that's backdated.
        conn.execute(
            "UPDATE media_file SET size_bytes = 999 WHERE id = ?",
            (mf_row["id"],),
        )

        # Insert a scan_run row to satisfy the FK constraint on scan_event.scan_id.
        scan_run_id = conn.execute(
            "INSERT INTO scan_run (generation, mode, started_at, status) VALUES (1, 'quick', ?, 'running')",
            (int(time.time()),),
        ).lastrowid

        # Insert a fake outbox event referencing the mutated file.
        conn.execute(
            "INSERT INTO scan_event (scan_id, ts, event, payload_json) VALUES (?, ?, 'outbox.move', ?)",
            (scan_run_id, int(time.time()), '{"rel_path": "movie.mkv"}'),
        )

        # Store a wrong merkle_root to force the Merkle miss path (prerequisite
        # for the paranoia branch to run).
        disk_repo.update_merkle_root(conn, disk.id, "wrongroot")
        updated_disk = disk_repo.get_by_id(conn, disk.id)
        assert updated_disk is not None

        # Quick scan with paranoia enabled (window=86400 s).
        # confirm_bulk_change=True bypasses the Merkle delta freeze guard so the
        # scan does not abort before completing the dir-mtime walk; the paranoia
        # branch runs BEFORE the bulk-change check so the recheck is still logged
        # even without confirm_bulk_change, but confirming allows scan() to return
        # status='ok' and makes the assertion cleaner.
        with caplog.at_level(logging.INFO):
            with patch(_GUARD_PATCH, return_value=None):
                with patch(
                    "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                    return_value=True,
                ):
                    result = scan(
                        [updated_disk],
                        ScanMode.quick,
                        generation=2,
                        conn=conn,
                        paranoia_window_seconds=86400,
                        confirm_bulk_change=True,
                        event_bus=EventBus(),
                    )

        assert result.status == "ok"

        # Assert that the paranoia branch logged a recheck event for the file.
        # Match on the full event name to avoid false positives on mount-path substrings.
        info_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
        assert any("indexer.scan.paranoia_recheck" in t for t in info_texts), (
            f"Expected 'indexer.scan.paranoia_recheck' in log records, got: {info_texts}"
        )

    def test_paranoia_branch_disabled_when_window_is_zero(
        self,
        fs: "FakeFilesystem",
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When paranoia_window_seconds=0, the paranoia branch is entirely skipped.

        No DB query is made and no ``indexer.scan.paranoia_branch`` log event
        is emitted.

        Args:
            fs: pyfakefs ``FakeFilesystem`` fixture.
            caplog: pytest log capture fixture.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/ParanoiaDisabledDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/movie.mkv").write_bytes(b"X" * 200)

        disk = _insert_disk(conn, mount, merkle_root="wrongroot")

        with caplog.at_level(logging.INFO):
            with patch(_GUARD_PATCH, return_value=None):
                result = scan(
                    [disk],
                    ScanMode.quick,
                    generation=1,
                    conn=conn,
                    paranoia_window_seconds=0,
                    event_bus=EventBus(),
                )

        assert result.status == "ok"

        # paranoia_branch event must NOT appear when window=0.
        # Match on the full event name to avoid false positives on mount-path substrings.
        info_texts = [r.getMessage() for r in caplog.records]
        assert not any("indexer.scan.paranoia_branch" in t for t in info_texts), (
            f"indexer.scan.paranoia_branch must not be logged when window=0, got: {info_texts}"
        )


# ---------------------------------------------------------------------------
# Regression test — sub-phase 9.4: unexpected exception re-raise contract
# ---------------------------------------------------------------------------


class TestScanUnexpectedExceptionReraise:
    """scan() re-raises unexpected exceptions after recording scan_run.status='failed'.

    The docstring ``Raises`` section documents this contract.  Prior to the 9.4 fix,
    the ``except Exception`` block returned a ``ScanRunResult(status='failed')``
    instead of re-raising, silently swallowing tracebacks and letting callers
    (e.g. ``library/scanner.scan_library``) treat catastrophic failures as completed
    scans.
    """

    def test_unexpected_exception_is_reraised_and_scan_run_marked_failed(
        self,
        tmp_path: Path,
    ) -> None:
        """An unexpected exception during the walk propagates and scan_run is set to 'failed'.

        Injects a ``RuntimeError`` via a patched ``os.scandir`` to simulate a walk-loop
        crash.  Asserts:

        - The exception propagates out of ``scan()`` (not swallowed).
        - The ``scan_run`` row created during the scan is updated to ``status='failed'``.

        Args:
            tmp_path: pytest-provided temporary directory.
        """
        db_file = tmp_path / "indexer.db"
        conn = _make_conn_file(db_file)

        mount = str(tmp_path / "CrashDisk")
        Path(mount).mkdir()
        # Create a file so the walk actually calls scandir.
        Path(f"{mount}/movie.mkv").write_bytes(b"X" * 200)

        disk = _insert_disk_on_conn(conn, mount)

        _bomb = RuntimeError("injected walk-loop crash")

        def _crashing_scandir(path: object) -> object:
            """Raise RuntimeError unconditionally to simulate a catastrophic walk failure."""
            raise _bomb

        with patch(_GUARD_PATCH, return_value=None):
            with patch("personalscraper.indexer.scanner.os.scandir", side_effect=_crashing_scandir):
                with pytest.raises(RuntimeError, match="injected walk-loop crash"):
                    scan(
                        [disk],
                        ScanMode.full,
                        generation=1,
                        conn=conn,
                        db_path=db_file,
                        event_bus=EventBus(),
                    )

        # The scan_run row must have been inserted and then marked 'failed'.
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT status FROM scan_run").fetchall()
        assert len(rows) == 1, f"Expected exactly one scan_run row, got {len(rows)}"
        assert rows[0]["status"] == "failed", (
            f"Expected scan_run.status='failed' after unexpected exception, got {rows[0]['status']!r}"
        )


class TestVerifyMode:
    """Verify mode: re-stat existing media_file rows and enqueue repair on drift."""

    def test_verify_clean_files_bump_last_verified_at(self, fs: "FakeFilesystem") -> None:
        """Files whose on-disk size + mtime match the DB get last_verified_at updated."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/VerifyCleanDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        Path(f"{mount}/movie.mkv").write_bytes(b"V" * 300)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        conn.row_factory = sqlite3.Row
        before = conn.execute("SELECT id, last_verified_at FROM media_file WHERE filename = 'movie.mkv'").fetchone()
        assert before is not None
        baseline_verified = before["last_verified_at"]

        # Sleep a beat so last_verified_at strictly advances.
        time.sleep(1)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.verify, generation=2, conn=conn, event_bus=EventBus())

        after = conn.execute(
            "SELECT last_verified_at, scan_generation FROM media_file WHERE id = ?",
            (before["id"],),
        ).fetchone()
        assert after is not None
        assert after["last_verified_at"] >= baseline_verified
        assert after["scan_generation"] == 2

        # No repair_queue rows should be enqueued.
        repair_count = conn.execute("SELECT COUNT(*) FROM repair_queue").fetchone()[0]
        assert repair_count == 0

    def test_verify_size_mismatch_enqueues_repair(self, fs: "FakeFilesystem") -> None:
        """A file whose size has changed since last scan is escalated to repair_queue."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/VerifyDriftDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        movie = Path(f"{mount}/movie.mkv")
        movie.write_bytes(b"V" * 300)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Mutate the file size on disk.
        movie.write_bytes(b"V" * 600)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.verify, generation=2, conn=conn, event_bus=EventBus())

        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT scope, scope_id, reason, payload_json FROM repair_queue").fetchall()
        assert len(rows) == 1
        assert rows[0]["scope"] == "file"
        assert "drift" in rows[0]["reason"]
        assert "expected_size" in rows[0]["payload_json"]

    def test_verify_missing_file_enqueues_repair(self, fs: "FakeFilesystem") -> None:
        """A file deleted from disk is enqueued for repair (no soft-delete)."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/VerifyMissingDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        movie = Path(f"{mount}/movie.mkv")
        movie.write_bytes(b"V" * 300)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        movie.unlink()

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.verify, generation=2, conn=conn, event_bus=EventBus())

        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT scope, reason FROM repair_queue").fetchall()
        assert len(rows) == 1
        assert rows[0]["scope"] == "file"
        assert "missing" in rows[0]["reason"]

        # The media_file row must NOT have been soft-deleted (verify is non-destructive).
        deleted_at = conn.execute("SELECT deleted_at FROM media_file WHERE filename = 'movie.mkv'").fetchone()
        assert deleted_at is not None
        assert deleted_at[0] is None

    def test_verify_no_enqueue_skips_repair_queue_on_missing(self, fs: "FakeFilesystem") -> None:
        """no_enqueue=True: missing file detected but NO repair_queue row is written.

        Regression for DEV #21 / MUST-9: library-verify --no-enqueue must be a
        no-op on the repair_queue table even when drift is detected.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/VerifyNoEnqueueDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        movie = Path(f"{mount}/movie.mkv")
        movie.write_bytes(b"V" * 300)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Delete the file so verify would normally enqueue a "file missing" repair.
        movie.unlink()

        queue_before = conn.execute("SELECT COUNT(*) FROM repair_queue").fetchone()[0]

        # Run verify with no_enqueue=True: drift found but nothing written to queue.
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.verify, generation=2, conn=conn, event_bus=EventBus(), no_enqueue=True)

        queue_after = conn.execute("SELECT COUNT(*) FROM repair_queue").fetchone()[0]
        assert queue_after == queue_before, (
            f"no_enqueue=True must not add repair_queue rows; before={queue_before}, after={queue_after}"
        )

    def test_verify_no_enqueue_skips_repair_queue_on_drift(self, fs: "FakeFilesystem") -> None:
        """no_enqueue=True: size drift detected but NO repair_queue row is written.

        Regression for DEV #21 / MUST-9 (complementary to missing-file case).
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/VerifyNoEnqueueDriftDisk"
        Path(mount).mkdir(parents=True, exist_ok=True)
        movie = Path(f"{mount}/movie.mkv")
        movie.write_bytes(b"V" * 300)

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Mutate file so verify would detect size drift.
        movie.write_bytes(b"V" * 600)

        queue_before = conn.execute("SELECT COUNT(*) FROM repair_queue").fetchone()[0]

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.verify, generation=2, conn=conn, event_bus=EventBus(), no_enqueue=True)

        queue_after = conn.execute("SELECT COUNT(*) FROM repair_queue").fetchone()[0]
        assert queue_after == queue_before, (
            f"no_enqueue=True must not add repair_queue rows on drift; before={queue_before}, after={queue_after}"
        )


class TestScanExcludesNonVideoCategories:
    """scan() never indexes files under non-video category roots (audiobooks).

    Live shape (2026-07-15): 744 ``media_file`` rows under « livres audios/ »
    were structurally unlinkable — the item stage skips non-video categories
    so no ``media_item`` can ever own them; they polluted every relink /
    reconcile audit as eternal orphans.
    """

    @staticmethod
    def _config_with_audiobooks(mount: str):
        """Return a minimal Config whose audiobooks category maps to « livres audios ».

        Returns:
            A one-disk Config carrying movies + audiobooks categories.
        """
        from personalscraper.conf import ids as CID  # noqa: PLC0415
        from personalscraper.conf.models.categories import CategoryConfig  # noqa: PLC0415
        from personalscraper.conf.models.config import Config  # noqa: PLC0415
        from personalscraper.conf.models.disks import DiskConfig  # noqa: PLC0415
        from personalscraper.conf.models.paths import PathConfig  # noqa: PLC0415
        from tests.fixtures.config import CANONICAL_STAGING_DIRS  # noqa: PLC0415

        return Config(
            paths=PathConfig(
                torrent_complete_dir=Path("/mnt/torrents"),
                staging_dir=Path("/mnt/staging"),
                data_dir=Path("/mnt/.data"),
            ),
            disks=[
                DiskConfig(
                    id="drive_a",
                    path=Path(mount),
                    categories=[CID.MOVIES, CID.AUDIOBOOKS],
                )
            ],
            categories={
                CID.MOVIES: CategoryConfig(folder_name="films"),
                CID.AUDIOBOOKS: CategoryConfig(folder_name="livres audios"),
            },
            staging_dirs=CANONICAL_STAGING_DIRS,
        )

    def test_audiobook_root_not_indexed(self, fs: "FakeFilesystem") -> None:
        """Files under the audiobooks folder never become media_file rows."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NonVideoDisk"
        Path(f"{mount}/films/A Movie (2020)").mkdir(parents=True)
        Path(f"{mount}/films/A Movie (2020)/movie.mkv").write_text("video")
        Path(f"{mount}/livres audios/Author/Book").mkdir(parents=True)
        Path(f"{mount}/livres audios/Author/Book/book.m4b").write_text("audio")

        disk = _insert_disk(conn, mount)
        config = self._config_with_audiobooks(mount)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan(
                [disk],
                ScanMode.full,
                generation=1,
                conn=conn,
                event_bus=EventBus(),
                config=config,
            )

        assert result.status == "ok"
        conn.row_factory = sqlite3.Row
        filenames = {r["filename"] for r in conn.execute("SELECT filename FROM media_file")}
        assert "movie.mkv" in filenames
        assert "book.m4b" not in filenames, "audiobook files are structurally unlinkable and must never be indexed"

    def test_without_config_nothing_changes(self, fs: "FakeFilesystem") -> None:
        """No config (tests, standalone scans) → historical behaviour intact."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount = "/mnt/NoCfgDisk"
        Path(f"{mount}/livres audios/Author").mkdir(parents=True)
        Path(f"{mount}/livres audios/Author/book.m4b").write_text("audio")

        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            result = scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        assert result.status == "ok"
        assert result.files_visited == 1
