"""Read-model + mapping helpers behind the ``/api/acquisition`` routes.

The route module (``web/routes/acquisition.py``) keeps only endpoint
definitions, dependency wiring, and response shaping; the DB read-model queries
and the domain→response mapping live here (route/service split, DESIGN T10).
Nothing in this module holds a write lock or performs a destructive mutation —
the acquisition mutations stay in the route bodies over the acquire store.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from fastapi import HTTPException, Request

from personalscraper.acquire.domain import FollowedSeries
from personalscraper.api.transport._policy import RetryPolicy
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.web.acquisition._helpers import _parse_json_dict
from personalscraper.web.models.acquisition import (
    DeferredTorrent,
    FollowedSeriesItem,
    MediaRefResponse,
    MediaSearchResponse,
    MediaSearchResult,
    RecentRun,
)
from personalscraper.web.models.pipeline import parse_steps_json

if TYPE_CHECKING:
    from collections.abc import Iterator

    from personalscraper.core.identity import MediaRef
    from personalscraper.scraper.search_ranking import RankedResult

logger = get_logger(__name__)

#: Trigger values counted as watcher-driven pipeline runs in the §5 recent list.
_WATCHER_TRIGGERS = ("completion", "safety_net", "manual")

#: How many recent acquisition-relevant runs the status endpoint surfaces.
_WATCHER_RECENT_RUNS = 10


# ── recent-runs read model (§5) ──────────────────────────────────────────


def _parse_run_counts(steps_json: str | None) -> dict[str, int] | None:
    """Extract the §5 numeric result from a run's ``steps_json``, or ``None``.

    The acquisition CLIs persist their counts as the ``counts`` mapping of a
    ``steps_json`` entry (see ``commands/_cli_run_row``). The LAST entry
    carrying counts wins.

    Fallback for pipeline runs (which record per-step ``success_count`` /
    ``skip_count`` / ``error_count`` but no semantic ``counts`` dict): derive a
    run-level summary — ``processed`` = max success across steps (the §1
    ``run_processed`` convention: every step sees the same media), ``skipped``
    = the ingest gate's skips, ``errors`` = sum. A skip-only watcher run then
    reads « 5 ignoré(s) » instead of a blank cell (live incident 2026-07-15:
    « Pipeline » rows with empty results).

    Args:
        steps_json: The raw ``steps_json`` column value.

    Returns:
        The counts mapping, or ``None`` when absent/unparseable.
    """
    steps = parse_steps_json(steps_json)
    if not steps:
        return None
    for step in reversed(steps):
        counts = step.get("counts")
        if isinstance(counts, dict):
            return {str(k): int(v) for k, v in counts.items() if isinstance(v, (int, float))}
    # Fallback: run-level summary from the native per-step count fields.
    processed = 0
    skipped = 0
    errors = 0
    saw_any = False
    for step in steps:
        success = step.get("success_count")
        skip = step.get("skip_count")
        error = step.get("error_count")
        if success is None and skip is None and error is None:
            continue
        saw_any = True
        if isinstance(success, (int, float)):
            processed = max(processed, int(success))
        if step.get("name") == "ingest" and isinstance(skip, (int, float)):
            skipped = int(skip)
        if isinstance(error, (int, float)):
            errors += int(error)
    if not saw_any:
        return None
    return {"processed": processed, "skipped": skipped, "errors": errors}


def _query_watcher_recent_runs(db_path: Path) -> list[RecentRun]:
    """Query the last N acquisition-relevant pipeline_run rows from library.db.

    Covers BOTH populations (§5 visibility): the watcher-triggered pipeline
    runs (legacy triggers) AND the acquisition CLI runs — ``follow-detect`` /
    ``grab`` / ``prime`` rows written by the crons, a human CLI, or the web
    runner — each carrying its structured numeric result when recorded. The
    ``prime`` rows are the acq-states amorce of a freshly followed series: a
    run the operator triggered by adding a follow must be as visible as any
    other.

    Args:
        db_path: Absolute path to the indexer SQLite database (library.db).

    Returns:
        A list of :class:`RecentRun` items, most recent first.
    """
    if not db_path.exists():
        return []

    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row

            placeholders = ", ".join("?" * len(_WATCHER_TRIGGERS))
            rows = conn.execute(
                f"""
                SELECT run_uid, started_at, ended_at, outcome, command, "trigger", steps_json
                FROM pipeline_run
                WHERE trigger IN ({placeholders})
                   OR command IN ('follow-detect', 'grab', 'prime')
                ORDER BY started_at DESC
                LIMIT ?
                """,
                list(_WATCHER_TRIGGERS) + [_WATCHER_RECENT_RUNS],
            ).fetchall()

            return [
                RecentRun(
                    run_uid=row["run_uid"],
                    started_at=float(row["started_at"]),
                    ended_at=(float(row["ended_at"]) if row["ended_at"] is not None else None),
                    outcome=row["outcome"],
                    command=row["command"],
                    trigger=row["trigger"],
                    result=_parse_run_counts(row["steps_json"]),
                )
                for row in rows
            ]
    except sqlite3.Error:
        logger.warning("acquisition_recent_runs_read_failed", exc_info=True)
        return []


def _list_deferred_torrents(config: Any) -> list[DeferredTorrent]:
    """Compute the watcher's current transient-deferral set for the UI (§1).

    Mirrors the watch daemon's per-cycle ``classify_deferrals`` call so the
    status endpoint and the daemon agree on what is deferred and why. Fully
    fail-soft: any client / probe error yields an empty list — the panel then
    simply shows nothing, never a 500.

    Args:
        config: The loaded application config.

    Returns:
        One :class:`DeferredTorrent` per deferred hash (possibly empty).
    """
    from personalscraper.core.tags import SEED_PURE  # noqa: PLC0415
    from personalscraper.ingest.deferral import (  # noqa: PLC0415
        classify_deferrals,
        deferral_probe_dirs,
    )
    from personalscraper.ingest.tracker import IngestTracker  # noqa: PLC0415
    from personalscraper.web.torrent_session import shared_torrent_client  # noqa: PLC0415

    try:
        # Shared cached session — one login per web process (see torrent_session).
        with shared_torrent_client(config.torrent) as client:
            if client is None:
                return []
            completed = client.get_completed()
        tracker = IngestTracker(tracker_path=config.paths.data_dir / "ingested_torrents.json")
        ingested = frozenset(tracker.load().keys())
        seed_pure = frozenset(t.hash for t in completed if SEED_PURE in (t.tags or []))
        dirs = deferral_probe_dirs(config)
        deferred = classify_deferrals(
            completed,
            min_ratio=config.ingest.min_ratio,
            ingest_dir=dirs[-1],
            min_free_gb=config.thresholds.min_free_space_staging_gb,
            staging_probe_dirs=dirs,
            exclude_hashes=ingested | seed_pure,
        )
        by_hash = {t.hash: t.name for t in completed}
        return [
            DeferredTorrent(name=by_hash.get(h, h[:16]), reason=reason)
            for h, reason in sorted(deferred.items(), key=lambda kv: by_hash.get(kv[0], ""))
        ]
    except Exception:
        logger.warning("acquisition_status_deferred_probe_failed", exc_info=True)
        return []


# ── media search (add-by-search, OBJ3) ───────────────────────────────────


#: Retry budget for a registry built INSIDE a request (D1). The pipeline's
#: default (4 attempts + exponential backoff over a 10 s / 15 s timeout) is
#: right for a background step and wrong for a user waiting on a 201: against a
#: host that accepts the TCP connection and never answers, one lookup burned
#: ~60-75 s and a two-provider enrichment ~2 minutes, with the worker thread
#: held throughout. One attempt bounds the worst case to the sum of the two
#: timeouts (~25 s).
_REQUEST_RETRY = RetryPolicy(max_attempts=1)


@contextmanager
def scoped_provider_clients(request: Request) -> "Iterator[tuple[object, object]]":
    """Yield request-scoped TMDB + TVDB clients, then release the registry.

    Mirrors the decisions-search pattern: a fresh AppContext + ProviderRegistry
    for this single request (never stored on ``app.state`` — the composition-
    boundary rule). Live search and create-follow enrichment are infrequent
    operator actions, not hot polling endpoints.

    Two properties this seam owns, both formerly documented gaps:

    * **Bounded** (D1): the providers are built with ``max_attempts=1`` through
      the registry's ``retry`` parameter — a real construction seam, not a
      mutation of ``client._transport._policy`` (frozen, private, and on TVDB
      merely READING ``_transport`` fires the bootstrap login).
    * **Closed** (D5): ``ProviderRegistry.close()`` releases each provider's
      ``requests.Session`` and its connection pool. It runs in a ``finally``, so
      it also runs when the body raises — the clients stay usable for the whole
      ``with`` block, which a ``finally`` inside a plain builder could not do.

    Args:
        request: The incoming FastAPI request.

    Yields:
        A ``(tmdb_client, tvdb_client)`` tuple of provider client objects.

    Raises:
        HTTPException: 502 when the provider registry cannot be built.
    """
    from personalscraper.cli_helpers import _build_app_context

    config = request.app.state.config
    settings = request.app.state.settings
    try:
        app_context = _build_app_context(config, settings, provider_retry=_REQUEST_RETRY)
        tmdb_client = app_context.provider_registry.get("tmdb")
        tvdb_client = app_context.provider_registry.get("tvdb")
    except Exception as exc:
        logger.error("acquisition_search_registry_failed", error=str(exc))
        raise HTTPException(status_code=502, detail="Provider registry unavailable") from exc
    try:
        yield tmdb_client, tvdb_client
    finally:
        # Teardown mirrors the CLI's ``per_step_boundary``: registry first, then
        # the acquisition handle. Fail-soft — a teardown error must never turn a
        # served response into a 500.
        try:
            app_context.provider_registry.close()
        except Exception:  # noqa: BLE001 — teardown must not mask the response
            logger.warning("acquisition_provider_registry_close_failed", exc_info=True)
        if app_context.acquire is not None:
            try:
                app_context.acquire.close()
            except Exception:  # noqa: BLE001 — same contract
                logger.warning("acquisition_acquire_context_close_failed", exc_info=True)


def resolve_series_tvdb(media_ref: MediaRef, tmdb_client: Any) -> int | None:
    """Resolve the TVDB id for a series followed by TMDB/IMDB alone.

    Episode detection (``poll_known``) skips any series whose ``media_ref`` has no
    ``tvdb_id``, so a TMDB/IMDB-only follow would be inert. This backfills the
    TVDB id via TMDB's cross-reference, keeping TVDB the detection primary
    (multi-provider separation): TMDB/IMDB only resolve it.

    - ``tvdb_id`` already set → returned as-is (no provider call).
    - ``tmdb_id`` set → ``get_tvdb_id(tmdb_id)`` (raw ``/tv/{id}/external_ids``).
    - ``imdb_id`` only → ``find_by_imdb`` → tmdb id → the same TVDB extraction.

    Fail-soft: any provider error, a missing TVDB cross-reference, or a malformed
    id degrades to ``None`` — the caller still creates the follow (flagged
    unresolved), never inert-and-silent (§méthode).

    Args:
        media_ref: The follow's provider IDs.
        tmdb_client: The request-scoped TMDB client (``get_tvdb_id`` +
            ``find_by_imdb``).

    Returns:
        The resolved TVDB series id, or ``None`` when it cannot be resolved.
    """
    if media_ref.tvdb_id is not None:
        return media_ref.tvdb_id
    try:
        tmdb_id = media_ref.tmdb_id
        if tmdb_id is None and media_ref.imdb_id is not None:
            tmdb_id = tmdb_client.find_by_imdb(media_ref.imdb_id)
        if tmdb_id is None:
            return None
        resolved: int | None = tmdb_client.get_tvdb_id(tmdb_id)
        return resolved
    except Exception as exc:  # noqa: BLE001 — fail-soft: never block the follow
        logger.warning("acquisition_follow_tvdb_resolve_failed", error=str(exc))
        return None


def run_media_search(
    request: Request,
    tmdb_client: object,
    tvdb_client: object,
    q: str,
    kind: Literal["movie", "tv"] | None,
    *,
    offset: int = 0,
    limit: int = 20,
) -> MediaSearchResponse:
    """Run the movie/TV search chains against already-built provider clients.

    Split out of the route so the registry's lifetime is one ``with`` block:
    the clients are used entirely inside it, and the 502 raised by a failing
    provider still unwinds through the context manager's ``finally``.

    Ranking is the RETRIEVAL engine
    (:mod:`personalscraper.scraper.search_ranking`), not the scrape matcher: the
    latter answers "is this folder that media?" and its anti-false-positive guards
    scored the wanted title at exactly 0.000 for a short keyword query.

    Args:
        request: The incoming FastAPI request (config for the ownership flag).
        tmdb_client: Request-scoped TMDB client.
        tvdb_client: Request-scoped TVDB client.
        q: The title to search for.
        kind: Optional ``"movie"``/``"tv"`` restriction (both when omitted).
        offset: Zero-based index of the first row to return.
        limit: Maximum rows to return.

    Returns:
        A :class:`MediaSearchResponse` carrying the requested page plus the TOTAL
        number of ranked candidates.

    Raises:
        HTTPException: 502 on provider API failure.
    """
    from personalscraper.scraper.search_ranking import (
        gather_tv_candidates,
        rank_search_results,
    )

    now_year = datetime.now(tz=UTC).year
    ranked: list[tuple[float, MediaSearchResult]] = []

    if kind in (None, "movie"):
        try:
            movie_rows = tmdb_client.search_movie(q, None)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.error("acquisition_search_movie_failed", error=str(exc))
            raise HTTPException(status_code=502, detail=f"Movie search failed: {exc}") from exc
        ranked.extend(
            (item.score, _to_search_result(item, "movie"))
            for item in rank_search_results(q, list(movie_rows), kind="movie", now_year=now_year)
        )

    if kind in (None, "tv"):
        # Both TV providers, merged: TVDB alone cannot rank (it publishes no
        # popularity), and the scrape rule "TMDB only when TVDB is silent" hid the
        # right answer whenever TVDB returned any row at all.
        tv_rows = gather_tv_candidates(tvdb_client, tmdb_client, q)
        ranked.extend(
            (item.score, _to_search_result(item, "tv"))
            for item in rank_search_results(q, tv_rows, kind="tv", now_year=now_year)
        )

    # One ordering across both kinds, so "Tout" is a real merge and not two
    # independently-truncated lists stapled together.
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    total = len(ranked)
    page = [item for _, item in ranked[offset : offset + limit]]
    results = page

    # §5 replacement confirmation: flag movie results already owned in the
    # library (by provider id, live files only) so the UI can ask before
    # following — the pipeline will REPLACE the existing version. Fail-soft:
    # an unreadable indexer leaves already_owned=False everywhere.
    indexer_db = request.app.state.config.indexer.db_path
    if indexer_db is not None and any(r.kind == "movie" for r in results):
        from personalscraper.core.identity import MediaRef
        from personalscraper.indexer.ownership import IndexerOwnershipChecker

        checker = IndexerOwnershipChecker(Path(indexer_db))
        try:
            for r in results:
                if r.kind != "movie":
                    continue
                ref = MediaRef(tmdb_id=r.provider_id) if r.provider == "tmdb" else MediaRef(tvdb_id=r.provider_id)
                r.already_owned = checker.owns(ref, kind="movie")
        finally:
            checker.close()

    return MediaSearchResponse(results=results, total=total, offset=offset, limit=limit)


# ── /api/acquisition/followed (write) ─────────────────────────────────────


def _to_search_result(candidate: "RankedResult", kind: str) -> MediaSearchResult:
    """Map a scored :class:`RankedResult` to a :class:`MediaSearchResult`.

    Args:
        candidate: The ranked provider candidate.
        kind: ``"movie"`` or ``"tv"`` (which search chain produced it).

    Returns:
        The tagged search result.
    """
    result = candidate.result
    # provider_id is a str on SearchResult but an int on the wire; a provider that
    # ever returns a non-numeric id must not 500 the whole search.
    try:
        provider_id = int(result.provider_id)
    except (TypeError, ValueError):
        provider_id = 0
    return MediaSearchResult(
        provider=result.provider,
        provider_id=provider_id,
        title=result.title,
        year=result.year,
        kind=kind,
        poster_url=result.poster_url or None,
        overview=result.overview or None,
        score=candidate.score,
    )


# ── followed-series domain → response mapping ─────────────────────────────


def _derive_tvdb_unresolved(fs: FollowedSeries) -> bool:
    """Whether an active show is inert for lack of a TVDB id.

    Episode detection (``poll_known``) skips any series without a ``tvdb_id``, so
    an ACTIVE show whose ``media_ref`` has none is inert — it will never detect an
    episode. Derived from state (not a create-time flag) so it is honest on EVERY
    surface — create, reactivate, the pause/resume toggle, and the list — never a
    silently inert follow (§méthode). Movies and paused follows are never flagged.

    Args:
        fs: The followed-series domain object.

    Returns:
        ``True`` iff *fs* is an active show with no TVDB id.
    """
    return fs.kind == "show" and fs.active and fs.media_ref.tvdb_id is None


def _build_followed_item(fs: FollowedSeries, wanted_pending: int) -> FollowedSeriesItem:
    """Convert a :class:`FollowedSeries` domain object to a response item.

    Args:
        fs: The domain object from the store (must have ``id`` set).
        wanted_pending: The COUNT of pending/searching wanted rows.

    Returns:
        A :class:`FollowedSeriesItem` ready for JSON serialization.
    """
    return FollowedSeriesItem(
        id=fs.id,  # type: ignore[arg-type]  # store.get guarantees id is set
        title=fs.title,
        media_ref=MediaRefResponse(
            tvdb_id=fs.media_ref.tvdb_id,
            tmdb_id=fs.media_ref.tmdb_id,
            imdb_id=fs.media_ref.imdb_id,
        ),
        active=fs.active,
        kind=fs.kind,
        cadence=_parse_json_dict(fs.cadence_json),
        added_at=float(fs.added_at),
        wanted_pending=wanted_pending,
        quality_profile=_parse_json_dict(fs.quality_profile_json),
        tvdb_unresolved=_derive_tvdb_unresolved(fs),
    )


def _item_from_followed(fs: FollowedSeries) -> FollowedSeriesItem:
    """Build a response item from a :class:`FollowedSeries` domain object.

    Populates ``media_ref`` from the domain object's ``media_ref`` field
    (NOT the raw JSON column — the domain object already has a parsed
    :class:`MediaRef`).  ``wanted_pending`` is set to 0 for newly created
    or reactivated items.

    Args:
        fs: The domain object from the store (must have ``id`` set).

    Returns:
        A :class:`FollowedSeriesItem` ready for JSON serialization.
    """
    return FollowedSeriesItem(
        id=fs.id,  # type: ignore[arg-type]  # store.get guarantees id is set
        title=fs.title,
        media_ref=MediaRefResponse(
            tvdb_id=fs.media_ref.tvdb_id,
            tmdb_id=fs.media_ref.tmdb_id,
            imdb_id=fs.media_ref.imdb_id,
        ),
        active=fs.active,
        kind=fs.kind,
        cadence=_parse_json_dict(fs.cadence_json),
        added_at=float(fs.added_at),
        wanted_pending=0,  # newly created/reactivated → no wanted items yet
        quality_profile=_parse_json_dict(fs.quality_profile_json),
        tvdb_unresolved=_derive_tvdb_unresolved(fs),
    )


def _count_wanted_pending(store: Any, followed_id: int) -> int:
    """Count pending/searching wanted rows for a followed series.

    Uses the store's connection directly for a cheap COUNT query.

    Args:
        store: An open :class:`ConcreteAcquireStore`.
        followed_id: Rowid of the ``followed_series`` row.

    Returns:
        The number of wanted rows in ``pending`` or ``searching`` status.
    """
    # Access the store's internal connection — safe because the store
    # is freshly built per-request (no thread-affinity risk).
    conn = store._conn
    if conn is None:
        return 0
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT COUNT(*) FROM wanted WHERE followed_id = ? AND status IN ('pending', 'searching')",
        (followed_id,),
    ).fetchone()
    return row[0] if row else 0
