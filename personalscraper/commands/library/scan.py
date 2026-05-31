"""Scan/index Typer commands for the library."""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

_log = get_logger("library_backfill_ids")


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
    """Bootstrap ``canonical_provider`` and seed ``external_ids_json`` from NFO files.

    Walks ``media_item`` rows in two cohorts:

    * **canonical cohort**: ``canonical_provider IS NULL`` — sets both
      canonical AND external_ids_json from NFO ``<uniqueid>`` elements.
    * **chicken-and-egg cohort**: ``canonical_provider`` is already set but
      ``external_ids_json IS NULL`` or ``='{}'`` — only seeds external IDs
      without touching the existing canonical provider.

    When the default declares an unsupported type (e.g. ``imdb``), falls
    back to the first supported sibling uniqueid (``tvdb`` or ``tmdb``).
    Uses merge-additive semantics: existing families are never overwritten.

    This resolves the chicken-and-egg blocker (DEV #27 / #54): backfill-ids
    requires ``external_ids_json[canonical].series_id`` as its anchor, but
    neither value is set on databases that pre-date the provider-ids feature.

    .. note::
       This command never CHANGES an existing ``canonical_provider`` value.
       To migrate between canonical providers (e.g. ``tmdb`` → ``tvdb`` for
       shows to leverage TVDB-primary scrape discipline), use the Plan A
       workflow (``library-rescrape``) which resets + re-scrapes explicitly.
       See ``docs/archive/features/provider-ids/DESIGN.md`` §3 for the
       TVDB-primary-for-shows / TMDB-primary-for-movies design rationale.

    Items without a ``dispatch_path`` or without a readable/valid NFO are
    counted in the breakdown (no_dispatch_path, nfo_missing, nfo_parse_error,
    unsupported_no_fallback) so the operator can see WHY
    ``populated < total_visited``.

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

    # init_canonical writes to canonical_provider + external_ids_json; ensure DB
    # is opened read-write (the default — open_db has no mode= parameter).
    event_bus = EventBus()
    conn = open_db(db_path, event_bus=event_bus)
    apply_migrations(conn, _Path(migrations_dir_path))

    from personalscraper.cli_state import state  # noqa: PLC0415

    console = state["console"]

    if dry_run:
        stats = init_canonical_from_nfo(conn, dry_run=True)
        conn.close()
        console.print(
            _json.dumps(
                {
                    "dry_run": True,
                    "canonical_provider_populated": stats.populated,
                    "populated_default": stats.populated_default,
                    "populated_fallback": stats.populated_fallback,
                    "total_visited": stats.total_visited,
                    "external_ids_seeded_with_canonical": stats.external_ids_seeded_with_canonical,
                    "external_ids_seeded_alone": stats.external_ids_seeded_alone,
                    "external_ids_already_present": stats.external_ids_already_present,
                    "skipped": {
                        "no_dispatch_path": stats.no_dispatch_path,
                        "nfo_missing": stats.nfo_missing,
                        "nfo_parse_error": stats.nfo_parse_error,
                        "nfo_read_error": stats.nfo_read_error,
                        "no_default_uniqueid": stats.no_default_uniqueid,
                        "unsupported_no_fallback": stats.unsupported_no_fallback,
                    },
                }
            )
        )
        return

    try:
        stats = init_canonical_from_nfo(conn)
        conn.commit()
    finally:
        conn.close()
    # Surface the per-outcome breakdown so the operator can see WHY items
    # were skipped (silent populated=0 on 1491 items was a real prod incident
    # 2026-05-23). The JSON-style dict is grepable + machine-readable.
    console.print(
        _json.dumps(
            {
                "status": "ok",
                "canonical_provider_populated": stats.populated,
                "populated_default": stats.populated_default,
                "populated_fallback": stats.populated_fallback,
                "total_visited": stats.total_visited,
                "external_ids_seeded_with_canonical": stats.external_ids_seeded_with_canonical,
                "external_ids_seeded_alone": stats.external_ids_seeded_alone,
                "external_ids_already_present": stats.external_ids_already_present,
                "skipped": {
                    "no_dispatch_path": stats.no_dispatch_path,
                    "nfo_missing": stats.nfo_missing,
                    "nfo_parse_error": stats.nfo_parse_error,
                    "nfo_read_error": stats.nfo_read_error,
                    "no_default_uniqueid": stats.no_default_uniqueid,
                    "unsupported_no_fallback": stats.unsupported_no_fallback,
                },
            }
        )
    )


@app.command("library-scan")
@handle_cli_errors
def library_scan(
    ctx: typer.Context,
    disk: Optional[str] = typer.Option(None, "--disk", "-d", help="Restrict scan to this disk label"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate scan without persisting any DB rows"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Index the media library — visible alias of ``library-index --mode full``.

    Walks all configured storage disks (or a single disk with ``--disk``),
    reads NFO files, and writes the rich ``media_item`` / ``season`` /
    ``episode`` rows together with the file-level ``media_file`` / ``path``
    rows into the indexer database.  This command is a thin, re-pointed
    alias: it delegates to the very same
    :func:`~personalscraper.indexer.commands.scan.library_index_command`
    that backs ``library-index``, fixing ``mode="full"``.

    Because the delegation target is shared, this alias preserves the
    indexer's behaviour exactly: ``--disk`` validation (an unknown label
    exits non-zero), idempotent re-scans, a rolled-back savepoint for
    ``--dry-run`` (no rows persisted), and a single
    :class:`~personalscraper.indexer.events.LibraryScanCompleted` emitted
    per scan.  The printed JSON summary is the indexer's summary, not the
    legacy bespoke shape.

    The command is kept for backwards compatibility and remains visible in
    ``--help``.  Unlike the legacy command, it no longer exposes ``--mode``:
    the alias is always equivalent to ``--mode full``.

    Use ``--dry-run`` to simulate without committing any DB rows.  Use
    ``--disk`` to restrict the file-level walk to a single disk label (as
    configured in ``config/paths.json5``).

    Examples:
        personalscraper library-scan
        personalscraper library-scan --disk disk_1
        personalscraper library-scan --dry-run
        personalscraper library-scan --disk disk_1 --dry-run
    """
    from uuid import uuid4  # noqa: PLC0415

    from personalscraper import cli as cli_compat  # noqa: PLC0415
    from personalscraper.cli_helpers import _build_app_context  # noqa: PLC0415
    from personalscraper.core.event_bus import current_correlation_id  # noqa: PLC0415
    from personalscraper.indexer.cli import library_index_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)

    # Build the process-scoped AppContext at the launchd command boundary
    # (DESIGN §Architecture — boundary-only rule), mirroring ``library-index``.
    # Only ``event_bus`` flows into the orchestrator; ``library_index_command``
    # still loads its own ``Config`` from ``config_path``.
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
            mode="full",
            disk=disk,
            dry_run=dry_run,
            config_path=effective_config,
            event_bus=event_bus,
        )
    finally:
        current_correlation_id.reset(token)
    if rc != 0:
        raise typer.Exit(rc)


@app.command("library-backfill-ids")
@handle_cli_errors
def library_backfill_ids(
    ctx: typer.Context,
    show: Optional[str] = typer.Option(None, "--show", help="Restrict pass to a single show title"),
    ids_only: bool = typer.Option(False, "--ids-only", help="Only backfill provider IDs, skip ratings"),
    ratings_only: bool = typer.Option(False, "--ratings-only", help="Only backfill ratings, skip provider IDs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate without writing to DB"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Backfill missing cross-provider IDs and multi-source ratings on library items.

    Walks every ``media_item`` row (or a single show with ``--show``),
    detects missing provider IDs and rating sources, fetches the missing
    data from TMDB, TVDB, IMDb (via OMDb), and Rotten Tomatoes (via OMDb),
    and merges the results additively — never overwriting the canonical
    provider anchor or already-present values.

    Prerequisites (in order):

    1. Run ``personalscraper library-init-canonical`` to seed
       ``canonical_provider`` on rows that pre-date the provider-ids
       feature.  Backfill cannot resolve cross-provider IDs without a
       canonical anchor.

    2. Ensure API credentials are set in ``.env``:

       - ``TMDB_API_KEY`` — required for TMDB-canonical rows
       - ``TVDB_API_KEY`` — required for TVDB-canonical rows
       - ``OMDB_API_KEY`` — required for IMDb and Rotten Tomatoes ratings

    Use ``--dry-run`` to preview what would be backfilled without touching
    the database.  Use ``--ids-only`` or ``--ratings-only`` to restrict
    the pass to one dimension.

    Examples:
        personalscraper library-backfill-ids --dry-run
        personalscraper library-backfill-ids --show "Breaking Bad"
        personalscraper library-backfill-ids --ids-only
        personalscraper library-backfill-ids --ratings-only
    """
    import os as _os  # noqa: PLC0415

    from personalscraper import cli as cli_compat  # noqa: PLC0415
    from personalscraper.cli_helpers import _build_app_context  # noqa: PLC0415
    from personalscraper.conf.loader import load_config  # noqa: PLC0415
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415
    from personalscraper.indexer.scanner._modes.backfill_ids import run_backfill_ids  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    cfg = ctx.obj.config if ctx.obj is not None else load_config(effective_config)

    if cfg.indexer.db_path is None:
        typer.echo("indexer.db_path is not configured", err=True)
        raise typer.Exit(code=1)

    db_path = Path(cfg.indexer.db_path)
    migrations_dir = _os.path.dirname(_migrations_pkg.__file__)

    # Build AppContext at the CLI boundary to get the shared ProviderRegistry.
    # The indexer driver (sub-phase 11.5) now consumes the registry directly —
    # the four typed-client extractions (TMDB/TVDB/IMDb/RT) that previously
    # lived here are gone, and the registry handles chain/fan_out semantics
    # internally per DESIGN §6.
    settings = cli_compat.get_settings()
    app_context = _build_app_context(cfg, settings)
    registry = app_context.provider_registry if not dry_run else None

    # Open DB in writer mode, apply migrations, then run the backfill pass.
    conn = open_db(db_path, event_bus=app_context.event_bus)
    apply_migrations(conn, Path(migrations_dir))

    try:
        stats = run_backfill_ids(
            conn,
            event_bus=app_context.event_bus,
            registry=registry,
            show_filter=show,
            ids_only=ids_only,
            ratings_only=ratings_only,
            dry_run=dry_run,
        )
        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    # Use typer.echo (not console.print) — the JSON payload exceeds the default
    # Rich terminal width (~80 chars) and would be word-wrapped, breaking
    # downstream `jq` consumers and the regression test that re-parses it.
    typer.echo(
        _json.dumps(
            {
                "dry_run": dry_run,
                "items_scanned": stats.items_scanned,
                "items_updated": stats.items_updated,
                "items_skipped": stats.items_skipped,
                "items_failed": stats.items_failed,
                "ids_added_count": stats.ids_added_count,
                "ratings_added_count": stats.ratings_added_count,
            }
        )
    )
