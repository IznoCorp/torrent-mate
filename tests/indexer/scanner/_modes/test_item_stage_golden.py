"""Characterization golden: library-index --mode full == legacy library-scan DB end-state.

This test is the safety net for Phase 3's deletion of library/scanner.py.
It must pass before any deletion is attempted. If it fails, Phase 3 is blocked.

Runs the legacy ``scan_library`` on a temp filesystem fixture, captures the
``media_item`` DB end-state as the baseline, then on a fresh in-memory DB runs
the new ``stage_library_items`` (pass 1 of ``library-index --mode full``), and
asserts the end-states are equal.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest

from personalscraper.conf.ids import TV_CATEGORY_IDS
from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.indexer.db import apply_migrations
from tests.fixtures.config import CANONICAL_STAGING_DIRS

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "personalscraper" / "indexer" / "migrations"


def _build_mini_library(tmp_path: Path) -> dict[str, Any]:
    """Build a temp filesystem + Config that mirrors the mini_library fixture.

    Replicates ``tests/library/test_integration.py`` lines 40-124 inline so
    the golden test is self-contained and does not depend on conftest fixtures.
    The fixture contains:

    * A complete movie "The Matrix (1999)" with tmdb+imdb NFO, artwork,
      ``.actors``, and ``.DS_Store``.
    * A no-NFO "Incomplete Movie".
    * A TV show "Fallout (2024)" with tmdb NFO, artwork, and ``Saison 01/``
      containing two episode files (one with a sibling .nfo, one without).

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        Dict with keys ``disk``, ``config``, ``disk_cfg``.
    """
    disk = tmp_path / "Disk1" / "medias"

    # --- Movie: complete ---
    matrix = disk / "films" / "The Matrix (1999)"
    matrix.mkdir(parents=True)
    (matrix / "The Matrix.mkv").write_bytes(b"\x00" * 1000)
    (matrix / "The Matrix.nfo").write_text(
        "<movie><title>The Matrix</title><year>1999</year>"
        '<uniqueid type="tmdb">603</uniqueid>'
        '<uniqueid type="imdb">tt0133093</uniqueid></movie>'
    )
    (matrix / "The Matrix-poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    (matrix / "The Matrix-landscape.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    actors = matrix / ".actors"
    actors.mkdir()
    (actors / "Keanu Reeves.jpg").write_bytes(b"\x00" * 50)
    (matrix / ".DS_Store").write_bytes(b"\x00" * 10)

    # --- Movie: incomplete (no NFO, bad naming) ---
    incomplete = disk / "films" / "Incomplete Movie"
    incomplete.mkdir(parents=True)
    (incomplete / "movie.mkv").write_bytes(b"\x00" * 1000)

    # --- TV Show ---
    fallout = disk / "series" / "Fallout (2024)"
    fallout.mkdir(parents=True)
    (fallout / "tvshow.nfo").write_text(
        '<tvshow><title>Fallout</title><uniqueid type="tmdb">106379</uniqueid></tvshow>'
    )
    (fallout / "poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    (fallout / "season01-poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    s01 = fallout / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01 - The Beginning.mkv").write_bytes(b"\x00" * 2000)
    (s01 / "S01E01 - The Beginning.nfo").write_text("<episodedetails><title>The Beginning</title></episodedetails>")
    (s01 / "S01E02 - The End.mkv").write_bytes(b"\x00" * 2000)
    show_actors = fallout / ".actors"
    show_actors.mkdir()
    (show_actors / "Ella Purnell.jpg").write_bytes(b"\x00" * 50)
    (fallout / "empty_release_dir").mkdir()

    # Build DiskConfig + Config for scan operations (mirrors mini_library lines 90-110).
    disk_cfg = DiskConfig(id="disk1", path=disk, categories=["movies", "tv_shows"])
    config = Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[disk_cfg],
        categories={
            "movies": CategoryConfig(folder_name="films"),
            "tv_shows": CategoryConfig(folder_name="series"),
        },
        staging_dirs=CANONICAL_STAGING_DIRS,
    )

    return {"disk": disk, "config": config, "disk_cfg": disk_cfg}


def _snapshot_media_items(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Sorted media_item rows as dicts — real post-migration-005 columns only.

    IDs come from ``external_ids_json`` (migration 005 dropped the flat columns);
    disk comes from the ``item_attribute`` flex row (key='dispatch_disk').

    Args:
        conn: Open SQLite connection with migrations applied and data populated.

    Returns:
        List of dicts, each with keys ``title``, ``kind``, ``year``,
        ``canonical_provider``, ``tvdb``, ``tmdb``, ``nfo_status``,
        ``category_id``, ``disk``, ordered by ``(title, kind)``.
    """
    rows = conn.execute(
        """
        SELECT mi.title, mi.kind, mi.year, mi.canonical_provider,
               json_extract(mi.external_ids_json, '$.tvdb.series_id') AS tvdb,
               json_extract(mi.external_ids_json, '$.tmdb.series_id') AS tmdb,
               mi.nfo_status, mi.category_id,
               (SELECT value FROM item_attribute
                 WHERE item_id = mi.id AND key = 'dispatch_disk') AS disk
          FROM media_item mi
         ORDER BY mi.title, mi.kind
        """
    ).fetchall()
    cols = [
        "title",
        "kind",
        "year",
        "canonical_provider",
        "tvdb",
        "tmdb",
        "nfo_status",
        "category_id",
        "disk",
    ]
    return [dict(zip(cols, r)) for r in rows]


@pytest.mark.integration
def test_full_mode_db_equals_library_scan_baseline(tmp_path: Path) -> None:
    """library-index --mode full must produce the same media_item rows as library-scan.

    Baseline = legacy ``scan_library``'s directory walk (scan_movie_dir /
    scan_tvshow_dir → _upsert_media_item → _upsert_seasons_and_episodes),
    which is the code path that writes ``media_item`` rows.  The full
    ``scan_library`` function also calls ``_indexer_scan`` at the end for
    file-level indexing, but that only writes ``media_file`` / ``path`` /
    ``scan_run`` rows — none of which the snapshot reads — and it requires
    a real mount point for disk identity bootstrapping.  Replicating the
    directory walk directly gives identical ``media_item`` rows without the
    side effect.

    Result = new ``stage_library_items`` on the same config.
    Both run against a fresh in-memory DB with all migrations applied.
    """
    from personalscraper.indexer.scanner._modes._item_stage import stage_library_items
    from personalscraper.library.scanner import (
        _ensure_disk_row,
        _upsert_media_item,
        _upsert_seasons_and_episodes,
        scan_movie_dir,
        scan_tvshow_dir,
    )

    fixture = _build_mini_library(tmp_path)
    config = fixture["config"]
    now_s = int(time.time())

    # --- Baseline: legacy scan_library directory walk (replicated verbatim) ---
    # Mirror lines 931-986 of library/scanner.py:scan_library.
    conn_legacy = sqlite3.connect(":memory:")
    apply_migrations(conn_legacy, MIGRATIONS_DIR)

    for disk_cfg in config.disks:
        if not disk_cfg.path.exists():
            continue
        _ensure_disk_row(conn_legacy, disk_cfg, now_s)
        for category_id in disk_cfg.categories:
            cat_cfg = config.category(category_id)
            category_dir = disk_cfg.path / cat_cfg.folder_name
            if not category_dir.is_dir():
                continue
            is_tvshow = category_id in TV_CATEGORY_IDS
            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                try:
                    if is_tvshow:
                        scan_item = scan_tvshow_dir(media_dir, disk_cfg.id, category_id)
                    else:
                        scan_item = scan_movie_dir(media_dir, disk_cfg.id, category_id)
                    item_id = _upsert_media_item(conn_legacy, scan_item, now_s)
                    if is_tvshow and scan_item.seasons:
                        _upsert_seasons_and_episodes(conn_legacy, item_id, scan_item.seasons)
                except OSError:
                    continue

    baseline = _snapshot_media_items(conn_legacy)
    conn_legacy.close()

    # --- New path: stage_library_items (pass 1 of library-index --mode full) ---
    conn_new = sqlite3.connect(":memory:")
    apply_migrations(conn_new, MIGRATIONS_DIR)
    stage_library_items(conn_new, config)
    result = _snapshot_media_items(conn_new)
    conn_new.close()

    assert baseline, "Baseline must not be empty — fixture has 3 media dirs"
    assert result == baseline, (
        f"DB end-state mismatch.\n\n"
        f"Baseline ({len(baseline)} rows):\n{baseline}\n\n"
        f"Result   ({len(result)} rows):\n{result}"
    )
