"""Unit tests for the enrich-mode performance optimisations.

Covers:
- Extension-based skip: ``_scan_disk_enrich`` passes ``wrapper=None`` to
  ``_enrich_one_file`` for non-video files so libmediainfo is not invoked
  on the ~84 % of library files that are sidecars (jpg / nfo / srt / ...).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner._modes import _scan_disk_enrich
from personalscraper.indexer.schema import DiskRow

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
