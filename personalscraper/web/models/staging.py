"""Pydantic models for the staging read-model API (webui-overhaul OBJ2A).

``GET /api/staging/media`` exposes one item per media folder currently sitting
in the staging area, enriched with the scraped NFO metadata, its matching
state (from the ``scrape_decision`` queue), trailer/poster presence, its
single pipeline **position** (P0-A.1 axiom) and the derived per-media
**timeline** (the eight Flow Board stages). This is the shared read-model
behind the staging library grid, the Flow Board stocks and the per-stage
media lists.

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

#: State of a media's single position (P0-A.1 axiom): awaiting its stage
#: (``pending``), being processed there by the live run (``active``), or
#: needing an operator/repair (``blocked`` — ``blocked_reason`` says why).
StagingPositionState = Literal["pending", "active", "blocked"]

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
        position_stage: The SINGLE stage this media is at (P0-A.1 axiom): its
            next unsatisfied stage, or the stage it is blocked at. Board
            stocks, the per-stage lists and the timeline all derive from it —
            one media, one station, never two.
        position_state: Whether the media awaits its stage (``pending``), is
            being processed there by the live run (``active``), or needs an
            operator (``blocked`` — see ``blocked_reason``).
        stages: The eight-stage per-media pipeline timeline (the position,
            unrolled: done before, position state at, pending after).
        blocked_reason: A human-readable French reason when
            ``position_state == "blocked"`` — the real ``verify``-gate reason
            (e.g. ``"Bloqué : épisodes non renommés …"``, the SAME gate that
            authorizes dispatch — product-intent.md §méthode rule 6) or the
            identification block (pending decision / needs enqueue /
            AUTRES kind to qualify). ``None`` when not blocked.
        dispatch_target: Dispatch preview, or ``None`` unless requested.
        continuation_requested_at: Epoch timestamp from the
            ``.continuation-requested`` marker file written when a continue was
            deferred (pipeline lock held). ``None`` when no deferral is recorded
            or the marker was consumed by a subsequent run. Drives the
            « Reprise demandée » chip in the UI (§8 durable trace).
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
    position_stage: str
    position_state: StagingPositionState
    stages: list[StagingStageStep] = []
    blocked_reason: str | None = None
    dispatch_target: StagingDispatchTarget | None = None
    continuation_requested_at: float | None = None


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


class EnqueueDecisionRequest(BaseModel):
    """Request body for ``POST /api/staging/media/{id}/enqueue``.

    Attributes:
        media_kind: The type to resolve the item as. Optional for movie/tvshow items
            (their kind is derived from the category), but MANDATORY for an item that
            sits in an ``other`` (unsorted / AUTRES) category — the operator picks the
            type the sort got wrong, and the item is physically reclassed into it.
            Only ``"movie"`` / ``"tvshow"`` are accepted.
    """

    media_kind: Literal["movie", "tvshow"] | None = None


class EnqueueDecisionResponse(BaseModel):
    """Response body for ``POST /api/staging/media/{id}/enqueue``.

    Attributes:
        ok: ``True`` when the item was enqueued as a pending scrape decision.
        media_kind: The kind of the enqueued item (``movie``/``tvshow``).
        title: The folder-derived title enqueued for resolution.
        decision_id: The ``scrape_decision.id`` of the enqueued row, so the
            client can open the resolution deck positioned on it (C18 — same
            grammar as an ambiguous card). ``None`` if the id could not be read.
        candidates_count: Number of provider candidates seeded at enqueue time
            (product-intent.md §3 — the deck opens WITH proposals, not empty).
        candidates_seeded: ``True`` when the provider search ran and produced the
            candidates; ``False`` when providers were unavailable and the decision
            was enqueued fail-soft with an empty candidate list (the UI then shows
            an explicit "no automatic proposal" state + a prefilled manual search).
    """

    ok: bool
    media_kind: StagingMediaKind
    title: str
    decision_id: int | None = None
    candidates_count: int = 0
    candidates_seeded: bool = False


class ContinueResponse(BaseModel):
    """Response body for ``POST /api/staging/media/{id}/continue`` (§5.2).

    Mirrors the resolve 202 pattern: the run is either spawned now (``run_uid``
    present) or deferred because another run holds the lock (``run_uid`` is
    ``None`` — « En file »).

    Attributes:
        ok: ``True`` when the continuation was accepted.
        media_id: The staging media id.
        run_uid: The pipeline run id when a new run was spawned, or ``None``
            when deferred.
        deferred: ``True`` when the run could not start because another run
            holds the pipeline lock.
        detail: Human-readable French status detail.
    """

    ok: bool
    media_id: str
    run_uid: str | None = None
    deferred: bool = False
    detail: str = ""


class DiscardResponse(BaseModel):
    """Response body for ``POST /api/staging/media/{id}/discard`` (§7).

    The ``journaled`` flag confirms the append-only destructive-op row was
    written and verified with a read-back. ``quarantine_path`` is always set on
    success (the item is moved, never emptied in-place); the field is kept
    optional (``str | None``) for schema stability — a future error path could
    return ``None`` while still carrying ``ok=False``.

    Attributes:
        ok: ``True`` when the discard was accepted.
        media_id: The staging media id.
        journaled: ``True`` when the destructive-op journal row was written and
            verified with a read-back.
        quarantine_path: Absolute path to the quarantine destination (always set
            on success; optional for schema stability so a future error response
            can carry ``None`` without a breaking model change).
        detail: Human-readable French status detail.
    """

    ok: bool
    media_id: str
    journaled: bool
    quarantine_path: str | None = None
    detail: str = ""
