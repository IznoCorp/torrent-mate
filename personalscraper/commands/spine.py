"""Spine-driven targeted maintenance actions (feature ``spine-actions``, F4).

Two operator actions keyed on the provenance spine (``staging_provenance``):

- ``acquisition-rescrape`` — re-scrape a precise grab / resume a stuck-at-scrape item.
  Reuses the FORCED scrape (``scrape_{movie,tvshow}_forced``) seeded from the row's
  ``media_ref`` (the grab seed), keeping ``current_path`` live across the canonical rename
  (the F2 scrape-resolve template). Holds only the per-staging-item scrape lock, so distinct
  items re-scrape in parallel while staying mutually exclusive with a full pipeline run.
- ``acquisition-requeue`` — requeue by journey state: trace ``info_hash`` → its ``wanted``
  row and send it back to ``pending`` (the next grab re-acquires). Lock-free.

Both are advisory / fail-soft PER ITEM: a per-item failure is counted and skipped, never
aborting the batch, and a manual/direct item (no spine row) is a no-op (ACC-06).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from personalscraper import cli_helpers
from personalscraper.acquire._provenance_store import STUCK_IDLE_SECONDS
from personalscraper.acquire.store import build_acquire_store
from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.cli_state import state
from personalscraper.commands._cli_run_row import cli_run_row
from personalscraper.lock import (
    acquire_scrape_resolve_lock,
    release_scrape_resolve_lock,
    scrape_locks_dir_for,
)
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns

if TYPE_CHECKING:
    from personalscraper.acquire._provenance_store import ProvenanceRow
    from personalscraper.acquire.store import ConcreteAcquireStore
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings

log = get_logger(__name__)


def _forced_id_for(row: ProvenanceRow) -> tuple[str, int] | None:
    """Resolve ``(provider, provider_id)`` for the forced re-scrape from the grab seed.

    Movies force TMDB; episodes/TV force TVDB, falling back to TMDB. ``None`` when the row
    carries no usable identity (a manual/direct item — direct it to the decision path).
    """
    ref = row.media_ref
    if ref is None:
        return None
    if row.kind == "movie":
        return ("tmdb", ref.tmdb_id) if ref.tmdb_id is not None else None
    if ref.tvdb_id is not None:
        return ("tvdb", ref.tvdb_id)
    if ref.tmdb_id is not None:
        return ("tmdb", ref.tmdb_id)
    return None


def _rescrape_row(row: ProvenanceRow, config: Config, settings: Settings, run_uid: str) -> str:
    """Re-scrape ONE tracked staging item. Returns ``rescraped`` / ``skipped`` / ``failed``.

    Skipped: no live folder, no grab seed (manual item), or the per-item scrape lock is busy
    (a full run / same-item resolve is active). Failed: the forced scrape errored or left no
    NFO. On success the spine is kept live (``move_path`` across the rename + ``set_scrape_run``).
    """
    if row.current_path is None:
        return "skipped"
    path = Path(row.current_path)
    if not path.exists():
        return "skipped"
    forced = _forced_id_for(row)
    if forced is None:
        return "skipped"
    provider, provider_id = forced

    pipeline_lock = config.paths.data_dir / "pipeline.lock"
    item_lock = acquire_scrape_resolve_lock(path, pipeline_lock, scrape_locks_dir_for(config.paths.data_dir))
    if item_lock is None:
        return "skipped"  # a full run / same-item resolve holds the lock
    try:
        from personalscraper.nfo_utils import glob_nfo_candidates  # noqa: PLC0415
        from personalscraper.scraper.orchestrator import Scraper  # noqa: PLC0415
        from personalscraper.scraper.run import _open_provenance_store  # noqa: PLC0415

        prov = _open_provenance_store(config)
        try:
            with per_step_boundary(config, settings) as app_context:
                scraper = Scraper(
                    settings=settings,
                    patterns=NamingPatterns(),
                    dry_run=False,
                    config=config,
                    event_bus=app_context.event_bus,
                    registry=app_context.provider_registry,
                    run_uid=run_uid,
                )
                if row.kind == "movie":
                    result = scraper.scrape_movie_forced(path, provider_id)
                else:
                    result = scraper.scrape_tvshow_forced(path, provider, provider_id)

            if result.error or result.action == "error":
                return "failed"
            final = result.media_path
            if not glob_nfo_candidates(final):
                return "failed"
            # Keep the spine live — the forced scrape does NOT auto-track the rename (only
            # process_movies/process_tvshows do), so move current_path explicitly, then
            # record the scrape stage + run (advisory / fail-soft).
            if prov is not None:
                if str(final) != str(path):
                    prov.provenance.move_path(str(path), str(final))
                prov.provenance.set_scrape_run(str(final), run_uid=run_uid, scraped_at=int(time.time()))
        finally:
            if prov is not None:
                prov.close()
    finally:
        release_scrape_resolve_lock(item_lock)
    return "rescraped"


def _resolve_targets(
    store: ConcreteAcquireStore, info_hash: str | None, path: str | None, stuck: bool, older_than: int
) -> list[ProvenanceRow]:
    """Resolve the set of provenance rows to act on from the CLI selectors (fail-soft reads)."""
    provenance = store.provenance
    if stuck:
        threshold = int(time.time()) - older_than
        return provenance.list_stuck(older_than=threshold, exists_fn=os.path.exists)
    if info_hash:
        row = provenance.by_hash(info_hash)
        return [row] if row is not None else []
    if path:
        row = provenance.by_path(path)
        return [row] if row is not None else []
    return []


@app.command(name="acquisition-rescrape")
@handle_cli_errors
def acquisition_rescrape(
    ctx: typer.Context,
    info_hash: str | None = typer.Option(None, "--hash", help="Re-scrape the item with this grab info-hash."),
    path: str | None = typer.Option(None, "--path", help="Re-scrape the item at this staging folder."),
    stuck: bool = typer.Option(False, "--stuck", help="Re-scrape ALL stuck in-flight items."),
    older_than: int = typer.Option(
        STUCK_IDLE_SECONDS, "--older-than", help="Stuck horizon in seconds (with --stuck)."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the targets without scraping."),
) -> None:
    """Re-scrape a precise grab / resume stuck items, seeded from the provenance registry."""
    config = ctx.obj.config
    settings = cli_helpers.get_settings()
    console = state["console"]

    store = build_acquire_store(config.acquire)
    try:
        targets = _resolve_targets(store, info_hash, path, stuck, older_than)
    finally:
        store.close()

    if not targets:
        console.print("[yellow]No matching tracked staging item to re-scrape.[/yellow]")
        return
    if dry_run:
        console.print(f"[bold]\\[dry-run] would re-scrape {len(targets)} item(s):[/bold]")
        for t in targets:
            console.print(f"  - {t.current_path}")
        return

    counts = {"rescraped": 0, "skipped": 0, "failed": 0}
    with cli_run_row(config, "acquisition-rescrape") as run_rec:
        for row in targets:
            outcome = _rescrape_row(row, config, settings, run_rec.run_uid)
            counts[outcome] += 1
        run_rec.record_counts(counts)
    console.print(f"[green]Re-scrape done:[/green] {counts}")


@app.command(name="acquisition-requeue")
@handle_cli_errors
def acquisition_requeue(
    ctx: typer.Context,
    info_hash: str = typer.Option(..., "--hash", help="Requeue the wanted row behind this grab info-hash."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without requeuing."),
) -> None:
    """Requeue by journey state: send the item's ``wanted`` row back to ``pending``."""
    config = ctx.obj.config
    console = state["console"]

    store = build_acquire_store(config.acquire)
    try:
        row = store.provenance.by_hash(info_hash)
        if row is None:
            console.print(f"[yellow]No provenance row for grab {info_hash}.[/yellow]")
            return
        # Trace info_hash → the OPEN grabbed wanted row(s) carrying that hash.
        targets = [w for w in store.wanted.list_grabbed() if (w.grabbed_hash or "").lower() == info_hash.lower()]
        if not targets:
            console.print(f"[yellow]No open grabbed wanted row for {info_hash} (nothing to requeue).[/yellow]")
            return
        if dry_run:
            console.print(f"[bold]\\[dry-run] would requeue {len(targets)} wanted row(s).[/bold]")
            return
        with cli_run_row(config, "acquisition-requeue") as run_rec:
            requeued = sum(1 for w in targets if w.id is not None and store.wanted.requeue_missing(w.id))
            run_rec.record_counts({"requeued": requeued})
        console.print(f"[green]Requeued {requeued} wanted row(s).[/green]")
    finally:
        store.close()
