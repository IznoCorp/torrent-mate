"""Maintenance Typer commands for the library."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from personalscraper import cli as cli_compat
from personalscraper.cli_app import app
from personalscraper.cli_helpers import _resolve_category, handle_cli_errors
from personalscraper.cli_state import state
from personalscraper.core.event_bus import EventBus


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
    no_enqueue: bool = typer.Option(
        False,
        "--no-enqueue",
        help=(
            "Read-only mode: walk and compare files but do NOT write to repair_queue. "
            "Useful for a dry audit where writing repair rows is undesirable."
        ),
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

    With ``--no-enqueue`` the scan reports mismatches but does not insert any
    rows into the repair queue (read-only audit mode).

    Examples:
        personalscraper library-verify
        personalscraper library-verify --disk Disk2
        personalscraper library-verify --budget 300
        personalscraper library-verify --no-enqueue
    """
    from personalscraper.cli_helpers import per_step_boundary  # noqa: PLC0415
    from personalscraper.indexer.cli import library_verify_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    loaded_config = ctx.obj.config if ctx.obj is not None else None
    if loaded_config is not None:
        settings = cli_compat.get_settings()
        with per_step_boundary(loaded_config, settings) as app_context:
            rc = library_verify_command(
                disk=disk,
                budget_seconds=float(budget) if budget is not None else None,
                no_enqueue=no_enqueue,
                config_path=effective_config,
                event_bus=app_context.event_bus,
            )
    else:
        # init-config path: ``ctx.obj.config`` was never populated. Construct
        # a fresh unobserved bus here at the CLI boundary so the contract
        # (event_bus required at the indexer command surface) holds locally.
        rc = library_verify_command(
            disk=disk,
            budget_seconds=float(budget) if budget is not None else None,
            no_enqueue=no_enqueue,
            config_path=effective_config,
            event_bus=EventBus(),
        )
    if rc != 0:
        raise typer.Exit(rc)


@app.command("library-repair")
@handle_cli_errors
def library_repair(
    ctx: typer.Context,
    budget: int = typer.Option(60, "--budget", help="Maximum seconds to spend draining the repair queue"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Preview mode: show how many repair_queue rows would be processed "
            "without actually draining them.  No DB writes occur."
        ),
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Drain the repair queue within a time budget.

    Processes pending repair rows in FIFO order.  Stops cleanly when the budget
    is exhausted.  Prints a JSON summary of processed / succeeded / failed counts.

    With ``--dry-run`` the command inspects the queue depth and reports what
    would be drained without modifying any rows (no-op on the database).

    Examples:
        personalscraper library-repair
        personalscraper library-repair --budget 120
        personalscraper library-repair --dry-run
    """
    from personalscraper.cli_helpers import per_step_boundary  # noqa: PLC0415
    from personalscraper.indexer.cli import library_repair_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    loaded_config = ctx.obj.config if ctx.obj is not None else None
    if loaded_config is not None:
        settings = cli_compat.get_settings()
        with per_step_boundary(loaded_config, settings) as app_context:
            rc = library_repair_command(
                budget_seconds=float(budget),
                dry_run=dry_run,
                config_path=effective_config,
                event_bus=app_context.event_bus,
            )
    else:
        # init-config boundary (no loaded config). Fresh unobserved bus
        # keeps the required-bus contract local to this CLI entry point.
        rc = library_repair_command(
            budget_seconds=float(budget),
            dry_run=dry_run,
            config_path=effective_config,
            event_bus=EventBus(),
        )
    if rc != 0:
        raise typer.Exit(rc)


@app.command()
@handle_cli_errors
def library_clean(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help="Actually delete (default: dry-run)"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Preview mode (explicit alias for the default behaviour). "
            "Show what would be deleted without deleting. "
            "Mutually exclusive with --apply."
        ),
    ),
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
    Use ``--apply`` to actually execute deletions.
    Use ``--dry-run`` to make the read-only intent explicit (equivalent to
    the default when ``--apply`` is not given).
    Use ``--only`` to target specific cleanup types.

    The ``orphans`` mode targets stale release directories that no longer
    contain a main video file — typically ``.actors/`` + trailer + NFO + artwork
    left behind after a manual video delete. It is opt-in (never part of the
    default "all" run) because the deletion granularity is the entire release
    directory.

    Examples:
        personalscraper library-clean
        personalscraper library-clean --dry-run
        personalscraper library-clean --apply
        personalscraper library-clean --apply --only actors
        personalscraper library-clean --only orphans                # dry-run
        personalscraper library-clean --only orphans --apply        # delete
        personalscraper library-clean --disk Disk1
    """
    from personalscraper.maintenance.disk_cleaner import clean_library

    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config

    # --dry-run and --apply are mutually exclusive: dry-run wins if both given
    # (belt-and-suspenders guard — Typer does not enforce XOR automatically).
    if dry_run and apply:
        console.print("[red]--dry-run and --apply are mutually exclusive.[/red]")
        raise typer.Exit(1)

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
    check: list[str] = typer.Option(None, "--check", help="Run only the named check(s); repeatable"),
    list_checks: bool = typer.Option(False, "--list-checks", help="List available checks and exit"),
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
    from personalscraper.io_utils import write_json
    from personalscraper.verify.library_checks import validate_from_index, validate_library

    console = state["console"]
    if list_checks:
        from personalscraper.verify.checks.base import CheckStage
        from personalscraper.verify.checks.catalog import list_checks as _list

        for spec in (s for s in _list() if s.stage == CheckStage.DISPATCH):
            fix_label = "fixable" if spec.fixable else "-"
            idx_label = "indexable" if spec.indexable else "-"
            console.print(
                f"  {spec.name:<34} [{spec.group}] "
                f"{spec.default_severity.value:<7} {fix_label:<8} {idx_label:<9} "
                f"{spec.description}"
            )
        raise typer.Exit(0)
    only = frozenset(check) if check else None
    if only is not None:
        from personalscraper.verify.checks.base import CheckStage
        from personalscraper.verify.checks.catalog import list_checks as _list_checks

        _available = {s.name for s in _list_checks() if s.stage == CheckStage.DISPATCH}
        _unknown = only - _available
        if _unknown:
            raise typer.BadParameter(
                f"Unknown check(s): {sorted(_unknown)}. Available dispatch checks: {sorted(_available)}"
            )

    category_id = _resolve_category(ctx, category)
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
            # library-validate --from-index opens the indexer DB read-only;
            # the AppContext bus is unavailable here (CLI flag, not a pipeline
            # step). A fresh unobserved bus is acceptable — the only emit is
            # ``DiskFullWarning`` from the pre-open guard, which is irrelevant
            # for a read-only validate scan.
            conn: sqlite3.Connection = open_db(db_path, event_bus=EventBus())
            apply_migrations(conn, migrations_dir)
            try:
                try:
                    result = validate_from_index(
                        conn,
                        disk_filter=disk,
                        category_filter=category_id,
                        only=only,
                    )
                except KeyError as exc:
                    raise typer.BadParameter(str(exc)) from exc
            finally:
                conn.close()
        else:
            console.print("[bold]Validating library...[/bold]")
            try:
                result = validate_library(
                    config,
                    disk_filter=disk,
                    category_filter=category_id,
                    fix=fix,
                    apply=apply,
                    only=only,
                )
            except KeyError as exc:
                raise typer.BadParameter(str(exc)) from exc

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
