"""Read-model + mapping helpers behind the ``/api/acquisition`` routes.

The route module (``web/routes/acquisition.py``) keeps only endpoint
definitions, dependency wiring, and response shaping; the DB read-model queries
and the domain→response mapping live here (route/service split, DESIGN T10).
Nothing in this module holds a write lock or performs a destructive mutation —
the acquisition mutations stay in the route bodies over the acquire store.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request

from personalscraper.acquire.domain import FollowedSeries
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.web.acquisition._helpers import _parse_json_dict
from personalscraper.web.models.acquisition import (
    DeferredTorrent,
    FollowedSeriesItem,
    MediaRefResponse,
    MediaSearchResult,
    RecentRun,
)
from personalscraper.web.models.pipeline import parse_steps_json

if TYPE_CHECKING:
    from personalscraper.scraper.decision_candidate import DecisionCandidate

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
    ``grab`` rows written by the crons, a human CLI, or the web runner — each
    carrying its structured numeric result when recorded.

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
                   OR command IN ('follow-detect', 'grab')
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


def _build_provider_clients(request: Request) -> tuple[object, object]:
    """Build request-scoped TMDB + TVDB clients for a live media search.

    Mirrors the decisions-search pattern: a fresh AppContext + ProviderRegistry
    for this single request (never stored on ``app.state`` — the composition-
    boundary rule). Live search is an infrequent operator action, not a hot
    polling endpoint.

    Args:
        request: The incoming FastAPI request.

    Returns:
        A ``(tmdb_client, tvdb_client)`` tuple of provider client objects.

    Raises:
        HTTPException: 502 when the provider registry cannot be built.
    """
    from personalscraper.cli_helpers import _build_app_context

    config = request.app.state.config
    settings = request.app.state.settings
    try:
        app_context = _build_app_context(config, settings)
        tmdb_client = app_context.provider_registry.get("tmdb")
        tvdb_client = app_context.provider_registry.get("tvdb")
    except Exception as exc:
        logger.error("acquisition_search_registry_failed", error=str(exc))
        raise HTTPException(status_code=502, detail="Provider registry unavailable") from exc
    return tmdb_client, tvdb_client


def _to_search_result(candidate: "DecisionCandidate", kind: str) -> MediaSearchResult:
    """Map a scored :class:`DecisionCandidate` to a :class:`MediaSearchResult`.

    Args:
        candidate: The scored provider candidate.
        kind: ``"movie"`` or ``"tv"`` (which search chain produced it).

    Returns:
        The tagged search result.
    """
    return MediaSearchResult(
        provider=candidate.provider,
        provider_id=candidate.provider_id,
        title=candidate.title,
        year=candidate.year,
        kind=kind,
        poster_url=candidate.poster_url,
        overview=candidate.overview,
        score=candidate.score,
    )


# ── followed-series domain → response mapping ─────────────────────────────


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
