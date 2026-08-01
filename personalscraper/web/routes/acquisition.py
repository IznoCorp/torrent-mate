"""Acquisition REST routes (acq-watch feature).

Four GET endpoints + three mutating endpoints (POST/PATCH/DELETE) under
/api/acquisition/ exposing the followed-series list, wanted queue, seed
obligations, watcher status, and follow CRUD.  Fed by direct reads/writes of
the shared WAL acquire.db — NOT an event projection (unlike S6).

All routes are guarded by require_session inherited from the parent
guarded_api router (registration in app.py).  Auth dependencies are NOT
added per-route — the auth perimeter is a single dependency at registration
time, per docs/reference/web-ui.md §6 (the single authority for this
convention; R14/R24).

Reads open a FRESH read-only sqlite3 connection PER REQUEST — the store's
shared self._conn is not safe across FastAPI request threads (TestClient
threadpool + uvicorn workers → thread-affinity ProgrammingError).  This
mirrors pipeline.py's _build_status pattern.

Writes use ``build_acquire_store`` to create a fresh ConcreteAcquireStore per
request — its own connection, safe across threads.  Each mutating route also
carries ``require_not_staging`` (staging → 403) and
``require_x_requested_with`` (CSRF → 400) as per-route dependencies.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from personalscraper.acquire._provenance_store import STUCK_IDLE_SECONDS, provenance_row_is_stuck
from personalscraper.acquire.cadence import Cadence
from personalscraper.acquire.desired import cadence_from_config, cadence_from_json, effective_cadence
from personalscraper.acquire.domain import FollowedSeries
from personalscraper.acquire.metadata_enrich import FollowMetadata, enrich_follow_metadata
from personalscraper.acquire.store import build_acquire_store
from personalscraper.conf.models._ranking import RankingConfig
from personalscraper.core.identity import MediaRef
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.web.acquisition._helpers import (
    _backfill_from_indexer,
    _cadence_readout,
    _parse_json_dict,
    _parse_media_ref,
    _row_col,
)
from personalscraper.web.acquisition.obligation_titles import resolve_obligation_titles
from personalscraper.web.acquisition.runner import parse_prime_options
from personalscraper.web.acquisition.service import (
    _build_followed_item,
    _count_wanted_pending,
    _item_from_followed,
    _list_deferred_torrents,
    _query_watcher_recent_runs,
    resolve_series_tvdb,
    run_media_search,
    scoped_provider_clients,
)
from personalscraper.web.deps import require_not_staging, require_x_requested_with
from personalscraper.web.models.acquisition import (
    AcquisitionDownloadsResponse,
    AcquisitionStatusResponse,
    CompletenessResponse,
    CreateFollowRequest,
    FollowedResponse,
    FollowedSeriesItem,
    JourneyItem,
    JourneysResponse,
    MediaRefResponse,
    MediaSearchResponse,
    ObligationItem,
    ObligationsResponse,
    RankingPreviewRelease,
    RankingPreviewResponse,
    SeasonGrabResponse,
    UpdateFollowRequest,
    WantedItemResponse,
    WantedResponse,
)
from personalscraper.web.routes.acquisition_triggers import enqueue_prime_run, pid_is_alive

if TYPE_CHECKING:
    from personalscraper.acquire.store import ConcreteAcquireStore
    from personalscraper.api.tracker._base import TrackerResult

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])
logger = get_logger(__name__)

_MAX_PAGE_SIZE = 200


# ── helpers ────────────────────────────────────────────────────────────


def _write_follow_metadata(
    store: "ConcreteAcquireStore",
    followed_id: int,
    metadata: FollowMetadata,
) -> None:
    """Persist the card metadata of a follow (OBJ3 + acq-states §7).

    A no-op when nothing is known — which, since the server enriches, now means
    the client sent nothing AND no provider could answer.  Fail-soft: a DB error
    is logged and swallowed — the follow itself already succeeded, the metadata
    is a nicety.

    Routes the write through the acquire store's ``follow.merge_metadata``
    (single ``_write_tx`` BEGIN IMMEDIATE) rather than opening a raw connection,
    so the web layer never bypasses the store's single-writer discipline
    (ACQUIRE-09). Reuses the caller's already-open ``store`` — no second
    connection. The merge is additive: a field the enrichment could not resolve
    must not erase a value a previous add path already stored.

    Args:
        store: The already-open acquire store the caller owns.
        followed_id: The row to update.
        metadata: The resolved card metadata (client candidate + provider).
    """
    if metadata.is_empty:
        return
    try:
        store.follow.merge_metadata(
            followed_id,
            poster_url=metadata.poster_url,
            overview=metadata.overview,
            year=metadata.year,
        )
    except Exception:  # noqa: BLE001 — fail-soft: the follow already succeeded, metadata is a nicety
        logger.warning("acquisition_follow_metadata_write_failed", followed_id=followed_id, exc_info=True)


def _resolve_follow_metadata(request: Request, body: CreateFollowRequest, media_ref: MediaRef) -> FollowMetadata:
    """Resolve the card metadata for a create/reactivate, enriching what is missing.

    The client candidate wins; the providers are only consulted for the fields
    it left out, so a POST carrying a full candidate makes ZERO provider calls.
    Fail-soft end to end: a registry that cannot be built is logged at WARNING
    and the follow keeps whatever the client sent — the 201 is never at risk
    (plan §7 « Fail-soft, jamais bloquant »).

    BOUNDED WORST CASE (D1). These provider calls are SYNCHRONOUS inside the
    request, and the enrichment makes at most two lookups (primary provider,
    then the fallback). They used to run the pipeline's retry loop —
    ``max_attempts=4`` over a 10 s (TMDB) / 15 s (TVDB) timeout plus
    exponential-jitter backoff — so a host that accepted the TCP connection and
    never answered burned ~60-75 s per lookup and ~2 minutes for a two-source
    enrichment, worker thread held throughout. ``scoped_provider_clients``
    builds the registry with ``max_attempts=1`` (a construction seam, not a
    mutation of private policy state), which bounds the worst case to the sum
    of the two timeouts (~25 s), and closes the registry on the way out.

    Args:
        request: The incoming FastAPI request (carries config + settings).
        body: The create request, source of the client-supplied values.
        media_ref: The follow's provider IDs.

    Returns:
        The resolved :class:`FollowMetadata`.
    """
    known = FollowMetadata(poster_url=body.poster_url, overview=body.overview, year=body.year)
    if known.is_complete:
        return known
    try:
        with scoped_provider_clients(request) as (tmdb_client, tvdb_client):
            return enrich_follow_metadata(
                media_ref,
                body.kind,
                tmdb_client=tmdb_client,
                tvdb_client=tvdb_client,
                existing=known,
            )
    except Exception as exc:  # noqa: BLE001 — incl. the HTTPException(502) the builder raises
        # Fail-soft end to end (plan §7): the follow keeps whatever the client
        # sent. The registry is released by the context manager either way.
        logger.warning("acquisition_follow_enrich_registry_failed", error=str(exc))
        return known


# ── /api/acquisition/followed ──────────────────────────────────────────


@router.get("/followed", response_model=FollowedResponse)
def get_followed(
    request: Request,
    active: Literal["all", "active", "inactive"] = Query("active"),
) -> FollowedResponse:
    """List followed series, filtered by active status.

    Args:
        request: The incoming FastAPI request.
        active: Filter: ``"active"`` (default), ``"all"``, or ``"inactive"``.

    Returns:
        A ``FollowedResponse`` with the matching items.
    """
    from personalscraper.core.identity import MediaRef  # noqa: PLC0415 — route-local, avoids web-boot cost
    from personalscraper.indexer.ownership import IndexerOwnershipChecker  # noqa: PLC0415
    from personalscraper.web.acquisition.truth import (  # noqa: PLC0415
        FollowTruth,
        compute_follow_truth,
        compute_movie_truth,
    )
    from personalscraper.web.models.acquisition import MovieFacts  # noqa: PLC0415

    db_path = request.app.state.config.acquire.db_path
    if db_path is None or not Path(db_path).exists():
        return FollowedResponse(items=[])

    # The library ownership checker holds a live library.db connection; open it
    # lazily (only when a row has a usable provider ref) and close it in the
    # finally so it never leaks — films now open it far more often than the
    # former shows-only path did.
    ownership_checker: IndexerOwnershipChecker | None = None
    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row

            if active == "inactive":
                rows = conn.execute("SELECT * FROM followed_series WHERE active = 0 ORDER BY id").fetchall()
            elif active == "all":
                rows = conn.execute("SELECT * FROM followed_series ORDER BY id").fetchall()
            else:
                rows = conn.execute("SELECT * FROM followed_series WHERE active = 1 ORDER BY id").fetchall()

            indexer_db_path = request.app.state.config.indexer.db_path

            # Cadence readout (OBJ3): resolve the global default once and batch the
            # pending wanted timings per series, so the next-search estimate + the
            # governing tier cost a single extra query for the whole list.
            now = int(time.time())
            try:
                global_cadence: Cadence | None = cadence_from_config(request.app.state.config.acquire.cadence)
            except (ValueError, AttributeError):  # a malformed cadence config must not 500 the list
                global_cadence = None
            timings_by_series: dict[int, list[tuple[int, int | None]]] = {}
            if global_cadence is not None:
                for w in conn.execute(
                    "SELECT followed_id, enqueued_at, last_search_at FROM wanted "
                    "WHERE followed_id IS NOT NULL AND status IN ('pending', 'searching')"
                ).fetchall():
                    last = None if w["last_search_at"] is None else int(w["last_search_at"])
                    timings_by_series.setdefault(int(w["followed_id"]), []).append((int(w["enqueued_at"]), last))

            # Batched lookup of in-flight priming runs — one query, never N+1.
            # An open prime run overrides the card status to
            # ``verification_en_cours``, so the predicate MUST be the one
            # ``_has_live_run`` applies: un-ended AND pid-alive. ``ended_at IS
            # NULL`` alone is not liveness — a runner that crashed never gets to
            # write ``ended_at``, so its row stays open forever and pinned the
            # card on « vérification en cours » for a process that died days
            # ago, while the 409 guard reading the same row let the action
            # through. The liveness check itself goes through the SINGLE
            # authority (:func:`pid_is_alive`), applied in one pass over the
            # handful of open prime rows the batched query returns.
            #
            # Parse the options_json through the single authority
            # (prime_options_json / parse_prime_options in the runner module) so
            # a reader can never interpret a row differently from how the writer
            # built it.
            #
            # This predicate is index-backed since indexer migration 016:
            # ``idx_pipeline_run_open_command ON pipeline_run (command) WHERE
            # ended_at IS NULL``. Partial on purpose — open runs are a handful
            # at any instant, so the index stays tiny however large this
            # append-only table gets, and a row leaves it the moment ended_at is
            # stamped (negligible write cost). Before it, every /followed render
            # walked the whole table.
            priming_follow_ids: set[int] = set()
            if indexer_db_path is not None and indexer_db_path.exists():
                try:
                    with closing(sqlite3.connect(str(indexer_db_path))) as idx_conn:
                        apply_pragmas(idx_conn)
                        idx_conn.row_factory = sqlite3.Row
                        open_primes = idx_conn.execute(
                            "SELECT pid, options_json FROM pipeline_run "
                            "WHERE command = 'prime' AND ended_at IS NULL AND pid IS NOT NULL"
                        ).fetchall()
                    for pr in open_primes:
                        if not pid_is_alive(pr["pid"]):
                            continue  # crashed runner → stale row, not a live verification
                        fid = parse_prime_options(pr["options_json"])
                        if fid is not None:
                            priming_follow_ids.add(fid)
                except sqlite3.Error:
                    logger.warning("acquisition_priming_lookup_failed", exc_info=True)

            items: list[FollowedSeriesItem] = []
            for row in rows:
                # COUNT wanted pending for this series.
                pending = conn.execute(
                    "SELECT COUNT(*) FROM wanted WHERE followed_id = ? AND status IN ('pending', 'searching')",
                    (row["id"],),
                ).fetchone()[0]
                # COUNT grabbed — the §5 "en cours d'acquisition" window (torrent
                # spotted → pipeline finished) that drives the film card status.
                grabbed = conn.execute(
                    "SELECT COUNT(*) FROM wanted WHERE followed_id = ? AND status = 'grabbed'",
                    (row["id"],),
                ).fetchone()[0]

                # Card metadata (OBJ3): cached columns first; year + season_count
                # backfilled from the indexer when the cache is empty.
                media_ref = _parse_media_ref(row["media_ref_json"])
                poster_url = cast("str | None", _row_col(row, "poster_url"))
                overview = cast("str | None", _row_col(row, "overview"))
                year = cast("int | None", _row_col(row, "year"))
                season_count = cast("int | None", _row_col(row, "season_count"))
                if year is None or season_count is None:
                    bf_year, bf_seasons = _backfill_from_indexer(indexer_db_path, media_ref.tvdb_id, media_ref.tmdb_id)
                    if year is None:
                        year = bf_year
                    if season_count is None:
                        season_count = bf_seasons

                # Next-search estimate + governing tier from the series' pending items.
                next_due: float | None = None
                cadence_tier: str | None = None
                if global_cadence is not None:
                    effective = effective_cadence(cadence_from_json(row["cadence_json"]), global_cadence)
                    next_due, cadence_tier = _cadence_readout(timings_by_series.get(row["id"], []), effective, now)

                # Five-state facts (acq-states phase 4): ownership (real disk
                # presence by provider ID) × the wanted queue × the last search
                # verdict — the card status derives from these facts, never from
                # a raw wanted counter. Shows cross the aired catalog into
                # per-state counts; films (D2-B) are a catalog of one and carry
                # their single unit's facts instead.
                truth = FollowTruth()
                movie_facts: MovieFacts | None = None
                kind = cast("str", _row_col(row, "kind")) or "show"
                try:
                    core_ref: MediaRef | None = MediaRef(
                        tvdb_id=media_ref.tvdb_id, tmdb_id=media_ref.tmdb_id, imdb_id=media_ref.imdb_id
                    )
                except ValueError:  # a ref-less legacy row cannot be looked up
                    core_ref = None
                if core_ref is not None:
                    if ownership_checker is None:
                        ownership_checker = IndexerOwnershipChecker(Path(indexer_db_path))
                    if kind == "movie":
                        movie_facts = compute_movie_truth(
                            conn, ownership_checker, followed_id=row["id"], media_ref=core_ref
                        )
                    else:
                        truth = compute_follow_truth(conn, ownership_checker, followed_id=row["id"], media_ref=core_ref)

                items.append(
                    FollowedSeriesItem(
                        id=row["id"],
                        title=row["title"],
                        media_ref=media_ref,
                        active=bool(row["active"]),
                        kind=kind,
                        cadence=_parse_json_dict(row["cadence_json"]),
                        added_at=float(row["added_at"]),
                        wanted_pending=pending,
                        wanted_grabbed=grabbed,
                        quality_profile=_parse_json_dict(row["quality_profile_json"]),
                        poster_url=poster_url,
                        overview=overview,
                        year=year,
                        season_count=season_count,
                        next_search_at=next_due,
                        cadence_tier=cadence_tier,
                        aired_count=truth.aired_count,
                        owned_count=truth.owned_count,
                        a_recuperer_count=truth.a_recuperer_count,
                        en_acquisition_count=truth.en_acquisition_count,
                        en_attente_count=truth.en_attente_count,
                        non_verifie_count=truth.non_verifie_count,
                        movie_facts=movie_facts,
                        priming_running=row["id"] in priming_follow_ids,
                    )
                )
            return FollowedResponse(items=items)
    except sqlite3.Error:
        logger.warning("acquisition_followed_read_failed", exc_info=True)
        return FollowedResponse(items=[])
    finally:
        if ownership_checker is not None:
            ownership_checker.close()


# ── /api/acquisition/followed/{id}/completeness ────────────────────────


@router.get("/followed/{followed_id}/completeness", response_model=CompletenessResponse)
def get_followed_completeness(request: Request, followed_id: int) -> CompletenessResponse:
    """Per-season / per-episode completeness for one followed series (§5).

    Read-only: crosses the detect-written aired catalog, the library (ownership
    by provider id) and the wanted queue into one honest matrix — "ce qui est
    déjà sorti vs ce qui est en médiathèque". No provider is polled here: the
    catalog comes from the cache alone, so this panel and the followed card read
    the same facts through the same derivation and can never disagree
    (acq-states phase 5). A follow with no cached catalog yields empty seasons
    and ``source="unknown"`` rather than a fabricated all-missing grid.

    Args:
        request: The incoming FastAPI request.
        followed_id: The ``followed_series`` rowid.

    Returns:
        The :class:`CompletenessResponse`.

    Raises:
        HTTPException: 404 when the follow is unknown.
    """
    from personalscraper.core.ownership import NullOwnershipChecker
    from personalscraper.indexer.ownership import IndexerOwnershipChecker
    from personalscraper.web.acquisition.completeness import compute_completeness

    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        followed = store.follow.get(followed_id)
        if followed is None:
            raise HTTPException(status_code=404, detail="Followed series not found")

        # No provider registry is built any more: the catalog is read from the
        # cache, so this route makes ZERO provider calls (NE-DOIT-PAS-8) and no
        # longer fails 502 on a registry construction problem.
        indexer_db = config.indexer.db_path
        checker = IndexerOwnershipChecker(Path(indexer_db)) if indexer_db is not None else NullOwnershipChecker()
        try:
            return compute_completeness(followed, ownership=checker, store=store)
        finally:
            if isinstance(checker, IndexerOwnershipChecker):
                checker.close()
    finally:
        store.close()


# ── /api/acquisition/wanted ────────────────────────────────────────────


_WANTED_STATUSES = Literal["all", "pending", "searching", "grabbed", "done", "abandoned"]


@router.get("/wanted", response_model=WantedResponse)
def get_wanted(
    request: Request,
    status: _WANTED_STATUSES = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_MAX_PAGE_SIZE),
) -> WantedResponse:
    """List wanted items, paginated, with optional status filter.

    Args:
        request: The incoming FastAPI request.
        status: Filter by wanted status (default ``"all"``).
        page: Page number (1-based, default 1).
        page_size: Items per page (1–200, default 50).

    Returns:
        A ``WantedResponse`` with the matching items + pagination metadata.
    """
    db_path = request.app.state.config.acquire.db_path
    if db_path is None or not Path(db_path).exists():
        return WantedResponse(items=[], total=0, page=page, page_size=page_size)

    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row

            # Build WHERE clause.
            where = ""
            params: list[str | int] = []
            if status != "all":
                where = "WHERE w.status = ?"
                params.append(status)

            # Count total.
            total = conn.execute(f"SELECT COUNT(*) FROM wanted w {where}", params).fetchone()[0]

            # Fetch page.
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"""
                SELECT w.*, fs.title AS fs_title
                FROM wanted w
                LEFT JOIN followed_series fs ON w.followed_id = fs.id
                {where}
                ORDER BY w.enqueued_at DESC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            ).fetchall()

            items: list[WantedItemResponse] = []
            for row in rows:
                items.append(
                    WantedItemResponse(
                        id=row["id"],
                        title=row["fs_title"] or "",
                        kind=row["kind"],
                        season=row["season"],
                        episode=row["episode"],
                        status=row["status"],
                        attempts=row["attempts"],
                        enqueued_at=float(row["enqueued_at"]),
                        last_search_at=(float(row["last_search_at"]) if row["last_search_at"] is not None else None),
                    )
                )
            return WantedResponse(items=items, total=total, page=page, page_size=page_size)
    except sqlite3.Error:
        logger.warning("acquisition_wanted_read_failed", exc_info=True)
        return WantedResponse(items=[], total=0, page=page, page_size=page_size)


# ── /api/acquisition/obligations ───────────────────────────────────────


_ObligationStatusFilter = Literal["all", "pending", "breached", "satisfied"]


@router.get("/obligations", response_model=ObligationsResponse)
def get_obligations(
    request: Request,
    status: _ObligationStatusFilter = Query("all"),
) -> ObligationsResponse:
    """List seed obligations with their current ratio state.

    Args:
        request: The incoming FastAPI request.
        status: Filter: ``"all"`` (default), ``"pending"``, ``"breached"``,
            or ``"satisfied"``.

    Returns:
        An ``ObligationsResponse`` with matching items.  Each item LEFT JOINs
        ``ratio_state`` on tracker name.
    """
    db_path = request.app.state.config.acquire.db_path
    if db_path is None or not Path(db_path).exists():
        return ObligationsResponse(items=[])

    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row

            where = ""
            params: list[str | int] = []
            if status == "pending":
                where = "WHERE so.satisfied_at IS NULL AND so.breached_at IS NULL"
            elif status == "breached":
                where = "WHERE so.breached_at IS NOT NULL"
            elif status == "satisfied":
                where = "WHERE so.satisfied_at IS NOT NULL"

            rows = conn.execute(
                f"""
                SELECT so.*, rs.observed_ratio, rs.accumulated_seed_time_s,
                       rs.hnr_count
                FROM seed_obligation so
                LEFT JOIN ratio_state rs ON so.source_tracker = rs.tracker_name
                {where}
                ORDER BY so.added_at DESC
                """,
                params,
            ).fetchall()

            items: list[ObligationItem] = []
            for row in rows:
                items.append(
                    ObligationItem(
                        info_hash=row["info_hash"],
                        source_tracker=row["source_tracker"],
                        dispatched_path=row["dispatched_path"],
                        min_seed_time_s=row["min_seed_time_s"],
                        min_ratio=float(row["min_ratio"]),
                        added_at=float(row["added_at"]),
                        satisfied_at=(float(row["satisfied_at"]) if row["satisfied_at"] is not None else None),
                        breached_at=(float(row["breached_at"]) if row["breached_at"] is not None else None),
                        released_at=(float(row["released_at"]) if row["released_at"] is not None else None),
                        observed_ratio=(float(row["observed_ratio"]) if row["observed_ratio"] is not None else None),
                        accumulated_seed_time_s=(
                            row["accumulated_seed_time_s"] if row["accumulated_seed_time_s"] is not None else None
                        ),
                        hnr_count=(row["hnr_count"] if row["hnr_count"] is not None else None),
                    )
                )
            try:
                resolve_obligation_titles(items, conn)
            except Exception:
                logger.warning("obligation_title_resolve_failed", exc_info=True)
            return ObligationsResponse(items=items)
    except sqlite3.Error:
        logger.warning("acquisition_obligations_read_failed", exc_info=True)
        return ObligationsResponse(items=[])


# ── /api/acquisition/status ────────────────────────────────────────────


@router.get("/status", response_model=AcquisitionStatusResponse)
def get_acquisition_status(request: Request) -> AcquisitionStatusResponse:
    """Return the watcher status and recent watcher-triggered runs.

    Args:
        request: The incoming FastAPI request.

    Returns:
        An ``AcquisitionStatusResponse`` with watcher enabled state, last
        successful run timestamp, and recent runs.
    """
    config = request.app.state.config
    acquire_path = config.acquire.db_path
    data_dir = config.paths.data_dir

    # watcher_enabled: NOT the watcher.paused sentinel.
    watcher_enabled = not (data_dir / "watcher.paused").exists()

    # last_successful_run_at: from watch_state KV in acquire.db.
    last_successful_run_at: float | None = None
    if acquire_path is not None and acquire_path.exists():
        try:
            with closing(sqlite3.connect(str(acquire_path))) as conn:
                apply_pragmas(conn)
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT value FROM watch_state WHERE key = ?",
                    ("last_successful_run_at",),
                ).fetchone()
                if row is not None:
                    last_successful_run_at = float(row["value"])
        except sqlite3.Error:
            logger.warning("acquisition_status_watch_state_failed", exc_info=True)

    # recent_runs: from library.db.
    indexer_path = config.indexer.db_path
    recent_runs = _query_watcher_recent_runs(indexer_path)

    return AcquisitionStatusResponse(
        last_successful_run_at=last_successful_run_at,
        watcher_enabled=watcher_enabled,
        recent_runs=recent_runs,
        deferred=_list_deferred_torrents(config),
    )


@router.get("/downloads", response_model=AcquisitionDownloadsResponse)
def get_acquisition_downloads(request: Request) -> AcquisitionDownloadsResponse:
    """List the live progress of every grabbed torrent (Phase 5 A4).

    Read-only + fail-soft (see :func:`list_active_downloads`): a torrent-client
    outage degrades to ``client_available=False``, never a 500.

    Args:
        request: The incoming FastAPI request.

    Returns:
        An :class:`AcquisitionDownloadsResponse`.
    """
    from personalscraper.web.acquisition.downloads import list_active_downloads

    return list_active_downloads(request.app.state.config)


# ── ranking preview (ranking editor, #18) ─────────────────────────────────


def _ranking_preview_samples() -> list["TrackerResult"]:
    """Build the fixed, representative release sample set for the ranking preview.

    Six synthetic releases spanning every scored axis (resolution, codec,
    language, source, provider, seeders, freeleech) so the operator sees a
    weight/value change reorder visible rows without running a real search.
    Fields are set explicitly (as the trackers would after title-parsing), so
    the preview scores exactly what a real grab would.
    """
    from personalscraper.api._units import ByteSize
    from personalscraper.api.tracker._base import TrackerResult

    return [
        TrackerResult(
            provider="tr4ker",
            tracker_id="s1",
            title="Sample.2024.MULTi.2160p.UHD.BluRay.x265 — tr4ker",
            size=ByteSize(15_000_000_000),
            seeders=40,
            leechers=2,
            is_freeleech=True,
            resolution="2160p",
            codec="x265",
            source="BluRay",
            language="MULTI",
        ),
        TrackerResult(
            provider="tr4ker",
            tracker_id="s2",
            title="Sample.2024.MULTi.1080p.WEB-DL.x265 — tr4ker",
            size=ByteSize(4_500_000_000),
            seeders=120,
            leechers=5,
            is_freeleech=True,
            resolution="1080p",
            codec="x265",
            source="WEB-DL",
            language="MULTI",
        ),
        TrackerResult(
            provider="c411",
            tracker_id="s3",
            title="Sample.2024.VFF.1080p.WEB-DL.x264 — c411",
            size=ByteSize(4_000_000_000),
            seeders=60,
            leechers=3,
            resolution="1080p",
            codec="x264",
            source="WEB-DL",
            language="VFF",
        ),
        TrackerResult(
            provider="c411",
            tracker_id="s4",
            title="Sample.2024.TRUEFRENCH.1080p.BluRay.x265 — c411",
            size=ByteSize(8_000_000_000),
            seeders=8,
            leechers=1,
            resolution="1080p",
            codec="x265",
            source="BluRay",
            language="TRUEFRENCH",
        ),
        TrackerResult(
            provider="lacale",
            tracker_id="s5",
            title="Sample.2024.VOSTFR.720p.HDTV.x264 — lacale",
            size=ByteSize(1_500_000_000),
            seeders=15,
            leechers=0,
            resolution="720p",
            codec="x264",
            source="HDTV",
            language="VOSTFR",
        ),
        TrackerResult(
            provider="lacale",
            tracker_id="s6",
            title="Sample.2024.MULTi.2160p.BluRay.x265 — lacale (low seed)",
            size=ByteSize(16_000_000_000),
            seeders=3,
            leechers=0,
            resolution="2160p",
            codec="x265",
            source="BluRay",
            language="MULTI",
        ),
        # ── 6 new samples (ticket 374) ──────────────────────────────
        TrackerResult(
            provider="tr4ker",
            tracker_id="s7",
            title="Demo.2025.TRUEFRENCH.2160p.REMUX.BluRay.x265 — tr4ker",
            size=ByteSize(52_000_000_000),
            seeders=200,
            leechers=10,
            resolution="2160p",
            codec="x265",
            source="BluRay",
            language="TRUEFRENCH",
        ),
        TrackerResult(
            provider="tr4ker",
            tracker_id="s8",
            title="Demo.S01.FRENCH.1080p.WEB-DL.x264 Season.Pack — tr4ker",
            size=ByteSize(80_000_000_000),
            seeders=25,
            leechers=6,
            is_freeleech=True,
            resolution="1080p",
            codec="x264",
            source="WEB-DL",
            language="FRENCH",
        ),
        TrackerResult(
            provider="c411",
            tracker_id="s9",
            title="Demo.2025.VOSTFR.1080p.WEB-DL.x265 — c411 (leech trap)",
            size=ByteSize(5_000_000_000),
            seeders=2,
            leechers=15,
            resolution="1080p",
            codec="x265",
            source="WEB-DL",
            language="VOSTFR",
        ),
        TrackerResult(
            provider="c411",
            tracker_id="s10",
            title="Demo.2025.VFF.720p.HDTV.x264 — c411",
            size=ByteSize(2_200_000_000),
            seeders=4,
            leechers=1,
            resolution="720p",
            codec="x264",
            source="HDTV",
            language="VFF",
        ),
        TrackerResult(
            provider="tr4ker",
            tracker_id="s11",
            title="Demo.2025.MULTi.2160p.WEB-DL.x265 — tr4ker",
            size=ByteSize(12_000_000_000),
            seeders=35,
            leechers=8,
            is_freeleech=True,
            resolution="2160p",
            codec="x265",
            source="WEB-DL",
            language="MULTI",
        ),
        TrackerResult(
            provider="c411",
            tracker_id="s12",
            title="Demo.2025.VOSTFR.2160p.BluRay.x265 — c411 (FL low seed)",
            size=ByteSize(18_000_000_000),
            seeders=5,
            leechers=0,
            is_freeleech=True,
            resolution="2160p",
            codec="x265",
            source="BluRay",
            language="VOSTFR",
        ),
    ]


@router.post("/ranking/preview", response_model=RankingPreviewResponse)
def preview_ranking(body: RankingConfig) -> RankingPreviewResponse:
    """Score the representative sample set under a candidate ranking (#18).

    Read-only + pure: no DB, no filesystem, no torrent client — it scores the
    fixed :func:`_ranking_preview_samples` set with the POSTed candidate config
    so the editor can render a live preview of the acquisition ranking. To keep
    every sample VISIBLE (a live preview must never silently drop rows), scoring
    runs with ``min_seeders`` neutralized; each row is instead flagged
    ``excluded`` when its seeders fall below the candidate ``min_seeders`` — so
    the operator SEES which releases the real ``rank()`` would drop. Rows sort
    non-excluded first (by score desc), excluded last.

    Not staging-guarded and no CSRF header: it mutates nothing, so it is safe
    on the read-only staging role and idempotent by construction.

    Args:
        body: The candidate ranking configuration to score with.

    Returns:
        A :class:`RankingPreviewResponse` with the scored, sorted samples.
    """
    from personalscraper.api.tracker._ranking import rank

    samples = _ranking_preview_samples()
    # Neutralize the seeder floor so EVERY sample is scored and shown; flag the
    # ones the real min_seeders would have dropped rather than hiding them.
    scored = rank(samples, body.model_copy(update={"min_seeders": 0}))
    rows = [
        RankingPreviewRelease(
            title=result.title,
            provider=str(result.provider),
            resolution=result.resolution,
            codec=result.codec,
            language=result.language,
            source=result.source,
            seeders=result.seeders,
            leechers=result.leechers,
            is_freeleech=result.is_freeleech,
            score=score,
            excluded=result.seeders < body.min_seeders,
        )
        for result, score in scored
    ]
    # Excluded rows sink to the end; within each group keep the score order.
    rows.sort(key=lambda r: (r.excluded, -r.score))
    # known_trackers: the hardcoded factory roster minus lacale (deprecated).
    # No torznab generic engine key exists in _TRACKER_CLASSES (ticket 374 check).
    from personalscraper.api.tracker._factory import _TRACKER_CLASSES

    known = sorted(k for k in _TRACKER_CLASSES if k != "lacale")
    return RankingPreviewResponse(ranked=rows, known_trackers=known)


# ── provenance journeys (« parcours » — F1) ───────────────────────────────


def _journey_media_ref(ref: "MediaRef | None") -> MediaRefResponse:
    """Convert a provenance MediaRef to the API response shape (empty when None)."""
    if ref is None:
        return MediaRefResponse()
    return MediaRefResponse(tvdb_id=ref.tvdb_id, tmdb_id=ref.tmdb_id, imdb_id=ref.imdb_id)


@router.get("/journeys", response_model=JourneysResponse)
def get_journeys(
    request: Request,
    run_uid: str | None = Query(default=None, description="Filter to acquisitions a given pipeline run touched (F3)."),
) -> JourneysResponse:
    """List each acquisition's pipeline journey from the provenance registry (F1/F3).

    Read-only: opens a fresh acquire store per request (like the other acquisition
    routes), reads the provenance journeys (most-recent first), and joins each row's
    follow title so the « Parcours » view is human-readable. When *run_uid* is given
    (F3 converse view), returns only the acquisitions that run advanced at any stage —
    « quelles acquisitions ce run a-t-il traitées ? ». The provenance READ is fail-soft
    (an empty list on a query error); a store open/migration failure surfaces as a 500,
    consistent with every other ``build_acquire_store`` route.

    Args:
        request: The incoming FastAPI request.
        run_uid: Optional pipeline-run hex id — restrict to that run's acquisitions.

    Returns:
        A :class:`JourneysResponse` — the acquisition journeys, most-recent first.
    """
    store = build_acquire_store(request.app.state.config.acquire)
    try:
        rows = store.provenance.list_journeys_for_run(run_uid) if run_uid else store.provenance.list_journeys()
        now = int(time.time())
        title_cache: dict[int, str | None] = {}
        items: list[JourneyItem] = []
        for row in rows:
            # F4: flag a stuck in-flight item (folder still on disk, idle past the horizon).
            stuck = provenance_row_is_stuck(row, now=now, idle_seconds=STUCK_IDLE_SECONDS, exists_fn=os.path.exists)
            follow_title: str | None = None
            if row.followed_id is not None:
                if row.followed_id not in title_cache:
                    follow = store.follow.get(row.followed_id)
                    title_cache[row.followed_id] = follow.title if follow is not None else None
                follow_title = title_cache[row.followed_id]
            items.append(
                JourneyItem(
                    info_hash=row.info_hash,
                    kind=row.kind,
                    media_ref=_journey_media_ref(row.media_ref),
                    scraped_ref=_journey_media_ref(row.scraped_ref) if row.scraped_ref is not None else None,
                    followed_id=row.followed_id,
                    follow_title=follow_title,
                    status=row.status,
                    ingest_path=row.ingest_path,
                    current_path=row.current_path,
                    dispatch_path=row.dispatch_path,
                    grabbed_at=row.grabbed_at,
                    ingested_at=row.ingested_at,
                    scraped_at=row.scraped_at,
                    dispatched_at=row.dispatched_at,
                    resolution_state=row.resolution_state,
                    decision_id=row.decision_id,
                    resolution_trigger=row.resolution_trigger,
                    grab_run_uid=row.grab_run_uid,
                    ingest_run_uid=row.ingest_run_uid,
                    scrape_run_uid=row.scrape_run_uid,
                    dispatch_run_uid=row.dispatch_run_uid,
                    stuck=stuck,
                )
            )
        return JourneysResponse(journeys=items)
    finally:
        store.close()


# ── media search (add-by-search, OBJ3) ───────────────────────────────────


@router.get("/search", response_model=MediaSearchResponse)
def search_media(
    request: Request,
    q: str = Query(..., min_length=1, description="Title to search for."),
    kind: Literal["movie", "tv"] | None = Query(
        default=None,
        description="Restrict to movies or TV; omit to search both.",
    ),
) -> MediaSearchResponse:
    """Search live providers for media to follow (add-by-search, OBJ3).

    Read-only: builds per-request provider clients and delegates to the same
    detailed confidence matchers the decisions search uses, tagging each result
    with its ``kind``. Results are merged across the requested kind(s) and
    sorted best-score-first.

    Args:
        request: The incoming FastAPI request.
        q: The title to search for.
        kind: Optional ``"movie"``/``"tv"`` restriction (both when omitted).

    Returns:
        A :class:`MediaSearchResponse` with the scored matches.

    Raises:
        HTTPException: 502 on provider registry build or provider API failure.
    """
    with scoped_provider_clients(request) as (tmdb_client, tvdb_client):
        return run_media_search(request, tmdb_client, tvdb_client, q, kind)


@router.post(
    "/followed",
    status_code=201,
    response_model=FollowedSeriesItem,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def create_follow(request: Request, body: CreateFollowRequest) -> FollowedSeriesItem:
    """Follow a new series (or reactivate an inactive one).

    Args:
        request: The incoming FastAPI request.
        body: The parsed :class:`CreateFollowRequest`.

    Returns:
        The created or reactivated :class:`FollowedSeriesItem`.

    Raises:
        HTTPException: 409 if the series is already actively followed.
    """
    config = request.app.state.config
    media_ref = MediaRef(
        tvdb_id=body.tvdb_id,
        tmdb_id=body.tmdb_id,
        imdb_id=body.imdb_id,
    )
    title = body.title or ""

    store = build_acquire_store(config.acquire)
    try:
        existing = store.follow.find_by_ref(media_ref)
        if existing is not None:
            assert existing.id is not None  # noqa: S101 — find_by_ref always sets id
            if existing.active:
                raise HTTPException(
                    status_code=409,
                    detail="Series is already followed (active=True)",
                )
            # Reactivate — matched by PRIMARY provider id (find_by_ref is more
            # lenient than the exact-media_ref_json upsert), and REFRESH the kind
            # so a re-follow of a film once followed as a series lands
            # kind='movie', not the stale 'show' (§5 — else its lifecycle stays
            # series-shaped and no movie wanted row is ever produced).
            store.follow.set_active(existing.id, True)
            store.follow.set_kind(existing.id, body.kind)
            # Reactivation backfills too: a follow paused before the server
            # enriched anything must not stay posterless just because it is old.
            metadata = _resolve_follow_metadata(request, body, media_ref)
            _write_follow_metadata(store, existing.id, metadata)
            # Reactivating re-primes: the catalog and the queue are as stale as
            # they were the day the follow was paused (plan §6 idempotence).
            prime_outcome = enqueue_prime_run(config.indexer.db_path, existing.id)
            reactivated = store.follow.get(existing.id)
            assert reactivated is not None  # noqa: S101 — just wrote it
            item = _item_from_followed(reactivated)
            item.poster_url = metadata.poster_url
            item.overview = metadata.overview
            item.year = metadata.year
            if prime_outcome in ("spawned", "already_running"):
                item.priming_running = True
            return item

        # A series followed by TMDB/IMDB alone has no tvdb_id, but episode
        # detection (poll_known) needs one — resolve it now so the follow is
        # detectable, keeping TVDB the detection primary. Films use the §5 title
        # lifecycle and never need a TVDB id. Fail-soft NON silencieux (§méthode):
        # if unresolved, follow anyway but flag it so the UI warns.
        # A series followed by TMDB/IMDB alone has no tvdb_id, but episode
        # detection needs one — resolve it now so the follow is detectable. When
        # unresolved, the follow is still created; ``tvdb_unresolved`` is DERIVED
        # from the stored state by the item builder (honest on every surface),
        # so nothing is set here beyond upgrading media_ref on success.
        if body.kind == "show" and media_ref.tvdb_id is None:
            resolved_tvdb: int | None = None
            try:
                with scoped_provider_clients(request) as (tmdb_client, _tvdb_client):
                    resolved_tvdb = resolve_series_tvdb(media_ref, tmdb_client)
            except Exception as exc:  # noqa: BLE001 — incl. the 502 the builder raises
                # A registry that cannot be built must not 500 the follow — mirror
                # _resolve_follow_metadata's fail-soft contract (§7).
                logger.warning("acquisition_follow_tvdb_registry_failed", error=str(exc))
            if resolved_tvdb is not None:
                media_ref = MediaRef(
                    tvdb_id=resolved_tvdb,
                    tmdb_id=media_ref.tmdb_id,
                    imdb_id=media_ref.imdb_id,
                )

        # New follow. The kind ('movie'|'show') starts the §5 film lifecycle:
        # detect will produce one movie wanted row and auto-unfollow once acquired.
        series = FollowedSeries(
            media_ref=media_ref,
            title=title,
            added_at=int(time.time()),
            active=True,
            kind=body.kind,
        )
        new_id = store.follow.add(series)
        created = store.follow.get(new_id)
        assert created is not None  # noqa: S101 — just inserted it
        # Persist + echo the card metadata: the search candidate when the client
        # supplied one, otherwise fetched from the provider by ID (§7 RC3 — the
        # by-ID add form sends no poster, and the card stayed blank forever).
        metadata = _resolve_follow_metadata(request, body, media_ref)
        _write_follow_metadata(store, new_id, metadata)
        # Amorce: catalog + queue + first search run NOW, through the existing
        # run authority — a fresh follow is never left idle until the 03:00
        # cron (the founding incident: a grab over an empty queue, rc=0).
        prime_outcome = enqueue_prime_run(config.indexer.db_path, new_id)
        item = _item_from_followed(created)
        item.poster_url = metadata.poster_url
        item.overview = metadata.overview
        item.year = metadata.year
        if prime_outcome in ("spawned", "already_running"):
            item.priming_running = True
        return item
    finally:
        store.close()


@router.patch(
    "/followed/{followed_id}",
    response_model=FollowedSeriesItem,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def update_follow(
    request: Request,
    followed_id: int,
    body: UpdateFollowRequest,
) -> FollowedSeriesItem:
    """Update the active flag or cadence for a followed series.

    Args:
        request: The incoming FastAPI request.
        followed_id: Rowid of the ``followed_series`` row.
        body: The parsed :class:`UpdateFollowRequest`.

    Returns:
        The updated :class:`FollowedSeriesItem`.

    Raises:
        HTTPException: 404 if the followed_id does not exist.
    """
    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        existing = store.follow.get(followed_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Followed series not found")

        if body.active is not None:
            store.follow.set_active(followed_id, body.active)

        if body.cadence is not None:
            cadence_json = json.dumps(body.cadence.model_dump())
            store.follow.set_cadence(followed_id, cadence_json)

        updated = store.follow.get(followed_id)
        assert updated is not None  # noqa: S101 — just wrote it

        # Count wanted pending for accurate response.
        wanted_pending = _count_wanted_pending(store, followed_id)
        return _build_followed_item(updated, wanted_pending)
    finally:
        store.close()


@router.delete(
    "/followed/{followed_id}",
    status_code=204,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def delete_follow(request: Request, followed_id: int) -> None:
    """Soft-unfollow a series (sets active=False).

    Args:
        request: The incoming FastAPI request.
        followed_id: Rowid of the ``followed_series`` row.

    Raises:
        HTTPException: 404 if the followed_id does not exist.
    """
    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        existing = store.follow.get(followed_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Followed series not found")
        store.follow.set_active(followed_id, False)
    finally:
        store.close()


# ── Season Grab (R4 / R5) ────────────────────────────────────────────────


def _count_absorbed_for_season(
    store: "ConcreteAcquireStore",
    followed_id: int,
    season: int,
) -> int:
    """Count episode rows already absorbed for a season by a season wanted.

    Args:
        store: An open acquire store.
        followed_id: FK to ``followed_series``.
        season: Season number (1-based).

    Returns:
        Number of episode rows with ``status='absorbed'`` for the follow+season.
    """
    store.wanted._conn.row_factory = sqlite3.Row
    row = store.wanted._conn.execute(
        "SELECT COUNT(*) AS cnt FROM wanted "
        "WHERE followed_id IS ? AND kind = 'episode' "
        "AND season = ? AND status = 'absorbed'",
        (followed_id, season),
    ).fetchone()
    return int(row["cnt"]) if row else 0


def _absorb_live_episodes_for_season(
    store: "ConcreteAcquireStore",
    followed_id: int,
    season: int,
    season_wanted_id: int,
) -> list[int]:
    """Absorb all live episode wanted rows for a season (R5).

    Args:
        store: An open acquire store.
        followed_id: FK to ``followed_series``.
        season: Season number (1-based).
        season_wanted_id: Rowid of the season wanted to absorb into.

    Returns:
        The list of episode rowids that were absorbed.
    """
    store.wanted._conn.row_factory = sqlite3.Row
    rows = store.wanted._conn.execute(
        "SELECT id FROM wanted "
        "WHERE followed_id IS ? AND kind = 'episode' "
        "AND season = ? AND status IN ('pending', 'searching', 'available')",
        (followed_id, season),
    ).fetchall()
    episode_ids = tuple(int(r["id"]) for r in rows)
    if episode_ids:
        store.wanted.absorb_episodes(season_wanted_id, episode_ids)
    return list(episode_ids)


@router.post(
    "/follows/{followed_id}/seasons/{season}/grab",
    status_code=201,
    response_model=SeasonGrabResponse,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def grab_season(
    request: Request,
    followed_id: int,
    season: int,
) -> SeasonGrabResponse:
    """Manually enqueue a season wanted for a followed series (R4).

    Creates a ``WantedItem(kind='season', season=N, episode=None)`` and
    absorbs every live episode wanted for that season (R5). Idempotent:
    returns the existing season row id if one already exists.

    Args:
        request: The incoming FastAPI request.
        followed_id: Rowid of the ``followed_series`` row.
        season: Season number (1-based).

    Returns:
        The created or existing season wanted with absorption count.

    Raises:
        HTTPException: 404 if the followed_id does not exist.
        HTTPException: 400 if season < 1 or the follow is not a show.
    """
    if season < 1:
        raise HTTPException(status_code=400, detail="Season must be >= 1")

    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        followed = store.follow.get(followed_id)
        if followed is None:
            raise HTTPException(status_code=404, detail="Followed series not found")
        if followed.kind != "show":
            raise HTTPException(
                status_code=400,
                detail="Season grab only applies to TV shows (kind='show')",
            )

        # Dedup: one live season wanted per follow+season
        existing = store.wanted.find(
            followed_id=followed_id,
            kind="season",
            season=season,
            episode=None,
        )
        if existing is not None:
            # Count already-absorbed episodes for a truthful response
            absorbed = _count_absorbed_for_season(store, followed_id, season)
            return SeasonGrabResponse(
                season_wanted_id=existing.id or 0,
                season=season,
                absorbed_count=absorbed,
            )

        assert followed.id is not None  # noqa: S101 — get() sets id
        now = int(time.time())

        from personalscraper.acquire.domain import WantedItem

        # Enqueue the season wanted
        season_wid = store.wanted.add(
            WantedItem(
                media_ref=followed.media_ref,
                kind="season",
                status="pending",
                enqueued_at=now,
                followed_id=followed.id,
                season=season,
                episode=None,
            )
        )

        # Absorb live episode wanteds for this season
        absorbed_ids = _absorb_live_episodes_for_season(
            store,
            followed.id,
            season,
            season_wid,
        )

        return SeasonGrabResponse(
            season_wanted_id=season_wid,
            season=season,
            absorbed_count=len(absorbed_ids),
        )
    finally:
        store.close()
