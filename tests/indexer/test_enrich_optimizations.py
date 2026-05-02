"""Unit tests for the enrich-mode performance optimisations.

Covers:
- Extension-based skip: ``_scan_disk_enrich`` passes ``wrapper=None`` to
  ``_enrich_one_file`` for non-video files so libmediainfo is not invoked
  on the ~84 % of library files that are sidecars (jpg / nfo / srt / ...).
- Backfill mode: ``_scan_disk_enrich_backfill`` targets only already-
  enriched files whose ``media_stream`` rows are missing
  migration-004 columns; UPDATEs in place; never touches NFO / artwork /
  ``enriched_at`` / linker.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner._modes import (
    _scan_disk_enrich,
    _scan_disk_enrich_backfill,
)
from personalscraper.indexer.schema import DiskRow, MediaStreamRow

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB seeded with the full migration chain."""
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)
    return c


def _seed_disk(c: sqlite3.Connection, mount: str) -> DiskRow:
    cur = c.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, NULL, 1, 0)",
        ("u-1", "TestDisk", mount, int(time.time())),
    )
    disk_id = cur.lastrowid
    return DiskRow(
        id=disk_id,
        uuid="u-1",
        label="TestDisk",
        mount_path=mount,
        last_seen_at=int(time.time()),
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )


def _seed_file(c: sqlite3.Connection, *, disk_id: int, rel_path: str, filename: str, size: int = 100) -> int:
    existing = c.execute("SELECT id FROM path WHERE disk_id = ? AND rel_path = ?", (disk_id, rel_path)).fetchone()
    if existing is not None:
        path_id = existing[0]
    else:
        path_cur = c.execute(
            "INSERT INTO path (disk_id, rel_path, dir_mtime_ns, last_walked_at) VALUES (?, ?, NULL, NULL)",
            (disk_id, rel_path),
        )
        path_id = path_cur.lastrowid
    file_cur = c.execute(
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns, "
        " oshash, xxh3_partial, xxh3_full, scan_generation, last_verified_at, enriched_at, "
        " miss_strikes, deleted_at) "
        "VALUES (NULL, ?, ?, ?, ?, NULL, NULL, NULL, NULL, 1, ?, NULL, 0, NULL)",
        (path_id, filename, size, int(time.time()) * 1_000_000_000, int(time.time())),
    )
    return file_cur.lastrowid


def test_enrich_skips_pymediainfo_for_non_video_extensions(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """``.jpg`` / ``.nfo`` / ``.srt`` files reach _enrich_one_file with wrapper=None.

    The video file alone receives the real wrapper. Saves the per-file
    pymediainfo cost (~500 ms-1 s) on the ~84 % of typical library files
    that are sidecars.
    """
    mount = str(tmp_path / "TestDisk")
    Path(mount).mkdir()
    for name in ("Inception.mkv", "Inception.nfo", "Inception-poster.jpg", "Inception.srt"):
        Path(mount, name).write_bytes(b"X" * 200)

    disk = _seed_disk(conn, mount)
    file_ids: dict[str, int] = {}
    for name in ("Inception.mkv", "Inception.nfo", "Inception-poster.jpg", "Inception.srt"):
        file_ids[name] = _seed_file(conn, disk_id=disk.id, rel_path=".", filename=name)

    captured_wrappers: dict[str, object] = {}

    def _fake_enrich_one_file(conn_arg, file_id, file_path, item_id, wrapper):  # noqa: ANN001
        # Map back to filename for assertion clarity.
        for name, fid in file_ids.items():
            if fid == file_id:
                captured_wrappers[name] = wrapper
                break
        # Mark the file as enriched so the loop progresses.
        conn_arg.execute("UPDATE media_file SET enriched_at = ? WHERE id = ?", (int(time.time()), file_id))

    sentinel_wrapper = object()
    with (
        patch("personalscraper.indexer.scanner._modes._enrich_one_file", side_effect=_fake_enrich_one_file),
        patch("personalscraper.indexer.scanner._modes.MediaInfoWrapper", return_value=sentinel_wrapper),
    ):
        budget_exhausted = [False]
        _scan_disk_enrich(
            conn,
            disk,
            budget_seconds=None,
            started_at_monotonic=time.monotonic(),
            budget_exhausted=budget_exhausted,
            scan_run_id=0,
        )

    # Video file: real wrapper passed through.
    assert captured_wrappers["Inception.mkv"] is sentinel_wrapper

    # Sidecars: wrapper is replaced by None to short-circuit pymediainfo.
    assert captured_wrappers["Inception.nfo"] is None
    assert captured_wrappers["Inception-poster.jpg"] is None
    assert captured_wrappers["Inception.srt"] is None


# ---------------------------------------------------------------------------
# Backfill mode
# ---------------------------------------------------------------------------


def test_backfill_targets_only_files_with_null_columns(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Files whose stream rows have every migration-004 column populated are skipped.

    The query joins ``media_stream`` with a NULL-on-any-new-column
    predicate; a fully populated row produces no match and the wrapper
    is not called.
    """
    mount = str(tmp_path / "TestDisk")
    Path(mount).mkdir()
    Path(mount, "Already.mkv").write_bytes(b"X" * 200)

    disk = _seed_disk(conn, mount)
    file_id = _seed_file(conn, disk_id=disk.id, rel_path=".", filename="Already.mkv", size=10_000_000)
    # Mark enriched + insert a stream that has every new column populated:
    # hdr_format='HDR10' (not NULL), is_default=1 (not NULL).
    conn.execute("UPDATE media_file SET enriched_at = ? WHERE id = ?", (int(time.time()), file_id))
    conn.execute(
        "INSERT INTO media_stream (file_id, idx, kind, codec, lang, channels, width, height, "
        " duration_ms, bitrate, hdr_format, is_atmos, is_default, forced, format) "
        "VALUES (?, 0, 'video', 'hevc', 'eng', NULL, 1920, 1080, NULL, NULL, 'HDR10', NULL, 1, NULL, NULL)",
        (file_id,),
    )

    extract_calls: list[Path] = []

    class _StubWrapper:
        def extract_streams(self, path: Path) -> list[MediaStreamRow]:
            extract_calls.append(path)
            return []

    with patch("personalscraper.indexer.scanner._modes.MediaInfoWrapper", return_value=_StubWrapper()):
        budget_exhausted = [False]
        _scan_disk_enrich_backfill(
            conn,
            disk,
            budget_seconds=None,
            started_at_monotonic=time.monotonic(),
            budget_exhausted=budget_exhausted,
            scan_run_id=0,
        )

    assert extract_calls == [], "Files with all migration-004 columns set must not be re-extracted"


def test_backfill_updates_in_place_only_missing_columns(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Backfill writes only ``COALESCE``-d new columns, never DELETEs / re-INSERTs."""
    mount = str(tmp_path / "TestDisk")
    Path(mount).mkdir()
    Path(mount, "Movie.mkv").write_bytes(b"X" * 200)

    disk = _seed_disk(conn, mount)
    file_id = _seed_file(conn, disk_id=disk.id, rel_path=".", filename="Movie.mkv", size=10_000_000)
    conn.execute("UPDATE media_file SET enriched_at = ? WHERE id = ?", (int(time.time()), file_id))
    # Stream row missing hdr_format and is_default; codec / dimensions already set.
    conn.execute(
        "INSERT INTO media_stream (file_id, idx, kind, codec, lang, channels, width, height, "
        " duration_ms, bitrate, hdr_format, is_atmos, is_default, forced, format) "
        "VALUES (?, 0, 'video', 'hevc', 'eng', NULL, 3840, 2160, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
        (file_id,),
    )
    # Also a stale enriched_at so we can verify it does NOT change.
    enriched_at_before = conn.execute("SELECT enriched_at FROM media_file WHERE id = ?", (file_id,)).fetchone()[0]

    extracted_row = MediaStreamRow(
        id=0,
        file_id=0,
        idx=0,
        kind="video",
        codec="OVERWRITE-IGNORED",  # backfill does not touch codec
        lang=None,
        channels=None,
        width=None,
        height=None,
        duration_ms=None,
        bitrate=None,
        hdr_format="Dolby Vision",
        is_atmos=None,
        is_default=True,
        forced=None,
        format=None,
    )

    class _StubWrapper:
        def extract_streams(self, path: Path) -> list[MediaStreamRow]:
            return [extracted_row]

    with patch("personalscraper.indexer.scanner._modes.MediaInfoWrapper", return_value=_StubWrapper()):
        budget_exhausted = [False]
        _scan_disk_enrich_backfill(
            conn,
            disk,
            budget_seconds=None,
            started_at_monotonic=time.monotonic(),
            budget_exhausted=budget_exhausted,
            scan_run_id=0,
        )

    row = conn.execute(
        "SELECT codec, height, hdr_format, is_default FROM media_stream WHERE file_id = ? AND idx = 0",
        (file_id,),
    ).fetchone()
    # codec untouched, height untouched, hdr_format + is_default backfilled.
    assert row[0] == "hevc"
    assert row[1] == 2160
    assert row[2] == "Dolby Vision"
    assert row[3] == 1

    # enriched_at must not be rewritten — backfill is non-destructive.
    enriched_at_after = conn.execute("SELECT enriched_at FROM media_file WHERE id = ?", (file_id,)).fetchone()[0]
    assert enriched_at_after == enriched_at_before


def test_backfill_skips_non_video_extensions(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """A ``.nfo`` file with NULL stream columns is silently skipped (sidecar)."""
    mount = str(tmp_path / "TestDisk")
    Path(mount).mkdir()
    Path(mount, "junk.nfo").write_bytes(b"X" * 200)

    disk = _seed_disk(conn, mount)
    file_id = _seed_file(conn, disk_id=disk.id, rel_path=".", filename="junk.nfo", size=200)
    conn.execute("UPDATE media_file SET enriched_at = ? WHERE id = ?", (int(time.time()), file_id))
    # An anomalous stream row (rare, but possible from a previous mediainfo
    # parse on a junk file). Still must not trigger re-extraction since the
    # extension is not a video container.
    conn.execute(
        "INSERT INTO media_stream (file_id, idx, kind, codec, lang, channels, width, height, "
        " duration_ms, bitrate, hdr_format, is_atmos, is_default, forced, format) "
        "VALUES (?, 0, 'video', 'junk', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
        (file_id,),
    )

    extract_calls: list[Path] = []

    class _StubWrapper:
        def extract_streams(self, path: Path) -> list[MediaStreamRow]:
            extract_calls.append(path)
            return []

    with patch("personalscraper.indexer.scanner._modes.MediaInfoWrapper", return_value=_StubWrapper()):
        budget_exhausted = [False]
        _scan_disk_enrich_backfill(
            conn,
            disk,
            budget_seconds=None,
            started_at_monotonic=time.monotonic(),
            budget_exhausted=budget_exhausted,
            scan_run_id=0,
        )

    assert extract_calls == [], "Sidecar .nfo files must never trigger pymediainfo in backfill"
