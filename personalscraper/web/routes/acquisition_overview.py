"""Acquisition « état de la machine » overview route (provenance F5 capstone).

A single read-only aggregate — ``GET /api/acquisition/overview`` — composing the F0–F4
spine into one rollup (acquisitions by stage + in-flight, the F4 stuck count, the
AUTHORITATIVE awaiting-resolution count, watcher/last-run context). Extracted from
``acquisition.py`` to keep that module under the 1000-LOC ceiling; same ``/api/acquisition``
prefix, registered under the single ``guarded_api`` auth perimeter (app.py). Every count is
an UNCAPPED aggregate (never a count over the 200-capped journey list — product-intent
§méthode rule 6). Read-only + fail-soft + NOT staging-guarded (writes nothing).
"""

from __future__ import annotations

import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from fastapi import APIRouter, Request

from personalscraper.acquire._provenance_store import STUCK_IDLE_SECONDS
from personalscraper.acquire.store import build_acquire_store
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.web.models.acquisition import AcquisitionOverviewResponse, PendingRunResponse

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])


def _read_last_successful_run_at(acquire_path: Path | None) -> int | None:
    """Read the last-successful-run epoch from the acquire watch_state KV (fail-soft None)."""
    if acquire_path is None or not acquire_path.exists():
        return None
    try:
        with closing(sqlite3.connect(str(acquire_path))) as conn:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT value FROM watch_state WHERE key = ?", ("last_successful_run_at",)).fetchone()
            return int(float(row["value"])) if row is not None else None
    except (sqlite3.Error, ValueError, TypeError):
        return None


def _count_pending_decisions(indexer_path: Path | None) -> int:
    """Count the AUTHORITATIVE pending scrape decisions in library.db (fail-soft 0).

    Mirrors the decisions route's ``pending_count`` semantics so the overview's
    « en attente de résolution » tile matches the decisions badge exactly.
    """
    if indexer_path is None or not indexer_path.exists():
        return 0
    try:
        with closing(sqlite3.connect(str(indexer_path))) as conn:
            apply_pragmas(conn)
            row = conn.execute("SELECT COUNT(*) FROM scrape_decision WHERE status = 'pending'").fetchone()
            return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0


@router.get("/overview", response_model=AcquisitionOverviewResponse)
def get_overview(request: Request) -> AcquisitionOverviewResponse:
    """The unified « état de la machine » rollup (F5 capstone). Read-only, fail-soft.

    Composes the F0–F4 spine into one view — acquisitions by status + in-flight total,
    the F4 stuck count (FS-truth), the authoritative awaiting-resolution count, and the
    watcher / last-run context — each an UNCAPPED aggregate (never a count over the
    200-capped journey list; product-intent §2/§5/§8 + §méthode rule 6). NOT staging-guarded
    (a read; writes nothing).

    Args:
        request: The incoming FastAPI request.

    Returns:
        An :class:`AcquisitionOverviewResponse` — the machine-state rollup.
    """
    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        by_status = store.provenance.stage_counts()
        now = int(time.time())
        stuck = len(store.provenance.list_stuck(older_than=now - STUCK_IDLE_SECONDS, exists_fn=os.path.exists))
        # §8 / DOIT-2 — the watcher's own wait, published by the daemon each cycle.
        # Fail-soft: an unreadable snapshot yields None, i.e. the interface says nothing
        # rather than inventing a countdown.
        try:
            pending = store.watch.get_pending_run()
        except Exception:  # noqa: BLE001 — fail-soft: a read error is silence, never a crash
            pending = None
    finally:
        store.close()

    in_flight = sum(by_status.get(s, 0) for s in ("grabbed", "ingested", "scraped"))
    return AcquisitionOverviewResponse(
        by_status=by_status,
        in_flight=in_flight,
        stuck=stuck,
        awaiting_resolution=_count_pending_decisions(config.indexer.db_path),
        watcher_enabled=not (config.paths.data_dir / "watcher.paused").exists(),
        last_successful_run_at=_read_last_successful_run_at(config.acquire.db_path),
        pending_run=(
            PendingRunResponse(
                fires_at=pending.fires_at,
                active_downloads=pending.active_downloads,
                updated_at=pending.updated_at,
            )
            if pending is not None
            else None
        ),
    )
