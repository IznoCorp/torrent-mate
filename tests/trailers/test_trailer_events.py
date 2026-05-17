"""Tests for the trailers event emits — Sub-phase 4.4.

Covers :class:`TrailerDownloaded` emission from
:mod:`personalscraper.trailers.orchestrator` after each successful
``YtdlpDownloader.download`` call. Failures (BOT_DETECTED, HTTP_ERROR,
YTDLP_ERROR) MUST NOT emit. The factory + envelope round-trip plumbing
required for the Phase 4 gate is also exercised here.

The ContextVar capture path (pipeline / standalone-command correlation
ID propagation into the emitted event) is exercised directly via
:data:`current_correlation_id` — the orchestrator runs synchronously
inside the bound region the caller sets up at its own boundary, so a
ContextVar bound around ``orchestrator.run()`` reaches the emit site
without further wiring.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.event_bus import (
    EventBus,
    current_correlation_id,
    event_from_envelope,
    event_to_envelope,
)
from personalscraper.trailers.events import TrailerDownloaded
from personalscraper.trailers.orchestrator import TrailersOrchestrator
from personalscraper.trailers.scanner import ScanItem
from tests.fixtures.event_bus import CollectingSubscriber, assert_event_round_trip
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES


def _make_config(tmp_path: Path) -> MagicMock:
    """Mirror the unit-test config builder from tests/trailers/test_orchestrator.py."""
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.languages = ["fr-FR", "en-US"]
    cfg.trailers.fallback_youtube_search = True
    cfg.trailers.search_query_format = "{title} {year} bande annonce"
    cfg.trailers.filters.min_file_size_bytes = 102400
    cfg.trailers.filters.max_filesize_mb = 500
    cfg.trailers.state_file = str(tmp_path / ".data/trailers_state.json")
    cfg.trailers.retry_after_days = [1, 7, 30]
    cfg.trailers.ytdlp.format = "best[ext=mp4]/best"
    cfg.trailers.ytdlp.socket_timeout_sec = 30
    cfg.trailers.ytdlp.retries = 3
    cfg.trailers.seasons.enabled = False
    cfg.trailers.library_check.movies = False
    cfg.trailers.library_check.tv_shows = True
    cfg.trailers.step.max_duration_sec = 1800
    return cfg


_SCAN_ITEM = ScanItem(
    path=Path("/fake/Fight Club (1999)"),
    media_type="movie",
    title="Fight Club",
    year=1999,
    tmdb_id="550",
)


def test_trailers_emit_trailer_downloaded_on_success(tmp_path: Path) -> None:
    """A SUCCESS download emits exactly one ``TrailerDownloaded`` with the locked URL."""
    from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

    bus = EventBus()
    collector: CollectingSubscriber[TrailerDownloaded] = CollectingSubscriber(bus, TrailerDownloaded)
    config = _make_config(tmp_path)
    orchestrator = TrailersOrchestrator(config=config, staging_dir=tmp_path, event_bus=bus)
    out_path = tmp_path / "Fight Club (1999)-trailer.mp4"

    with (
        patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
        patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
        patch.object(
            orchestrator._downloader,
            "download",
            return_value=DownloadResult(status=DownloadStatus.SUCCESS, output_path=out_path),
        ),
    ):
        counts = orchestrator.run()

    assert counts["downloaded"] == 1
    assert len(collector.received) == 1
    event = collector.received[0]
    assert event.media_path == _SCAN_ITEM.path
    assert event.trailer_path == out_path
    assert event.source_url == "https://youtube.com/watch?v=X"


@pytest.mark.parametrize("failure_status", ["BOT_DETECTED", "HTTP_ERROR", "YTDLP_ERROR"])
def test_trailers_do_not_emit_on_failure(tmp_path: Path, failure_status: str) -> None:
    """Failed downloads never emit ``TrailerDownloaded`` — the catalog records completions only."""
    from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

    bus = EventBus()
    collector: CollectingSubscriber[TrailerDownloaded] = CollectingSubscriber(bus, TrailerDownloaded)
    config = _make_config(tmp_path)
    orchestrator = TrailersOrchestrator(config=config, staging_dir=tmp_path, event_bus=bus)
    status = getattr(DownloadStatus, failure_status)

    with (
        patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
        patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
        patch.object(
            orchestrator._downloader,
            "download",
            return_value=DownloadResult(status=status, error_message="failure"),
        ),
    ):
        orchestrator.run()

    assert collector.received == []


def test_trailer_downloaded_has_factory() -> None:
    """``TrailerDownloaded`` is registered in ``EVENT_SAMPLE_FACTORIES``."""
    assert TrailerDownloaded in EVENT_SAMPLE_FACTORIES


def test_trailer_downloaded_envelope_roundtrip() -> None:
    """``TrailerDownloaded`` survives envelope round-trip with Path coercion."""
    original = EVENT_SAMPLE_FACTORIES[TrailerDownloaded]()
    envelope = event_to_envelope(original)
    assert envelope["_type"] == "TrailerDownloaded"
    reconstructed = event_from_envelope(envelope)
    assert type(reconstructed) is TrailerDownloaded
    assert_event_round_trip(original, reconstructed)
    assert isinstance(reconstructed.media_path, Path)  # type: ignore[attr-defined]
    assert isinstance(reconstructed.trailer_path, Path)  # type: ignore[attr-defined]


def test_trailers_emit_works_from_pipeline_step_path(tmp_path: Path) -> None:
    """ContextVar bound by the pipeline step propagates into the emitted event.

    Simulates the pipeline-step bootstrap (Phase 3.2) that binds
    ``current_correlation_id`` for the duration of a pipeline run; the
    synchronous orchestrator dispatch runs inside that bound region.
    """
    from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

    bus = EventBus()
    collector: CollectingSubscriber[TrailerDownloaded] = CollectingSubscriber(bus, TrailerDownloaded)
    config = _make_config(tmp_path)
    orchestrator = TrailersOrchestrator(config=config, staging_dir=tmp_path, event_bus=bus)

    token = current_correlation_id.set("run-pipeline-abc")
    try:
        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=X"),
            patch.object(
                orchestrator._downloader,
                "download",
                return_value=DownloadResult(
                    status=DownloadStatus.SUCCESS,
                    output_path=tmp_path / "out.mp4",
                ),
            ),
        ):
            orchestrator.run()
    finally:
        current_correlation_id.reset(token)

    assert len(collector.received) == 1
    assert collector.received[0].correlation_id == "run-pipeline-abc"


def test_trailers_emit_works_from_standalone_command_path(tmp_path: Path) -> None:
    """ContextVar bound by the standalone Typer command propagates into the emit.

    Simulates the ``personalscraper trailers download`` CLI bootstrap
    (Phase 2.5) that binds ``current_correlation_id`` to a per-invocation
    run id distinct from any pipeline run.
    """
    from personalscraper.scraper.ytdlp_downloader import DownloadResult, DownloadStatus

    bus = EventBus()
    collector: CollectingSubscriber[TrailerDownloaded] = CollectingSubscriber(bus, TrailerDownloaded)
    config = _make_config(tmp_path)
    orchestrator = TrailersOrchestrator(config=config, staging_dir=tmp_path, event_bus=bus)

    token = current_correlation_id.set("trailers-cli-run-xyz")
    try:
        with (
            patch.object(orchestrator._scanner, "scan_staging", return_value=[_SCAN_ITEM]),
            patch.object(orchestrator._finder, "find", return_value="https://youtube.com/watch?v=Z"),
            patch.object(
                orchestrator._downloader,
                "download",
                return_value=DownloadResult(
                    status=DownloadStatus.SUCCESS,
                    output_path=tmp_path / "out.mp4",
                ),
            ),
        ):
            orchestrator.run()
    finally:
        current_correlation_id.reset(token)

    assert len(collector.received) == 1
    assert collector.received[0].correlation_id == "trailers-cli-run-xyz"
