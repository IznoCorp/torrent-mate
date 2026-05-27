"""End-to-end aggregate tests for the ``provider-ids`` feature.

Combines several phase contracts into a small set of focused scenarios
that prove the feature works on a realistic mini-fixture without
depending on live HTTP services :

1. **Migration round-trip** — phase 7 schema is reachable through every
   write path established in phases 7.5 and 10.
2. **Drift hardening** — phase 4 verify check refuses NFOs whose
   episodes lack the canonical uniqueid, even when the show-level
   tvshow.nfo is otherwise valid.
3. **Backfill idempotence** — phase 8 ``run_backfill_ids`` is a no-op
   on a fully-populated library (DESIGN §5).
4. **Capability composition** — phases 11/13/14 produced clients that
   compose only the atomic capabilities they implement (DESIGN §4).

These tests are deliberately fast and HTTP-free. The full pipeline
behaviour is exercised by the phase-specific test suites ; this file
acts as the cross-phase regression net.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.api.metadata._base import Notations
from personalscraper.api.metadata._contracts import (
    IDCrossRef,
    IDValidator,
    MovieDetailsProvider,
    RatingProvider,
    TvDetailsProvider,
)
from personalscraper.api.metadata.imdb import IMDbClient
from personalscraper.api.metadata.registry import FanOutResult, ProviderRegistry
from personalscraper.api.metadata.rotten_tomatoes import RottenTomatoesClient
from personalscraper.api.notify._contracts import HealthChecker, Notifier
from personalscraper.api.torrent._contracts import (
    AuthenticatedClient,
    TorrentController,
    TorrentInspector,
    TorrentLister,
    TorrentStateInspector,
)
from personalscraper.api.torrent.qbittorrent import QBitClient
from personalscraper.api.tracker._contracts import CategoryListable, TorrentSearchable
from personalscraper.api.tracker.c411 import C411Client
from personalscraper.api.tracker.lacale import LaCaleClient
from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner._modes.backfill_ids import run_backfill_ids

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _named(name: str) -> MagicMock:
    """Build a MagicMock with ``provider_name`` set to ``name``."""
    m = MagicMock()
    m.provider_name = name
    return m


def _registry_mock(
    *,
    ratings: list[MagicMock] | None = None,
    details: list[MagicMock] | None = None,
) -> MagicMock:
    """Build a registry mock for the indexer driver.

    Args:
        ratings: Providers returned from ``fan_out(RatingProvider)``.
        details: Providers returned from ``chain(MovieDetailsProvider)``
            and ``chain(TvDetailsProvider)``.
    """
    reg = MagicMock(spec=ProviderRegistry)
    reg.fan_out.return_value = FanOutResult(values=ratings or [], attempted=[])
    reg.chain.return_value = details or []
    reg.emit_provider_fallback = MagicMock()
    reg.emit_provider_exhausted = MagicMock()
    return reg


# Reference the capability Protocols so the formatter does not strip them —
# they document the shape of providers handed to ``chain``/``fan_out`` in
# the registry mocks below.
_ = (MovieDetailsProvider, TvDetailsProvider)


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """In-memory DB seeded with the full migration chain (5 versions)."""
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)
    return c


def _seed_complete_item(conn: sqlite3.Connection, *, title: str) -> int:
    """Insert a media_item with every external_ids family + every rating source."""
    now = int(time.time())
    external_ids = json.dumps(
        {
            "tvdb": {"series_id": "9001"},
            "tmdb": {"series_id": "5005"},
            "imdb": {"series_id": "tt0944947"},
        }
    )
    ratings = json.dumps(
        {
            "entries": [
                {"source": "imdb", "score": "8.5/10", "votes": 1_000_000},
                {"source": "rotten_tomatoes", "score": "91%", "votes": 0},
            ]
        }
    )
    cur = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, original_title, year, category_id, "
        "external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
        "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang) "
        "VALUES (?, ?, ?, NULL, 2008, 'tv_shows', ?, ?, 'tvdb', NULL, NULL, ?, ?, NULL, 0, 'fr')",
        ("show", title, title, external_ids, ratings, now, now),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Migration + write-path round-trip
# ---------------------------------------------------------------------------


def test_e2e_migration_005_round_trip(conn: sqlite3.Connection) -> None:
    """A row written through the new columns reads back identically."""
    item_id = _seed_complete_item(conn, title="Breaking Bad")
    row = conn.execute(
        "SELECT external_ids_json, ratings_json, canonical_provider FROM media_item WHERE id = ?",
        (item_id,),
    ).fetchone()
    assert row is not None
    eids = json.loads(row[0])
    assert eids["tvdb"]["series_id"] == "9001"
    assert eids["imdb"]["series_id"] == "tt0944947"
    assert row[2] == "tvdb"


# ---------------------------------------------------------------------------
# Backfill idempotence
# ---------------------------------------------------------------------------


def test_e2e_backfill_idempotent_on_complete_library(conn: sqlite3.Connection) -> None:
    """A fully-populated library survives ``run_backfill_ids`` unchanged.

    DESIGN §5 idempotence — a second pass on the same library MUST
    produce zero updates.
    """
    _seed_complete_item(conn, title="Breaking Bad")
    imdb = _named("imdb")
    rt = _named("rotten_tomatoes")
    bus = EventBus()
    registry = _registry_mock(ratings=[imdb, rt])

    stats = run_backfill_ids(conn, event_bus=bus, registry=registry)

    assert stats.items_scanned == 1
    assert stats.items_updated == 0
    assert stats.items_skipped == 1
    imdb.get_rating.assert_not_called()
    rt.get_rating.assert_not_called()


def _seed_partial_item(conn: sqlite3.Connection, *, title: str) -> int:
    """Insert a media_item that has only the canonical TVDB id + IMDb rating gap.

    Used by :func:`test_e2e_backfill_partial_then_idempotent` to prove that
    a partial row gets filled additively (TVDB stays untouched, IMDb id +
    ratings get added) and that the second pass is a no-op.
    """
    now = int(time.time())
    external_ids = json.dumps({"tvdb": {"series_id": "9001"}})
    cur = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, original_title, year, category_id, "
        "external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
        "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang) "
        "VALUES (?, ?, ?, NULL, 2008, 'tv_shows', ?, NULL, 'tvdb', NULL, NULL, ?, ?, NULL, 0, 'fr')",
        ("show", title, title, external_ids, now, now),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def test_e2e_backfill_partial_then_idempotent(conn: sqlite3.Connection) -> None:
    """A partially-populated row is filled additively and the second pass is a no-op.

    Step 1 — Seed a row whose canonical TVDB id exists but IMDb id +
    rating sources are missing. Wire a TVDB client whose
    ``get_tv(...)`` returns ``MediaDetails.external_ids = {"tmdb":
    "5005", "imdb": "tt0944947"}``, plus an IMDb façade that returns
    one ``Notations`` row. After the pass, TVDB stays unchanged, IMDb
    + TMDB get written, and the IMDb rating appears in
    ``ratings_json``.

    Step 2 — Re-run the same backfill on the now-complete row. The
    pass must report zero updates ; mocks must observe zero calls.
    Proves DESIGN §5 idempotence on the partial-fill path.
    """
    item_id = _seed_partial_item(conn, title="Breaking Bad")

    tvdb_client = _named("tvdb")
    tvdb_client.get_tv.return_value = MagicMock(external_ids={"tmdb": "5005", "imdb": "tt0944947"})
    imdb = _named("imdb")
    imdb.get_rating.return_value = [Notations(provider="omdb", source="imdb", score=9.5, votes_count=2_000_000)]
    rt = _named("rotten_tomatoes")
    rt.get_rating.return_value = None
    bus = EventBus()
    registry = _registry_mock(ratings=[imdb, rt], details=[tvdb_client])

    stats = run_backfill_ids(
        conn,
        event_bus=bus,
        registry=registry,
    )

    assert stats.items_updated == 1
    assert stats.items_skipped == 0
    assert stats.ids_added_count == 2
    assert stats.ratings_added_count == 1

    # Reload the row and check the additive merge.
    row = conn.execute("SELECT external_ids_json, ratings_json FROM media_item WHERE id = ?", (item_id,)).fetchone()
    eids = json.loads(row[0])
    assert eids["tvdb"]["series_id"] == "9001"
    assert eids["tmdb"]["series_id"] == "5005"
    assert eids["imdb"]["series_id"] == "tt0944947"
    ratings = json.loads(row[1])
    sources = {e["source"] for e in ratings["entries"]}
    assert "imdb" in sources

    # Second pass — idempotence. Reset mock call history so the assertion
    # below is unambiguous about the new pass.
    tvdb_client.get_tv.reset_mock()
    imdb.get_rating.reset_mock()
    rt.get_rating.reset_mock()

    stats2 = run_backfill_ids(
        conn,
        event_bus=bus,
        registry=registry,
    )

    assert stats2.items_updated == 0
    assert stats2.items_skipped == 1
    # No cross-ref refetch — the IDs gap is empty after pass 1.
    tvdb_client.get_tv.assert_not_called()
    # No rating refetch — the IMDb source is already present.
    imdb.get_rating.assert_not_called()


def test_e2e_backfill_canonical_in_cross_refs_is_safely_ignored(
    conn: sqlite3.Connection,
) -> None:
    """Canonical family in cross-ref payload is skipped by the safe-merge.

    Pins DESIGN §3 cross-contamination guard via the
    ``merge_ids_without_overwrite`` canonical-family skip clause —
    proves that a TVDB-canonical row remains untouched even when the
    TVDB client echoes back a TVDB id in the cross-ref payload.
    """
    item_id = _seed_partial_item(conn, title="Breaking Bad")

    tvdb_client = _named("tvdb")
    # Echo the canonical family back in the cross-ref payload to assert
    # the merge skips it (the seeded tvdb id "9001" must stay).
    tvdb_client.get_tv.return_value = MagicMock(external_ids={"tvdb": "OVERWRITE", "tmdb": "5005"})
    bus = EventBus()
    registry = _registry_mock(details=[tvdb_client])

    stats = run_backfill_ids(conn, event_bus=bus, registry=registry, ratings_only=False, ids_only=True)

    assert stats.ids_added_count == 1  # only tmdb added, tvdb echo skipped

    row = conn.execute("SELECT external_ids_json FROM media_item WHERE id = ?", (item_id,)).fetchone()
    eids = json.loads(row[0])
    assert eids["tvdb"]["series_id"] == "9001"  # canonical preserved
    assert eids["tmdb"]["series_id"] == "5005"  # cross-ref added


def test_e2e_backfill_no_canonical_client_logs_warning(
    conn: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When no canonical client is wired, the IDs path logs a clear warning per row.

    Pins the silent-failure-hunter finding from the post-review : an
    operator running ``backfill-ids`` without configuring the TMDB /
    TVDB clients must see why nothing happened.
    """
    _seed_partial_item(conn, title="Breaking Bad")
    bus = EventBus()

    import logging  # noqa: PLC0415

    # Pass registry=None to exercise the "no registry passed" branch — the
    # Phase 11 migration consolidated the four typed-client branches into
    # a single registry guard.
    with caplog.at_level(logging.WARNING, logger="indexer.backfill_ids"):
        run_backfill_ids(conn, event_bus=bus, registry=None, ids_only=True)

    messages = " ".join(record.message for record in caplog.records)
    assert "backfill_ids_path_disabled_no_registry" in messages
    assert "backfill_ids_path_no_registry" in messages


def test_e2e_backfill_canonical_id_missing_logs_warning(
    conn: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When canonical_provider is set but external_ids_json has no series_id, log it.

    This row is a drift candidate — the indexer noted a canonical
    provider but the JSON column never recorded the id. Without the
    log the silent skip would mask the drift.
    """
    now = int(time.time())
    # canonical_provider says tmdb but external_ids_json carries nothing under tmdb
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, original_title, year, category_id, "
        "external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
        "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang) "
        "VALUES (?, ?, ?, NULL, 2008, 'tv_shows', '{}', NULL, 'tmdb', NULL, NULL, ?, ?, NULL, 0, 'fr')",
        ("show", "Orphan", "Orphan", now, now),
    )
    tmdb_client = _named("tmdb")
    bus = EventBus()
    registry = _registry_mock(details=[tmdb_client])

    import logging  # noqa: PLC0415

    with caplog.at_level(logging.WARNING, logger="indexer.backfill_ids"):
        run_backfill_ids(conn, event_bus=bus, registry=registry, ids_only=True)

    messages = " ".join(record.message for record in caplog.records)
    assert "backfill_ids_canonical_id_missing" in messages
    # And we never called the canonical client because we had no anchor.
    tmdb_client.get_tv.assert_not_called()


def test_e2e_backfill_cross_ref_fetch_failure_is_fail_soft(
    conn: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A canonical-client exception is logged and the row stays untouched.

    Confirms the fail-soft contract on the new cross-ref path — one
    bad row never aborts the pass.
    """
    item_id = _seed_partial_item(conn, title="Breaking Bad")
    tvdb_client = _named("tvdb")
    tvdb_client.get_tv.side_effect = RuntimeError("simulated TVDB outage")
    bus = EventBus()
    registry = _registry_mock(details=[tvdb_client])

    import logging  # noqa: PLC0415

    with caplog.at_level(logging.WARNING, logger="indexer.backfill_ids"):
        stats = run_backfill_ids(conn, event_bus=bus, registry=registry, ids_only=True)

    assert stats.items_failed == 0  # fail-soft: counted as skip, not failure
    assert stats.items_updated == 0
    messages = " ".join(record.message for record in caplog.records)
    assert "backfill_cross_ref_fetch_failed" in messages

    row = conn.execute("SELECT external_ids_json FROM media_item WHERE id = ?", (item_id,)).fetchone()
    eids = json.loads(row[0])
    assert eids == {"tvdb": {"series_id": "9001"}}  # unchanged


# ---------------------------------------------------------------------------
# Capability composition cross-checks (phases 1, 11, 13, 14)
# ---------------------------------------------------------------------------


def test_e2e_metadata_facades_satisfy_capabilities() -> None:
    """IMDb façade composes IDValidator + RatingProvider + IDCrossRef."""
    backend = MagicMock()
    facade = IMDbClient(backend=backend)
    assert isinstance(facade, IDValidator)
    assert isinstance(facade, RatingProvider)
    assert isinstance(facade, IDCrossRef)


def test_e2e_rt_facade_satisfies_rating_only() -> None:
    """RottenTomatoes façade composes only RatingProvider."""
    facade = RottenTomatoesClient(backend=MagicMock())
    assert isinstance(facade, RatingProvider)
    assert not isinstance(facade, IDValidator)


def test_e2e_tracker_clients_compose_capabilities() -> None:
    """Both LaCale and C411 satisfy TorrentSearchable + CategoryListable."""
    transport = MagicMock()
    lacale = LaCaleClient(transport=transport)
    c411 = C411Client(transport=transport)
    for client in (lacale, c411):
        assert isinstance(client, TorrentSearchable)
        assert isinstance(client, CategoryListable)


def test_e2e_qbit_client_composes_all_torrent_capabilities() -> None:
    """``QBitClient`` satisfies all 5 atomic torrent capabilities."""
    client = QBitClient(host="http://localhost", port=8080, username="u", password="p")
    assert isinstance(client, TorrentLister)
    assert isinstance(client, TorrentInspector)
    assert isinstance(client, AuthenticatedClient)
    assert isinstance(client, TorrentStateInspector)
    assert isinstance(client, TorrentController)


def test_e2e_notify_clients_match_capabilities() -> None:
    """Notify clients satisfy only their declared capability.

    A bidirectional negation pins DESIGN §4 — no client should claim a
    capability it does not implement.
    """
    from personalscraper.api.notify.healthchecks import HealthcheckClient  # noqa: PLC0415
    from personalscraper.api.notify.telegram import TelegramNotifier  # noqa: PLC0415

    telegram = TelegramNotifier(transport=MagicMock(), chat_id="42")
    healthcheck = HealthcheckClient(transport=MagicMock())

    assert isinstance(telegram, Notifier)
    assert not isinstance(telegram, HealthChecker)
    assert isinstance(healthcheck, HealthChecker)
    assert not isinstance(healthcheck, Notifier)


# ---------------------------------------------------------------------------
# Rating dataclass round-trip (sanity for the IMDb/RT pair)
# ---------------------------------------------------------------------------


def test_e2e_imdb_rt_facade_pair_handles_omdb_response() -> None:
    """A single OMDb call surfaces as one IMDb row + one RT row through the façades.

    Pins the phase-3 façade pair contract : both façades read from the
    same OMDb payload but each filters down to its own source. The
    test uses ``Notations`` fakes to avoid touching the network.
    """
    backend = MagicMock()
    backend.get_notations.return_value = [
        Notations(provider="omdb", source="imdb", score=9.0, votes_count=10),
        Notations(provider="omdb", source="rotten_tomatoes", score=94.0, votes_count=0),
    ]

    imdb = IMDbClient(backend=backend)
    rt = RottenTomatoesClient(backend=backend)

    imdb_rating = imdb.get_rating("tt0468569")
    rt_rating = rt.get_rating("tt0468569")

    assert imdb_rating is not None and imdb_rating[0].source == "imdb"
    assert rt_rating is not None and rt_rating[0].source == "rotten_tomatoes"
