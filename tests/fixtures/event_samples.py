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
from personalscraper.indexer.events import (
    DiskFullWarning,
    LibraryScanCompleted,
)
from personalscraper.models import FailedItem, PipelineReport, StepReport
from personalscraper.pipeline_events import (
    ItemProgressed,
    PipelineEnded,
    PipelinePaused,
    PipelineResumed,
    PipelineStarted,
    StepCompleted,
    StepErrored,
    StepStarted,
)
from personalscraper.trailers.events import TrailerDownloaded
from personalscraper.verify.events import VerifyItemDone

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


@register_factory(PipelinePaused)
def make_pipeline_paused() -> PipelinePaused:
    """Realistic :class:`PipelinePaused` factory."""
    return PipelinePaused()


@register_factory(PipelineResumed)
def make_pipeline_resumed() -> PipelineResumed:
    """Realistic :class:`PipelineResumed` factory."""
    return PipelineResumed()


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


# ---------------------------------------------------------------------------
# provider-ids feature — sub-phase 8.4 backfill events
# ---------------------------------------------------------------------------

from personalscraper.indexer.events import (  # noqa: E402, PLC0415
    BackfillCompleted,
    BackfillItemCompleted,
    BackfillSkipped,
    BackfillStarted,
)


@register_factory(BackfillStarted)
def make_backfill_started() -> BackfillStarted:
    """Realistic :class:`BackfillStarted` factory."""
    return BackfillStarted(scope="library", item_count=42)


@register_factory(BackfillItemCompleted)
def make_backfill_item_completed() -> BackfillItemCompleted:
    """Realistic :class:`BackfillItemCompleted` factory."""
    return BackfillItemCompleted(
        item_id=17,
        item_title="Inception",
        ids_added=("imdb",),
        ratings_added=("imdb", "rotten_tomatoes"),
    )


@register_factory(BackfillSkipped)
def make_backfill_skipped() -> BackfillSkipped:
    """Realistic :class:`BackfillSkipped` factory."""
    return BackfillSkipped(item_id=18, item_title="The Matrix", reason="already_complete")


@register_factory(BackfillCompleted)
def make_backfill_completed() -> BackfillCompleted:
    """Realistic :class:`BackfillCompleted` factory."""
    return BackfillCompleted(
        scope="library",
        scanned=42,
        updated=10,
        skipped=30,
        failed=2,
        ids_added_count=15,
        ratings_added_count=20,
    )


@register_factory(VerifyItemDone)
def make_verify_item_done() -> VerifyItemDone:
    """Realistic :class:`VerifyItemDone` factory (tech-debt 0.16.0 sub-phase 3.1, DEV #6/#40)."""
    return VerifyItemDone(
        item="Inception (2010)",
        status="valid",
        errors=[],
        checks_passed=12,
        checks_total=12,
    )


# Registry events (arch-cleanup-2 Phase 1) — imported lazily after the module
# body so the heavy ``personalscraper.api.metadata.registry`` package (which
# pulls in the transport stack) is only resolved when this fixture module loads,
# matching the deferred-import pattern used for the indexer events above.
from personalscraper.api._contracts import MediaType  # noqa: E402
from personalscraper.api.metadata.registry import AttemptOutcome, ProviderMatch  # noqa: E402
from personalscraper.api.metadata.registry._events import (  # noqa: E402
    LockedCapabilityUnresolved,
    ProviderExhaustedEvent,
    ProviderFallbackTriggered,
    RegistryBootValidated,
    RegistryFanOutCompleted,
)


@register_factory(ProviderFallbackTriggered)
def make_provider_fallback_triggered() -> ProviderFallbackTriggered:
    """Realistic :class:`ProviderFallbackTriggered` factory."""
    return ProviderFallbackTriggered(
        capability="MetadataClient",
        from_provider="tmdb",
        to_provider="tvdb",
        reason="network",
        exc_type="requests.Timeout",
        item={"title": "Inception", "year": 2010},
    )


@register_factory(ProviderExhaustedEvent)
def make_provider_exhausted_event() -> ProviderExhaustedEvent:
    """Realistic :class:`ProviderExhaustedEvent` factory."""
    return ProviderExhaustedEvent(
        capability="MetadataClient",
        attempted=(
            AttemptOutcome(provider="tmdb", reason="network", detail="timeout"),
            AttemptOutcome(provider="tvdb", reason="empty_result"),
        ),
        item={"title": "Inception", "year": 2010},
    )


@register_factory(LockedCapabilityUnresolved)
def make_locked_capability_unresolved() -> LockedCapabilityUnresolved:
    """Realistic :class:`LockedCapabilityUnresolved` factory."""
    return LockedCapabilityUnresolved(
        capability="MetadataClient",
        match=ProviderMatch(provider="tmdb", id="27205", media_type=MediaType.MOVIE),
        chain_tried=("tmdb", "tvdb"),
    )


@register_factory(RegistryFanOutCompleted)
def make_registry_fan_out_completed() -> RegistryFanOutCompleted:
    """Realistic :class:`RegistryFanOutCompleted` factory."""
    return RegistryFanOutCompleted(
        capability="RatingProvider",
        attempted=(
            AttemptOutcome(provider="tmdb", reason="empty_result"),
            AttemptOutcome(provider="imdb", reason="circuit_open"),
        ),
        eligible=2,
    )


@register_factory(RegistryBootValidated)
def make_registry_boot_validated() -> RegistryBootValidated:
    """Realistic :class:`RegistryBootValidated` factory."""
    return RegistryBootValidated(
        providers=("tmdb", "tvdb"),
        capabilities={"MetadataClient": ("tmdb", "tvdb"), "RatingProvider": ("tmdb",)},
    )


# ---------------------------------------------------------------------------
# acquire-events feature (RP4) — 10 acquisition event factories
# ---------------------------------------------------------------------------

from personalscraper.acquire.events import (  # noqa: E402, PLC0415
    CrossSeedInjected,
    CrossSeedRejected,
    GrabFailed,
    GrabSucceeded,
    RatioMeasured,
    SeedObligationBreached,
    SeedObligationRecorded,
    SeedObligationSatisfied,
    SeriesFollowed,
    SeriesUnfollowed,
    TrackerAuthFailed,
    WantedAbandoned,
    WantedEnqueued,
    WatcherRunTriggered,
)
from personalscraper.core.identity import MediaRef  # noqa: E402, PLC0415

_BREAKING_BAD_REF = MediaRef(tvdb_id=81189, tmdb_id=1396, imdb_id="tt0903747")
_INCEPTION_REF = MediaRef(tvdb_id=None, tmdb_id=27205, imdb_id="tt1375666")


@register_factory(SeriesFollowed)
def make_series_followed() -> SeriesFollowed:
    """Realistic SeriesFollowed factory — Breaking Bad."""
    return SeriesFollowed(media_ref=_BREAKING_BAD_REF, title="Breaking Bad")


@register_factory(SeriesUnfollowed)
def make_series_unfollowed() -> SeriesUnfollowed:
    """Realistic SeriesUnfollowed factory — Breaking Bad."""
    return SeriesUnfollowed(media_ref=_BREAKING_BAD_REF)


@register_factory(WantedEnqueued)
def make_wanted_enqueued() -> WantedEnqueued:
    """Realistic WantedEnqueued factory — Breaking Bad S05E01."""
    return WantedEnqueued(
        media_ref=_BREAKING_BAD_REF,
        kind="episode",
        season=5,
        episode=1,
    )


@register_factory(WantedAbandoned)
def make_wanted_abandoned() -> WantedAbandoned:
    """Realistic WantedAbandoned factory — Inception movie."""
    return WantedAbandoned(
        media_ref=_INCEPTION_REF,
        reason="cutoff_reached",
    )


@register_factory(GrabSucceeded)
def make_grab_succeeded() -> GrabSucceeded:
    """Realistic GrabSucceeded factory — lacale grab with tags."""
    return GrabSucceeded(
        media_ref=_BREAKING_BAD_REF,
        info_hash="a" * 40,
        source_tracker="lacale",
        category="tv_shows",
        tags=("freeleech", "hd"),
    )


@register_factory(GrabFailed)
def make_grab_failed() -> GrabFailed:
    """Realistic GrabFailed factory — network failure, no tracker resolved."""
    return GrabFailed(
        media_ref=None,
        source_tracker="lacale",
        reason="ConnectionError: Max retries exceeded",
    )


@register_factory(SeedObligationRecorded)
def make_seed_obligation_recorded() -> SeedObligationRecorded:
    """Realistic SeedObligationRecorded factory."""
    return SeedObligationRecorded(
        info_hash="b" * 40,
        source_tracker="lacale",
        min_seed_time_s=86400,
        dispatched_path="/Volumes/Disk1/TV Shows/Breaking Bad (2008)",
    )


@register_factory(SeedObligationBreached)
def make_seed_obligation_breached() -> SeedObligationBreached:
    """Realistic SeedObligationBreached factory."""
    return SeedObligationBreached(
        info_hash="b" * 40,
        source_tracker="lacale",
        dispatched_path="/Volumes/Disk1/TV Shows/Breaking Bad (2008)",
    )


@register_factory(SeedObligationSatisfied)
def make_seed_obligation_satisfied() -> SeedObligationSatisfied:
    """Realistic SeedObligationSatisfied factory."""
    return SeedObligationSatisfied(
        info_hash="b" * 40,
        source_tracker="lacale",
    )


@register_factory(RatioMeasured)
def make_ratio_measured() -> RatioMeasured:
    """Realistic RatioMeasured factory — lacale ratio below target."""
    return RatioMeasured(
        tracker="lacale",
        observed_ratio=0.87,
        target_ratio=1.0,
    )


@register_factory(TrackerAuthFailed)
def make_tracker_auth_failed() -> TrackerAuthFailed:
    """Realistic TrackerAuthFailed factory — lacale 401, Breaking Bad."""
    return TrackerAuthFailed(
        tracker="lacale",
        http_status=401,
        media_ref=_BREAKING_BAD_REF,
    )


@register_factory(CrossSeedInjected)
def make_cross_seed_injected() -> CrossSeedInjected:
    """Realistic CrossSeedInjected factory — cross-seeded to c411 from lacale source."""
    return CrossSeedInjected(
        info_hash="d" * 40,
        source_tracker="c411",
        source_hash="b" * 40,
        save_path="/Volumes/Disk1/TV Shows/Breaking Bad (2008)",
    )


@register_factory(CrossSeedRejected)
def make_cross_seed_rejected() -> CrossSeedRejected:
    """Realistic CrossSeedRejected factory — structural mismatch on root_name."""
    return CrossSeedRejected(
        info_hash="e" * 40,
        tracker="c411",
        reason="structural_mismatch: root_name",
        source_hash="b" * 40,
    )


@register_factory(WatcherRunTriggered)
def make_watcher_run_triggered() -> WatcherRunTriggered:
    """Realistic WatcherRunTriggered factory — daemon completion trigger."""
    return WatcherRunTriggered(reason="completion")


__all__ = ["EVENT_SAMPLE_FACTORIES", "register_factory"]
