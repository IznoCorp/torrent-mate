"""Library maintenance Typer commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import typer

from personalscraper import cli as cli_compat
from personalscraper.cli_app import app
from personalscraper.cli_helpers import _resolve_category, handle_cli_errors
from personalscraper.cli_state import state
from personalscraper.logger import get_logger

log = get_logger("cli")


@app.command()
@handle_cli_errors
def library_scan(
    ctx: typer.Context,
    disk: str = typer.Option(None, "--disk", help="Scan only this disk (id from config)"),
    category: str = typer.Option(None, "--category", help="Scan only this category"),
) -> None:
    """Scan library structure and populate the indexer database.

    Walks all configured storage disks and records every media file in the
    indexer database.  The ``--disk`` and ``--category`` filters are no longer
    supported (the indexer always performs a full scan); passing them prints a
    deprecation warning and the flags are ignored.

    Use ``library-index`` for the full-featured indexer command.

    Examples:
        personalscraper library-scan
    """
    import sqlite3  # noqa: PLC0415

    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415
    from personalscraper.library.scanner import scan_library  # noqa: PLC0415

    console = state["console"]
    config = ctx.obj.config

    # --disk and --category are no longer forwarded to scan_library; warn once.
    if disk is not None:
        console.print(
            "[yellow]Warning:[/yellow] --disk is deprecated for library-scan "
            "and is ignored. Use library-index --disk instead."
        )
    if category is not None:
        console.print(
            "[yellow]Warning:[/yellow] --category is deprecated for library-scan "
            "and is ignored. Use library-index instead."
        )

    db_path = config.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn: sqlite3.Connection = open_db(db_path)
    apply_migrations(conn, migrations_dir)

    console.print("[bold]Scanning library...[/bold]")
    scan_library(config, conn)

    total = conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0]
    console.print(f"[green]Scan complete:[/green] {total} files indexed in {db_path}")


@app.command("library-status")
@handle_cli_errors
def library_status(
    ctx: typer.Context,
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Show the latest completed indexer scan run summary.

    Queries the indexer database for the most recently completed scan run
    and prints a one-line summary.  Prints "no scans yet" when the database
    has no completed scan runs.

    Examples:
        personalscraper library-status
        personalscraper library-status --config /path/to/config.json5
    """
    from personalscraper.indexer.cli import library_status_command  # noqa: PLC0415

    # Prefer explicit --config passed to this sub-command; fall back to the
    # global --config stored on the app context.
    effective_config: Path | None = config or (ctx.obj.config_override if ctx.obj else None)
    rc = library_status_command(effective_config)
    raise typer.Exit(rc)


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
    from personalscraper.indexer.cli import library_index_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
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
    )
    if rc != 0:
        raise typer.Exit(rc)


@app.command("library-verify")
@handle_cli_errors
def library_verify(
    ctx: typer.Context,
    disk: Optional[str] = typer.Option(None, "--disk", help="Restrict verification to this disk label"),
    budget: Optional[int] = typer.Option(
        None,
        "--budget",
        help="Wall-clock budget in seconds; partial verifies are safe to resume.",
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Re-stat every indexed file and mark mismatches for repair.

    Runs a verify-mode scan that re-checks every file's stat metadata against
    the stored snapshot.  Files that no longer match are escalated to the repair
    queue — they are NOT soft-deleted.  Use this command to identify drift
    before deciding whether to accept or revert changes.

    With ``--budget`` the verify pass exits cleanly when the wall-clock limit
    is reached; the next invocation continues from where it stopped (every
    file commits ``last_verified_at`` individually so partial progress is
    preserved across runs).

    Examples:
        personalscraper library-verify
        personalscraper library-verify --disk Disk2
        personalscraper library-verify --budget 300
    """
    from personalscraper.indexer.cli import library_verify_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    rc = library_verify_command(
        disk=disk,
        budget_seconds=float(budget) if budget is not None else None,
        config_path=effective_config,
    )
    if rc != 0:
        raise typer.Exit(rc)


@app.command("library-search")
@handle_cli_errors
def library_search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Query string, e.g. 'year:2024 disk:Disk1 -nfo:valid'"),
    limit: int = typer.Option(50, "--limit", help="Maximum number of results to return"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Search indexed media items with the flex-attr query language.

    Field syntax: ``field:value``, ``-field:value`` (negation), ``year:>=2020``,
    ``title:"Exact Title"``.  Unknown fields exit 2.

    Examples:
        personalscraper library-search "year:2024 disk:Disk1 -nfo:valid"
        personalscraper library-search "kind:show codec:hevc -trailer"
        personalscraper library-search 'title:"Lost Highway"'
    """
    from personalscraper.indexer.cli import library_search_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    rc = library_search_command(query, limit=limit, config_path=effective_config)
    if rc != 0:
        raise typer.Exit(rc)


@app.command("library-repair")
@handle_cli_errors
def library_repair(
    ctx: typer.Context,
    budget: int = typer.Option(60, "--budget", help="Maximum seconds to spend draining the repair queue"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Drain the repair queue within a time budget.

    Processes pending repair rows in FIFO order.  Stops cleanly when the budget
    is exhausted.  Prints a JSON summary of processed / succeeded / failed counts.

    Examples:
        personalscraper library-repair
        personalscraper library-repair --budget 120
    """
    from personalscraper.indexer.cli import library_repair_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    rc = library_repair_command(budget_seconds=float(budget), config_path=effective_config)
    if rc != 0:
        raise typer.Exit(rc)


@app.command("library-reconcile")
@handle_cli_errors
def library_reconcile(
    ctx: typer.Context,
    scope: list[str] = typer.Option(
        [],
        "--scope",
        help=(
            "Restrict to a detector scope (repeatable). "
            "Choices: merkle, dispatch_path, enrich, release, season, item. "
            "Omit to run every detector."
        ),
    ),
    enqueue_repairs: bool = typer.Option(
        False,
        "--enqueue-repairs",
        help="Push every divergence into repair_queue for library-repair to drain.",
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Detect index ↔ filesystem divergences without a full rescan.

    Runs DB-only checks (one ``Path.exists()`` for the dispatch_path
    detector — every other detector is pure SQL) and prints a JSON
    report of findings.  Optionally enqueues each finding into
    ``repair_queue`` so ``library-repair`` can fix them within a
    bounded budget.

    Detector scopes:

    - ``merkle`` — disk merkle drift between stored and computed roots.
    - ``dispatch_path`` — items whose dispatch_path attribute is gone.
    - ``enrich`` — files whose enriched_at is older than mtime.
    - ``release`` — orphan media_release rows + null-release files.
    - ``season`` — denormalised season.episode_count drift.
    - ``item`` — media_item rows with no file evidence.

    Examples:
        personalscraper library-reconcile
        personalscraper library-reconcile --scope enrich --scope release
        personalscraper library-reconcile --enqueue-repairs
    """
    from personalscraper.indexer.cli import library_reconcile_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    rc = library_reconcile_command(
        scopes=scope if scope else None,
        enqueue_repairs=enqueue_repairs,
        config_path=effective_config,
    )
    if rc != 0:
        raise typer.Exit(rc)


@app.command("library-ghost-audit")
@handle_cli_errors
def library_ghost_audit(
    ctx: typer.Context,
    disk: str = typer.Option(None, "--disk", help="Audit only this disk (id from config)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Audit storage disks for NTFS-via-macFUSE ghost dirents.

    Walks every directory on each storage disk and lists every entry
    that ``os.scandir`` reports but ``os.stat`` cannot reach. These
    "ghost" entries are produced by macFUSE-NTFS when the directory
    listing returns a filename in one Unicode normalisation form (NFD)
    while the kernel inode is keyed under the other (NFC). Once a ghost
    exists, the directory cannot be emptied — neither ``rm -rf`` nor
    the project's own ``_scandir_rmtree`` walker can remove it.

    The audit is read-only: it only reports the paths. Recovery
    requires unmounting the affected NTFS volume and either running
    fsck on it or mounting it on a Windows host that can repair the
    directory entry.

    Output: per-disk count and a sample list of ghost paths.

    Examples:
        personalscraper library-ghost-audit
        personalscraper library-ghost-audit --disk Disk1
    """
    import os as _os  # noqa: PLC0415

    console = state["console"]
    cfg = ctx.obj.config
    assert cfg is not None

    total_ghosts = 0
    for d in cfg.disks:
        if disk and d.id != disk:
            continue
        if not d.path.exists():
            console.print(f"[yellow]{d.id}: not mounted, skipped[/yellow]")
            continue
        ghosts: list[str] = []
        try:
            for root, dirs, files in _os.walk(str(d.path)):
                for entry_name in list(dirs) + list(files):
                    full = _os.path.join(root, entry_name)
                    try:
                        _os.stat(full)
                    except FileNotFoundError:
                        ghosts.append(full)
                    except OSError:
                        # Permission denied / EIO are not ghosts; skip.
                        continue
        except OSError as exc:
            console.print(f"[red]{d.id}: walk error: {exc}[/red]")
            continue

        total_ghosts += len(ghosts)
        if ghosts:
            console.print(f"[red]{d.id}: {len(ghosts)} ghost dirent(s)[/red]")
            for g in ghosts[:10]:
                console.print(f"  {g}")
            if len(ghosts) > 10:
                console.print(f"  … and {len(ghosts) - 10} more")
        else:
            console.print(f"[green]{d.id}: clean[/green]")

    if total_ghosts == 0:
        console.print("[bold green]All disks clean — no ghost dirents.[/bold green]")
    else:
        console.print(
            f"[bold red]{total_ghosts} total ghost dirent(s) across all audited disks.[/bold red]\n"
            "Recovery: unmount the affected NTFS volume and run fsck, or "
            "remount on a Windows host to repair the directory entries."
        )
        raise typer.Exit(1)


@app.command("library-relink")
@handle_cli_errors
def library_relink(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help="Persist link updates (default: dry-run)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Relink ``media_file`` rows whose ``release_id`` is NULL.

    Walks every ``media_file`` row with ``release_id IS NULL AND
    deleted_at IS NULL`` and replays
    :func:`~personalscraper.indexer.release_linker.link_file_to_release`
    against the file's absolute path. The function resolves the owning
    item via the same dispatch_path / title / title-year strategies the
    enrich pass uses, so this is a self-healing recovery for files that
    were inserted before their item was dispatched (cold Stage A) or
    after a release_linker bug left the link behind.

    Output is the count of (linked, unmatched, errored) files. Use
    ``--apply`` to commit; the dry-run mode reports the same numbers
    without touching the database.

    Examples:
        personalscraper library-relink
        personalscraper library-relink --apply
    """
    import sqlite3 as _sqlite3  # noqa: PLC0415
    from pathlib import Path as _Path  # noqa: PLC0415

    from personalscraper.indexer.release_linker import link_file_to_release  # noqa: PLC0415

    console = state["console"]
    cfg = ctx.obj.config
    assert cfg is not None
    db_path = cfg.indexer.db_path

    conn = _sqlite3.connect(str(db_path))
    try:
        disks = {did: _Path(mp) for did, mp in conn.execute("SELECT id, mount_path FROM disk WHERE is_mounted = 1")}
        if not disks:
            console.print("[yellow]No mounted disks — nothing to relink.[/yellow]")
            raise typer.Exit(0)

        rows = list(
            conn.execute(
                """
                SELECT mf.id, mf.filename, p.disk_id, p.rel_path
                FROM media_file mf
                JOIN path p ON p.id = mf.path_id
                WHERE mf.release_id IS NULL AND mf.deleted_at IS NULL
                """,
            )
        )
        if not rows:
            console.print("[green]No orphan media_file rows. Library is fully linked.[/green]")
            raise typer.Exit(0)

        console.print(f"Found [bold]{len(rows)}[/bold] orphan media_file row(s).")
        linked = unmatched = errors = 0
        for mf_id, filename, disk_id, rel_path in rows:
            mount = disks.get(disk_id)
            if mount is None:
                continue
            abs_path = mount / rel_path / filename
            try:
                result = link_file_to_release(conn, mf_id, str(abs_path))
                if result is not None:
                    linked += 1
                else:
                    unmatched += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                log.warning("library_relink_failed", file_id=mf_id, path=str(abs_path), error=str(exc))

        if apply:
            conn.commit()
            console.print(
                f"[green]Applied:[/green] linked={linked}, unmatched={unmatched}, errors={errors}",
            )
        else:
            conn.rollback()
            console.print(
                f"[yellow]DRY-RUN:[/yellow] would link={linked}, unmatched={unmatched}, errors={errors}",
            )
    finally:
        conn.close()


@app.command("library-show")
@handle_cli_errors
def library_show(
    ctx: typer.Context,
    item_id: int = typer.Argument(..., help="media_item.id to display"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Pretty-print all stored data for a single media item.

    Prints media_item fields, season/episode rows, media_file rows with streams,
    item_attribute rows, and deleted_item history.  Exits 2 for unknown ids.

    Examples:
        personalscraper library-show 42
    """
    from personalscraper.indexer.cli import library_show_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    rc = library_show_command(item_id, config_path=effective_config)
    if rc != 0:
        raise typer.Exit(rc)


@app.command()
@handle_cli_errors
def library_clean(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help="Actually delete (default: dry-run)"),
    only: str = typer.Option(
        None,
        "--only",
        help="Only clean: actors, empty, junk, release, orphans",
    ),
    disk: str = typer.Option(None, "--disk", help="Clean only this disk (id from config)"),
    category: str = typer.Option(None, "--category", help="Clean only this category"),
) -> None:
    """Remove .actors/, empty dirs, junk files from storage disks.

    Dry-run by default — shows what would be deleted without deleting.
    Use --apply to actually execute deletions.
    Use --only to target specific cleanup types.

    The ``orphans`` mode targets stale release directories that no longer
    contain a main video file — typically ``.actors/`` + trailer + NFO + artwork
    left behind after a manual video delete. It is opt-in (never part of the
    default "all" run) because the deletion granularity is the entire release
    directory.

    Examples:
        personalscraper library-clean
        personalscraper library-clean --apply
        personalscraper library-clean --apply --only actors
        personalscraper library-clean --only orphans                # dry-run
        personalscraper library-clean --only orphans --apply        # delete
        personalscraper library-clean --disk Disk1
    """
    from personalscraper.library.disk_cleaner import clean_library

    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config

    # Validate --only parameter
    valid_only = {"actors", "empty", "junk", "release", "orphans"}
    if only and only not in valid_only:
        console.print(f"[red]Invalid --only value '{only}'. Valid: {', '.join(sorted(valid_only))}[/red]")
        raise typer.Exit(1)

    # Acquire lock only when applying changes
    if apply:
        if not cli_compat.acquire_lock():
            console.print("[red]Another instance is running. Exiting.[/red]")
            raise typer.Exit(1)

    try:
        mode = "[bold red]APPLY[/bold red]" if apply else "[bold yellow]DRY-RUN[/bold yellow]"
        console.print(f"[bold]Cleaning library ({mode})...[/bold]")

        result = clean_library(
            config,
            apply=apply,
            only=only,
            disk_filter=disk,
            category_filter=category_id,
        )

        if result.dry_run:
            console.print(
                f"[yellow]DRY-RUN:[/yellow] Would delete {result.deleted_count} items "
                f"({result.freed_bytes / 1024 / 1024:.1f} MB)"
            )
            # Orphan deletes a whole release directory at once — high blast
            # radius. List the first matches so the operator can sanity-check
            # before re-running with --apply.
            if only == "orphans" and result.details:
                preview = result.details[:20]
                console.print(f"[dim]Preview ({len(preview)} of {len(result.details)}):[/dim]")
                for line in preview:
                    console.print(f"  {line}")
                if len(result.details) > len(preview):
                    console.print(f"  [dim]… and {len(result.details) - len(preview)} more[/dim]")
        else:
            console.print(
                f"[green]Deleted:[/green] {result.deleted_count} items "
                f"({result.freed_bytes / 1024 / 1024:.1f} MB freed)"
            )
            if result.error_count:
                console.print(f"[red]Errors:[/red] {result.error_count} deletions failed (NTFS)")
                for err in result.errors:
                    console.print(f"  {err}")
    finally:
        if apply:
            cli_compat.release_lock()


@app.command()
@handle_cli_errors
def library_validate(
    ctx: typer.Context,
    disk: str = typer.Option(None, "--disk", help="Validate only this disk"),
    category: str = typer.Option(None, "--category", help="Validate only this category"),
    fix: bool = typer.Option(False, "--fix", help="Attempt automatic fixes"),
    apply: bool = typer.Option(False, "--apply", help="Apply fixes (requires --fix)"),
    from_index: bool = typer.Option(
        False,
        "--from-index",
        help=(
            "Read NFO + artwork status from the indexer DB instead of walking "
            "the filesystem. Skips structural checks (empty dirs, NTFS chars, "
            "dir naming) and does not support --fix. See validate_from_index "
            "docstring for the full trade-off list."
        ),
    ),
) -> None:
    """Validate NFO, artwork, naming conformity of library items.

    Checks each media item on storage disks against quality rules.
    Use --fix --apply to attempt automatic corrections.
    Use --from-index for a fast pre-screen that reads NFO + artwork status
    from the indexer DB (NFO presence + poster/landscape only; no structural
    checks; no --fix support).

    Examples:
        personalscraper library-validate
        personalscraper library-validate --disk Disk1
        personalscraper library-validate --fix --apply
        personalscraper library-validate --from-index
    """
    from personalscraper.library.models import write_json
    from personalscraper.library.validator import validate_from_index, validate_library

    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config

    if from_index and (fix or apply):
        console.print("[red]--from-index does not support --fix / --apply[/red]")
        raise typer.Exit(1)

    if apply and not fix:
        console.print("[red]--apply requires --fix[/red]")
        raise typer.Exit(1)

    if fix and apply:
        if not cli_compat.acquire_lock():
            console.print("[red]Another instance is running. Exiting.[/red]")
            raise typer.Exit(1)

    try:
        if from_index:
            console.print("[bold]Validating library (from index)...[/bold]")
            import sqlite3  # noqa: PLC0415

            from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
            from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

            db_path = config.indexer.db_path
            migrations_dir = Path(_migrations_pkg.__file__).parent
            conn: sqlite3.Connection = open_db(db_path)
            apply_migrations(conn, migrations_dir)
            try:
                result = validate_from_index(
                    conn,
                    disk_filter=disk,
                    category_filter=category_id,
                )
            finally:
                conn.close()
        else:
            console.print("[bold]Validating library...[/bold]")
            result = validate_library(
                config,
                disk_filter=disk,
                category_filter=category_id,
                fix=fix,
                apply=apply,
            )

        output_path = config.paths.data_dir / "library_validation.json"
        write_json(result, output_path)

        console.print(
            f"[green]Valid:[/green] {result.valid_count}  "
            f"[yellow]Fixed:[/yellow] {result.fixed_count}  "
            f"[red]Issues:[/red] {result.issues_count}  "
            f"→ {output_path}"
        )

        if fix and result.issues_count:
            console.print(
                f"\n[yellow]{result.issues_count} items have API-dependent issues.[/yellow]\n"
                "  Use: personalscraper library-rescrape"
            )
    finally:
        if fix and apply:
            cli_compat.release_lock()


@app.command()
@handle_cli_errors
def library_analyze(
    ctx: typer.Context,
    disk: str = typer.Option(None, "--disk", help="Analyze only this disk"),
    category: str = typer.Option(None, "--category", help="Analyze only this category"),
    max_items: int = typer.Option(None, "--max-items", help="Limit number of items to analyze"),
    from_index: bool = typer.Option(
        False,
        "--from-index",
        help=(
            "Read codec / audio / subtitle data from the indexer DB instead of "
            "running ffprobe per file. Requires a prior `library-index --mode enrich` "
            "pass; HDR / Atmos detection is approximated (see analyze_from_index docstring)."
        ),
    ),
) -> None:
    """Deep scan video files with ffprobe (codec, audio, subtitles) and print a summary.

    Most I/O-intensive command — schedule during off-peak hours. Use
    ``--from-index`` to read enrich-populated streams from the DB instead
    (orders of magnitude faster, with the documented HDR / Atmos caveats).

    The result set is **not persisted to disk** (the legacy
    ``library_analysis.json`` cache was removed when the indexer DB became
    the single source of truth).  ``library-recommend`` runs this scan
    inline before producing recommendations, so there is no need to call
    ``library-analyze`` first as a side-effect setup step.

    Examples:
        personalscraper library-analyze
        personalscraper library-analyze --disk <disk_id> --category series
        personalscraper library-analyze --max-items 50
        personalscraper library-analyze --from-index
    """
    from personalscraper.library.analyzer import analyze_from_index, analyze_library

    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config

    if from_index:
        console.print("[bold]Analyzing library (from index)...[/bold]")
        import sqlite3  # noqa: PLC0415

        from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
        from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

        db_path = config.indexer.db_path
        migrations_dir = Path(_migrations_pkg.__file__).parent
        conn: sqlite3.Connection = open_db(db_path)
        apply_migrations(conn, migrations_dir)
        try:
            result = analyze_from_index(
                conn,
                disk_filter=disk,
                category_filter=category_id,
                max_items=max_items,
            )
        finally:
            conn.close()
    else:
        console.print("[bold]Analyzing library (ffprobe)...[/bold]")
        result = analyze_library(
            config,
            disk_filter=disk,
            category_filter=category_id,
            max_items=max_items,
        )

    # Aggregate codec / audio profile distributions for the summary.
    codec_counts: dict[str, int] = {}
    audio_counts: dict[str, int] = {}
    for item in result.items:
        for media_file in item.files:
            codec = media_file.video.codec or "unknown"
            codec_counts[codec] = codec_counts.get(codec, 0) + 1
            profile = media_file.audio_profile or "unknown"
            audio_counts[profile] = audio_counts.get(profile, 0) + 1

    console.print(f"[green]Analysis complete:[/green] {result.item_count} items, {result.file_count} files")
    if codec_counts:
        codecs = ", ".join(f"{c}={n}" for c, n in sorted(codec_counts.items(), key=lambda kv: -kv[1]))
        console.print(f"  Codecs: {codecs}")
    if audio_counts:
        audio = ", ".join(f"{p}={n}" for p, n in sorted(audio_counts.items(), key=lambda kv: -kv[1]))
        console.print(f"  Audio profiles: {audio}")


@app.command()
@handle_cli_errors
def library_recommend(
    ctx: typer.Context,
    sort: str = typer.Option("priority", "--sort", help="Sort by: priority, size, codec"),
    export: str = typer.Option(None, "--export", help="Export format: csv"),
    disk: str = typer.Option(None, "--disk", help="Filter to this disk"),
    category: str = typer.Option(None, "--category", help="Filter to this category"),
    from_index: bool = typer.Option(
        False,
        "--from-index",
        help=(
            "Read codec / audio / subtitle data from the indexer DB instead of "
            "running ffprobe per file. Requires a prior `library-index --mode enrich` "
            "pass."
        ),
    ),
) -> None:
    """Generate re-download recommendations from a fresh ffprobe analysis.

    Runs the ffprobe analysis inline (no on-disk cache) and feeds the
    in-memory result to the recommender.  Preferences come from
    ``config.library``.  Output is written to ``library_recommendations.json``.
    Pass ``--from-index`` to skip ffprobe and read streams from the indexer
    DB instead (orders of magnitude faster on a populated index).

    Examples:
        personalscraper library-recommend
        personalscraper library-recommend --sort size
        personalscraper library-recommend --export csv
        personalscraper library-recommend --from-index
    """
    import csv

    from personalscraper.library.analyzer import analyze_from_index, analyze_library
    from personalscraper.library.models import write_json
    from personalscraper.library.recommender import generate_recommendations

    # Resolve alias now so unknown --category values fail fast.
    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config

    # Validate --sort parameter
    valid_sorts = {"priority", "size", "codec"}
    if sort not in valid_sorts:
        console.print(f"[red]Invalid --sort value '{sort}'. Valid: {', '.join(sorted(valid_sorts))}[/red]")
        raise typer.Exit(1)

    if from_index:
        console.print("[bold]Analyzing library (from index)...[/bold]")
        import sqlite3  # noqa: PLC0415

        from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
        from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

        db_path = config.indexer.db_path
        migrations_dir = Path(_migrations_pkg.__file__).parent
        conn: sqlite3.Connection = open_db(db_path)
        apply_migrations(conn, migrations_dir)
        try:
            analysis = analyze_from_index(
                conn,
                disk_filter=disk,
                category_filter=category_id,
            )
        finally:
            conn.close()
    else:
        # Run analysis inline — no on-disk cache.  The legacy
        # library_analysis.json was removed when the indexer DB became the
        # single source of truth (DESIGN §10.2).
        console.print("[bold]Analyzing library (ffprobe)...[/bold]")
        analysis = analyze_library(
            config,
            disk_filter=disk,
            category_filter=category_id,
        )

    # Use preferences from config.library (no separate file).
    prefs = config.library

    result = generate_recommendations(analysis.items, prefs)

    # Sort
    sort_keys = {
        "priority": lambda r: {"high": 0, "medium": 1, "low": 2}.get(r.priority, 3),
        "size": lambda r: -(r.estimated_savings_gb or 0),
        "codec": lambda r: r.current.codec,
    }
    if sort in sort_keys:
        result.items.sort(key=sort_keys[sort])

    # Write JSON
    output_path = config.paths.data_dir / "library_recommendations.json"
    write_json(result, output_path)

    # CSV export
    if export == "csv":
        csv_path = config.paths.data_dir / "library_recommendations.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "title",
                    "type",
                    "disk",
                    "codec",
                    "resolution",
                    "size_gb",
                    "audio",
                    "priority",
                    "savings_gb",
                    "reasons",
                ]
            )
            for r in result.items:
                writer.writerow(
                    [
                        r.title,
                        r.media_type,
                        r.disk,
                        r.current.codec,
                        r.current.resolution,
                        f"{r.current.size_gb:.1f}",
                        r.current.audio_profile,
                        r.priority,
                        f"{r.estimated_savings_gb or 0:.1f}",
                        "; ".join(r.reasons),
                    ]
                )
        console.print(f"[green]CSV exported:[/green] {csv_path}")

    console.print(
        f"[green]Recommendations:[/green] {result.total_recommendations} items, "
        f"~{result.estimated_total_savings_gb:.1f} GB potential savings → {output_path}"
    )


@app.command()
@handle_cli_errors
def library_rescrape(
    ctx: typer.Context,
    only: str = typer.Option(None, "--only", help="Only fix: nfo, artwork, episodes"),
    disk: str = typer.Option(None, "--disk", help="Rescrape only this disk"),
    category: str = typer.Option(None, "--category", help="Rescrape only this category"),
    interactive: bool = typer.Option(False, "--interactive", help="Confirm low-confidence matches"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying files"),
    max_items: int = typer.Option(None, "--max-items", help="Limit number of items to process"),
) -> None:
    """Targeted re-scrape of library items via TMDB/TVDB.

    Only repairs what is broken per item: missing NFO, missing artwork,
    unrenamed episodes. Items already conforming are skipped.

    Examples:
        personalscraper library-rescrape --dry-run
        personalscraper library-rescrape --only artwork
        personalscraper library-rescrape --disk <disk_id> --max-items 50
        personalscraper library-rescrape --interactive
    """
    from personalscraper.library.models import write_json
    from personalscraper.library.rescraper import rescrape_library

    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config
    settings = cli_compat.get_settings()

    valid_only = {"nfo", "artwork", "episodes"}
    if only and only not in valid_only:
        console.print(f"[red]Invalid --only value '{only}'. Valid: {', '.join(sorted(valid_only))}[/red]")
        raise typer.Exit(1)

    if not dry_run:
        if not cli_compat.acquire_lock():
            console.print("[red]Another instance is running. Exiting.[/red]")
            raise typer.Exit(1)

    try:
        mode = "[bold yellow]DRY-RUN[/bold yellow]" if dry_run else "[bold green]LIVE[/bold green]"
        console.print(f"[bold]Rescraping library ({mode})...[/bold]")

        result = rescrape_library(
            config,
            settings,
            disk_filter=disk,
            category_filter=category_id,
            only=only,
            interactive=interactive,
            dry_run=dry_run,
            max_items=max_items,
        )

        output_path = config.paths.data_dir / "library_rescrape.json"
        write_json(result, output_path)

        total = result.fixed_count + result.skipped_count + result.error_count
        console.print(
            f"[green]Fixed:[/green] {result.fixed_count}  "
            f"[yellow]Skipped:[/yellow] {result.skipped_count}  "
            f"[red]Errors:[/red] {result.error_count}  "
            f"(total: {total}) → {output_path}"
        )
    finally:
        if not dry_run:
            cli_compat.release_lock()


@app.command()
@handle_cli_errors
def library_report(
    ctx: typer.Context,
    format: str = typer.Option("text", "--format", help="Output format: text or json"),
) -> None:
    """Display library statistics and health report.

    Aggregates data from the indexer DB (totals, NFO / artwork health, disk
    distribution, per-item sizes) and supplementary JSON outputs from
    ``library-validate``, ``library-recommend``, and ``library-rescrape``.

    Examples:
        personalscraper library-report
        personalscraper library-report --format json
    """
    from personalscraper.dispatch.disk_scanner import get_disk_status
    from personalscraper.indexer.db import open_db
    from personalscraper.library.analyzer import analyze
    from personalscraper.library.models import read_json, write_json
    from personalscraper.library.reporter import format_report_text, generate_report

    config = ctx.obj.config
    console = state["console"]

    # Load supplementary JSON outputs (validation, recommendations, rescrape).
    # The legacy library_scan.json / library_analysis.json files are no
    # longer read — the indexer DB is the source of truth (DESIGN §10.2).
    def _load(name: str) -> dict[str, Any] | None:
        path = config.paths.data_dir / name
        if path.exists():
            try:
                return read_json(path)
            except (OSError, ValueError) as exc:
                log.warning("report_data_load_failed", file=name, error=str(exc))
                console.print(f"[yellow]Warning: {name} corrupted ({exc}), skipping.[/yellow]")
                return None
        return None

    validation_data = _load("library_validation.json")
    recommendation_data = _load("library_recommendations.json")
    rescrape_data = _load("library_rescrape.json")

    # Query the indexer DB for totals, NFO / artwork health, disk distribution.
    db_path = config.indexer.db_path
    analysis_result = None
    if db_path.exists():
        try:
            conn = open_db(db_path)
            analysis_result = analyze(conn)
            conn.close()
        except Exception as exc:
            log.warning("report_indexer_query_failed", error=str(exc))
            console.print(f"[yellow]Warning: indexer DB query failed ({exc}), skipping analysis.[/yellow]")

    if not any([analysis_result, validation_data, recommendation_data, rescrape_data]):
        console.print("[yellow]No library data found. Run library-index first.[/yellow]")
        raise typer.Exit(1)

    # Get live disk free space
    disk_statuses = [get_disk_status(dc) for dc in config.disks]

    report = generate_report(
        analysis_result,
        validation_data,
        recommendation_data,
        disk_statuses=disk_statuses,
        rescrape_data=rescrape_data,
    )

    if format == "json":
        output_path = config.paths.data_dir / "library_report.json"
        write_json(report, output_path)
        console.print(f"[green]Report written to {output_path}[/green]")
    else:
        console.print(format_report_text(report))


# ---------------------------------------------------------------------------
# Config sub-app commands
# ---------------------------------------------------------------------------
