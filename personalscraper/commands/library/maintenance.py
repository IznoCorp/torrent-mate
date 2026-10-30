"""Maintenance Typer commands for the library."""

from __future__ import annotations

from pathlib import Path

import typer

from personalscraper import cli_helpers
from personalscraper.cli_app import app
from personalscraper.cli_helpers import CommandContext, _resolve_category, boundary, handle_cli_errors
from personalscraper.cli_state import state
from personalscraper.core.event_bus import EventBus
from personalscraper.i18n import t


@app.command("library-verify", help=t("cli_library.maintenance.verify_help"))
@handle_cli_errors
@boundary(needs="app", lock=False, journal=False, staging=False)
def library_verify(
    ctx: typer.Context,
    disk: str | None = typer.Option(None, "--disk", help=t("cli_library.maintenance.verify_disk_help")),
    budget: int | None = typer.Option(
        None,
        "--budget",
        help=t("cli_library.maintenance.verify_budget_help"),
    ),
    no_enqueue: bool = typer.Option(
        False,
        "--no-enqueue",
        help=t("cli_library.maintenance.no_enqueue_help"),
    ),
    config: Path | None = typer.Option(None, "--config", "-c", help=t("cli_library.maintenance.config_help")),
    *,
    bundle: CommandContext,
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
    from personalscraper.indexer.cli import library_verify_command  # noqa: PLC0415

    effective_config: Path | None = config or (ctx.obj.config_override if ctx.obj else None)
    # The boundary's "app" tier builds the AppContext (via per_step_boundary,
    # binding correlation_id) exactly as the pre-boundary path did; only its bus
    # flows into the indexer command.
    app_context = bundle.app_context
    assert app_context is not None
    rc = library_verify_command(
        disk=disk,
        budget_seconds=float(budget) if budget is not None else None,
        no_enqueue=no_enqueue,
        config_path=effective_config,
        event_bus=app_context.event_bus,
    )
    if rc != 0:
        raise typer.Exit(rc)


@app.command("library-repair", help=t("cli_library.maintenance.repair_help"))
@handle_cli_errors
@boundary(needs="app", lock=False, journal=False, staging=False)
def library_repair(
    ctx: typer.Context,
    budget: int = typer.Option(60, "--budget", help=t("cli_library.maintenance.repair_budget_help")),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=t("cli_library.maintenance.repair_dry_run_help"),
    ),
    config: Path | None = typer.Option(None, "--config", "-c", help=t("cli_library.maintenance.config_help")),
    *,
    bundle: CommandContext,
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
    from personalscraper.indexer.cli import library_repair_command  # noqa: PLC0415

    effective_config: Path | None = config or (ctx.obj.config_override if ctx.obj else None)
    app_context = bundle.app_context
    assert app_context is not None
    rc = library_repair_command(
        budget_seconds=float(budget),
        dry_run=dry_run,
        config_path=effective_config,
        event_bus=app_context.event_bus,
    )
    if rc != 0:
        raise typer.Exit(rc)


@app.command(help=t("cli_library.maintenance.clean_help"))
@handle_cli_errors
def library_clean(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help=t("cli_library.maintenance.clean_apply_help")),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=t("cli_library.maintenance.clean_dry_run_help"),
    ),
    only: str = typer.Option(
        None,
        "--only",
        help=t("cli_library.maintenance.clean_only_help"),
    ),
    disk: str = typer.Option(None, "--disk", help=t("cli_library.maintenance.clean_disk_help")),
    category: str = typer.Option(None, "--category", help=t("cli_library.maintenance.clean_category_help")),
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
    # Local imports for fail-open delete authority building.
    # Kept inside the function to stay off the module's hot path and avoid
    # pulling per_step_boundary (+ its transitive AppContext build) for every
    # library-* command.
    from personalscraper.cli_helpers import per_step_boundary  # noqa: PLC0415
    from personalscraper.core.delete_permit import AllowAllPermit, DeletePermit  # noqa: PLC0415
    from personalscraper.maintenance.disk_cleaner import clean_library

    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config

    # --dry-run and --apply are mutually exclusive: dry-run wins if both given
    # (belt-and-suspenders guard — Typer does not enforce XOR automatically).
    if dry_run and apply:
        console.print("[red]" + t("cli_library.maintenance.clean_exclusive") + "[/red]")
        raise typer.Exit(1)

    # Validate --only parameter
    valid_only = {"actors", "empty", "junk", "release", "orphans"}
    if only and only not in valid_only:
        console.print(
            "[red]"
            + t("cli_library.maintenance.invalid_only", value=only, valid=", ".join(sorted(valid_only)))
            + "[/red]"
        )
        raise typer.Exit(1)

    # Acquire lock only when applying changes. Exit 3 = lock busy — the
    # maintenance runner re-queues on this code (app/run_queue.py, §6), so it
    # must stay distinguishable from a real error (exit 1).
    if apply:
        if not cli_helpers.acquire_pipeline_lock(
            config.paths.data_dir / "pipeline.lock",
            cli_helpers.scrape_locks_dir_for(config.paths.data_dir),
        ):
            console.print("[red]" + t("cli_library.maintenance.lock_busy") + "[/red]")
            raise typer.Exit(3)

    def _run_and_report(permit: DeletePermit) -> None:
        """Run ``clean_library`` with *permit* and render the result.

        Extracted so the body can run BOTH inside the per_step_boundary scope
        (when the authority builds — the acquire store must stay OPEN while
        ``clean_library`` consults ``permit.may_delete``) AND on the fail-open
        fallback path (build failed → ``AllowAllPermit``). Exceptions raised
        here propagate to the caller — only an authority-BUILD failure is
        fail-open; ``clean_library``'s own errors must NOT be swallowed.

        Args:
            permit: The deletion authority (live ``DeleteAuthority`` or the
                fail-open ``AllowAllPermit`` fallback).
        """
        mode = (
            "[bold red]" + t("cli_library.maintenance.mode_apply") + "[/bold red]"
            if apply
            else "[bold yellow]" + t("cli_library.maintenance.mode_dry_run") + "[/bold yellow]"
        )
        console.print("[bold]" + t("cli_library.maintenance.cleaning", mode=mode) + "[/bold]")

        result = clean_library(
            config,
            apply=apply,
            only=only,
            disk_filter=disk,
            category_filter=category_id,
            permit=permit,
        )

        if result.dry_run:
            console.print(
                t(
                    "cli_library.maintenance.would_delete",
                    label="[yellow]" + t("cli_library.maintenance.dry_run_label") + "[/yellow]",
                    items=result.deleted_count,
                    size=f"{result.freed_bytes / 1024 / 1024:.1f}",
                )
            )
            if result.skipped_by_obligation:
                console.print(
                    t(
                        "cli_library.maintenance.skipped_obligation",
                        label="[blue]" + t("cli_library.maintenance.skipped_obligation_label") + "[/blue]",
                        items=result.skipped_by_obligation,
                    )
                )
            # Orphan deletes a whole release directory at once — high blast
            # radius. List the first matches so the operator can sanity-check
            # before re-running with --apply.
            if only == "orphans" and result.details:
                preview = result.details[:20]
                console.print(
                    "[dim]"
                    + t("cli_library.maintenance.preview", shown=len(preview), total=len(result.details))
                    + "[/dim]"
                )
                for line in preview:
                    console.print("  " + str(line))
                if len(result.details) > len(preview):
                    console.print(
                        "  [dim]"
                        + t("cli_library.maintenance.and_more", items=len(result.details) - len(preview))
                        + "[/dim]"
                    )
        else:
            console.print(
                t(
                    "cli_library.maintenance.deleted",
                    label="[green]" + t("cli_library.maintenance.deleted_label") + "[/green]",
                    items=result.deleted_count,
                    size=f"{result.freed_bytes / 1024 / 1024:.1f}",
                )
            )
            if result.skipped_by_obligation:
                console.print(
                    t(
                        "cli_library.maintenance.skipped_obligation",
                        label="[blue]" + t("cli_library.maintenance.skipped_obligation_label") + "[/blue]",
                        items=result.skipped_by_obligation,
                    )
                )
            if result.error_count:
                console.print(
                    t(
                        "cli_library.maintenance.deletions_failed",
                        label="[red]" + t("cli_library.maintenance.errors_label") + "[/red]",
                        items=result.error_count,
                    )
                )
                for err in result.errors:
                    console.print("  " + str(err))

    # Build the fail-open deletion authority from the acquisition lobe
    # (DESIGN §7.4 / §9), then run clean_library WHILE the store is still open.
    #
    # C2 fix: ``permit.may_delete`` reads the acquire store, so the store must
    # stay OPEN for the whole clean_library run. The boundary's ``finally``
    # closes ``app_context.acquire`` on exit — so clean_library MUST execute
    # INSIDE the ``with`` block (a previous version derived the permit inside,
    # then ran clean_library after the block had already closed the store →
    # may_delete hit "AcquireStore is closed" → fail-open ALLOW swallowed the
    # hard-skip). On a build/enter failure (store absent, unreadable, migration
    # error) we fall through to the AllowAllPermit path so cleanup still runs
    # (fail-open, DESIGN §9). clean_library's OWN exceptions are NOT swallowed:
    # the ``cleaned`` flag flips to True the instant we hand control to
    # ``_run_and_report``, so an exception after that point re-raises instead of
    # being mistaken for an authority-build failure.
    settings = cli_helpers.get_settings()
    cleaned = False
    try:
        try:
            with per_step_boundary(config, settings) as app_context:
                acquire = getattr(app_context, "acquire", None)
                authority = getattr(acquire, "delete_authority", None) if acquire is not None else None
                permit: DeletePermit = authority if authority is not None else AllowAllPermit()
                # Run + report INSIDE the boundary so the store is alive for
                # every may_delete consult.
                cleaned = True
                _run_and_report(permit)
        except Exception:
            if cleaned:
                # The failure came from clean_library / reporting (not the
                # authority build) — do NOT swallow it as fail-open.
                raise
            # Fail-open: building/entering the authority failed → cleanup still
            # proceeds with an always-ALLOW permit (DESIGN §9).
            _run_and_report(AllowAllPermit())
    finally:
        if apply:
            cli_helpers.release_lock()


@app.command(help=t("cli_library.maintenance.validate_help"))
@handle_cli_errors
def library_validate(
    ctx: typer.Context,
    disk: str = typer.Option(None, "--disk", help=t("cli_library.maintenance.validate_disk_help")),
    category: str = typer.Option(None, "--category", help=t("cli_library.maintenance.validate_category_help")),
    fix: bool = typer.Option(False, "--fix", help=t("cli_library.maintenance.fix_help")),
    apply: bool = typer.Option(False, "--apply", help=t("cli_library.maintenance.validate_apply_help")),
    from_index: bool = typer.Option(
        False,
        "--from-index",
        help=t("cli_library.maintenance.validate_from_index_help"),
    ),
    check: list[str] = typer.Option(None, "--check", help=t("cli_library.maintenance.check_help")),
    list_checks: bool = typer.Option(False, "--list-checks", help=t("cli_library.maintenance.list_checks_help")),
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
            fix_label = t("cli_library.maintenance.fixable") if spec.fixable else "-"
            idx_label = t("cli_library.maintenance.indexable") if spec.indexable else "-"
            row = (
                f"  {spec.name:<34} [{spec.group}] "
                f"{spec.default_severity.value:<7} {fix_label:<8} {idx_label:<9} "
                f"{spec.description}"
            )
            console.print(row)
        raise typer.Exit(0)
    only = frozenset(check) if check else None
    if only is not None:
        from personalscraper.verify.checks.base import CheckStage
        from personalscraper.verify.checks.catalog import list_checks as _list_checks

        _available = {s.name for s in _list_checks() if s.stage == CheckStage.DISPATCH}
        _unknown = only - _available
        if _unknown:
            raise typer.BadParameter(
                t(
                    "cli_library.maintenance.unknown_checks",
                    unknown=str(sorted(_unknown)),
                    available=str(sorted(_available)),
                )
            )

    category_id = _resolve_category(ctx, category)
    config = ctx.obj.config

    if from_index and (fix or apply):
        console.print("[red]" + t("cli_library.maintenance.from_index_no_fix") + "[/red]")
        raise typer.Exit(1)

    if apply and not fix:
        console.print("[red]" + t("cli_library.maintenance.apply_requires_fix") + "[/red]")
        raise typer.Exit(1)

    if fix and apply:
        if not cli_helpers.acquire_pipeline_lock(
            config.paths.data_dir / "pipeline.lock",
            cli_helpers.scrape_locks_dir_for(config.paths.data_dir),
        ):
            # Exit 3 = lock busy (the maintenance runner re-queues on this code).
            console.print("[red]" + t("cli_library.maintenance.lock_busy") + "[/red]")
            raise typer.Exit(3)

    try:
        if from_index:
            # Advisory: --from-index runs the DB-backed (IndexableCheck) subset
            # only. If the operator scoped --check to non-indexable checks (e.g.
            # dir_naming, no_empty_dirs, season_structure), those silently
            # produce nothing in DB-mode. Warn rather than raise — the request is
            # well-formed, just vacuous for the named checks.
            if only is not None:
                from personalscraper.verify.checks.base import (  # noqa: PLC0415
                    CheckStage as _Stage,
                )
                from personalscraper.verify.checks.base import (  # noqa: PLC0415
                    IndexableCheck as _Indexable,
                )
                from personalscraper.verify.checks.registry import registry as _registry  # noqa: PLC0415

                non_indexable = sorted(
                    name for name in only if not isinstance(_registry.get(_Stage.DISPATCH, name), _Indexable)
                )
                if non_indexable:
                    console.print(
                        t(
                            "cli_library.maintenance.non_indexable",
                            label="[yellow]" + t("cli_library.maintenance.note_label") + "[/yellow]",
                            checks=str(non_indexable),
                        )
                    )
            console.print("[bold]" + t("cli_library.maintenance.validating_from_index") + "[/bold]")
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
            console.print("[bold]" + t("cli_library.maintenance.validating") + "[/bold]")
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
            t(
                "cli_library.maintenance.validation_summary",
                valid_label="[green]" + t("cli_library.maintenance.valid_label") + "[/green]",
                valid=result.valid_count,
                fixed_label="[yellow]" + t("cli_library.maintenance.fixed_label") + "[/yellow]",
                fixed=result.fixed_count,
                issues_label="[red]" + t("cli_library.maintenance.issues_label") + "[/red]",
                issues=result.issues_count,
                path=str(output_path),
            )
        )

        if fix and result.issues_count:
            console.print(
                "\n[yellow]"
                + t("cli_library.maintenance.api_issues", items=result.issues_count)
                + "[/yellow]\n"
                + t("cli_library.maintenance.use_rescrape")
            )
    finally:
        if fix and apply:
            cli_helpers.release_lock()
