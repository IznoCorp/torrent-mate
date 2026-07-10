"""Pydantic models for the acquisition API (acq-watch feature).

See docs/features/acq-watch/DESIGN.md §3.2–3.3 for the route contracts these
models serve.
"""

from __future__ import annotations

from pydantic import BaseModel


class MediaRefResponse(BaseModel):
    """Provider-ID key exposed in API responses (tvdb_id primary)."""

    tvdb_id: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None


class FollowedSeriesItem(BaseModel):
    """A single followed series in the list response."""

    id: int
    title: str
    media_ref: MediaRefResponse
    active: bool
    cadence: dict[str, object] | None = None  # parsed from cadence_json
    added_at: float  # epoch seconds
    wanted_pending: int  # COUNT from wanted table
    quality_profile: dict[str, object] | None = None  # read-only, parsed from quality_profile_json


class FollowedResponse(BaseModel):
    """Response for GET /api/acquisition/followed."""

    items: list[FollowedSeriesItem]


class WantedItemResponse(BaseModel):
    """A single wanted item in the paginated list."""

    id: int
    title: str  # joined from followed_series
    kind: str  # "movie" | "episode"
    season: int | None = None
    episode: int | None = None
    status: str  # "pending" | "searching" | "grabbed" | "done" | "abandoned"
    attempts: int
    enqueued_at: float  # epoch seconds
    last_search_at: float | None = None  # epoch seconds


class WantedResponse(BaseModel):
    """Paginated response for GET /api/acquisition/wanted."""

    items: list[WantedItemResponse]
    total: int
    page: int
    page_size: int


class ObligationItem(BaseModel):
    """A seed obligation with its current ratio state."""

    info_hash: str
    source_tracker: str
    dispatched_path: str | None = None
    min_seed_time_s: int
    min_ratio: float
    added_at: float  # epoch seconds
    satisfied_at: float | None = None  # epoch seconds
    breached_at: float | None = None  # epoch seconds
    released_at: float | None = None  # epoch seconds
    # Joined from ratio_state (may be None if no ratio recorded)
    observed_ratio: float | None = None
    accumulated_seed_time_s: int | None = None
    hnr_count: int | None = None


class ObligationsResponse(BaseModel):
    """Response for GET /api/acquisition/obligations."""

    items: list[ObligationItem]


class RecentRun(BaseModel):
    """A recent watcher-triggered pipeline run summary."""

    run_uid: str
    started_at: float  # epoch seconds
    ended_at: float | None = None  # epoch seconds
    outcome: str | None = None  # "success" | "error" | "killed" | None


class AcquisitionStatusResponse(BaseModel):
    """Response for GET /api/acquisition/status."""

    last_successful_run_at: float | None = None  # epoch seconds
    watcher_enabled: bool
    recent_runs: list[RecentRun] = []
