"""Tests for the backfill_ids scanner mode driver (phase 8.2).

The driver walks ``media_item`` rows, detects gaps via the pure
helpers exercised in :mod:`tests.indexer.test_backfill_ids`, and
writes the merged payloads back through a fail-soft UPDATE. The
tests below pin the orchestration contract — fail-soft on a façade
exception, no-op when every row is already populated, dry-run
guarantees no DB writes.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.api._helpers import ProviderFeatureUnavailable
from personalscraper.api.metadata._base import Notations
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner._modes.backfill_ids import (
    BackfillStats,
    run_backfill_ids,
)

MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """In-memory DB seeded with the full migration chain."""
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)
    return c


def _insert_item(
    conn: sqlite3.Connection,
    *,
    title: str,
    external_ids_json: str = "{}",
    ratings_json: str | None = None,
    canonical_provider: str | None = "tvdb",
) -> int:
    """Insert a minimal ``media_item`` and return its id."""
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, original_title, year, category_id, "
        "external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
        "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang) "
        "VALUES (?, ?, ?, NULL, 2020, 'movies', ?, ?, ?, NULL, NULL, ?, ?, NULL, 0, 'fr')",
        (
            "movie",
            title,
            title,
            external_ids_json,
            ratings_json,
            canonical_provider,
            now,
            now,
        ),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _imdb_notation() -> Notations:
    return Notations(provider="omdb", source="imdb", score=8.5, votes_count=1_000_000)


def _rt_notation() -> Notations:
    return Notations(provider="omdb", source="rotten_tomatoes", score=91.0, votes_count=0)


# ---------------------------------------------------------------------------
# Happy path — gap detected, fetched, merged
# ---------------------------------------------------------------------------


def test_backfill_appends_missing_imdb_rating(conn: sqlite3.Connection) -> None:
    """A row with an IMDb anchor + no ratings receives IMDb + RT rating rows."""
    eids = json.dumps({"imdb": {"series_id": "tt0944947"}})
    item_id = _insert_item(conn, title="Show", external_ids_json=eids, ratings_json=None)

    imdb = MagicMock()
    imdb.get_rating.return_value = [_imdb_notation()]
    rt = MagicMock()
    rt.get_rating.return_value = [_rt_notation()]

    stats = run_backfill_ids(conn, imdb_client=imdb, rt_client=rt)

    assert stats.items_updated == 1
    assert stats.ratings_added_count == 2
    row = conn.execute(
        "SELECT ratings_json FROM media_item WHERE id = ?", (item_id,)
    ).fetchone()
    sources = sorted(entry["source"] for entry in json.loads(row[0])["entries"])
    assert sources == ["imdb", "rotten_tomatoes"]


def test_backfill_skips_fully_populated_row(conn: sqlite3.Connection) -> None:
    """A row already carrying every family + every rating source is skipped."""
    eids = json.dumps(
        {
            "tvdb": {"series_id": "9001"},
            "tmdb": {"series_id": "5005"},
            "imdb": {"series_id": "tt0944947"},
        }
    )
    ratings = json.dumps(
        {
            "entries": [
                {"source": "imdb", "score": "8.5/10", "votes": 10},
                {"source": "rotten_tomatoes", "score": "91%", "votes": 0},
            ]
        }
    )
    _insert_item(conn, title="Full", external_ids_json=eids, ratings_json=ratings)

    imdb = MagicMock()
    rt = MagicMock()

    stats = run_backfill_ids(conn, imdb_client=imdb, rt_client=rt)

    assert stats.items_updated == 0
    assert stats.items_skipped == 1
    imdb.get_rating.assert_not_called()
    rt.get_rating.assert_not_called()


def test_backfill_dry_run_does_not_write(conn: sqlite3.Connection) -> None:
    """``dry_run=True`` keeps the DB row untouched even when a gap is detected."""
    eids = json.dumps({"imdb": {"series_id": "tt0944947"}})
    item_id = _insert_item(conn, title="Dry", external_ids_json=eids, ratings_json=None)

    imdb = MagicMock()
    imdb.get_rating.return_value = [_imdb_notation()]

    stats = run_backfill_ids(conn, imdb_client=imdb, rt_client=None, dry_run=True)

    assert stats.items_updated == 1  # logically updated
    row = conn.execute("SELECT ratings_json FROM media_item WHERE id = ?", (item_id,)).fetchone()
    # ratings_json on disk unchanged.
    assert row[0] is None


def test_backfill_fails_soft_on_provider_exception(conn: sqlite3.Connection) -> None:
    """A façade raising ``ProviderFeatureUnavailable`` is logged, loop continues.

    The row is treated as having no rating data ; the rest of the
    library backfill keeps running.
    """
    eids = json.dumps({"imdb": {"series_id": "tt0944947"}})
    _insert_item(conn, title="Broken", external_ids_json=eids, ratings_json=None)
    _insert_item(
        conn,
        title="Ok",
        external_ids_json=json.dumps({"imdb": {"series_id": "tt0000001"}}),
        ratings_json=None,
    )

    imdb_seq = MagicMock()
    imdb_seq.get_rating.side_effect = [
        ProviderFeatureUnavailable("imdb", "get_rating", "outage"),
        [_imdb_notation()],
    ]

    stats = run_backfill_ids(conn, imdb_client=imdb_seq, rt_client=None)

    # The failing row counted as "no ratings to add" → skipped, not failed.
    assert stats.items_skipped >= 1
    assert stats.items_updated == 1


def test_backfill_respects_show_filter(conn: sqlite3.Connection) -> None:
    """``show_filter`` restricts the pass to the matching ``title``."""
    eids = json.dumps({"imdb": {"series_id": "tt0944947"}})
    _insert_item(conn, title="Target", external_ids_json=eids, ratings_json=None)
    _insert_item(
        conn,
        title="Other",
        external_ids_json=json.dumps({"imdb": {"series_id": "tt0000001"}}),
        ratings_json=None,
    )

    imdb = MagicMock()
    imdb.get_rating.return_value = [_imdb_notation()]

    stats = run_backfill_ids(conn, imdb_client=imdb, rt_client=None, show_filter="Target")

    assert stats.items_scanned == 1
    assert stats.items_updated == 1


def test_backfill_no_imdb_id_skips_rating_fetch(conn: sqlite3.Connection) -> None:
    """Without an IMDb anchor, the IMDb / RT façades are not called."""
    _insert_item(conn, title="NoAnchor", external_ids_json="{}", ratings_json=None)

    imdb = MagicMock()
    rt = MagicMock()

    stats = run_backfill_ids(conn, imdb_client=imdb, rt_client=rt)

    imdb.get_rating.assert_not_called()
    rt.get_rating.assert_not_called()
    # The IDs branch is currently a placeholder so the row is treated as
    # nothing-to-do at the ratings layer ; ``items_skipped`` is acceptable.
    assert isinstance(stats, BackfillStats)
