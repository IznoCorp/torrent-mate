"""Sub-phase 3.4 — every step emits ``ItemProgressed`` on the bus.

The 9 pipeline steps (``ingest``, ``sort``, ``clean``, ``scrape``, ``cleanup``,
``enforce``, ``verify``, ``trailers``, ``dispatch``) each accept an ``event_bus``
keyword argument and emit an ``ItemProgressed`` per item they process (the
legacy per-item observer channel was deleted in Sub-phase 3.7b).

These tests verify the plumbing per step by driving the step with a
``CollectingSubscriber[ItemProgressed]`` attached to a real ``EventBus`` and
asserting that:

- at least one ``ItemProgressed`` is collected per item the step processes,
- every emitted ``ItemProgressed`` has the expected ``step`` name,
- envelope round-trip succeeds (``event_to_envelope`` does not raise
  ``TypeError`` — covers the JSON-safety contract for all payload shapes).

Per-step assertions cover the detail-keyset additions required by the plan:

- ``scrape``: matched/skipped_low_confidence events carry ``provider`` and
  ``confidence`` keys in ``details``.
- ``verify``: ``ok`` events carry ``category`` in ``details``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.event_bus import EventBus, event_to_envelope
from personalscraper.pipeline_events import ItemProgressed
from tests.fixtures.event_bus import CollectingSubscriber


@pytest.fixture
def bus() -> EventBus:
    """Fresh in-process bus per test."""
    return EventBus()


@pytest.fixture
def sub(bus: EventBus) -> CollectingSubscriber[ItemProgressed]:
    """Collect every ItemProgressed emitted during the test."""
    return CollectingSubscriber(bus, ItemProgressed)


def _assert_json_safe(events: list[ItemProgressed]) -> None:
    """Every emitted event must serialise via the envelope path."""
    for e in events:
        envelope = event_to_envelope(e)
        # json.dumps catches any non-JSON-safe leaf the envelope helper left through.
        json.dumps(envelope)


# --- sort -----------------------------------------------------------------


def test_run_sort_emits_item_progressed_per_item(
    tmp_path: Path, bus: EventBus, sub: CollectingSubscriber[ItemProgressed], monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_sort emits ItemProgressed for each item processed by the sorter."""
    from personalscraper.models import SortResult
    from personalscraper.sorter.run import run_sort

    ingest = tmp_path / "097-TEMP"
    ingest.mkdir(parents=True)
    (ingest / "a.mkv").write_text("x")
    (ingest / "b.mkv").write_text("y")

    fake_results = [
        SortResult(
            source=ingest / "a.mkv",
            destination=tmp_path / "M/a",
            media_type="movie",
            title="a",
            year=None,
            season=None,
            episode=None,
            status="moved",
            message=None,
        ),
        SortResult(
            source=ingest / "b.mkv",
            destination=tmp_path / "M/b",
            media_type="movie",
            title="b",
            year=None,
            season=None,
            episode=None,
            status="skipped",
            message="dup",
        ),
    ]

    monkeypatch.setattr(
        "personalscraper.sorter.run.Sorter",
        lambda *a, **kw: MagicMock(process=lambda *_a, **_kw: fake_results),
    )

    config = MagicMock()
    config.paths.staging_dir = tmp_path
    config.paths.data_dir = tmp_path / ".data"
    config.paths.data_dir.mkdir(exist_ok=True)
    monkeypatch.setattr("personalscraper.sorter.run.find_ingest_dir", lambda _: MagicMock())
    monkeypatch.setattr("personalscraper.sorter.run.staging_path", lambda *_a, **_k: ingest)

    run_sort(MagicMock(), staging_dir=tmp_path, config=config, dry_run=True, event_bus=bus)

    assert sub.received, "sort emitted no ItemProgressed"
    assert all(e.step == "sort" for e in sub.received)
    _assert_json_safe(sub.received)


# --- clean / cleanup ------------------------------------------------------


def test_run_clean_emits_item_progressed_per_category(
    tmp_path: Path, bus: EventBus, sub: CollectingSubscriber[ItemProgressed], monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_clean emits ItemProgressed start+terminal for each category dir."""
    from personalscraper.process.run import run_clean

    staging = tmp_path
    movies = staging / "M"
    tv = staging / "T"
    movies.mkdir()
    tv.mkdir()

    config = MagicMock()
    config.paths.staging_dir = staging
    config.fuzzy_match = MagicMock()

    monkeypatch.setattr("personalscraper.process.run.find_by_file_type", lambda _c, _t: MagicMock())
    # Two categories iterated; static folder name is enough — both end up under staging.
    monkeypatch.setattr("personalscraper.process.run.folder_name", lambda _e: "X")
    config.paths.staging_dir = staging
    monkeypatch.setattr("personalscraper.process.dedup.dedup_folders", lambda *_a, **_k: (0, 0))
    monkeypatch.setattr("personalscraper.process.reclean._has_polluted_folders", lambda _p: False)
    monkeypatch.setattr(
        "personalscraper.process.reclean.reclean_folders",
        lambda *_a, **_k: MagicMock(success_count=0, skip_count=0, error_count=0, details=[], warnings=[], renames={}),
    )

    run_clean(MagicMock(), config, dry_run=True, event_bus=bus)

    assert sub.received, "clean emitted no ItemProgressed"
    assert all(e.step == "clean" for e in sub.received)
    _assert_json_safe(sub.received)


def test_run_cleanup_emits_item_progressed_per_category(
    tmp_path: Path, bus: EventBus, sub: CollectingSubscriber[ItemProgressed], monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_cleanup emits ItemProgressed start+terminal for each category dir."""
    from personalscraper.process.run import run_cleanup

    staging = tmp_path
    config = MagicMock()
    config.paths.staging_dir = staging

    monkeypatch.setattr("personalscraper.process.run.find_by_file_type", lambda _c, _t: MagicMock())
    monkeypatch.setattr("personalscraper.process.run.folder_name", lambda _e: "X")
    monkeypatch.setattr(
        "personalscraper.process.cleanup.cleanup_empty_dirs",
        lambda *_a, **_k: MagicMock(success_count=0, details=[]),
    )

    run_cleanup(MagicMock(), config, dry_run=True, event_bus=bus)

    assert sub.received, "cleanup emitted no ItemProgressed"
    assert all(e.step == "cleanup" for e in sub.received)
    _assert_json_safe(sub.received)


# --- enforce --------------------------------------------------------------


def test_run_enforce_emits_item_progressed_per_item(
    tmp_path: Path, bus: EventBus, sub: CollectingSubscriber[ItemProgressed], monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_enforce emits ItemProgressed for sanitize / structure / coherence loops."""
    from personalscraper.enforce.run import run_enforce

    sanitize_result = MagicMock(old_name="film", new_name="film_clean", action="renamed")
    monkeypatch.setattr("personalscraper.enforce.run.sanitize_files", lambda *_a, **_k: [sanitize_result])

    structure_result = MagicMock(action="repaired", fixes=["nfo_added"], warnings=[])
    structure_result.path = tmp_path / "film"
    monkeypatch.setattr("personalscraper.enforce.run.validate_structure", lambda *_a, **_k: [structure_result])

    coherence_result = MagicMock(warnings=[])
    coherence_result.path = tmp_path / "film"
    monkeypatch.setattr("personalscraper.enforce.run.check_coherence", lambda *_a, **_k: [coherence_result])

    run_enforce(MagicMock(), MagicMock(), dry_run=True, event_bus=bus)

    assert sub.received, "enforce emitted no ItemProgressed"
    assert all(e.step == "enforce" for e in sub.received)
    _assert_json_safe(sub.received)


# --- verify ---------------------------------------------------------------


def test_run_verify_emits_item_progressed_with_category(
    tmp_path: Path, bus: EventBus, sub: CollectingSubscriber[ItemProgressed], monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_verify emits ItemProgressed and ``ok`` payload carries ``category``."""
    from personalscraper.verify.run import run_verify
    from personalscraper.verify.verifier import VerifyResult

    fake_results = [
        VerifyResult(
            media_path=tmp_path / "film",
            media_type="movie",
            status="valid",
            category="movies",
            fixes_applied=[],
            errors=[],
            warnings=[],
        )
    ]
    verifier_instance = MagicMock(
        verify_all_movies=lambda *_a, **_k: fake_results,
        verify_all_tvshows=lambda *_a, **_k: [],
    )
    fake_verifier = MagicMock(side_effect=lambda **_kw: verifier_instance)
    fake_verifier.get_dispatchable = staticmethod(lambda results: results)
    monkeypatch.setattr("personalscraper.verify.run.Verifier", fake_verifier)
    monkeypatch.setattr("personalscraper.verify.run._has_items_to_verify", lambda *_a, **_k: True)
    monkeypatch.setattr("personalscraper.verify.run.find_by_file_type", lambda _c, _t: MagicMock())
    monkeypatch.setattr("personalscraper.verify.run.folder_name", lambda _e: "M")

    config = MagicMock()
    config.paths.staging_dir = tmp_path
    # Ensure the M dir exists so verify enters its body.
    (tmp_path / "M").mkdir(parents=True, exist_ok=True)

    run_verify(MagicMock(), config, dry_run=True, event_bus=bus)

    assert sub.received, "verify emitted no ItemProgressed"
    assert all(e.step == "verify" for e in sub.received)
    ok_events = [e for e in sub.received if e.status == "ok"]
    assert ok_events, "verify did not emit any 'ok' event"
    assert "category" in ok_events[0].details
    assert ok_events[0].details["category"] == "movies"
    _assert_json_safe(sub.received)


# --- scrape ---------------------------------------------------------------


def test_run_scrape_emits_item_progressed_with_provider_and_confidence(
    tmp_path: Path, bus: EventBus, sub: CollectingSubscriber[ItemProgressed], monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_scrape matched events carry ``provider`` and ``confidence`` in details."""
    from personalscraper.scraper._shared import ScrapeResult
    from personalscraper.scraper.run import run_scrape

    match = MagicMock(api_id=1, api_title="X", api_year=2024, confidence=0.95, source="tmdb")
    fake_results = [
        ScrapeResult(
            media_path=tmp_path / "film",
            media_type="movie",
            match=match,
            action="scraped",
        )
    ]
    monkeypatch.setattr(
        "personalscraper.scraper.run.Scraper",
        lambda **_kw: MagicMock(
            process_movies=lambda *_a, **_k: fake_results,
            process_tvshows=lambda *_a, **_k: [],
        ),
    )
    monkeypatch.setattr("personalscraper.scraper.run._has_unscraped_items", lambda *_a, **_k: True)
    monkeypatch.setattr("personalscraper.scraper.run._needs_repair", lambda *_a, **_k: False)
    monkeypatch.setattr("personalscraper.scraper.run.find_by_file_type", lambda _c, _t: MagicMock())
    monkeypatch.setattr("personalscraper.scraper.run.folder_name", lambda _e: "M")

    config = MagicMock()
    config.paths.staging_dir = tmp_path
    (tmp_path / "M").mkdir(parents=True, exist_ok=True)

    run_scrape(MagicMock(), config, dry_run=True, event_bus=bus)

    assert sub.received, "scrape emitted no ItemProgressed"
    assert all(e.step == "scrape" for e in sub.received)
    matched = [e for e in sub.received if e.status == "matched"]
    assert matched, "scrape did not emit any 'matched' event"
    assert matched[0].details["provider"] == "tmdb"
    assert matched[0].details["confidence"] == 0.95
    _assert_json_safe(sub.received)


# --- trailers -------------------------------------------------------------


def test_run_trailers_emits_item_progressed_on_skip(
    bus: EventBus, sub: CollectingSubscriber[ItemProgressed], tmp_path: Path
) -> None:
    """run_trailers emits one ItemProgressed when the step is skipped by flag."""
    from personalscraper.trailers.step import run_trailers

    config = MagicMock()
    config.trailers.enabled = True

    run_trailers(
        config=config,
        staging_dir=tmp_path,
        verified=[],
        skip_trailers=True,
        event_bus=bus,
        registry=MagicMock(spec=ProviderRegistry),
    )

    assert len(sub.received) == 1
    assert sub.received[0].step == "trailers"
    assert sub.received[0].status == "skipped"
    _assert_json_safe(sub.received)


# --- ingest ---------------------------------------------------------------


def test_run_ingest_emits_item_progressed_per_torrent(
    tmp_path: Path, bus: EventBus, sub: CollectingSubscriber[ItemProgressed], monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_ingest emits ItemProgressed start + terminal per torrent listed."""
    from personalscraper.ingest.ingest import run_ingest

    torrent = MagicMock(name="T", hash="abc", ratio=2.0)
    torrent.name = "Acme.Movie.2024"
    client = MagicMock(
        get_completed=lambda: [torrent],
        get_all_hashes=lambda: {"abc"},
    )
    monkeypatch.setattr("personalscraper.ingest.ingest.build_active_torrent_client", lambda *_a, **_k: client)
    monkeypatch.setattr("personalscraper.ingest.ingest.QBitClient", lambda **_kw: client)

    tracker = MagicMock(is_ingested=lambda _h: True, get_entry=lambda _h: None)
    monkeypatch.setattr("personalscraper.ingest.ingest.IngestTracker", lambda *_a, **_k: tracker)

    config = MagicMock()
    config.torrent.active = "qbittorrent"
    config.paths.staging_dir = tmp_path
    config.paths.data_dir = tmp_path / ".data"
    config.paths.data_dir.mkdir(exist_ok=True)

    run_ingest(
        MagicMock(),
        dry_run=True,
        ingest_dir=tmp_path / "097-TEMP",
        staging_dir=tmp_path,
        config=config,
        event_bus=bus,
    )

    assert sub.received, "ingest emitted no ItemProgressed"
    assert all(e.step == "ingest" for e in sub.received)
    _assert_json_safe(sub.received)


# --- dispatch -------------------------------------------------------------


def test_run_dispatch_emits_item_progressed_per_item(
    tmp_path: Path, bus: EventBus, sub: CollectingSubscriber[ItemProgressed], monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_dispatch emits ItemProgressed start + terminal per dispatched item."""
    from personalscraper.dispatch._types import DispatchResult
    from personalscraper.dispatch.run import run_dispatch

    fake_result = DispatchResult(
        source=tmp_path / "film",
        destination=tmp_path / "disk_a" / "M" / "film",
        action="moved",
        disk="disk_a",
        reason=None,
    )

    class _FakeIndex:
        count = 1

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def begin_preview(self):
            pass

        def rollback_preview(self):
            pass

        def commit_preview(self):
            pass

        def rebuild(self, *_a, **_k):
            return 0

    monkeypatch.setattr("personalscraper.dispatch.run.MediaIndex", lambda *_a, **_k: _FakeIndex())
    monkeypatch.setattr(
        "personalscraper.dispatch.run.Dispatcher",
        lambda **_kw: MagicMock(process=lambda **_k: [fake_result]),
    )
    monkeypatch.setattr("personalscraper.dispatch.run._cleanup_staging_orphans", lambda *_a, **_k: 0)

    config = MagicMock()
    config.paths.staging_dir = tmp_path
    config.indexer.db_path = tmp_path / ".idx.db"
    config.categories = []

    run_dispatch(MagicMock(), config, dry_run=True, verified=[], event_bus=bus)

    assert sub.received, "dispatch emitted no ItemProgressed"
    assert all(e.step == "dispatch" for e in sub.received)
    _assert_json_safe(sub.received)
