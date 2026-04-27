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
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.merkle import DiskUnmountedError, compute_merkle_root
from personalscraper.indexer.repos import disk_repo, log_repo
from personalscraper.indexer.scanner import (
    EXCLUDED_NAMES,
    IndexerConfigError,
    ScanMode,
    ScanRunResult,
    _build_disk_fingerprints,
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
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

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
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

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
            result = scan([disk], ScanMode.full, generation=1, conn=conn)

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
            scan([disk], ScanMode.full, generation=1, conn=conn)

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
                result = scan([updated_disk], ScanMode.quick, generation=2, conn=conn)

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
                result = scan([disk], ScanMode.quick, generation=1, conn=conn)

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
            scan([disk], ScanMode.full, generation=1, conn=conn)

        # Store a wrong merkle_root to force Merkle miss in quick scan.
        disk_repo.update_merkle_root(conn, disk.id, "wrongroot")

        # Quick scan with dir-mtime reliable — the subdir mtime has not changed.
        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                return_value=True,
            ):
                result = scan([disk], ScanMode.quick, generation=2, conn=conn)

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
            scan([disk], ScanMode.full, generation=1, conn=conn)

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
                result = scan([disk], ScanMode.quick, generation=2, conn=conn)

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
            result = scan([disk], ScanMode.quick, generation=1, conn=conn)

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
            scan([disk], ScanMode.full, generation=1, conn=conn)

        # Seed a wrong merkle_root so the Merkle miss path is taken.
        disk_repo.update_merkle_root(conn, disk.id, "wrongroot")

        # Quick scan with dir-mtime UNRELIABLE → skip optimisation disabled.
        with patch(_GUARD_PATCH, return_value=None):
            with patch(
                "personalscraper.indexer.scanner._verify_dir_mtime_reliable",
                return_value=False,
            ):
                result = scan([disk], ScanMode.quick, generation=2, conn=conn)

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
            scan([disk], ScanMode.full, generation=1, conn=conn)

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
            scan([disk], ScanMode.full, generation=1, conn=conn)

        # Mark dead.mkv as deleted.
        now_s = int(time.time())
        conn.execute(
            "UPDATE media_file SET deleted_at = ? WHERE filename = 'dead.mkv'",
            (now_s,),
        )

        fps = _build_disk_fingerprints(conn, disk.id)
        assert len(fps) == 1, f"Expected 1 fingerprint (alive only), got {len(fps)}"


# Suppress unused-import warning: PathRow is used as a type in helper signatures
# that may be referenced from future tests; keep it imported for forward compatibility.
_PathRow = PathRow
