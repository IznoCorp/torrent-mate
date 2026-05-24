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
from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner._modes.backfill_ids import (
    BackfillStats,
    _backfill_one,
    init_canonical_from_nfo,
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

    stats = run_backfill_ids(conn, event_bus=EventBus(), imdb_client=imdb, rt_client=rt)

    assert stats.items_updated == 1
    assert stats.ratings_added_count == 2
    row = conn.execute("SELECT ratings_json FROM media_item WHERE id = ?", (item_id,)).fetchone()
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

    stats = run_backfill_ids(conn, event_bus=EventBus(), imdb_client=imdb, rt_client=rt)

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

    stats = run_backfill_ids(conn, event_bus=EventBus(), imdb_client=imdb, rt_client=None, dry_run=True)

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

    stats = run_backfill_ids(conn, event_bus=EventBus(), imdb_client=imdb_seq, rt_client=None)

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

    stats = run_backfill_ids(conn, event_bus=EventBus(), imdb_client=imdb, rt_client=None, show_filter="Target")

    assert stats.items_scanned == 1
    assert stats.items_updated == 1


def test_backfill_emits_event_bus_lifecycle_events(conn: sqlite3.Connection) -> None:
    """A full pass emits Started + ItemCompleted/Skipped + Completed on the bus.

    Pins the contract documented in :mod:`personalscraper.indexer.events` :
    one ``BackfillStarted`` at the top, one per-item event per row, one
    ``BackfillCompleted`` at the end.
    """
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415
    from personalscraper.indexer.events import (  # noqa: PLC0415
        BackfillCompleted,
        BackfillItemCompleted,
        BackfillSkipped,
        BackfillStarted,
    )

    eids = json.dumps({"imdb": {"series_id": "tt0944947"}})
    _insert_item(conn, title="WithRatings", external_ids_json=eids, ratings_json=None)
    fully_done = json.dumps(
        {
            "tvdb": {"series_id": "9001"},
            "tmdb": {"series_id": "5005"},
            "imdb": {"series_id": "tt0944947"},
        }
    )
    fully_done_ratings = json.dumps(
        {
            "entries": [
                {"source": "imdb", "score": "8.5/10", "votes": 10},
                {"source": "rotten_tomatoes", "score": "91%", "votes": 0},
            ]
        }
    )
    _insert_item(conn, title="Skipped", external_ids_json=fully_done, ratings_json=fully_done_ratings)

    imdb = MagicMock()
    imdb.get_rating.return_value = [_imdb_notation()]

    captured: list[object] = []
    bus = EventBus()
    bus.subscribe(BackfillStarted, captured.append)
    bus.subscribe(BackfillItemCompleted, captured.append)
    bus.subscribe(BackfillSkipped, captured.append)
    bus.subscribe(BackfillCompleted, captured.append)

    run_backfill_ids(conn, event_bus=bus, imdb_client=imdb, rt_client=None)

    types = [type(event).__name__ for event in captured]
    assert types[0] == "BackfillStarted"
    assert types[-1] == "BackfillCompleted"
    assert "BackfillItemCompleted" in types
    assert "BackfillSkipped" in types


def test_backfill_propagates_programmer_class_exceptions(conn: sqlite3.Connection) -> None:
    """TypeError / AttributeError / KeyError from a façade must escape the loop.

    The DESIGN §4 fail-soft contract is for transport-class errors. A
    refactor regression (renamed field, deleted column, signature drift)
    should surface as a bug — burying it as one warning per row would
    leave the operator with a thousand log lines and a backfill that
    "completes" with bogus data.
    """
    _insert_item(conn, title="WillCrash", external_ids_json='{"imdb": {"series_id": "tt1"}}', ratings_json=None)

    imdb = MagicMock()
    imdb.get_rating.side_effect = TypeError("renamed parameter foo")

    with pytest.raises(TypeError, match="renamed parameter foo"):
        run_backfill_ids(conn, event_bus=EventBus(), imdb_client=imdb, rt_client=None)


def test_backfill_quota_short_circuit_preserves_caller_args(conn: sqlite3.Connection) -> None:
    """OmdbQuotaExhausted disables ratings via local flag (not arg reassignment).

    Before this fix, the loop would set imdb_client = None / rt_client = None,
    mutating bindings owned by the caller. The local-flag refactor leaves the
    references intact so a caller that re-uses them (e.g. for diagnostic
    inspection after run_backfill_ids returns) still sees the original
    object — even though no subsequent row called .get_rating() on it.
    """
    from personalscraper.api.metadata.omdb import OmdbQuotaExhausted  # noqa: PLC0415

    _insert_item(conn, title="First", external_ids_json='{"imdb": {"series_id": "tt1"}}', ratings_json=None)
    _insert_item(conn, title="Second", external_ids_json='{"imdb": {"series_id": "tt2"}}', ratings_json=None)

    imdb = MagicMock()
    # First call raises quota; subsequent calls must NOT happen.
    imdb.get_rating.side_effect = [OmdbQuotaExhausted(pre_call=True)]
    rt = MagicMock()

    stats = run_backfill_ids(conn, event_bus=EventBus(), imdb_client=imdb, rt_client=rt)

    # imdb.get_rating called exactly once (the first row); the second row's
    # rating attempt was short-circuited by the ratings_disabled flag.
    assert imdb.get_rating.call_count == 1
    rt.get_rating.assert_not_called()  # disabled after first quota signal
    # Both rows accounted for in stats (one skipped via quota, one via no-op or skip).
    assert stats.items_scanned == 2


def test_backfill_no_imdb_id_skips_rating_fetch(conn: sqlite3.Connection) -> None:
    """Without an IMDb anchor, the IMDb / RT façades are not called."""
    _insert_item(conn, title="NoAnchor", external_ids_json="{}", ratings_json=None)

    imdb = MagicMock()
    rt = MagicMock()

    stats = run_backfill_ids(conn, event_bus=EventBus(), imdb_client=imdb, rt_client=rt)

    imdb.get_rating.assert_not_called()
    rt.get_rating.assert_not_called()
    # The IDs branch is currently a placeholder so the row is treated as
    # nothing-to-do at the ratings layer ; ``items_skipped`` is acceptable.
    assert isinstance(stats, BackfillStats)


# ---------------------------------------------------------------------------
# Regression — stats counters reflect actual DB writes (11.2)
# ---------------------------------------------------------------------------


class _FailingConn:
    """Wraps a real sqlite3.Connection but raises OperationalError on UPDATE.

    sqlite3.Connection.execute is a read-only C-level attribute, so
    ``patch.object`` / ``monkeypatch.setattr`` cannot intercept it.
    Instead we pass this proxy as the ``conn`` argument — it delegates
    everything to the real connection except ``execute``, which raises
    when the SQL starts with ``UPDATE``.
    """

    def __init__(self, real: sqlite3.Connection) -> None:
        object.__setattr__(self, "_real", real)

    def execute(self, sql: str, params=None) -> sqlite3.Cursor:
        if sql.lstrip().upper().startswith("UPDATE"):
            raise sqlite3.OperationalError("database is locked")
        if params is not None:
            return self._real.execute(sql, params)
        return self._real.execute(sql)

    def __getattr__(self, name: str):
        return getattr(self._real, name)

    def __setattr__(self, name: str, value) -> None:
        setattr(self._real, name, value)


def test_backfill_one_stats_not_inflated_on_db_failure(conn: sqlite3.Connection) -> None:
    """Stats counters stay 0 when conn.execute raises OperationalError.

    Pin the regression fix: ids_added_count and ratings_added_count must
    reflect actual DB writes, not pre-write increments. An OperationalError
    on the UPDATE must leave counters at 0.
    """
    eids = json.dumps({"imdb": {"series_id": "tt0944947"}})
    item_id = _insert_item(conn, title="FailRow", external_ids_json=eids, ratings_json=None)

    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, kind, title, external_ids_json, ratings_json, canonical_provider FROM media_item WHERE id = ?",
        (item_id,),
    ).fetchone()
    assert row is not None

    stats = BackfillStats()
    imdb = MagicMock()
    imdb.get_rating.return_value = [_imdb_notation()]

    failing_conn = _FailingConn(conn)
    try:
        _backfill_one(
            failing_conn,
            row,
            imdb_client=imdb,
            rt_client=None,
            tmdb_client=None,
            tvdb_client=None,
            ids_only=False,
            ratings_only=False,
            dry_run=False,
            stats=stats,
        )
    except sqlite3.OperationalError:
        pass

    assert stats.ids_added_count == 0, f"ids_added_count={stats.ids_added_count}, expected 0"
    assert stats.ratings_added_count == 0, f"ratings_added_count={stats.ratings_added_count}, expected 0"


def test_init_canonical_stats_rollback_on_operational_error(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """populated_default stays 0 when conn.execute raises OperationalError.

    Pin the regression fix: populated_default / populated_fallback counters
    reflect actual DB writes. An OperationalError on the UPDATE must leave
    them at 0 and increment parse_unexpected_error instead.
    """
    # Create a temp directory with a valid NFO carrying a tmdb default uniqueid.
    media_dir = tmp_path / "TestMovie"
    media_dir.mkdir()
    nfo_path = media_dir / "TestMovie.nfo"
    nfo_path.write_text(
        '<?xml version="1.0" encoding="utf-8"?><movie><uniqueid type="tmdb" default="true">12345</uniqueid></movie>'
    )

    # Insert a row pointing to this directory, with canonical_provider=NULL
    # so it hits the canonical cohort path.
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, original_title, year, category_id, "
        "external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
        "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang) "
        "VALUES (?, ?, ?, NULL, 2020, 'movies', '{}', NULL, NULL, NULL, NULL, ?, ?, NULL, 0, 'fr')",
        ("movie", "TestMovie", "TestMovie", now, now),
    )
    item_id = cur.lastrowid
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, ?, ?)",
        (item_id, "dispatch_path", str(media_dir)),
    )

    failing_conn = _FailingConn(conn)
    stats = init_canonical_from_nfo(failing_conn, dry_run=False)

    assert stats.populated_default == 0, f"populated_default={stats.populated_default}, expected 0"
    assert stats.populated_fallback == 0, f"populated_fallback={stats.populated_fallback}, expected 0"
    # The OperationalError is caught by the fail-soft per-row except handler.
    assert stats.parse_unexpected_error == 1, f"parse_unexpected_error={stats.parse_unexpected_error}, expected 1"
