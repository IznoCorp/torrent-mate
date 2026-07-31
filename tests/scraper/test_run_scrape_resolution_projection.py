"""Phase 2 (decisions-spine, F2) — scrape-finalizer resolution projection.

The scrape finalizer projects the decision lifecycle onto the provenance spine.

Anti-regression contract:

- The authoritative ``scrape_decision`` write is UNCHANGED — every enqueued item
  still lands a ``pending`` row (the operator-facing decision queue is untouched).
- The spine projection is ADDITIVE and advisory: a *tracked* (follow-driven) item's
  provenance row gains ``resolution_state='awaiting'``; a *manual/direct* item (no spine
  row) gets NOTHING written to the spine (its decision lives only in ``scrape_decision``).
"""

from __future__ import annotations

import sqlite3
import unicodedata
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.acquire.store import build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.scraper.run import run_scrape
from personalscraper.scraper.scraper import ScrapeResult
from tests.fixtures.config import CANONICAL_STAGING_DIRS

_MIGRATION_013 = (
    Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations" / "013_scrape_decision.sql"
)


def _create_library_db(db_path: Path) -> None:
    """Create a library.db carrying the ``scrape_decision`` table (real migration 013)."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    conn.commit()
    conn.executescript(_MIGRATION_013.read_text(encoding="utf-8"))
    conn.close()


def test_awaiting_projected_on_tracked_item_and_manual_noop(tmp_path: Path) -> None:
    """A tracked item gets resolution_state='awaiting'; a manual item stays spine-less."""
    staging = tmp_path / "staging"
    movies_dir = staging / "001-MOVIES"
    movies_dir.mkdir(parents=True)
    tracked = movies_dir / "Ambiguous Movie"
    tracked.mkdir()
    manual = movies_dir / "Manual Movie"
    manual.mkdir()

    # Spine: a follow-driven item ingested at the ambiguous folder (manual item has none).
    acquire_db = tmp_path / "acquire.db"
    store = build_acquire_store(AcquireConfig(db_path=acquire_db))
    store.provenance.upsert_grab("hh", followed_id=None, media_ref=MediaRef(tmdb_id=1), kind="movie", grabbed_at=1)
    store.provenance.set_ingest("hh", ingest_path=str(tracked), ingested_at=2)
    store.close()

    library_db = tmp_path / "library.db"
    _create_library_db(library_db)

    settings = MagicMock()
    settings.tmdb_api_key = "fake"
    settings.tvdb_api_key = "fake"

    config = MagicMock()
    config.staging_dirs = CANONICAL_STAGING_DIRS
    config.paths.staging_dir = staging
    config.indexer.db_path = library_db
    config.acquire = AcquireConfig(db_path=acquire_db)

    results = [
        ScrapeResult(media_path=tracked, media_type="movie", action="queued_for_decision", decision_trigger="mid_band"),
        ScrapeResult(media_path=manual, media_type="movie", action="queued_for_decision", decision_trigger="ambiguous"),
    ]

    with (
        patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
        patch("personalscraper.scraper.run.Scraper") as MockScraper,
    ):
        mock = MockScraper.return_value
        mock.process_movies.return_value = results
        mock.process_tvshows.return_value = []
        run_scrape(settings, config=config, movies_only=True, event_bus=EventBus(), registry=MagicMock())

    # Authoritative decision write UNCHANGED — both items are pending in scrape_decision.
    conn = sqlite3.connect(str(library_db))
    apply_pragmas(conn)
    conn.row_factory = sqlite3.Row
    statuses = {
        unicodedata.normalize("NFC", r["staging_path"]): r["status"]
        for r in conn.execute("SELECT staging_path, status FROM scrape_decision")
    }
    conn.close()
    assert statuses[unicodedata.normalize("NFC", str(tracked))] == "pending"
    assert statuses[unicodedata.normalize("NFC", str(manual))] == "pending"

    # Spine projection: tracked → 'awaiting' (+ trigger); manual → NO spine row.
    store = build_acquire_store(AcquireConfig(db_path=acquire_db))
    try:
        trow = store.provenance.by_path(str(tracked))
        assert trow is not None
        assert trow.resolution_state == "awaiting"
        assert trow.resolution_trigger == "mid_band"
        assert trow.decision_id is not None  # stamped from DecisionWriter.upsert's return
        assert store.provenance.by_path(str(manual)) is None
    finally:
        store.close()


def test_dry_run_touches_neither_decision_nor_spine(tmp_path: Path) -> None:
    """A --dry-run preview never writes scrape_decision nor the spine projection (F47/F51)."""
    staging = tmp_path / "staging"
    movies_dir = staging / "001-MOVIES"
    movies_dir.mkdir(parents=True)
    tracked = movies_dir / "Ambiguous Movie"
    tracked.mkdir()

    acquire_db = tmp_path / "acquire.db"
    store = build_acquire_store(AcquireConfig(db_path=acquire_db))
    store.provenance.upsert_grab("hh", followed_id=None, media_ref=MediaRef(tmdb_id=1), kind="movie", grabbed_at=1)
    store.provenance.set_ingest("hh", ingest_path=str(tracked), ingested_at=2)
    store.close()

    library_db = tmp_path / "library.db"
    _create_library_db(library_db)

    settings = MagicMock()
    settings.tmdb_api_key = "fake"
    settings.tvdb_api_key = "fake"
    config = MagicMock()
    config.staging_dirs = CANONICAL_STAGING_DIRS
    config.paths.staging_dir = staging
    config.indexer.db_path = library_db
    config.acquire = AcquireConfig(db_path=acquire_db)

    results = [
        ScrapeResult(media_path=tracked, media_type="movie", action="queued_for_decision", decision_trigger="mid_band")
    ]
    with (
        patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
        patch("personalscraper.scraper.run.Scraper") as MockScraper,
    ):
        mock = MockScraper.return_value
        mock.process_movies.return_value = results
        mock.process_tvshows.return_value = []
        run_scrape(settings, config=config, dry_run=True, movies_only=True, event_bus=EventBus(), registry=MagicMock())

    conn = sqlite3.connect(str(library_db))
    apply_pragmas(conn)
    assert conn.execute("SELECT COUNT(*) FROM scrape_decision").fetchone()[0] == 0
    conn.close()
    store = build_acquire_store(AcquireConfig(db_path=acquire_db))
    try:
        row = store.provenance.by_path(str(tracked))
        assert row is not None
        assert row.resolution_state is None  # dry-run left the projection untouched
    finally:
        store.close()
