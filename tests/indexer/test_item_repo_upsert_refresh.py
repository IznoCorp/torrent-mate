"""Regression: re-scan refreshes artwork_json / nfo_status (e2e loop 1, #8).

They used to be written at INSERT only — an item whose artwork appeared after
its first indexing kept ``has_poster=0`` forever (prod: 28 items reported
poster-less while their posters sat on disk), and a later-fixed NFO kept its
stale status.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from personalscraper.indexer import migrations as _migrations_pkg
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.repos.item_repo import MediaItemRow


def _row(**overrides) -> MediaItemRow:
    base = {
        "id": 0,
        "kind": "movie",
        "title": "Sherlock Holmes",
        "title_sort": "Sherlock Holmes",
        "original_title": None,
        "year": 2009,
        "category_id": "movies",
        "external_ids_json": "{}",
        "ratings_json": None,
        "canonical_provider": None,
        "nfo_status": "missing",
        "artwork_json": None,
        "date_created": 1_750_000_000,
        "date_modified": 1_750_000_000,
        "date_metadata_refreshed": None,
        "is_locked": 0,
        "preferred_lang": "fr",
    }
    base.update(overrides)
    return MediaItemRow(**base)


def _conn(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "library.db"))
    apply_migrations(conn, Path(_migrations_pkg.__file__).parent)
    return conn


def test_rescan_refreshes_artwork_and_nfo_status(tmp_path: Path) -> None:
    """A later scan carrying fresh artwork/nfo facts overwrites the stale ones."""
    conn = _conn(tmp_path)
    item_id = item_repo.upsert(conn, _row(artwork_json=None, nfo_status="missing"))

    # The poster appeared on disk; the next scan reports it.
    item_repo.upsert(conn, _row(artwork_json='{"poster": 1}', nfo_status="valid"))

    stored = conn.execute(
        "SELECT artwork_json, nfo_status, has_poster FROM media_item WHERE id = ?", (item_id,)
    ).fetchone()
    assert stored[0] == '{"poster": 1}'
    assert stored[1] == "valid"
    assert stored[2] == 1  # the generated has_poster column follows


def test_none_artwork_preserves_stored_value(tmp_path: Path) -> None:
    """A caller that computes no artwork facts (dispatch path) preserves them."""
    conn = _conn(tmp_path)
    item_id = item_repo.upsert(conn, _row(artwork_json='{"poster": 1}', nfo_status="valid"))

    item_repo.upsert(conn, _row(artwork_json=None, nfo_status=None))

    stored = conn.execute("SELECT artwork_json, nfo_status FROM media_item WHERE id = ?", (item_id,)).fetchone()
    assert stored[0] == '{"poster": 1}'
    assert stored[1] == "valid"


class TestExternalIdsRefresh:
    """NFO id corrections must propagate to existing rows (2026-07-15).

    Live incident: « New Girl (2011) » carried its TVDB id under type=tmdb;
    after the operator-corrected NFO was rescanned, the media_item row STILL
    held tmdb=248682 (Rabe Rudi) — the upsert UPDATE branch refreshed
    artwork/nfo_status but never external_ids_json, so every wrong legacy id
    was immortal (wrong posters downloaded on rescrape, ownership misses).
    """

    def test_nfo_id_correction_overwrites_family(self, tmp_path: Path) -> None:
        """Re-upsert with a corrected tmdb id updates that family."""
        conn = _conn(tmp_path)
        first = _row(external_ids_json='{"tmdb": {"series_id": "248682", "episode_id": null}}')
        item_id = item_repo.upsert(conn, first)

        corrected = _row(external_ids_json='{"tmdb": {"series_id": "1420", "episode_id": null}}')
        assert item_repo.upsert(conn, corrected) == item_id

        stored = json.loads(
            conn.execute("SELECT external_ids_json FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
        )
        assert stored["tmdb"]["series_id"] == "1420", "the corrected NFO id must win"

    def test_merge_preserves_families_the_nfo_lacks(self, tmp_path: Path) -> None:
        """A tmdb-only NFO must not erase the backfilled tvdb/imdb families."""
        conn = _conn(tmp_path)
        first = _row(
            external_ids_json=(
                '{"tmdb": {"series_id": "248682", "episode_id": null},'
                ' "tvdb": {"series_id": "248682", "episode_id": null},'
                ' "imdb": {"series_id": "tt1826940", "episode_id": null}}'
            )
        )
        item_id = item_repo.upsert(conn, first)

        corrected = _row(external_ids_json='{"tmdb": {"series_id": "1420", "episode_id": null}}')
        item_repo.upsert(conn, corrected)

        stored = json.loads(
            conn.execute("SELECT external_ids_json FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
        )
        assert stored["tmdb"]["series_id"] == "1420"
        assert stored["tvdb"]["series_id"] == "248682", "families absent from the NFO survive"
        assert stored["imdb"]["series_id"] == "tt1826940"

    def test_idless_caller_preserves_ids(self, tmp_path: Path) -> None:
        """A caller without ids (dispatch path, '{}') never clobbers them."""
        conn = _conn(tmp_path)
        first = _row(external_ids_json='{"tmdb": {"series_id": "1420", "episode_id": null}}')
        item_id = item_repo.upsert(conn, first)

        idless = _row(external_ids_json="{}")
        item_repo.upsert(conn, idless)

        stored = json.loads(
            conn.execute("SELECT external_ids_json FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
        )
        assert stored["tmdb"]["series_id"] == "1420"
