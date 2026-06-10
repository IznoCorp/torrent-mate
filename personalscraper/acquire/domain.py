# personalscraper/acquire/domain.py
"""Frozen domain value objects for the acquisition lobe (RP3).

All objects are keyed on ``core.identity.MediaRef`` (tvdb_id primary).
QualityProfile + source-criteria are deferred to RP3a; the columns are
present in the schema as nullable JSON passthroughs until then.

Import direction: core.identity + stdlib only (acquire/ must never import
indexer/, scraper/, or any triage package).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from personalscraper.core.identity import MediaRef

WantedKind = Literal["movie", "episode"]
WantedStatus = Literal["pending", "searching", "grabbed", "done", "abandoned"]


@dataclass(frozen=True)
class FollowedSeries:
    """A TV series or movie the user wants to automatically acquire.

    Attributes:
        media_ref: Provider-ID key (tvdb_id primary).
        title: Human-readable title (for logging/display).
        active: Whether this series is actively searched.
        added_at: Unix epoch seconds when the series was followed.
        quality_profile_json: Nullable JSON string; rich profile = RP3a.
        cadence_json: Nullable JSON string; RP9/D2.
    """

    media_ref: MediaRef
    title: str
    added_at: int
    active: bool = True
    quality_profile_json: str | None = None
    cadence_json: str | None = None


@dataclass(frozen=True)
class WantedItem:
    """A specific episode or movie the acquisition engine wants to grab.

    Attributes:
        media_ref: Provider-ID key.
        kind: ``"movie"`` or ``"episode"``.
        status: Current acquisition state.
        enqueued_at: Unix epoch seconds when the item was enqueued.
        followed_id: FK to followed_series row (optional when standalone).
        season: Season number (episodes only).
        episode: Episode number (episodes only).
        criteria_json: Nullable JSON for search criteria (RP3a).
        last_search_at: Unix epoch seconds of last search attempt.
        attempts: Number of search attempts made.
    """

    media_ref: MediaRef
    kind: WantedKind
    status: WantedStatus
    enqueued_at: int
    followed_id: int | None = None
    season: int | None = None
    episode: int | None = None
    criteria_json: str | None = None
    last_search_at: int | None = None
    attempts: int = 0

    def __post_init__(self) -> None:
        """Validate kind and status values.

        Raises:
            ValueError: If kind or status is not a valid literal.
        """
        valid_kinds: tuple[str, ...] = ("movie", "episode")
        valid_statuses: tuple[str, ...] = ("pending", "searching", "grabbed", "done", "abandoned")
        if self.kind not in valid_kinds:
            raise ValueError(f"Invalid WantedItem.kind={self.kind!r}; must be one of {valid_kinds}")
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid WantedItem.status={self.status!r}; must be one of {valid_statuses}")


@dataclass(frozen=True)
class SeedObligation:
    """A seed obligation created when a torrent payload is dispatched.

    The deletion authority consults this table before permitting any deletion
    of a dispatched path.

    Attributes:
        info_hash: Torrent info-hash (hex string).
        source_tracker: Tracker name string (e.g. ``"lacale"``).
        min_seed_time_s: Minimum seed time in seconds (snapshot from TrackerEconomyConfig).
        min_ratio: Minimum ratio (snapshot).
        added_at: Unix epoch seconds when obligation was recorded.
        dispatched_path: Absolute path of the dispatched media (set after move).
        satisfied_at: Unix epoch seconds when obligation was satisfied (nullable).
        breached_at: Unix epoch seconds when obligation was breached (nullable).
        released_at: Unix epoch seconds when tracker released the obligation (nullable).
    """

    info_hash: str
    source_tracker: str
    min_seed_time_s: int
    min_ratio: float
    added_at: int
    dispatched_path: str | None = None
    satisfied_at: int | None = None
    breached_at: int | None = None
    released_at: int | None = None


@dataclass(frozen=True)
class RatioState:
    """Per-tracker ratio state (DORMANT — writer arrives with Ratio C1, Vague 5).

    Table is created now as a data-carrier; no RP3 code writes to it.

    Attributes:
        tracker_name: Tracker identifier (PK).
        observed_ratio: Last observed upload/download ratio.
        accumulated_seed_time_s: Total accumulated seed time in seconds.
        hnr_count: Number of hit-and-run events recorded.
        updated_at: Unix epoch seconds of last update.
    """

    tracker_name: str
    observed_ratio: float
    accumulated_seed_time_s: int
    hnr_count: int
    updated_at: int


__all__ = ["FollowedSeries", "RatioState", "SeedObligation", "WantedItem", "WantedKind", "WantedStatus"]
