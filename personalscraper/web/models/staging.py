"""Pydantic models for the staging read-model API (webui-overhaul OBJ2A).

``GET /api/staging/media`` exposes one item per media folder currently sitting
in the staging area, enriched with the scraped NFO metadata, its matching
state (from the ``scrape_decision`` queue), trailer/poster presence, and a
per-media pipeline **timeline** (the nine Flow Board stages, each with a
derived state). This is the shared read-model behind both the OBJ2A staging
library grid and the OBJ1 per-media Media Timeline drawer.

The read-model is derived, not stored: it scans the configured
``staging_dirs`` tree on the filesystem, reads the local ``*.nfo`` files, and
joins the live ``scrape_decision`` rows. No new table, no write path — the
staging instance can serve it read-only (ENV-SEP).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

#: Kind of a staged media folder. ``movie``/``tvshow`` are the scrapable kinds
#: enriched with NFO + poster + seasons; the remaining kinds are reported as-is
#: (present in staging but not part of the scrape/match/trailer flow), and
#: ``unsorted`` is a folder still sitting in the ingest dir before sort ran.
StagingMediaKind = Literal["movie", "tvshow", "ebook", "audio", "app", "other", "unsorted"]

#: Top-level matching verdict for a staged media (drives the library grid chip).
#: ``matched`` = a valid NFO with provider ids is present; ``ambiguous`` = a
#: pending ``scrape_decision`` awaits an operator choice; ``absent`` = neither
#: (not yet scraped, or the scraper found no confident match).
StagingMatch = Literal["matched", "ambiguous", "absent"]

#: State of one pipeline stage for a single media in its timeline.
#: ``done`` = the stage produced its artefact; ``active`` = the live run is
#: currently at this stage for this item; ``blocked`` = it needs an operator
#: (a pending decision); ``pending`` = not reached yet; ``skipped`` = the stage
#: does not apply to this media kind (e.g. scraping an ebook).
StagingStageState = Literal["done", "active", "blocked", "pending", "skipped"]

#: How a staged media would be dispatched to permanent storage (opt-in preview).
StagingDispatchMode = Literal["replace", "merge", "new", "unknown"]


class StagingStageStep(BaseModel):
    """One stage of a staged media's per-item pipeline timeline.

    Attributes:
        key: Stable stage identifier (``arrival`` … ``dispatch``), aligned with
            the OBJ1 Flow Board stage keys.
        label: French display label (e.g. ``"Scraping"``).
        state: Derived state of this stage for this media.
    """

    key: str
    label: str
    state: StagingStageState


class StagingSeason(BaseModel):
    """A season subfolder of a staged TV show.

    Attributes:
        season: Season number parsed from the ``Saison NN`` folder name.
        label: The on-disk folder label (e.g. ``"Saison 17"``).
        episode_count: Number of episode video files inside the season folder.
    """

    season: int
    label: str
    episode_count: int


class StagingDispatchTarget(BaseModel):
    """Preview of where a staged media would be dispatched (opt-in).

    Computed only when the list endpoint is called with ``with_dispatch=true``
    (a filesystem/disk scan per item). Best-effort and fail-soft: any error
    yields ``mode="unknown"`` with a ``reason`` rather than failing the whole
    response.

    Attributes:
        mode: ``replace`` (movie whose folder already exists on a disk),
            ``merge`` (TV show whose folder already exists — episodes are
            merged), ``new`` (no existing folder — goes to the disk with the
            most free space), or ``unknown`` (could not resolve).
        disk: Target disk id, or ``None`` when unresolved.
        category_id: Resolved storage category id (e.g. ``"movies"``), or
            ``None``.
        reason: Short human-readable explanation of the decision.
    """

    mode: StagingDispatchMode
    disk: str | None = None
    category_id: str | None = None
    reason: str


class StagingMediaItem(BaseModel):
    """One media folder currently present in the staging area.

    Attributes:
        id: Stable URL-safe identifier — the truncated SHA-1 of the staging
            path relative to ``staging_dir``. Used by the poster route to
            resolve back to the folder without ever trusting a client path.
        category: The staging subfolder the media sits in (e.g.
            ``"001-MOVIES"``).
        folder: The media folder name (e.g. ``"Fight Club (1999)"``).
        relative_path: ``category/folder`` — the path relative to the staging
            root (never an absolute path, so no host layout leaks).
        media_kind: Kind of media (drives enrichment + grid filtering).
        title: NFO ``<title>`` when scraped, else the folder name (year
            stripped).
        year: Release year from the NFO or the folder name, or ``None``.
        overview: NFO ``<plot>`` (description), or ``None`` when unscraped.
        provider_ids: Mapping of provider family → id string from the NFO
            ``<uniqueid>`` rows (e.g. ``{"tvdb": "475278", "tmdb": "315820"}``).
        match: Top-level matching verdict.
        decision_id: The ``scrape_decision.id`` when ``match == "ambiguous"``,
            else ``None`` (lets the grid deep-link to the resolution deck).
        decision_trigger: The ambiguity trigger (``"ambiguous"`` /
            ``"below_threshold"`` / ``"mid_band"``), or ``None``.
        has_nfo: Whether a ``movie.nfo`` / ``tvshow.nfo`` is present.
        has_poster: Whether a local ``poster.jpg``/``poster.png`` is present.
        has_trailer: Whether a trailer file is present (Plex convention).
        poster_url: The guarded local poster route
            (``/api/staging/media/{id}/poster``) when a poster exists, else
            ``None`` (the frontend ``MediaPoster`` shows its initials fallback).
        seasons: Season breakdown for a TV show, or ``None`` for other kinds.
        episode_count: Total episode video files across seasons (TV show), or
            ``None``.
        video_count: Number of video files anywhere in the media tree.
        size_bytes: Total size of the media folder in bytes.
        modified_at: Epoch seconds of the most recent file mtime in the tree
            (drives the default ``recent`` sort).
        stages: The nine-stage per-media pipeline timeline.
        dispatch_target: Dispatch preview, or ``None`` unless requested.
    """

    id: str
    category: str
    folder: str
    relative_path: str
    media_kind: StagingMediaKind
    title: str
    year: int | None = None
    overview: str | None = None
    provider_ids: dict[str, str] = {}
    match: StagingMatch
    decision_id: int | None = None
    decision_trigger: str | None = None
    has_nfo: bool = False
    has_poster: bool = False
    has_trailer: bool = False
    poster_url: str | None = None
    seasons: list[StagingSeason] | None = None
    episode_count: int | None = None
    video_count: int = 0
    size_bytes: int = 0
    modified_at: float | None = None
    stages: list[StagingStageStep] = []
    dispatch_target: StagingDispatchTarget | None = None


class StagingCounts(BaseModel):
    """Aggregate counts across the whole staging area (for filter chips).

    Computed over the full unpaginated set so the UI can label its filters
    without a second request.

    Attributes:
        total: Total number of staged media folders.
        matched: How many have a confident match (valid NFO + ids).
        ambiguous: How many await an operator decision.
        absent: How many are neither matched nor ambiguous.
        scraped: How many carry an NFO.
        with_trailer: How many have a trailer file.
        awaiting_action: How many have at least one ``blocked`` timeline stage.
    """

    total: int = 0
    matched: int = 0
    ambiguous: int = 0
    absent: int = 0
    scraped: int = 0
    with_trailer: int = 0
    awaiting_action: int = 0


class StagingMediaResponse(BaseModel):
    """Response body for ``GET /api/staging/media``.

    Attributes:
        items: The media items for the current page, already sorted/filtered.
        counts: Aggregate counts over the full (unpaginated, unfiltered) set.
        total: Number of items after filtering (for pagination).
        page: 1-indexed page number echoed back.
        page_size: Page size echoed back.
    """

    items: list[StagingMediaItem]
    counts: StagingCounts
    total: int
    page: int
    page_size: int


class EnqueueDecisionResponse(BaseModel):
    """Response body for ``POST /api/staging/media/{id}/enqueue``.

    Attributes:
        ok: ``True`` when the item was enqueued as a pending scrape decision.
        media_kind: The kind of the enqueued item (``movie``/``tvshow``).
        title: The folder-derived title enqueued for resolution.
        decision_id: The ``scrape_decision.id`` of the enqueued row, so the
            client can open the resolution deck positioned on it (C18 — same
            grammar as an ambiguous card). ``None`` if the id could not be read.
    """

    ok: bool
    media_kind: StagingMediaKind
    title: str
    decision_id: int | None = None
