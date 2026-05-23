"""Scan/index Typer commands for the library."""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.core.event_bus import EventBus


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
    # (DESIGN §Architecture — boundary-only rule). Only ``event_bus`` flows
    # into the orchestrator; ``library_index_command`` still loads its own
    # ``Config`` from ``config_path``.
    loaded_config = ctx.obj.config if ctx.obj is not None else None
    if loaded_config is not None:
        settings = cli_compat.get_settings()
        app_context = _build_app_context(loaded_config, settings)
        event_bus = app_context.event_bus
    else:
        # init-config path: ``ctx.obj.config`` was never populated. Fresh
        # unobserved bus keeps the required-bus contract local to this
        # CLI entry point.
        event_bus = EventBus()

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


@app.command("library-init-canonical")
@handle_cli_errors
def library_init_canonical(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Report counts without writing to DB"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Bootstrap ``canonical_provider`` on library items from their NFO files.

    Walks every ``media_item`` row where ``canonical_provider IS NULL``,
    resolves its NFO via the ``dispatch_path`` attribute, and reads the
    ``<uniqueid default="true">`` element's ``type`` attribute.  When
    found, sets ``canonical_provider`` accordingly so that a subsequent
    ``library-index --mode backfill-ids`` can use it as the anchor for
    cross-provider ID and rating enrichment.

    This is the bootstrap step for the chicken-and-egg problem on BDBs
    that pre-date the provider-ids feature (DEV #54): backfill-ids
    requires ``canonical_provider`` to be set, but nothing populates it
    on a DB that was indexed before the scraper wrote the field.

    Items without a ``dispatch_path`` attribute (scanner-only rows that
    have never been dispatched) or without a readable / valid NFO are
    silently skipped — the pass is best-effort by design.

    Examples:
        personalscraper library-init-canonical
        personalscraper library-init-canonical --dry-run
    """
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415
    from personalscraper.indexer.scanner._modes.backfill_ids import init_canonical_from_nfo  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)

    # Resolve config — reuse the standard loader used by other library commands.
    from personalscraper.conf.loader import load_config  # noqa: PLC0415

    cfg = ctx.obj.config if ctx.obj is not None else load_config(effective_config)
    from pathlib import Path as _Path  # noqa: PLC0415

    if cfg.indexer.db_path is None:
        typer.echo("indexer.db_path is not configured", err=True)
        raise typer.Exit(code=1)
    db_path = _Path(cfg.indexer.db_path)  # narrow Any|Path|None → Path for open_db()
    migrations_dir = _migrations_pkg.__file__
    import os as _os  # noqa: PLC0415

    migrations_dir_path = _os.path.dirname(migrations_dir)

    # Open DB in writer mode so we can UPDATE canonical_provider.
    event_bus = EventBus()
    conn = open_db(db_path, event_bus=event_bus)
    apply_migrations(conn, _Path(migrations_dir_path))

    from personalscraper.cli_state import state  # noqa: PLC0415

    console = state["console"]

    if dry_run:
        # Dry-run: count items with dispatch_path but no canonical_provider and
        # a readable NFO that carries a default uniqueid. Do not write.
        import sqlite3 as _sqlite3  # noqa: PLC0415

        conn.row_factory = _sqlite3.Row
        rows = conn.execute(
            "SELECT COUNT(*) FROM media_item m "
            "LEFT JOIN item_attribute ia ON ia.item_id = m.id AND ia.key = 'dispatch_path' "
            "WHERE m.canonical_provider IS NULL"
        ).fetchone()
        null_count = rows[0] if rows else 0
        conn.close()
        console.print(_json.dumps({"dry_run": True, "items_without_canonical_provider": null_count}))
        return

    try:
        populated = init_canonical_from_nfo(conn)
        conn.commit()
    finally:
        conn.close()

    console.print(_json.dumps({"status": "ok", "canonical_provider_populated": populated}))


@app.command("library-scan")
@handle_cli_errors
def library_scan(
    ctx: typer.Context,
    disk: Optional[str] = typer.Option(None, "--disk", "-d", help="Restrict scan to this disk label"),
    mode: str = typer.Option("full", "--mode", help="Scan mode (currently only 'full' is supported)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Count media dirs without writing to DB"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Scan media directories on disks and create media_item rows from NFOs.

    Walks all configured storage disks (or a single disk with --disk),
    scans movie / TV show directories, reads NFO files, and writes
    ``media_item``, ``season``, ``episode``, and ``item_attribute`` rows
    to the indexer DB.  Delegates file-level indexing to the underlying
    indexer scanner so ``media_file`` / ``path`` rows are also populated.

    Use ``--dry-run`` to count directories that would be scanned without
    writing any DB rows.  Use ``--disk`` to restrict the scan to a single
    disk label (as configured in ``config/paths.json5``).

    Examples:
        personalscraper library-scan
        personalscraper library-scan --disk disk_1
        personalscraper library-scan --dry-run
        personalscraper library-scan --disk disk_1 --dry-run
    """
    import os as _os  # noqa: PLC0415

    from personalscraper import cli as cli_compat  # noqa: PLC0415
    from personalscraper.cli_helpers import per_step_boundary  # noqa: PLC0415
    from personalscraper.cli_state import state as _state  # noqa: PLC0415
    from personalscraper.conf.loader import load_config  # noqa: PLC0415
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415
    from personalscraper.library.scanner import scan_library  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    cfg = ctx.obj.config if ctx.obj is not None else load_config(effective_config)
    console = _state["console"]

    # Validate --disk filter early so the user gets a clear error message
    # before we open the DB or acquire the writer lock.
    if disk is not None:
        disk_ids = {d.id for d in cfg.disks}
        if disk not in disk_ids:
            typer.echo(
                f"Unknown disk '{disk}'. Configured disks: {', '.join(sorted(disk_ids))}",
                err=True,
            )
            raise typer.Exit(code=1)

    if dry_run:
        # Dry-run: count media directories that would be scanned.  Walk the
        # category directories without writing any DB rows.
        total_dirs = 0
        for disk_cfg in cfg.disks:
            if disk is not None and disk_cfg.id != disk:
                continue
            if not disk_cfg.path.exists():
                console.print(f"[yellow]Disk not mounted — skipping: {disk_cfg.id}[/yellow]")
                continue
            for category_id in disk_cfg.categories:
                cat_cfg = cfg.category(category_id)
                category_dir = disk_cfg.path / cat_cfg.folder_name
                if not category_dir.is_dir():
                    continue
                total_dirs += sum(1 for d in category_dir.iterdir() if d.is_dir() and not d.name.startswith("."))
        console.print(_json.dumps({"dry_run": True, "media_dirs_to_scan": total_dirs, "disk_filter": disk}))
        return

    # Live scan — acquire writer lock, open DB, call scan_library.
    if not cli_compat.acquire_lock():
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)

    if cfg.indexer.db_path is None:
        typer.echo("indexer.db_path is not configured", err=True)
        raise typer.Exit(code=1)
    db_path = Path(cfg.indexer.db_path)  # narrow Any|Path|None → Path for mypy strict mode

    migrations_dir = _os.path.dirname(_migrations_pkg.__file__)

    try:
        settings = cli_compat.get_settings()
        with per_step_boundary(cfg, settings) as app_context:
            conn = open_db(db_path, event_bus=app_context.event_bus)
            apply_migrations(conn, Path(migrations_dir))
            try:
                # Apply --disk filter by restricting config.disks to the
                # requested disk only.  We shadow the attribute rather than
                # mutating the shared config so other components remain
                # unaffected.
                if disk is not None:
                    filtered_disks = [d for d in cfg.disks if d.id == disk]
                    cfg = cfg.model_copy(update={"disks": filtered_disks})

                scan_library(cfg, conn, event_bus=app_context.event_bus)
                conn.commit()
            finally:
                conn.close()
    finally:
        cli_compat.release_lock()

    console.print(_json.dumps({"status": "ok", "disk_filter": disk}))
