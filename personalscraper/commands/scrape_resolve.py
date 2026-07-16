"""Scrape-resolve CLI — targeted metadata fetch by provider ID for the scrape-arbiter.

Resolves a pending ``scrape_decision`` row by fetching metadata directly from the
chosen provider (TMDB or TVDB) by its known ID, generating NFO + downloading artwork
into the staging folder, then marking the decision ``resolved``.  Acquires a
**per-staging-item** scrape lock (``<data_dir>/locks/scrape/<sha1(path)>.lock``) for
its lifetime so distinct items resolve in parallel, while staying mutually exclusive
with any global ``pipeline.lock`` holder (webui-ux phase 4) — both human-runnable and
safe as a web-runner subprocess.

Registered as ``personalscraper scrape-resolve`` on the shared Typer app.
"""

from __future__ import annotations

import sqlite3 as _sqlite3
import unicodedata
from pathlib import Path

import typer

from personalscraper import cli_helpers
from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.cli_state import state
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.lock import (
    acquire_scrape_resolve_lock,
    release_scrape_resolve_lock,
    scrape_locks_dir_for,
)
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns

log = get_logger(__name__)

_VALID_PROVIDERS = frozenset({"tmdb", "tvdb"})
_VALID_VIA = frozenset({"pick", "search_override"})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lookup_decision(db_path: Path, staging_path: Path) -> tuple[int, str, str] | None:
    """Look up a ``scrape_decision`` row by *staging_path* (NFC, F35).

    Tries the AS-GIVEN path first (matching the writer's as-scanned storage),
    then the ``.resolve()``d form for a human who passed an equivalent path.

    Args:
        db_path: Path to the indexer SQLite database.
        staging_path: The staging directory argument.

    Returns:
        ``(id, media_kind, status)`` for the matched row, or ``None``.
    """
    candidates = [
        unicodedata.normalize("NFC", str(staging_path)),
        unicodedata.normalize("NFC", str(staging_path.resolve())),
    ]
    seen: set[str] = set()
    conn = _sqlite3.connect(str(db_path), isolation_level=None)
    try:
        apply_pragmas(conn)
        for key in candidates:
            if key in seen:
                continue
            seen.add(key)
            row = conn.execute(
                "SELECT id, media_kind, status FROM scrape_decision WHERE staging_path = ?",
                (key,),
            ).fetchone()
            if row is not None:
                return (int(row[0]), str(row[1]), str(row[2]))
    finally:
        conn.close()
    return None


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


@app.command()
@handle_cli_errors
def scrape_resolve(
    ctx: typer.Context,
    staging_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Path to the staging directory for the media item.",
    ),
    provider: str = typer.Option(
        ...,
        "--provider",
        help="Metadata provider: 'tmdb' or 'tvdb'.",
    ),
    provider_id: int = typer.Option(
        ...,
        "--id",
        help="Numeric identifier assigned by the provider.",
    ),
    via: str = typer.Option(
        "pick",
        "--via",
        help="Resolution provenance: 'pick' (candidate from the queue) or 'search_override'.",
    ),
) -> None:
    """Resolve a pending scrape decision by fetching metadata by provider ID.

    Fetches movie or TV-show metadata directly from TMDB (movies) or
    TMDB/TVDB (TV shows) by a known provider ID, writes NFO + artwork into
    the staging folder, and marks the matching ``scrape_decision`` row as
    ``resolved``.

    Acquires the SCOPED per-staging-item scrape lock
    (:func:`~personalscraper.lock.acquire_scrape_resolve_lock`) for its lifetime —
    it does NOT self-acquire the global ``pipeline.lock`` (two-tier scoped locking,
    webui-ux phase 4).  Distinct staging items resolve in PARALLEL (distinct
    per-item locks), the SAME item blocks (idempotent guard), and any global
    ``pipeline.lock`` holder (full run / maintenance) makes the resolve back off —
    the item lock is fail-closed against the global lock.  Safe as both a direct
    human invocation and a web-runner subprocess.

    Note: the ``"scrape-resolve"`` entry in
    ``personalscraper.web.maintenance.runner._CLI_SELF_LOCKING`` is VESTIGIAL for
    this command — the decisions runner
    (:mod:`personalscraper.web.decisions.runner`) that spawns this CLI consults no
    such set and never acquires the global lock on its behalf; the entry only
    matters to the maintenance runner, which does not spawn scrape-resolve.

    Exit codes:
        0 — success (NFO written, artwork downloaded, decision resolved).
        1 — scrape error (API failure, NFO write failure).
        2 — misconfiguration (missing DB, unknown provider, no matching
            pending decision row, invalid provider for media kind).
        3 — lock busy (same item already resolving, or a global pipeline
            holder is active). Distinct from 1 so the web decisions runner
            can QUEUE (retry the spawn) on lock races without ever retrying
            a real scrape failure (operator directive 2026-07-15: a resolve
            must never surface a 409 while a pipeline run holds the lock).
    """
    config = ctx.obj.config
    console = state["console"]
    settings = cli_helpers.get_settings()

    # ── 1. Validate provider + via ───────────────────────────────────────
    if provider not in _VALID_PROVIDERS:
        console.print(
            f"[red]Invalid provider '{provider}'. Must be one of: {', '.join(sorted(_VALID_PROVIDERS))}.[/red]"
        )
        raise typer.Exit(2)
    if via not in _VALID_VIA:
        console.print(f"[red]Invalid --via '{via}'. Must be one of: {', '.join(sorted(_VALID_VIA))}.[/red]")
        raise typer.Exit(2)

    # ── 2. Validate DB path ──────────────────────────────────────────────
    db_path = config.indexer.db_path
    if not db_path.exists():
        console.print(f"[red]Indexer DB not found at {db_path}; run `library-index` first.[/red]")
        raise typer.Exit(2)

    # ── 3. Look up decision row by NFC-normalized staging path ───────────
    # The writer stores the AS-SCANNED path (never .resolve()d); the web runner
    # passes that stored path straight back.  Match it first, then fall back to
    # the resolved form for a human who typed an equivalent/relative path — the
    # two canonicalizations must not diverge silently (F35).
    row = _lookup_decision(db_path, staging_path)
    if row is None:
        console.print(f"[red]No decision row found for staging path: {staging_path}[/red]")
        raise typer.Exit(2)

    decision_id: int = row[0]
    media_kind: str = row[1]
    status: str = row[2]

    if status != "pending":
        console.print(f"[red]Decision {decision_id} is already '{status}', not 'pending'.[/red]")
        raise typer.Exit(2)

    # ── 4. Validate provider ↔ media_kind ────────────────────────────────
    if media_kind == "movie" and provider != "tmdb":
        console.print(f"[red]Movies require provider 'tmdb', got '{provider}'.[/red]")
        raise typer.Exit(2)

    # ── 5. Acquire the per-staging-item scrape lock (exit 1 if held) ──────
    # Scoped, scrape-only locking (webui-ux phase 4): register a per-item lock
    # under <data_dir>/locks/scrape/ so two resolves on DISTINCT staging paths
    # run in PARALLEL, while a resolve stays mutually exclusive with any global
    # pipeline holder.  acquire_scrape_resolve_lock is claim-first-then-verify
    # (register the item lock, THEN check pipeline.lock) — fail-closed against a
    # concurrent full run / maintenance.  It returns None either when the SAME
    # item is already resolving or when a global holder is active.
    pipeline_lock = config.paths.data_dir / "pipeline.lock"
    scrape_locks_dir = scrape_locks_dir_for(config.paths.data_dir)
    item_lock = acquire_scrape_resolve_lock(staging_path, pipeline_lock, scrape_locks_dir)
    if item_lock is None:
        console.print("[yellow]Lock busy (pipeline run or same-item resolve active). Exiting.[/yellow]")
        raise typer.Exit(3)

    try:
        # Re-check status inside the critical section (F45): the step-3 read
        # was outside the lock, so a concurrent invocation could have resolved
        # this row while we waited. Bail before doing any provider/NFO work.
        recheck = _lookup_decision(db_path, staging_path)
        if recheck is None or recheck[2] != "pending":
            now_status = recheck[2] if recheck else "gone"
            console.print(f"[red]Decision {decision_id} is no longer 'pending' (now '{now_status}'). Aborting.[/red]")
            raise typer.Exit(2)

        console.print(f"[bold]Scrape-resolving '{staging_path.name}' via {provider}:{provider_id}...[/bold]")

        patterns = NamingPatterns()

        with per_step_boundary(config, settings) as app_context:
            # Delegate to the SAME scrape services as the automatic pipeline via
            # a forced provider match (the operator has already asserted the
            # identity). This produces a COMPLETE canonical result — folder +
            # video rename for movies, episode rename + per-episode NFOs for TV,
            # plus the NFO and artwork — instead of the previous NFO-only write
            # that left the folder/video/episodes unrenamed and the pipeline's
            # ``verify`` step blocking dispatch (product-intent §méthode; the
            # resolve-but-never-dispatch loop the operator reported).
            from personalscraper.scraper.orchestrator import Scraper  # noqa: PLC0415

            scraper = Scraper(
                settings=settings,
                patterns=patterns,
                dry_run=False,
                config=config,
                event_bus=app_context.event_bus,
                registry=app_context.provider_registry,
            )
            if media_kind == "movie":
                scrape_result = scraper.scrape_movie_forced(staging_path, provider_id)
            else:
                scrape_result = scraper.scrape_tvshow_forced(staging_path, provider, provider_id)

            if scrape_result.error or scrape_result.action == "error":
                detail = scrape_result.error or scrape_result.action
                console.print(f"[red]Scrape failed for '{staging_path.name}': {detail}[/red]")
                raise typer.Exit(1)

            # ── 5b. Verify an NFO actually landed before marking resolved ──
            # 'resolved' must imply a scraped folder (an NFO on disk). The forced
            # write may have RENAMED the folder to its canonical ``Title (Year)``
            # form, so check the RESULT's ``media_path`` (the post-rename path),
            # not the original ``staging_path`` — otherwise a renamed-but-scraped
            # item looks unscraped. A scrape that left no NFO — a write no-op, or
            # an NFO removed mid-flight — must NOT report success, else the
            # library shows a 'resolved' item as unscraped and the operator
            # cannot tell it needs re-doing (webui-overhaul #3).
            from personalscraper.nfo_utils import glob_nfo_candidates  # noqa: PLC0415

            final_path = scrape_result.media_path
            if not glob_nfo_candidates(final_path):
                console.print(
                    f"[red]No NFO on disk after scraping '{final_path.name}' — "
                    f"not marking decision {decision_id} resolved (it stays pending).[/red]"
                )
                raise typer.Exit(1)

            # ── 6. Mark decision resolved ─────────────────────────────────
            # Fail-loud (F05): the NFO/artwork are already on disk, but if the
            # status write does not land the decision must NOT report success —
            # otherwise the item stays pending and gets re-resolved (duplicate
            # scrape). resolve() returns False when the row is no longer pending
            # and raises DecisionWriteError on a DB error.
            from personalscraper.scraper.decision_writer import (  # noqa: PLC0415
                DecisionWriteError,
                DecisionWriter,
            )

            writer = DecisionWriter(db_path)
            try:
                marked = writer.resolve(decision_id, provider, provider_id, via=via)
            except DecisionWriteError as exc:
                console.print(f"[red]NFO written but resolve-mark failed for decision {decision_id}: {exc}[/red]")
                raise typer.Exit(1) from exc
            if not marked:
                console.print(
                    f"[red]NFO written but decision {decision_id} was no longer pending — not marked resolved.[/red]"
                )
                raise typer.Exit(1)

        console.print(f"[green]Successfully resolved decision {decision_id} via {provider}:{provider_id}.[/green]")

    finally:
        release_scrape_resolve_lock(item_lock)
