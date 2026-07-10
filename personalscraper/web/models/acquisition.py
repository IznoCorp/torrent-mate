"""Pydantic models for the acquisition API (acq-watch feature).

See docs/features/acq-watch/DESIGN.md §3.2–3.3 for the route contracts these
models serve.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator


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


# ── Request models (write routes) ────────────────────────────────────────


class CreateFollowRequest(BaseModel):
    """Request body for POST /api/acquisition/followed.

    At least one provider ID is required (422 otherwise).  *title* is optional
    — when omitted the backend stores an empty string.  The web form will
    always send a title, but the route accepts ``None`` for programmatic
    clients.
    """

    tvdb_id: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    title: str | None = None

    @model_validator(mode="after")
    def _at_least_one_id(self) -> "CreateFollowRequest":
        """Validate that at least one provider ID is provided.

        Returns:
            The validated instance.

        Raises:
            ValueError: If all three provider IDs are ``None``.
        """
        if self.tvdb_id is None and self.tmdb_id is None and self.imdb_id is None:
            raise ValueError("At least one provider ID (tvdb_id, tmdb_id, or imdb_id) is required")
        return self


class CadenceShape(BaseModel):
    """Per-series search cadence override (editable).

    The shape mirrors what the backend ``effective_cadence`` resolver consumes
    from ``cadence_json``.  The PATCH endpoint validates incoming cadence
    against this schema before writing to ``cadence_json``.
    """

    interval_minutes: int
    # Future RP9/D2 fields added here (e.g. per-season windows).
    # For S7, interval_minutes is the only active field.


class UpdateFollowRequest(BaseModel):
    """Request body for PATCH /api/acquisition/followed/{id}.

    Every field is optional — only the provided fields are updated.
    *cadence* is validated against :class:`CadenceShape` before writing to
    ``cadence_json``.  ``quality_profile_json`` is intentionally ABSENT
    (RP3a deferred — do NOT expose an editor until the backend consumes it).
    """

    active: bool | None = None
    cadence: CadenceShape | None = None
