import json
import sqlite3
from pathlib import Path

from personalscraper.indexer.scanner._modes._item_stage import (
    build_item_row,
    upsert_item_with_attrs,
)

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import item_repo

# tests/indexer/scanner/_modes/ → parents[4] == repo root
MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "personalscraper" / "indexer" / "migrations"


def _make_db() -> sqlite3.Connection:
    """Real indexer schema (post-005) via apply_migrations — never drifts."""
    conn = sqlite3.connect(":memory:")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def test_build_item_row_routes_ids_and_canonical() -> None:
    """build_item_row routes provider IDs into external_ids_json + canonical."""
    row = build_item_row(
        title="The Godfather",
        kind="movie",
        year=1972,
        category_id="movies",
        tvdb_id=None,
        tmdb_id="238",
        nfo_default="tmdb",
        nfo_status="valid",
    )
    assert row["canonical_provider"] == "tmdb"
    assert row["title"] == "The Godfather"
    assert row["kind"] == "movie"
    # IDs live in external_ids_json (migration 005), NOT flat columns.
    assert json.loads(row["external_ids_json"])["tmdb"]["series_id"] == "238"


def test_upsert_item_with_attrs_creates_row() -> None:
    """upsert_item_with_attrs writes the media_item row and dispatch attrs."""
    conn = _make_db()
    row = build_item_row(
        title="Breaking Bad",
        kind="show",
        year=2008,
        category_id="tv_shows",
        tvdb_id="81189",
        tmdb_id="1396",
        nfo_default="tvdb",
        nfo_status="valid",
    )
    item_id = upsert_item_with_attrs(
        conn,
        row,
        attrs={
            item_repo._ATTR_DISPATCH_NORM_TITLE: "breaking bad",
            item_repo._ATTR_DISPATCH_DISK: "disk1",
            item_repo._ATTR_DISPATCH_PATH: "/mnt/disk1/series/Breaking Bad (2008)",
        },
    )
    assert isinstance(item_id, int)
    assert conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] == 1
    # show + tvdb_id → tvdb (kind beats the NFO-declared default).
    cp = conn.execute("SELECT canonical_provider FROM media_item WHERE id=?", (item_id,)).fetchone()[0]
    assert cp == "tvdb"
    # dispatch_normalized_title attr persisted (trailers / dispatch INNER JOIN on it).
    nt = conn.execute(
        "SELECT value FROM item_attribute WHERE item_id=? AND key=?",
        (item_id, item_repo._ATTR_DISPATCH_NORM_TITLE),
    ).fetchone()[0]
    assert nt == "breaking bad"


def test_upsert_item_nfo_missing_flags_issue() -> None:
    """NFO-less dirs must be indexed (folder-name fallback) AND flagged — never dropped."""
    conn = _make_db()
    row = build_item_row(
        title="Unknown Show",
        kind="show",
        year=None,
        category_id="tv_shows",
        tvdb_id=None,
        tmdb_id=None,
        nfo_default=None,
        nfo_status="missing",
    )
    item_id = upsert_item_with_attrs(
        conn,
        row,
        attrs={},
        issues=[{"type": "nfo_missing", "detail": None}],
    )
    # item must exist (folder-name fallback) — never silently dropped.
    assert conn.execute("SELECT COUNT(*) FROM media_item WHERE id=?", (item_id,)).fetchone()[0] == 1
    # issue must be flagged with a detected_at timestamp.
    issue_count = conn.execute(
        "SELECT COUNT(*) FROM item_issue WHERE item_id=? AND type='nfo_missing'", (item_id,)
    ).fetchone()[0]
    assert issue_count >= 1
