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

from personalscraper.acquire._provenance_store import STUCK_IDLE_SECONDS, journey_release_name
from personalscraper.acquire.stalled_grabs import StalledGrab, list_stalled_grabs
from personalscraper.acquire.store import AcquireStore, build_acquire_store
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.web.acquisition.to_handle import build_to_handle
from personalscraper.web.models.acquisition import (
    AcquisitionOverviewResponse,
    PendingRunResponse,
    StalledGrabItem,
    StalledGrabsResponse,
    ToHandleItemModel,
    ToHandleResponse,
)

log = get_logger("web.acquisition.overview")

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])


def _collect_stalled(store: AcquireStore, *, now: int, last_run_finished_at: int | None) -> list[StalledGrab]:
    """Return the parked « récupéré » acquisitions, using the shared derivation.

    Single seam for BOTH the overview count and the drill-down list, so a tile can never
    announce a number the list then contradicts (§13 — une seule dérivation par question).

    Args:
        store: An open acquire store (the caller owns its lifetime).
        now: Current epoch seconds.
        last_run_finished_at: Epoch the last pipeline run finished, or ``None``.

    Returns:
        The stalled acquisitions, oldest step first.
    """
    return list_stalled_grabs(
        store.wanted.list_grabbed(),
        store.provenance.by_hash,
        now=now,
        release_name_for=journey_release_name,
        last_run_finished_at=last_run_finished_at,
    )


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
        # §14.1 — « récupéré » n'est pas un état de repos. Fail-soft : un défaut de lecture
        # doit dégrader le compteur, jamais faire tomber tout le tableau de bord.
        last_run = _read_last_successful_run_at(config.acquire.db_path)
        try:
            stalled_grabs = len(_collect_stalled(store, now=now, last_run_finished_at=last_run))
        except Exception as exc:  # noqa: BLE001 — fail-soft: la vue d'ensemble ne 500 jamais
            # Ce filet a MASQUÉ un vrai défaut de code pendant l'écriture (un sérialiseur
            # inexistant) : un compteur à 0 se lit « tout va bien ». Un fail-soft muet est
            # exactement le « rien en silence » que §8 interdit — il doit donc parler.
            log.warning("acquisition_overview_stalled_grabs_failed", error=str(exc))
            stalled_grabs = 0
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
        stalled_grabs=stalled_grabs,
        awaiting_resolution=_count_pending_decisions(config.indexer.db_path),
        watcher_enabled=not (config.paths.data_dir / "watcher.paused").exists(),
        last_successful_run_at=last_run,
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


@router.get("/stalled-grabs", response_model=StalledGrabsResponse)
def get_stalled_grabs(request: Request) -> StalledGrabsResponse:
    """Les acquisitions parquées à « récupéré » qui n'atteignent jamais la médiathèque.

    Le détail derrière le compteur de la vue d'ensemble : §8 interdit un nombre sans
    accès à ce qu'il compte, et §14.1 fait de « récupéré » un état transitoire — une
    ligne qui y stagne doit se voir, avec sa raison.

    Lecture seule, fail-soft, non staging-guarded (n'écrit rien).

    Args:
        request: La requête FastAPI entrante.

    Returns:
        Un :class:`StalledGrabsResponse`, la plus ancienne d'abord.
    """
    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        titles = {f.id: f.title for f in store.follow.list_all() if f.id is not None}
        stalled = _collect_stalled(
            store,
            now=int(time.time()),
            last_run_finished_at=_read_last_successful_run_at(config.acquire.db_path),
        )
        wanted_titles = {w.id: titles.get(w.followed_id or -1, "") for w in store.wanted.list_grabbed()}
    finally:
        store.close()

    return StalledGrabsResponse(
        items=[
            StalledGrabItem(
                wanted_id=s.wanted_id,
                title=wanted_titles.get(s.wanted_id) or "(sans titre)",
                kind=s.kind,
                season=s.season,
                episode=s.episode,
                info_hash=s.info_hash,
                release_name=s.release_name,
                since=s.since,
                reason=s.reason,
            )
            for s in stalled
        ]
    )


@router.get("/to-handle", response_model=ToHandleResponse)
def get_to_handle(request: Request) -> ToHandleResponse:
    """Blocked media CARRIED BY AN ACQUISITION, plus the count of the others.

    §14.3: a journey has no hole. An item grabbed then ingested that stalls at
    identification is in the middle of ITS journey; it must stay visible from the
    acquisition surface. A manual deposit is not an acquisition: it is counted
    (orphan_count) but never listed here; it belongs on the « À traiter » panel
    in Contrôle.

    Read-only, fail-soft, not staging-guarded (writes nothing).

    Args:
        request: The incoming FastAPI request.

    Returns:
        A :class:`ToHandleResponse` — the blocked items carried by an acquisition,
        oldest first, plus the orphan count.
    """
    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        rollup = build_to_handle(indexer_db=config.indexer.db_path, store=store)
    finally:
        store.close()

    return ToHandleResponse(
        items=[ToHandleItemModel(**vars(item)) for item in rollup.items],
        orphan_count=rollup.orphan_count,
    )
