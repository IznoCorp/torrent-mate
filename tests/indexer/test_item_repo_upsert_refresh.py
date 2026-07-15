"""Regression: re-scan refreshes artwork_json / nfo_status (e2e loop 1, #8).

They used to be written at INSERT only — an item whose artwork appeared after
its first indexing kept ``has_poster=0`` forever (prod: 28 items reported
poster-less while their posters sat on disk), and a later-fixed NFO kept its
stale status.
"""

from __future__ import annotations

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
