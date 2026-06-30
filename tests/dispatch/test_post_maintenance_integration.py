"""Integration/regression tests for post-dispatch index maintenance.

Reproduces the 2026-06-29 ``items_without_files=6`` symptom where freshly
dispatched items had releases but 0 linked media_file rows.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance


@pytest.fixture
def temp_library_db(tmp_path: Path) -> Path:
    """Create a minimal library.db with the schema needed for relinking.

    Schema mirrors the real ``personalscraper/indexer/migrations/001_init.sql``
    + ``002_nullable_release_id_oshash.sql`` with only the columns that the
    linker reads or writes.  Each NOT NULL column is included so INSERTs
    succeed against SQLite's strict checking.
    """
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE disk (
            id INTEGER PRIMARY KEY,
            uuid TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            mount_path TEXT,
            is_mounted INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE media_item (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL CHECK(kind IN ('movie','show')),
            title TEXT NOT NULL,
            title_sort TEXT NOT NULL,
            year INTEGER,
            category_id TEXT NOT NULL,
            date_created INTEGER NOT NULL,
            date_modified INTEGER NOT NULL,
            preferred_lang TEXT NOT NULL DEFAULT 'fr'
        );
        CREATE TABLE season (
            id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES media_item(id),
            number INTEGER NOT NULL,
            episode_count INTEGER NOT NULL DEFAULT 0,
            has_poster INTEGER NOT NULL DEFAULT 0,
            episodes_with_nfo INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE episode (
            id INTEGER PRIMARY KEY,
            season_id INTEGER NOT NULL REFERENCES season(id),
            number INTEGER NOT NULL,
            title TEXT
        );
        CREATE TABLE media_release (
            id INTEGER PRIMARY KEY,
            item_id INTEGER REFERENCES media_item(id),
            episode_id INTEGER REFERENCES episode(id),
            quality TEXT,
            edition TEXT,
            primary_lang TEXT
        );
        CREATE TABLE path (
            id INTEGER PRIMARY KEY,
            disk_id INTEGER NOT NULL REFERENCES disk(id),
            rel_path TEXT NOT NULL
        );
        CREATE TABLE media_file (
            id INTEGER PRIMARY KEY,
            filename TEXT NOT NULL,
            path_id INTEGER REFERENCES path(id),
            release_id INTEGER REFERENCES media_release(id),
            size_bytes INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            oshash TEXT,
            scan_generation INTEGER NOT NULL,
            last_verified_at INTEGER NOT NULL,
            miss_strikes INTEGER NOT NULL DEFAULT 0,
            deleted_at INTEGER
        );
        CREATE TABLE item_attribute (
            id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES media_item(id),
            key TEXT NOT NULL,
            value TEXT NOT NULL
        );
    """)

    # Insert a disk.
    conn.execute(
        "INSERT INTO disk (id, uuid, label, mount_path, is_mounted) VALUES (1, 'fake-uuid-test', 'disk_1', ?, 1)",
        (str(tmp_path / "disk_1"),),
    )

    # Create the disk mount dir.
    disk_dir = tmp_path / "disk_1"
    disk_dir.mkdir()

    # Insert a dispatched movie: has item + release but 0 linked files.
    conn.execute(
        "INSERT INTO media_item (id, kind, title, title_sort, year, "
        "category_id, date_created, date_modified, preferred_lang) "
        "VALUES (1, 'movie', 'Test Movie', 'Test Movie', 2025, "
        "'movies', 1719676800, 1719676800, 'fr')"
    )
    conn.execute(
        "INSERT INTO media_release (id, item_id, quality, edition, primary_lang) VALUES (1, 1, NULL, NULL, NULL)"
    )
    # Insert item_attribute with dispatch_path so the linker can find the item.
    movie_dir = disk_dir / "Test Movie"
    movie_dir.mkdir()
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (1, 'dispatch_path', ?)",
        (str(movie_dir),),
    )

    # Insert a path and a media_file with release_id=NULL (the regression symptom).
    conn.execute("INSERT INTO path (id, disk_id, rel_path) VALUES (1, 1, 'Test Movie')")
    # Create a dummy video file.
    video_file = movie_dir / "Test.Movie.2025.1080p.mkv"
    video_file.write_text("fake video content")
    conn.execute(
        "INSERT INTO media_file (id, filename, path_id, release_id, "
        "size_bytes, mtime_ns, oshash, scan_generation, last_verified_at) "
        "VALUES (1, 'Test.Movie.2025.1080p.mkv', 1, NULL, "
        "17, 1719676800000000000, 'deadbeefdeadbeef', 1, 1719676800)"
    )

    conn.commit()
    conn.close()
    return db_path


def test_integration_media_file_linked_after_maintenance(tmp_path: Path, temp_library_db: Path) -> None:
    """After post_maintenance, media_file rows gain linked release_id.

    This is the regression test for the 2026-06-29 symptom: freshly dispatched
    items had releases but 0 linked media_file rows (items_without_files=6).
    The hook must link those files.
    """
    touched_disks = {"disk_1"}

    # Build a mock Config that points to our temp DB.
    mock_config = MagicMock()
    mock_config.indexer.db_path = temp_library_db
    mock_config.indexer.post_dispatch_maintenance.enabled = True

    # The scan step uses library_index_command which needs full config.
    # We patch the scan to a no-op (the integration concern is relink + fix).
    # Use the REAL _run_relink and _run_fix_season_counts (not mocked)
    # so we exercise the actual linker code against the temp DB.
    with patch(
        "personalscraper.dispatch.post_maintenance._scan_disk_incremental",
        return_value=0,
    ):
        run_post_dispatch_maintenance(mock_config, touched_disks, enabled=True)

    # Verify: the media_file now has a non-NULL release_id.
    conn = sqlite3.connect(str(temp_library_db))
    row = conn.execute("SELECT release_id FROM media_file WHERE id = 1").fetchone()
    conn.close()

    assert row is not None, "media_file row should exist"
    assert row[0] is not None, (
        "REGRESSION: media_file.release_id is still NULL after post_maintenance — "
        "the 2026-06-29 symptom (items_without_files=6) was NOT fixed"
    )


def test_integration_noop_when_all_files_linked(tmp_path: Path, temp_library_db: Path) -> None:
    """Post-maintenance is a no-op when all files are already linked."""
    # Pre-link the file.
    conn = sqlite3.connect(str(temp_library_db))
    conn.execute("UPDATE media_file SET release_id = 1 WHERE id = 1")
    conn.commit()
    conn.close()

    mock_config = MagicMock()
    mock_config.indexer.db_path = temp_library_db
    mock_config.indexer.post_dispatch_maintenance.enabled = True

    with patch(
        "personalscraper.dispatch.post_maintenance._scan_disk_incremental",
        return_value=0,
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)

    # Verify: no change — release_id still 1.
    conn = sqlite3.connect(str(temp_library_db))
    row = conn.execute("SELECT release_id FROM media_file WHERE id = 1").fetchone()
    conn.close()
    assert row is not None and row[0] == 1
