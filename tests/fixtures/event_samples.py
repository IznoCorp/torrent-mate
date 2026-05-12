"""Sample-event factory registry for the bus's v1 catalog.

Each concrete :class:`Event` subclass registers a real-data factory here;
``test_every_event_has_factory`` enforces 100% coverage so round-trip and
rendering tests can iterate every event class without ``MagicMock``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from personalscraper.core.circuit import (
    CircuitBreakerClosed,
    CircuitBreakerHalfOpened,
    CircuitBreakerOpened,
)
from personalscraper.core.event_bus import Event
from personalscraper.dispatch.events import ItemDispatched
from personalscraper.indexer.events import DiskFullWarning, LibraryScanCompleted
from personalscraper.models import FailedItem, PipelineReport, StepReport
from personalscraper.pipeline_events import (
    ItemProgressed,
    PipelineEnded,
    PipelineStarted,
    StepCompleted,
    StepErrored,
    StepStarted,
)
from personalscraper.trailers.events import TrailerDownloaded

#: Public registry — keyed by event class, value is a zero-arg factory.
EVENT_SAMPLE_FACTORIES: dict[type[Event], Callable[[], Event]] = {}


def register_factory(event_type: type[Event]) -> Callable[[Callable[[], Event]], Callable[[], Event]]:
    """Decorator that records a factory for ``event_type`` in the registry.

    Raises ``ValueError`` on duplicate registration so a second import does
    not silently shadow the first.
    """

    def _decorator(factory: Callable[[], Event]) -> Callable[[], Event]:
        if event_type in EVENT_SAMPLE_FACTORIES:
            raise ValueError(f"Factory for {event_type.__name__} already registered")
        EVENT_SAMPLE_FACTORIES[event_type] = factory
        return factory

    return _decorator


# Deterministic timestamps so envelope round-trip assertions stay reproducible.
_T0 = datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 5, 12, 10, 5, 0, tzinfo=timezone.utc)


def _make_real_step_report() -> StepReport:
    """Realistic ``StepReport`` exercising every field type used by the bus encoder."""
    return StepReport(
        name="trailers",
        success_count=4,
        skip_count=1,
        error_count=2,
        warnings=["torrent_client_slow", "tmdb_rate_limited"],
        details=["downloaded: Inception (2010)", "skipped: already_present"],
        status="partial",
        counts={"downloaded": 4, "bot_detected": 1, "no_trailer": 1},
        failed_items=[
            FailedItem(item_id="movie:tmdb:1", reason="bot_detected", detail="sign in"),
            FailedItem(item_id="movie:tmdb:42", reason="timeout"),
        ],
        renames={"Some.Folder.2020": "Some Folder (2020)"},
        unmatched_paths=["Mystery.Title.2019"],
        details_payload={"copied": ["a", "b"], "failed": [], "skipped_already_present": []},
    )


def _make_real_pipeline_report() -> PipelineReport:
    """Realistic ``PipelineReport`` carrying one populated step."""
    report = PipelineReport(started_at=_T0, finished_at=_T1)
    report.add_step("trailers", _make_real_step_report())
    return report


@register_factory(PipelineStarted)
def make_pipeline_started() -> PipelineStarted:
    """Realistic :class:`PipelineStarted` factory."""
    return PipelineStarted(report=_make_real_pipeline_report())


@register_factory(PipelineEnded)
def make_pipeline_ended() -> PipelineEnded:
    """Realistic :class:`PipelineEnded` factory."""
    return PipelineEnded(report=_make_real_pipeline_report())


@register_factory(StepStarted)
def make_step_started() -> StepStarted:
    """Realistic :class:`StepStarted` factory."""
    return StepStarted(step="scrape")


@register_factory(StepCompleted)
def make_step_completed() -> StepCompleted:
    """Realistic :class:`StepCompleted` factory."""
    return StepCompleted(step="trailers", report=_make_real_step_report(), elapsed_s=12.5)


@register_factory(StepErrored)
def make_step_errored() -> StepErrored:
    """Realistic :class:`StepErrored` factory."""
    return StepErrored(
        step="dispatch",
        error_class="OSError",
        error_message="[Errno 28] No space left on device: '/Volumes/disk-A'",
    )


@register_factory(ItemProgressed)
def make_item_progressed() -> ItemProgressed:
    """Realistic :class:`ItemProgressed` factory."""
    return ItemProgressed(
        step="scrape",
        item="Inception.2010.1080p.BluRay.x264.mkv",
        status="scraped",
        details={"provider": "tmdb", "confidence": 0.94, "tmdb_id": 27205},
    )


@register_factory(CircuitBreakerOpened)
def make_circuit_breaker_opened() -> CircuitBreakerOpened:
    """Realistic :class:`CircuitBreakerOpened` factory."""
    return CircuitBreakerOpened(
        breaker="tmdb",
        failure_count=5,
        last_error_class="ConnectionError",
        last_error_message="HTTPSConnectionPool(host='api.themoviedb.org'): Max retries exceeded",
    )


@register_factory(CircuitBreakerClosed)
def make_circuit_breaker_closed() -> CircuitBreakerClosed:
    """Realistic :class:`CircuitBreakerClosed` factory."""
    return CircuitBreakerClosed(breaker="tmdb")


@register_factory(CircuitBreakerHalfOpened)
def make_circuit_breaker_half_opened() -> CircuitBreakerHalfOpened:
    """Realistic :class:`CircuitBreakerHalfOpened` factory."""
    return CircuitBreakerHalfOpened(breaker="tmdb")


@register_factory(DiskFullWarning)
def make_disk_full_warning() -> DiskFullWarning:
    """Realistic :class:`DiskFullWarning` factory (GB-scale numbers exercise the byte→GB renderer)."""
    return DiskFullWarning(
        disk_path=Path("/Volumes/Disk1"),
        free_bytes=1_000_000_000,
        threshold_bytes=10_000_000_000,
    )


@register_factory(ItemDispatched)
def make_item_dispatched() -> ItemDispatched:
    """Realistic :class:`ItemDispatched` factory."""
    return ItemDispatched(
        item="Inception (2010)",
        target_disk=Path("/Volumes/Disk1"),
        category_id="movies",
        action="moved",
    )


@register_factory(TrailerDownloaded)
def make_trailer_downloaded() -> TrailerDownloaded:
    """Realistic :class:`TrailerDownloaded` factory."""
    return TrailerDownloaded(
        media_path=Path("/Volumes/Disk1/movies/Inception (2010)"),
        trailer_path=Path("/Volumes/Disk1/movies/Inception (2010)/Inception-trailer.mp4"),
        source_url="https://www.youtube.com/watch?v=YoHD9XEInc0",
    )


@register_factory(LibraryScanCompleted)
def make_library_scan_completed() -> LibraryScanCompleted:
    """Realistic :class:`LibraryScanCompleted` factory."""
    return LibraryScanCompleted(mode="quick", scanned=12_345, errors=2, elapsed_s=187.42)


__all__ = ["EVENT_SAMPLE_FACTORIES", "register_factory"]
