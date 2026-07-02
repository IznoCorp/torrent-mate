"""Acquisition event catalog (RP4).

Defines the 10 typed events emitted by the acquisition lobe. All classes are
frozen kw_only dataclasses over :class:`~personalscraper.core.event_bus.Event`.
Payload fields mirror the already-persisted
:mod:`personalscraper.acquire.domain` value objects so shapes are determined
by shipped data, not speculation (DESIGN §3).

Import direction: imports ``core.event_bus``, ``core.identity``, and stdlib
only — no ``indexer``, ``scraper``, or triage imports (acquire/ layering rule).

Producers arrive in waves 4–5 (Follow D1–D3, Ratio C1, Seed-Safety O2,
Watcher). RP4 defines the shapes; events stay unused until then.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from personalscraper.core.event_bus import Event
from personalscraper.core.identity import MediaRef


@dataclass(frozen=True, kw_only=True)
class SeriesFollowed(Event):
    """A TV series or movie was added to the follow list.

    Emitted by Follow D1 when the user subscribes to a series.

    Attributes:
        media_ref: Provider-ID key (tvdb_id primary).
        title: Human-readable title for logging/display.
    """

    media_ref: MediaRef
    title: str


@dataclass(frozen=True, kw_only=True)
class SeriesUnfollowed(Event):
    """A TV series or movie was removed from the follow list.

    Emitted by Follow D1 when the user unsubscribes from a series.

    Attributes:
        media_ref: Provider-ID key (tvdb_id primary).
    """

    media_ref: MediaRef


@dataclass(frozen=True, kw_only=True)
class WantedEnqueued(Event):
    """A specific episode or movie was added to the wanted queue.

    Emitted by Follow D2 when a new episode/movie is queued for acquisition.

    Attributes:
        media_ref: Provider-ID key (tvdb_id primary).
        kind: ``"movie"`` or ``"episode"``.
        season: Season number (episodes only; ``None`` for movies).
        episode: Episode number (episodes only; ``None`` for movies).
    """

    media_ref: MediaRef
    kind: Literal["movie", "episode"]
    season: int | None
    episode: int | None


@dataclass(frozen=True, kw_only=True)
class WantedAbandoned(Event):
    """A wanted item was abandoned (e.g. cutoff reached, no source found).

    Emitted by Follow D2 when an item leaves the queue without being grabbed.

    Attributes:
        media_ref: Provider-ID key (tvdb_id primary).
        reason: Human-readable abandonment reason.
    """

    media_ref: MediaRef
    reason: str


@dataclass(frozen=True, kw_only=True)
class GrabSucceeded(Event):
    """A torrent was successfully grabbed from a tracker.

    Emitted by RP5b (Follow D3 + Ratio C1) after a successful grab POST.

    Attributes:
        media_ref: Provider-ID key; ``None`` when the grab is unbound to a
            specific media item (e.g. manual grab or freeleech sweep).
        info_hash: Torrent info-hash (hex string).
        source_tracker: Tracker name (e.g. ``"lacale"``).
        category: Category ID string (``None`` if unknown at grab time).
        tags: Ordered tuple of tracker-assigned tags.
    """

    media_ref: MediaRef | None
    info_hash: str
    source_tracker: str
    category: str | None
    tags: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class GrabFailed(Event):
    """A torrent grab attempt failed.

    Emitted by RP5b on any grab failure (network, parse, no results, etc.).

    Attributes:
        media_ref: Provider-ID key; ``None`` when unbound to a specific item.
        source_tracker: Tracker name; ``None`` when failure is pre-selection.
        reason: Human-readable failure reason.
    """

    media_ref: MediaRef | None
    source_tracker: str | None
    reason: str


@dataclass(frozen=True, kw_only=True)
class SeedObligationRecorded(Event):
    """A seed obligation was created when a dispatched payload is registered.

    Emitted by the dispatch step / O2 when a new ``SeedObligation`` row is
    inserted (e.g. after a successful real dispatch with ``action != "dry_run"``).

    Attributes:
        info_hash: Torrent info-hash (hex string).
        source_tracker: Tracker name (e.g. ``"lacale"``).
        min_seed_time_s: Minimum seed time in seconds (snapshot from economy config).
        dispatched_path: Absolute path of the dispatched media; ``None`` until move.
    """

    info_hash: str
    source_tracker: str
    min_seed_time_s: int
    dispatched_path: str | None


@dataclass(frozen=True, kw_only=True)
class SeedObligationBreached(Event):
    """A seed obligation was breached (seeding stopped before min_seed_time).

    Emitted by O2 when ``acquire.hnr_risk`` structlog warning would fire
    today (this event is the typed equivalent that supervisors subscribe to).

    Attributes:
        info_hash: Torrent info-hash (hex string).
        source_tracker: Tracker name (e.g. ``"lacale"``).
        dispatched_path: Absolute path of the dispatched media; ``None`` if unset.
    """

    info_hash: str
    source_tracker: str
    dispatched_path: str | None


@dataclass(frozen=True, kw_only=True)
class SeedObligationSatisfied(Event):
    """A seed obligation was satisfied (seeding completed successfully).

    Emitted by O2 when the obligation's min_seed_time_s has elapsed.

    Attributes:
        info_hash: Torrent info-hash (hex string).
        source_tracker: Tracker name (e.g. ``"lacale"``).
    """

    info_hash: str
    source_tracker: str


@dataclass(frozen=True, kw_only=True)
class RatioMeasured(Event):
    """A tracker ratio measurement was recorded.

    Emitted by Ratio C1 after each ratio poll cycle.

    Attributes:
        tracker: Tracker identifier string (e.g. ``"lacale"``).
        observed_ratio: Latest measured upload/download ratio.
        target_ratio: Configured minimum ratio threshold.
    """

    tracker: str
    observed_ratio: float
    target_ratio: float


@dataclass(frozen=True, kw_only=True)
class TrackerAuthFailed(Event):
    """A tracker rejected the grab with an auth error (HTTP 401/403).

    Emitted by the acquisition orchestrator's ``except TrackerAuthError``
    branch when a ``.torrent`` download fails because the tracker credential
    (apikey/passkey/token) is broken. The item is abandoned (a broken
    credential will not self-heal by retrying the same item); this event is
    the operator-routable signal that the credential needs fixing.

    Attributes:
        tracker: Provider wire name the grab targeted (``top.provider``,
            lowercase).
        http_status: The rejecting HTTP status (401 or 403).
        media_ref: The desired item that could not be grabbed.
    """

    tracker: str
    http_status: int
    media_ref: MediaRef


@dataclass(frozen=True, kw_only=True)
class CrossSeedInjected(Event):
    """Emitted when a cross-seed torrent is successfully injected + verified.

    Emitted by :class:`~personalscraper.acquire.cross_seed.CrossSeedService`
    after the obligation record is persisted (emit-after-persist convention).

    Attributes:
        info_hash: The info-hash of the injected torrent.
        source_tracker: The tracker the ``.torrent`` was fetched from (target).
        source_hash: The info-hash of the original (source) torrent.
        save_path: Absolute path to the data directory used as save path.
    """

    info_hash: str
    source_tracker: str
    source_hash: str
    save_path: str


@dataclass(frozen=True, kw_only=True)
class CrossSeedRejected(Event):
    """Emitted when a cross-seed candidate is rejected before injection.

    Emitted by :class:`~personalscraper.acquire.cross_seed.CrossSeedService`
    at each rejection point — fetch failure, magnet, parse error, structural
    mismatch, or recheck failure.

    Attributes:
        info_hash: The info-hash of the CANDIDATE ``.torrent`` (not the
            source). When the candidate carries no hash, this is the
            download URL or ``"unknown"``.
        tracker: The tracker the candidate was fetched from.
        reason: Human-readable rejection reason
            (e.g. ``"structural_mismatch: root_name"``, ``"fetch_failed"``).
        source_hash: The info-hash of the source torrent that triggered the
            cross-seed attempt.
    """

    info_hash: str
    tracker: str
    reason: str
    source_hash: str


__all__ = [
    "CrossSeedInjected",
    "CrossSeedRejected",
    "GrabFailed",
    "GrabSucceeded",
    "RatioMeasured",
    "SeedObligationBreached",
    "SeedObligationRecorded",
    "SeedObligationSatisfied",
    "SeriesFollowed",
    "SeriesUnfollowed",
    "TrackerAuthFailed",
    "WantedAbandoned",
    "WantedEnqueued",
]
