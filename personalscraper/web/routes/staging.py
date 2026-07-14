"""Staging read-model REST routes (webui-overhaul OBJ2A).

Two read-only endpoints under ``/api/staging/`` behind the ``require_session``
perimeter inherited from ``guarded_api`` (registration in ``app.py``; the auth
guard is never added per-route — web-ui.md §6, R14/R24):

- ``GET /media`` → :class:`StagingMediaResponse` — one item per staged media
  folder, enriched (NFO + matching + trailer/poster + per-media pipeline
  timeline), with pagination / sort / filter and aggregate filter counts.
- ``GET /media/{media_id}/poster`` → the local ``poster.jpg`` for a media,
  resolved from its stable id (never a client path).

Both are read-only and staging-safe (no ``require_not_staging`` / no
``X-Requested-With``): they read the staging tree + ``library.db`` and never
write, so the read-only staging web instance serves them unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from personalscraper.conf.models.config import Config
from personalscraper.logger import get_logger
from personalscraper.web.deps import require_not_staging, require_x_requested_with
from personalscraper.web.models.pipeline import PipelineState
from personalscraper.web.models.staging import (
    EnqueueDecisionRequest,
    EnqueueDecisionResponse,
    StagingCounts,
    StagingDispatchTarget,
    StagingMatch,
    StagingMediaItem,
    StagingMediaKind,
    StagingMediaResponse,
)
from personalscraper.web.staging.dispatch_preview import (
    build_free_space_by_id,
    preview_dispatch,
)
from personalscraper.web.staging.nfo import read_nfo_metadata
from personalscraper.web.staging.read_model import (
    _title_from_folder,
    _year_from_folder,
    find_nfo,
    poster_file_for,
    resolve_media_dir,
    resolve_other_item,
    resolve_scrapable_item,
    scan_staging_media,
)

router = APIRouter(prefix="/api/staging", tags=["staging"])
logger = get_logger(__name__)

#: Maximum page size accepted by the list endpoint.
_MAX_PAGE_SIZE = 200

#: Stage keys accepted by the ``stage`` filter (the eight Flow Board stages —
#: see ``web/staging/stages.py``, the single taxonomy source).
StageKeyFilter = Literal[
    "arrival",
    "sorting",
    "cleaning",
    "matching",
    "scraping",
    "trailers",
    "verify",
    "dispatch",
]

SortKey = Literal["recent", "title", "year", "size"]


def _config(request: Request) -> Config:
    """Return the loaded ``Config`` from application state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The ``Config`` on ``request.app.state.config``.
    """
    return cast(Config, request.app.state.config)


def _live_step(request: Request, db_path: Path) -> str | None:
    """Return the live pipeline run's current step name, or ``None``.

    Reuses the pipeline status builder so the staging timeline marks the same
    frontier stage ``active`` as the OBJ1 Flow Board. Fail-soft: any error
    yields ``None`` (no stage is marked active).

    Args:
        request: The incoming FastAPI request.
        db_path: Absolute path to ``library.db``.

    Returns:
        The current step name when a run is live, else ``None``.
    """
    from personalscraper.web.routes.pipeline import _build_status

    try:
        data_dir = _config(request).paths.data_dir
        status = _build_status(data_dir, db_path)
    except Exception as exc:  # noqa: BLE001 — status is advisory for the timeline
        logger.debug("staging_live_step_failed", error=str(exc))
        return None
    return status.step if status.state == PipelineState.running else None


def _compute_counts(items: list[StagingMediaItem]) -> StagingCounts:
    """Aggregate filter counts over the full (unpaginated) item set.

    Args:
        items: All scanned staged media items.

    Returns:
        The :class:`StagingCounts` chip totals.
    """
    counts = StagingCounts(total=len(items))
    for item in items:
        if item.match == "matched":
            counts.matched += 1
        elif item.match == "ambiguous":
            counts.ambiguous += 1
        else:
            counts.absent += 1
        if item.has_nfo:
            counts.scraped += 1
        if item.has_trailer:
            counts.with_trailer += 1
        if item.position_state == "blocked":
            counts.awaiting_action += 1
    return counts


def _matches_filters(
    item: StagingMediaItem,
    *,
    category: str | None,
    kind: StagingMediaKind | None,
    match: StagingMatch | None,
    stage: StageKeyFilter | None,
    query: str | None,
    missing_trailer: bool,
) -> bool:
    """Whether an item passes every active filter.

    Args:
        item: The candidate item.
        category: Staging subfolder filter, or ``None``.
        kind: Media-kind filter, or ``None``.
        match: Matching-verdict filter, or ``None``.
        stage: Keep only items whose single position is this stage (P0-A.1 —
            each item matches exactly one stage filter, never several).
        query: Case-insensitive title substring, or ``None``.
        missing_trailer: When ``True``, keep only items without a trailer file.

    Returns:
        ``True`` when the item satisfies all supplied filters.
    """
    if category is not None and item.category != category:
        return False
    if kind is not None and item.media_kind != kind:
        return False
    if match is not None and item.match != match:
        return False
    if query and query.casefold() not in item.title.casefold():
        return False
    if stage is not None and item.position_stage != stage:
        return False
    if missing_trailer and item.has_trailer:
        return False
    return True


def _sort_items(items: list[StagingMediaItem], sort: SortKey) -> None:
    """Sort items in place by the requested key.

    Args:
        items: The filtered items (mutated in place).
        sort: One of ``recent`` (newest mtime first), ``title`` (A→Z),
            ``year`` (newest first), ``size`` (largest first).
    """
    if sort == "title":
        items.sort(key=lambda i: i.title.casefold())
    elif sort == "year":
        items.sort(key=lambda i: (i.year is None, -(i.year or 0)))
    elif sort == "size":
        items.sort(key=lambda i: -i.size_bytes)
    else:  # recent
        items.sort(key=lambda i: (i.modified_at is None, -(i.modified_at or 0.0)))


def _dispatch_for_item(config: Config, item: StagingMediaItem, free: dict[str, float]) -> StagingDispatchTarget:
    """Compute the opt-in dispatch preview for one page item.

    Reconstructs the absolute media folder from ``staging_dir / relative_path``
    and reads the NFO ``<category>`` hint (only when scraped) for an accurate
    category, then delegates to :func:`preview_dispatch`.

    Args:
        config: The loaded config.
        item: The read-model item to preview.
        free: Free-space map (built once per request).

    Returns:
        The dispatch preview (``mode="unknown"`` on any resolution error).
    """
    media_dir = Path(config.paths.staging_dir) / item.relative_path
    category_hint: str | None = None
    if item.has_nfo:
        nfo_path = find_nfo(media_dir, item.media_kind)
        if nfo_path is not None:
            category_hint = read_nfo_metadata(nfo_path).category_id
    return preview_dispatch(
        config,
        media_kind=item.media_kind,
        media_dir=media_dir,
        category_hint=category_hint,
        size_bytes=item.size_bytes,
        free_space_by_id=free,
    )


@router.get("/media", response_model=StagingMediaResponse)
def list_staging_media(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_MAX_PAGE_SIZE),
    category: str | None = Query(None),
    kind: StagingMediaKind | None = Query(None),
    match: StagingMatch | None = Query(None),
    stage: StageKeyFilter | None = Query(None),
    sort: SortKey = Query("recent"),
    q: str | None = Query(None),
    missing_trailer: bool = Query(False),
    with_dispatch: bool = Query(False),
) -> StagingMediaResponse:
    """List staged media with pagination, sort, filters and aggregate counts.

    Scans the staging tree once, enriches each media folder, computes the filter
    chip counts over the full set, then applies the filters, sort and
    pagination. ``with_dispatch=true`` additionally computes a dispatch-target
    preview for the items on the returned page (a per-disk free-space + folder
    stat — off the hot path by default).

    All query params are OpenAPI-constrained (closed enums, bounded page size)
    so the typed frontend contract rejects an invalid value and the backend
    returns 422 rather than silently coercing.

    Args:
        request: The incoming FastAPI request.
        page: 1-indexed page number.
        page_size: Items per page (1..200).
        category: Filter by staging subfolder (e.g. ``"001-MOVIES"``).
        kind: Filter by media kind.
        match: Filter by matching verdict.
        stage: Keep items at/awaiting this timeline stage.
        sort: Sort key (default ``recent``).
        q: Case-insensitive title substring.
        missing_trailer: Keep only items lacking a trailer file (A1).
        with_dispatch: Compute the dispatch preview for the page items.

    Returns:
        A :class:`StagingMediaResponse` (page items, counts, total, page,
        page_size). Fail-soft: an empty/absent staging tree yields an empty
        list, never a 500.
    """
    config = _config(request)
    db_path = cast(Path, config.indexer.db_path)

    live_step = _live_step(request, db_path)
    all_items = scan_staging_media(config, db_path, live_step=live_step)

    counts = _compute_counts(all_items)

    filtered = [
        item
        for item in all_items
        if _matches_filters(
            item, category=category, kind=kind, match=match, stage=stage, query=q, missing_trailer=missing_trailer
        )
    ]
    _sort_items(filtered, sort)

    total = len(filtered)
    start = (page - 1) * page_size
    page_items = filtered[start : start + page_size]

    if with_dispatch and page_items:
        free = build_free_space_by_id(config)
        for item in page_items:
            item.dispatch_target = _dispatch_for_item(config, item, free)

    return StagingMediaResponse(
        items=page_items,
        counts=counts,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/media/{media_id}/poster")
def get_staging_poster(media_id: str, request: Request) -> FileResponse:
    """Serve the local poster image for a staged media, by its stable id.

    Re-derives the media folder from the id (matching freshly-computed ids, so
    a client can never inject a path) and returns its ``poster.jpg`` with the
    right image content-type.

    Args:
        media_id: The stable media id from a list item.
        request: The incoming FastAPI request.

    Returns:
        A :class:`FileResponse` streaming the poster file.

    Raises:
        404: No staged media matches the id, or it has no local poster.
    """
    config = _config(request)
    resolved = resolve_media_dir(config, media_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Media not found")
    _, media_dir = resolved
    poster = poster_file_for(media_dir)
    if poster is None:
        raise HTTPException(status_code=404, detail="No poster for this media")
    return FileResponse(str(poster))


def _reclass_other_item(config: Config, media_dir: Path, media_kind: str) -> Path:
    """Move an unsorted (AUTRES) item into the operator-chosen category.

    Reuses the sorter's move authority (:meth:`Sorter.reclass_item`) so the item is
    placed exactly as a normal sort would — cleaned to ``Title (Year)`` for movies —
    and later dispatches under the right on-disk name (dispatch derives the on-disk
    folder from the staging folder name, so a raw release name must not survive).

    Args:
        config: The loaded config (staging layout + paths).
        media_dir: The item's current folder under an ``other`` category.
        media_kind: The operator-chosen kind (``"movie"`` or ``"tvshow"``).

    Returns:
        The item's new folder path under the chosen category.

    Raises:
        HTTPException: 409 when the destination already exists, 500 on move failure.
    """
    from personalscraper.core.media_types import FileType
    from personalscraper.sorter.sorter import Sorter

    file_type = FileType.MOVIE if media_kind == "movie" else FileType.TVSHOW
    result = Sorter(config, dry_run=False).reclass_item(media_dir, config.paths.staging_dir, file_type)
    if result.status == "moved":
        return result.destination
    if result.status == "skipped":
        raise HTTPException(
            status_code=409,
            detail=f"A '{result.destination.name}' folder already exists in the target category",
        )
    raise HTTPException(status_code=500, detail=f"Could not reclass item: {result.message}")


@router.post(
    "/media/{media_id}/enqueue",
    response_model=EnqueueDecisionResponse,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def enqueue_staging_decision(
    media_id: str,
    request: Request,
    body: EnqueueDecisionRequest = Body(default_factory=EnqueueDecisionRequest),
) -> EnqueueDecisionResponse:
    """Enqueue a non-identified staged item as a pending scrape decision.

    Lets the operator send an item that never got a match (``absent`` — no search
    button otherwise) into the resolution deck, where the deck's manual search +
    validate resolves it (writing the NFO via the #3-fixed ``scrape-resolve``). The
    id is re-derived from the staging tree (no client path); only ``movie``/
    ``tvshow`` items qualify directly; an item in an ``other`` (unsorted / AUTRES)
    category qualifies too when *body* names the type the sort got wrong, and is
    physically reclassed into it. Idempotent: ``DecisionWriter.upsert`` refreshes an
    existing pending row and never overrides a resolved/dismissed verdict.

    Args:
        media_id: The stable media id from a list item.
        request: The incoming FastAPI request.
        body: Optional request body; its ``media_kind`` is required for an item in an
            ``other`` (AUTRES) category and ignored for movie/tvshow items.

    Returns:
        An :class:`EnqueueDecisionResponse`.

    Raises:
        400: The item is unsorted (AUTRES) and no ``media_kind`` was supplied.
        404: No scrapable staged media matches the id.
        409: The reclass destination already exists in the target category.
        503: No indexer DB configured.
    """
    config = _config(request)
    # Fail before any side effect: an AUTRES reclass below physically MOVES the
    # folder, so a missing DB must 503 BEFORE the move — otherwise the item is
    # orphaned out of 098-AUTRES with no decision row to show for it.
    db_path = config.indexer.db_path
    if db_path is None:
        raise HTTPException(status_code=503, detail="No indexer database configured")

    resolved = resolve_scrapable_item(config, media_id)
    if resolved is not None:
        media_dir, media_kind, title, year = resolved
    else:
        # The item may sit in an 'other' (unsorted / AUTRES) category the sort could
        # not type. It is resolvable only when the operator supplies the type the sort
        # got wrong (§3 safety net), and is then physically reclassed into that
        # category so it scrapes + dispatches under a clean name.
        other = resolve_other_item(config, media_id)
        if other is None:
            raise HTTPException(status_code=404, detail="No scrapable media matches this id")
        chosen = body.media_kind
        if chosen is None:
            raise HTTPException(
                status_code=400,
                detail="This item is unsorted (AUTRES); choose a type (movie/tvshow) to resolve it",
            )
        other_dir, title, year = other
        media_kind = chosen
        media_dir = _reclass_other_item(config, other_dir, media_kind)
        # The sorter just built the destination from its CLEANED title (raw
        # 'The.Wild.Robot.2024...-GRP' → 'The Wild Robot (2024)'), so derive the
        # search title/year from the reclassed folder name. Seeding the provider
        # search with the raw release name guarantees zero proposals — the exact
        # empty-deck §3 forbids (proven live on the Wild Robot fixture: raw name
        # → 0 candidates; cleaned name → real matches).
        cleaned_title = _title_from_folder(media_dir.name)
        cleaned_year = _year_from_folder(media_dir.name)
        if cleaned_title != media_dir.name or cleaned_year is not None:
            title = cleaned_title
            year = cleaned_year if cleaned_year is not None else year

    # §3 — seed candidates so the item enters the resolution deck WITH proposals,
    # never an empty shell. Reuse the very same provider matchers as
    # POST /api/decisions/{id}/search (one search path, not a second mechanism).
    # Fail-soft: a provider outage still enqueues the decision, but with
    # candidates_seeded=False so the UI shows an explicit "no automatic proposal"
    # state (+ prefilled manual search) instead of a silently empty grid.
    from personalscraper.web.decisions.search import ProviderSearchError, search_candidates

    candidates_seeded = False
    try:
        candidates = search_candidates(request, media_kind, title, year)
        candidates_seeded = True
    except ProviderSearchError as exc:
        logger.warning(
            "staging_enqueue_candidate_seed_failed",
            media_id=media_id,
            title=title,
            error=str(exc),
        )
        candidates = []
    candidates_json = json.dumps([c.model_dump() for c in candidates])

    from personalscraper.scraper.decision_writer import DecisionWriter

    decision_id = DecisionWriter(db_path).upsert(
        staging_path=media_dir,
        media_kind=media_kind,
        extracted_title=title,
        extracted_year=year,
        trigger="manual",
        candidates_json=candidates_json,
        run_uid=None,
        # Operator's explicit manual resolve: re-open the decision even if it was
        # previously resolved/dismissed (legacy item still non-identified) so it
        # re-enters the deck. The pipeline's automatic upsert keeps the F07 guard.
        reopen=True,
    )
    logger.info(
        "staging_enqueue_decision",
        media_id=media_id,
        title=title,
        media_kind=media_kind,
        candidates_count=len(candidates),
        candidates_seeded=candidates_seeded,
    )
    return EnqueueDecisionResponse(
        ok=True,
        media_kind=cast("StagingMediaKind", media_kind),
        title=title,
        decision_id=decision_id,
        candidates_count=len(candidates),
        candidates_seeded=candidates_seeded,
    )
