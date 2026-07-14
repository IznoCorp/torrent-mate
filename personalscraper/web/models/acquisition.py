"""Pydantic models for the acquisition API (acq-watch feature).

See docs/features/acq-watch/DESIGN.md §3.2–3.3 for the route contracts these
models serve.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, computed_field, model_validator

#: Followed-series lifecycle status, derived server-side (C14) so the UI paints
#: without re-deriving business state in JSX.
FollowStatus = Literal["disabled", "pending", "acquiring", "up_to_date"]

#: Per-episode acquisition state for the §5 completeness read-model.
EpisodeState = Literal["en_mediatheque", "manquant", "en_file", "en_cours"]


class MediaRefResponse(BaseModel):
    """Provider-ID key exposed in API responses (tvdb_id primary)."""

    tvdb_id: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None


class FollowedSeriesItem(BaseModel):
    """A single followed series or film in the list response."""

    id: int
    title: str
    media_ref: MediaRefResponse
    active: bool
    #: "show" (default) or "movie" — drives the §5 film lifecycle display
    #: (en attente / en cours d'acquisition / retiré une fois en médiathèque).
    kind: str = "show"
    cadence: dict[str, object] | None = None  # parsed from cadence_json
    added_at: float  # epoch seconds
    wanted_pending: int  # COUNT from wanted table
    #: COUNT of wanted rows status='grabbed' — the §5 "en cours d'acquisition"
    #: window (torrent spotted → pipeline finished) for a followed film.
    wanted_grabbed: int = 0
    quality_profile: dict[str, object] | None = None  # read-only, parsed from quality_profile_json
    # Card display metadata (webui-overhaul OBJ3): cached at follow time from the
    # search candidate (poster_url = remote provider image URL); year + season_count
    # additionally backfilled from the indexer when absent. All nullable.
    poster_url: str | None = None
    overview: str | None = None
    year: int | None = None
    season_count: int | None = None
    # Cadence readout (webui-overhaul OBJ3): the next epoch at which an automatic
    # search becomes due for this series (min over its pending wanted items), and
    # the governing temperature tier ("hot"/"warm"/"cold"/"cutoff"). Both are
    # ``None`` when nothing is pending (the series is up to date).
    next_search_at: float | None = None
    cadence_tier: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> FollowStatus:
        """Lifecycle status derived from ``active`` + wanted counts (C14 / §5).

        Single server-side source of truth so the UI maps status → tone/label
        without re-deriving business state in JSX:

        - ``disabled``: the follow is paused (not active).
        - ``acquiring``: a grab landed and the torrent is on its way through
          the pipeline (§5 film "en cours d'acquisition": du torrent repéré
          jusqu'au pipeline terminé). Takes precedence over ``pending``.
        - ``pending``: at least one wanted search is in flight ("en attente").
        - ``up_to_date``: active with nothing pending.

        Returns:
            The derived lifecycle status.
        """
        if not self.active:
            return "disabled"
        if self.wanted_grabbed > 0:
            return "acquiring"
        if self.wanted_pending > 0:
            return "pending"
        return "up_to_date"


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
    """A recent acquisition-relevant pipeline run summary.

    Covers watcher-triggered pipeline runs AND the acquisition CLI runs
    (``follow-detect`` / ``grab``), each carrying its §5 numeric result when
    the CLI recorded one.
    """

    run_uid: str
    started_at: float  # epoch seconds
    ended_at: float | None = None  # epoch seconds
    outcome: str | None = None  # "success" | "error" | "killed" | None
    #: CLI command for acquisition runs ("follow-detect" | "grab"), else None.
    command: str | None = None
    #: What launched the run ("cron" | "cli" | "web" | watcher triggers).
    trigger: str | None = None
    #: §5 « résultat chiffré » — e.g. {"detected": 3, "enqueued": 2} for detect,
    #: {"grabbed": 1, "retried": 0, …} for grab. None when not recorded.
    result: dict[str, int] | None = None


class AcquisitionStatusResponse(BaseModel):
    """Response for GET /api/acquisition/status."""

    last_successful_run_at: float | None = None  # epoch seconds
    watcher_enabled: bool
    recent_runs: list[RecentRun] = []


class MediaSearchResult(BaseModel):
    """One provider match returned by the acquisition media search.

    Mirrors a ``DecisionCandidate`` (provider identity + poster/overview/score)
    plus a ``kind`` tag so the add-by-search cards can show film vs série.

    Attributes:
        provider: The metadata provider (``"tmdb"`` or ``"tvdb"``).
        provider_id: The provider's numeric identifier.
        title: The matched title.
        year: The release year, or ``None`` when the provider did not return one.
        kind: ``"movie"`` or ``"tv"`` (which search chain produced the result).
        poster_url: The provider poster URL, or ``None``.
        overview: A short plot summary, or ``None``.
        score: The matching-engine confidence score (0.0–1.0).
    """

    provider: str
    provider_id: int
    title: str
    year: int | None = None
    kind: str
    poster_url: str | None = None
    overview: str | None = None
    score: float
    #: §5 replacement confirmation: ``True`` when the library already holds a
    #: live file for this provider id — the UI must ask before following (the
    #: pipeline will REPLACE the existing version once acquired).
    already_owned: bool = False


class MediaSearchResponse(BaseModel):
    """Response for GET /api/acquisition/search.

    Attributes:
        results: The scored matches across the requested kind(s), best first.
    """

    results: list[MediaSearchResult]


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
    #: "show" (default) or "movie" — the §5 film lifecycle starts here: a movie
    #: follow produces ONE wanted item at detect time and is auto-unfollowed
    #: once the acquired file reaches the library.
    kind: Literal["movie", "show"] = "show"
    # Optional card metadata captured from the add-by-search candidate (OBJ3).
    poster_url: str | None = None
    overview: str | None = None
    year: int | None = None

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


class GrabTriggerResponse(BaseModel):
    """Response body for ``POST /api/acquisition/followed/{id}/search`` (OBJ3).

    Returned ``202`` when a per-series manual grab has been launched.

    Attributes:
        run_uid: The unique identifier of the launched grab run — the frontend
            polls ``GET /api/pipeline/history/{run_uid}`` for its outcome.
    """

    run_uid: str


# ── Completeness read-model (§5 series: aired vs library vs queue) ─────────


class EpisodeCompleteness(BaseModel):
    """One aired episode's acquisition state (§5 épisode par épisode).

    Attributes:
        episode: Episode number within the season.
        title: Episode title, or ``None`` when the provider omitted it.
        air_date: ISO ``YYYY-MM-DD`` air date.
        state: ``en_mediatheque`` (a live file exists in the library),
            ``en_file`` (a pending wanted row), ``en_cours`` (a wanted row is
            searching/grabbed — acquisition under way), or ``manquant`` (aired,
            not owned, not queued).
    """

    episode: int
    title: str | None = None
    air_date: str | None = None
    state: EpisodeState


class SeasonCompleteness(BaseModel):
    """Per-season aggregate + per-episode detail (§5 saison par saison).

    Attributes:
        season: Season number (1-based; specials excluded by the poller).
        owned: Episodes with a live library file.
        queued: Episodes currently in the wanted queue (en_file + en_cours).
        total: Aired episodes in the season.
        episodes: The per-episode states, ordered by episode number.
    """

    season: int
    owned: int
    queued: int
    total: int
    episodes: list[EpisodeCompleteness]


class CompletenessResponse(BaseModel):
    """Response for ``GET /api/acquisition/followed/{id}/completeness``.

    Attributes:
        followed_id: The follow this completeness was computed for.
        title: The followed title (display).
        kind: ``"show"`` or ``"movie"`` (movies get an empty seasons list —
            their lifecycle lives on the card status instead).
        provider_catalog_empty: ``True`` when the provider returned NO aired
            episodes (the Top Chef case — the UI must say "catalogue provider
            vide", never render a misleading all-missing matrix).
        seasons: Season-by-season completeness, newest season first.
    """

    followed_id: int
    title: str
    kind: str
    provider_catalog_empty: bool = False
    seasons: list[SeasonCompleteness]


#: Live state of a grabbed torrent, normalised across clients (A4). ``in_client``
#: is the fall-through when the raw client state is not one of the known buckets.
DownloadState = Literal["downloading", "stalled", "seeding", "paused", "queued", "in_client", "missing"]


class AcquisitionDownload(BaseModel):
    """One grabbed torrent surfaced in the acquisition downloads panel (A4).

    Attributes:
        media_ref: Provider-ID key of the wanted item.
        title: Followed-series/film display title (empty if the follow is gone).
        kind: ``"movie"`` or ``"episode"``.
        season: Season number (episodes only).
        episode: Episode number (episodes only).
        info_hash: The grabbed torrent's info hash.
        name: Torrent display name from the client (empty when ``missing``).
        progress: Download progress 0.0–1.0 (0.0 when the client has no record).
        state: Normalised live state. ``missing`` = grabbed row whose hash the
            client no longer knows (removed / not yet visible) — surfaced
            honestly rather than hidden.
        size_bytes: Total size from the client (0 when unknown).
    """

    media_ref: MediaRefResponse
    title: str
    kind: str
    season: int | None = None
    episode: int | None = None
    info_hash: str
    name: str = ""
    progress: float = 0.0
    state: DownloadState
    size_bytes: int = 0


class AcquisitionDownloadsResponse(BaseModel):
    """Response for ``GET /api/acquisition/downloads`` (A4).

    Attributes:
        downloads: Active/grabbed downloads, in-progress first then by recency.
        client_available: ``False`` when the torrent client could not be reached
            (the UI shows a soft "client injoignable" note instead of an empty
            list that would read as "no downloads").
    """

    downloads: list[AcquisitionDownload] = []
    client_available: bool = True
