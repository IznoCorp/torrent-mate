"""Sample-event factory registry — Sub-phase 1.8 mechanism.

Production events from Phase 3 onwards register a factory here so the
``test_every_event_has_factory`` gate (Sub-phase 1.8 + activated from Phase 3)
can verify that every concrete event in the bus's class registry has a
known-good real-data instance available for round-trip and rendering tests.

Phase 3.1 adds the six pipeline events
(:class:`~personalscraper.pipeline_events.PipelineStarted`,
:class:`~personalscraper.pipeline_events.PipelineEnded`,
:class:`~personalscraper.pipeline_events.StepStarted`,
:class:`~personalscraper.pipeline_events.StepCompleted`,
:class:`~personalscraper.pipeline_events.StepErrored`,
:class:`~personalscraper.pipeline_events.ItemProgressed`). Each factory
constructs realistic Report instances — never ``MagicMock`` — so the
envelope round-trip exercises real serialization paths.
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
from personalscraper.indexer.events import DiskFullWarning
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

# Public registry — keyed by event class. Each entry is a zero-argument
# factory returning a fully-populated event instance with realistic
# (NEVER MagicMock) field values, suitable for envelope round-trip tests.
EVENT_SAMPLE_FACTORIES: dict[type[Event], Callable[[], Event]] = {}


def register_factory(
    event_type: type[Event],
) -> Callable[[Callable[[], Event]], Callable[[], Event]]:
    """Decorator that registers a factory for ``event_type``.

    Use as::

        @register_factory(MyEvent)
        def make_my_event() -> MyEvent:
            return MyEvent(field1="real", field2=Path("/var/data/x.mp4"))

    Args:
        event_type: The concrete ``Event`` subclass the factory produces.

    Returns:
        A no-op decorator that records the factory in
        ``EVENT_SAMPLE_FACTORIES``.

    Raises:
        ValueError: if a factory is already registered for ``event_type`` —
            two factories for one type would let later imports silently
            shadow earlier ones, masking test bugs.
    """

    def _decorator(factory: Callable[[], Event]) -> Callable[[], Event]:
        if event_type in EVENT_SAMPLE_FACTORIES:
            raise ValueError(
                f"Factory for {event_type.__name__} already registered "
                f"(previous: {EVENT_SAMPLE_FACTORIES[event_type]!r})",
            )
        EVENT_SAMPLE_FACTORIES[event_type] = factory
        return factory

    return _decorator


# Deterministic timestamps for reproducible round-trip equality.
_T0 = datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 5, 12, 10, 5, 0, tzinfo=timezone.utc)


def _make_real_step_report() -> StepReport:
    """Build a realistic ``StepReport`` with non-empty representative fields.

    Populates every field type at least once: counters, warnings, details,
    counts, ``failed_items`` (the tuple-coercion path), and a JSON-safe
    ``details_payload`` dict. Exercises the bus encoder/decoder on the
    full Report shape, not just defaults.
    """
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
    """Build a realistic ``PipelineReport`` with one populated step."""
    report = PipelineReport(started_at=_T0, finished_at=_T1)
    report.add_step("trailers", _make_real_step_report())
    return report


@register_factory(PipelineStarted)
def make_pipeline_started() -> PipelineStarted:
    """Realistic :class:`PipelineStarted` for round-trip tests."""
    return PipelineStarted(report=_make_real_pipeline_report())


@register_factory(PipelineEnded)
def make_pipeline_ended() -> PipelineEnded:
    """Realistic :class:`PipelineEnded` for round-trip tests."""
    return PipelineEnded(report=_make_real_pipeline_report())


@register_factory(StepStarted)
def make_step_started() -> StepStarted:
    """Realistic :class:`StepStarted` for round-trip tests."""
    return StepStarted(step="scrape")


@register_factory(StepCompleted)
def make_step_completed() -> StepCompleted:
    """Realistic :class:`StepCompleted` carrying a populated ``StepReport``."""
    return StepCompleted(
        step="trailers",
        report=_make_real_step_report(),
        elapsed_s=12.5,
    )


@register_factory(StepErrored)
def make_step_errored() -> StepErrored:
    """Realistic :class:`StepErrored` with a stringified error."""
    return StepErrored(
        step="dispatch",
        error_class="OSError",
        error_message="[Errno 28] No space left on device: '/Volumes/disk-A'",
    )


@register_factory(ItemProgressed)
def make_item_progressed() -> ItemProgressed:
    """Realistic :class:`ItemProgressed` with JSON-safe details."""
    return ItemProgressed(
        step="scrape",
        item="Inception.2010.1080p.BluRay.x264.mkv",
        status="scraped",
        details={"provider": "tmdb", "confidence": 0.94, "tmdb_id": 27205},
    )


@register_factory(CircuitBreakerOpened)
def make_circuit_breaker_opened() -> CircuitBreakerOpened:
    """Realistic :class:`CircuitBreakerOpened` for round-trip tests."""
    return CircuitBreakerOpened(
        breaker="tmdb",
        failure_count=5,
        last_error_class="ConnectionError",
        last_error_message="HTTPSConnectionPool(host='api.themoviedb.org'): Max retries exceeded",
    )


@register_factory(CircuitBreakerClosed)
def make_circuit_breaker_closed() -> CircuitBreakerClosed:
    """Realistic :class:`CircuitBreakerClosed` for round-trip tests."""
    return CircuitBreakerClosed(breaker="tmdb")


@register_factory(CircuitBreakerHalfOpened)
def make_circuit_breaker_half_opened() -> CircuitBreakerHalfOpened:
    """Realistic :class:`CircuitBreakerHalfOpened` for round-trip tests."""
    return CircuitBreakerHalfOpened(breaker="tmdb")


@register_factory(DiskFullWarning)
def make_disk_full_warning() -> DiskFullWarning:
    """Realistic :class:`DiskFullWarning` for round-trip tests.

    ``free_bytes`` and ``threshold_bytes`` use representative GB-scale
    values so the cassette body assertions in
    ``tests/subscribers/test_telegram_subscriber.py`` exercise the
    integer-floor-to-GB rendering path.
    """
    return DiskFullWarning(
        disk_path=Path("/Volumes/Disk1"),
        free_bytes=1_000_000_000,
        threshold_bytes=10_000_000_000,
    )


@register_factory(ItemDispatched)
def make_item_dispatched() -> ItemDispatched:
    """Realistic :class:`ItemDispatched` for round-trip tests."""
    return ItemDispatched(
        item="Inception (2010)",
        target_disk=Path("/Volumes/Disk1"),
        category_id="movies",
        action="moved",
    )


@register_factory(TrailerDownloaded)
def make_trailer_downloaded() -> TrailerDownloaded:
    """Realistic :class:`TrailerDownloaded` for round-trip tests."""
    return TrailerDownloaded(
        media_path=Path("/Volumes/Disk1/movies/Inception (2010)"),
        trailer_path=Path("/Volumes/Disk1/movies/Inception (2010)/Inception-trailer.mp4"),
        source_url="https://www.youtube.com/watch?v=YoHD9XEInc0",
    )


__all__ = ["EVENT_SAMPLE_FACTORIES", "register_factory"]
