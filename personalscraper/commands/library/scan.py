"""Scan/index Typer commands for the library."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors


@app.command("library-index")
@handle_cli_errors
def library_index(
    ctx: typer.Context,
    mode: str = typer.Option("full", "--mode", help="Scan mode: full, quick, incremental, or enrich"),
    disk: Optional[str] = typer.Option(None, "--disk", help="Restrict scan to this disk label"),
    budget: Optional[int] = typer.Option(None, "--budget", help="Budget in seconds"),
    no_budget: bool = typer.Option(
        False,
        "--no-budget",
        help=(
            "Disable the wall-clock budget for this run (overrides --budget and config). "
            "Use for manual full enrich passes that must drain every pending file."
        ),
    ),
    backfill_streams: bool = typer.Option(
        False,
        "--backfill-streams",
        help=(
            "Enrich-only: target already-enriched files whose media_stream rows are "
            "missing migration-004 columns (hdr_format / is_atmos / is_default / "
            "forced / format) and UPDATE only those columns in place. Skips NFO / "
            "artwork / linker work. Much faster than re-running the full enrich."
        ),
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate scan without persisting any DB rows"),
    wait_for_lock: int = typer.Option(0, "--wait-for-lock", help="Seconds to wait for the writer lock"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
    confirm_bulk_change: bool = typer.Option(
        False,
        "--confirm-bulk-change",
        help="Bypass bulk-restore freeze guard (use after --mode quick reports a high Merkle delta).",
    ),
    rebuild: bool = typer.Option(
        False,
        "--rebuild",
        help="Quarantine corrupt DB and create a fresh one, then run full Stage-A scan.",
    ),
) -> None:
    """Run a full or quick media indexer scan.

    Walks all configured storage disks (or a single disk with --disk),
    records every file in the indexer database, and prints a JSON summary.

    Use --mode quick for a fast Merkle + dir-mtime short-circuit scan.
    Use --dry-run to simulate without committing any DB changes.
    Use --confirm-bulk-change to override the bulk-restore freeze guard.
    Use --rebuild to quarantine a corrupt DB and rebuild from scratch.

    Examples:
        personalscraper library-index
        personalscraper library-index --mode quick
        personalscraper library-index --disk MyDisk --mode full
        personalscraper library-index --dry-run --mode full
        personalscraper library-index --mode quick --confirm-bulk-change
        personalscraper library-index --rebuild
    """
    from uuid import uuid4  # noqa: PLC0415

    from personalscraper import cli as cli_compat  # noqa: PLC0415
    from personalscraper.cli_helpers import _build_app_context  # noqa: PLC0415
    from personalscraper.core.event_bus import current_correlation_id  # noqa: PLC0415
    from personalscraper.indexer.cli import library_index_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)

    # Build the process-scoped AppContext at the launchd command boundary
    # (Sub-phase 2.5 — boundary-only rule from DESIGN §Architecture). The
    # AppContext is built here even though ``library_index_command`` still
    # loads its own ``Config`` from ``config_path`` for backward
    # compatibility — only ``event_bus`` flows into the orchestrator
    # (Phase 4 adds ``LibraryIndexed`` emits).
    loaded_config = ctx.obj.config if ctx.obj is not None else None
    if loaded_config is not None:
        settings = cli_compat.get_settings()
        app_context = _build_app_context(loaded_config, settings)
        event_bus = app_context.event_bus
    else:
        event_bus = None  # init-config path; never reached for library-index in practice.

    # Bind a fresh ``run_id`` for the duration of the scan — every Event
    # constructed downstream captures it as ``correlation_id``.
    token = current_correlation_id.set(str(uuid4()))
    try:
        rc = library_index_command(
            mode=mode,
            disk=disk,
            budget_seconds=budget,
            no_budget=no_budget,
            backfill_streams=backfill_streams,
            dry_run=dry_run,
            wait_for_lock_seconds=wait_for_lock,
            config_path=effective_config,
            confirm_bulk_change=confirm_bulk_change,
            rebuild=rebuild,
            event_bus=event_bus,
        )
    finally:
        current_correlation_id.reset(token)
    if rc != 0:
        raise typer.Exit(rc)
