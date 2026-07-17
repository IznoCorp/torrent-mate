"""End-to-end test: cold full-mode scan and enrich mode (Phase 2.5 / 4.2).

Covers the "cold scan" half of the cold-to-warm indexer lifecycle:
- Build a pyfakefs fixture with ~10 items across 2 mock disks.
- Run ``scan()`` in ``ScanMode.full`` directly (CLI wired in sub-phase 2.7).
- Assert that ``media_file`` row count matches the fixture.
- Assert ``enriched_at IS NULL`` for all rows (mediainfo is a later sub-phase).
- Assert ``scan_run.status == 'ok'``.
- Assert ``oshash`` is non-empty hex for video files; ``""`` for non-video.

The "enrich" half (sub-phase 4.2):
- After the cold full scan (all ``enriched_at IS NULL``), run ``ScanMode.enrich``.
- Mock pymediainfo to return 1 video + 1 audio stream for video files.
- Assert ``media_stream`` rows are created for video files.
- Assert ``enriched_at`` is set (non-NULL) for all files.

Note on pyfakefs + sqlite3:
    pyfakefs intercepts all filesystem I/O.  To work around this, each test
    calls ``fs.pause()`` before building the in-memory DB (which reads SQL
    migration files from disk via ``apply_migrations``), then ``fs.resume()``
    before constructing the fake directory tree.

Note on FK constraints:
    ``media_file.release_id`` is nullable since migration 002.  Stage A inserts
    rows with ``release_id=NULL`` and ``oshash=NULL`` for non-video files.
    FK enforcement remains enabled (no workaround needed).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo, log_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.schema import DiskRow

if TYPE_CHECKING:
    from pyfakefs.fake_filesystem import FakeFilesystem

MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conn_real() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema.

    Must be called while the real filesystem is active (i.e. after ``fs.pause()``
    and before ``fs.resume()``).  ``apply_migrations`` reads SQL files from disk.

    FK enforcement is enabled (the default per ``db.open_db``).  Stage A inserts
    ``release_id=NULL`` and ``oshash=NULL`` for non-video files, which is valid
    since migration 002 made both columns nullable.

    Returns:
        Open :class:`sqlite3.Connection` with migrations applied and FK ON.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection, label: str, mount_path: str) -> DiskRow:
    """Insert a minimal disk row and return the populated :class:`DiskRow` with its PK.

    Args:
        conn: Open SQLite connection.
        label: Human-readable disk label.
        mount_path: Absolute path of the fake mount point.

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


# ---------------------------------------------------------------------------
# Cold scan fixture definition
#
# 10 files across 2 mock disks:
#   Disk A (/mnt/DiskA): 6 files
#     movies/Inception (2010)/Inception.mkv        — video
#     movies/Inception (2010)/Inception.nfo        — non-video
#     movies/The Matrix (1999)/The.Matrix.1999.mkv — video
#     tvshows/Breaking Bad (2008)/S01E01.mkv        — video
#     tvshows/Breaking Bad (2008)/S01E02.mkv        — video
#     tvshows/Breaking Bad (2008)/show.nfo          — non-video
#   Disk B (/mnt/DiskB): 4 files
#     movies/Parasite (2019)/Parasite.mkv           — video
#     movies/Parasite (2019)/Parasite.nfo           — non-video
#     movies/Joker (2019)/Joker.mkv                 — video
#     movies/Joker (2019)/Joker.jpg                 — non-video
# ---------------------------------------------------------------------------

_DISK_A_FILES: list[tuple[str, bytes, bool]] = [
    ("movies/Inception (2010)/Inception.mkv", b"V" * 300, True),
    ("movies/Inception (2010)/Inception.nfo", b"<nfo/>", False),
    ("movies/The Matrix (1999)/The.Matrix.1999.mkv", b"W" * 300, True),
    ("tvshows/Breaking Bad (2008)/S01E01.mkv", b"X" * 300, True),
    ("tvshows/Breaking Bad (2008)/S01E02.mkv", b"Y" * 300, True),
    ("tvshows/Breaking Bad (2008)/show.nfo", b"<nfo/>", False),
]

_DISK_B_FILES: list[tuple[str, bytes, bool]] = [
    ("movies/Parasite (2019)/Parasite.mkv", b"Z" * 300, True),
    ("movies/Parasite (2019)/Parasite.nfo", b"<nfo/>", False),
    ("movies/Joker (2019)/Joker.mkv", b"A" * 300, True),
    ("movies/Joker (2019)/Joker.jpg", b"\xff\xd8\xff\xe0", False),
]

_TOTAL_FILES = len(_DISK_A_FILES) + len(_DISK_B_FILES)  # 10
_VIDEO_FILENAMES = {
    "Inception.mkv",
    "The.Matrix.1999.mkv",
    "S01E01.mkv",
    "S01E02.mkv",
    "Parasite.mkv",
    "Joker.mkv",
}
_NON_VIDEO_FILENAMES = {
    "Inception.nfo",
    "show.nfo",
    "Parasite.nfo",
    "Joker.jpg",
}


def _build_fixture(fs: "FakeFilesystem", mount_a: str, mount_b: str) -> None:
    """Create the fake directory tree for the cold-scan fixture.

    Args:
        fs: pyfakefs filesystem object (``fs.resume()`` must have been called).
        mount_a: Absolute path of the first fake disk mount point.
        mount_b: Absolute path of the second fake disk mount point.
    """
    for rel, content, _ in _DISK_A_FILES:
        abs_path = Path(mount_a) / rel
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(content)

    for rel, content, _ in _DISK_B_FILES:
        abs_path = Path(mount_b) / rel
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(content)


# ---------------------------------------------------------------------------
# Cold scan test
# ---------------------------------------------------------------------------


class TestColdScan:
    """Full-mode cold scan records all fixture files with correct fingerprints."""

    def test_cold_scan_full_mode(self, fs: "FakeFilesystem") -> None:
        """Full scan across 2 disks: 10 files indexed, oshash populated, enriched_at NULL."""
        # Build DB while real FS is accessible.
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount_a = "/mnt/DiskA"
        mount_b = "/mnt/DiskB"

        # Build the fake directory tree.
        _build_fixture(fs, mount_a, mount_b)

        # Insert disk rows.
        disk_a = _insert_disk(conn, "DiskA", mount_a)
        disk_b = _insert_disk(conn, "DiskB", mount_b)

        # Run full-mode scan (no index drop in unit tests — keep it fast).
        with patch(_GUARD_PATCH, return_value=None):
            result = scan(
                [disk_a, disk_b],
                mode=ScanMode.full,
                generation=1,
                conn=conn,
                drop_indexes=False,
                event_bus=EventBus(),
            )

        # ---- Basic counters ----
        assert result.status == "ok", f"Expected 'ok', got {result.status!r}"
        assert result.files_visited == _TOTAL_FILES, f"Expected {_TOTAL_FILES} files, got {result.files_visited}"

        # ---- scan_run row ----
        run_row = log_repo.get_scan_run_by_id(conn, result.scan_run_id)
        assert run_row is not None
        assert run_row.status == "ok"

        # ---- media_file count ----
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, oshash, enriched_at FROM media_file").fetchall()
        assert len(rows) == _TOTAL_FILES, f"Expected {_TOTAL_FILES} media_file rows, got {len(rows)}"

        # ---- enriched_at must be NULL for all rows (mediainfo not yet wired) ----
        for row in rows:
            assert row["enriched_at"] is None, (
                f"enriched_at must be NULL for {row['filename']!r}, got {row['enriched_at']}"
            )

        # ---- oshash assertions ----
        by_name = {r["filename"]: r["oshash"] for r in rows}

        for vname in _VIDEO_FILENAMES:
            assert vname in by_name, f"Video file {vname!r} missing from media_file"
            assert by_name[vname] is not None, f"Video file {vname!r} oshash must not be None"
            assert by_name[vname] != "", f"Video file {vname!r} must have non-empty oshash"
            assert len(by_name[vname]) == 16, f"oshash for {vname!r} must be 16 hex chars, got {by_name[vname]!r}"

        for nname in _NON_VIDEO_FILENAMES:
            assert nname in by_name, f"Non-video file {nname!r} missing from media_file"
            assert by_name[nname] is None, (
                f"Non-video file {nname!r} must have oshash=None (NULL), got {by_name[nname]!r}"
            )


# ---------------------------------------------------------------------------
# Enrich scan test (sub-phase 4.2)
# ---------------------------------------------------------------------------


def _make_fake_mi_result(n_video: int = 1, n_audio: int = 1) -> MagicMock:
    """Build a fake MediaInfo parse result with *n_video* + *n_audio* tracks.

    Args:
        n_video: Number of video tracks to include.
        n_audio: Number of audio tracks to include.

    Returns:
        A :class:`~unittest.mock.MagicMock` whose ``.tracks`` attribute contains
        the requested video and audio tracks plus one ``General`` track (which the
        wrapper must filter out).
    """

    def _track(track_type: str, stream_id: int = 0) -> SimpleNamespace:
        return SimpleNamespace(
            track_type=track_type,
            stream_identifier=stream_id,
            codec_id=None,
            format="h264" if track_type == "Video" else "AAC",
            language=None,
            channel_s=2 if track_type == "Audio" else None,
            width=1920 if track_type == "Video" else None,
            height=1080 if track_type == "Video" else None,
            duration=90000,
            bit_rate=4000000,
        )

    tracks = [SimpleNamespace(track_type="General")]  # always filtered by wrapper
    tracks += [_track("Video", i) for i in range(n_video)]
    tracks += [_track("Audio", i) for i in range(n_audio)]

    mi = MagicMock()
    mi.tracks = tracks
    return mi


class TestEnrichScan:
    """Enrich mode (ScanMode.enrich) on the cold fixture — sub-phase 4.2 E2E."""

    def test_enrich_after_cold_scan(self, fs: "FakeFilesystem") -> None:
        """After a cold full scan, enrich mode populates media_stream and enriched_at.

        Steps:
        1. Run a cold ``ScanMode.full`` scan → assert ``enriched_at IS NULL`` for all rows.
        2. Run ``ScanMode.enrich`` with mocked pymediainfo (1 video + 1 audio per file).
        3. Assert ``media_stream`` rows exist for video files (size gate passes because
           ``min_size_mb=0`` inside _scan_disk_enrich).
        4. Assert ``enriched_at`` is non-NULL for all files after enrichment.
        """
        # Build DB while real FS is accessible.
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        mount_a = "/mnt/DiskA"
        mount_b = "/mnt/DiskB"

        _build_fixture(fs, mount_a, mount_b)

        disk_a = _insert_disk(conn, "DiskA", mount_a)
        disk_b = _insert_disk(conn, "DiskB", mount_b)

        # --- Step 1: cold full scan ---
        with patch(_GUARD_PATCH, return_value=None):
            full_result = scan(
                [disk_a, disk_b],
                mode=ScanMode.full,
                generation=1,
                conn=conn,
                drop_indexes=False,
                event_bus=EventBus(),
            )

        assert full_result.status == "ok"
        assert full_result.files_visited == _TOTAL_FILES

        # All files must have enriched_at=NULL after the full scan.
        conn.row_factory = sqlite3.Row
        all_rows = conn.execute("SELECT filename, enriched_at FROM media_file").fetchall()
        for row in all_rows:
            assert row["enriched_at"] is None, f"enriched_at must be NULL after full scan for {row['filename']!r}"

        # --- Step 2: enrich scan with mocked pymediainfo ---
        fake_mi = _make_fake_mi_result(n_video=1, n_audio=1)

        with patch(_GUARD_PATCH, return_value=None):
            with patch("personalscraper.indexer.mediainfo.MediaInfo.parse", return_value=fake_mi):
                enrich_result = scan(
                    [disk_a, disk_b],
                    mode=ScanMode.enrich,
                    generation=2,
                    conn=conn,
                    event_bus=EventBus(),
                )

        assert enrich_result.status == "ok"

        # --- Step 3: assert media_stream rows created for video files ---
        conn.row_factory = sqlite3.Row
        # Fetch all media_stream rows joined to filename for legibility.
        stream_rows = conn.execute(
            """
            SELECT mf.filename, ms.kind
              FROM media_stream ms
              JOIN media_file mf ON mf.id = ms.file_id
            """
        ).fetchall()
        stream_by_name: dict[str, list[str]] = {}
        for sr in stream_rows:
            stream_by_name.setdefault(sr["filename"], []).append(sr["kind"])

        for vname in _VIDEO_FILENAMES:
            assert vname in stream_by_name, (
                f"No media_stream rows found for video file {vname!r}; files with streams: {list(stream_by_name)}"
            )
            kinds = stream_by_name[vname]
            assert "video" in kinds, f"Expected video stream for {vname!r}, got {kinds}"
            assert "audio" in kinds, f"Expected audio stream for {vname!r}, got {kinds}"

        # Non-video files may also have streams if pymediainfo returns any;
        # the key requirement is that video files always have streams.

        # --- Step 4: assert enriched_at populated for all files ---
        conn.row_factory = sqlite3.Row
        final_rows = conn.execute("SELECT filename, enriched_at FROM media_file").fetchall()
        assert len(final_rows) == _TOTAL_FILES

        for row in final_rows:
            assert row["enriched_at"] is not None, f"enriched_at must be set after enrich pass for {row['filename']!r}"
            assert row["enriched_at"] > 0, f"enriched_at must be a positive epoch seconds value for {row['filename']!r}"
