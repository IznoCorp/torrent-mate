"""Pipeline-related Typer commands."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import typer

from personalscraper import cli_helpers
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import (
    CommandContext,
    _build_app_context,
    boundary,
    handle_cli_errors,
)
from personalscraper.cli_state import state
from personalscraper.conf.staging import find_ingest_dir, staging_path
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.run_journal import LogTailHandler

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config


def _journal_lock_conflict(config: Config, *, dry_run: bool) -> None:
    """R9: leave a terminal ``pipeline_run`` row when a run loses the lock race.

    The web ``POST /api/pipeline/run`` returns a ``run_uid`` in its 202 *before*
    the spawned ``personalscraper run`` subprocess acquires ``pipeline.lock``. If
    that subprocess loses the race it exits here without writing any row, so
    ``GET /api/pipeline/history/{run_uid}`` would 404 forever (orphan run_uid).

    When a web run_uid was injected via ``PERSONALSCRAPER_RUN_UID``, write a
    terminal ``error`` row for it so the identifier always resolves. Fail-soft:
    journaling a lock conflict must never change the exit behaviour.

    Args:
        config: The active configuration (for ``indexer.db_path``).
        dry_run: Whether the losing run was a dry run (recorded on the row).
    """
    run_uid = os.environ.get("PERSONALSCRAPER_RUN_UID")
    if not run_uid:
        return
    db_path = config.indexer.db_path
    if db_path is None:
        return
    log = get_logger("pipeline")
    try:
        writer = PipelineRunWriter(db_path)
        writer.insert(run_uid, trigger="web", dry_run=dry_run, pid=os.getpid(), if_absent=True)
        writer.finalize(
            run_uid,
            "error",
            error="Could not acquire pipeline.lock — another run is already active.",
        )
    except Exception:
        log.warning("pipeline_lock_conflict_row_write_failed", run_uid=run_uid, exc_info=True)


def _run_help() -> str:
    """Build the help string for the ``run`` command from the live step registry.

    Reads :data:`~personalscraper.pipeline_steps.DEFAULT_STEPS` at import time so
    the help text automatically reflects any future step additions or removals
    without requiring a manual docstring update.

    Returns:
        Human-readable one-liner listing every pipeline step in order,
        e.g. ``"Run full pipeline (ingest → sort → … → dispatch)."``.
    """
    from personalscraper.pipeline_steps import DEFAULT_STEPS  # noqa: PLC0415

    steps = " → ".join(DEFAULT_STEPS.keys())
    return f"Run full pipeline ({steps})."


@command_with_telemetry()
@handle_cli_errors
@boundary(stream_events=True, build_torrent_client=True)
def ingest(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving"),
    *,
    bundle: CommandContext,
) -> None:
    """Ingest completed torrents from qBittorrent."""
    config = ctx.obj.config
    assert config is not None  # guaranteed non-None by callback
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    staging_dir = config.paths.staging_dir
    ingest_dir = staging_path(config, find_ingest_dir(config))
    # Fail-safe copy-vs-move (§7 HnR): inject the seed-obligation
    # checker from the acquire context via the core port.
    _acquire = getattr(app_context, "acquire", None)
    _seed_checker = getattr(_acquire, "delete_authority", None)
    report = cli_helpers.run_ingest(
        bundle.settings,
        dry_run=dry_run,
        ingest_dir=ingest_dir,
        staging_dir=staging_dir,
        config=config,
        event_bus=app_context.event_bus,
        torrent_client=app_context.torrent_client,
        seed_checker=_seed_checker,
    )
    console.print(
        f"[bold]Ingest:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
    )


@command_with_telemetry()
@handle_cli_errors
@boundary(stream_events=True)
def sort(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving"),
    *,
    bundle: CommandContext,
) -> None:
    """Sort and clean media files."""
    from personalscraper.sorter.run import run_sort

    config = ctx.obj.config
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    report = run_sort(
        bundle.settings,
        staging_dir=config.paths.staging_dir,
        dry_run=dry_run,
        config=config,
        event_bus=app_context.event_bus,
    )
    console.print(
        f"[bold]Sort:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
    )
    if state["verbose"]:
        for detail in report.details:
            console.print(f"  {detail}")


@command_with_telemetry()
@handle_cli_errors
@boundary(stream_events=True)
def scrape(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt for ambiguous matches"),
    movies_only: bool = typer.Option(False, "--movies-only", help="Process only movies"),
    tvshows_only: bool = typer.Option(False, "--tvshows-only", help="Process only TV shows"),
    *,
    bundle: CommandContext,
) -> None:
    """Scrape metadata and artwork from TMDB/TVDB."""
    from personalscraper.scraper.run import run_scrape

    config = ctx.obj.config  # Guaranteed non-None by callback.
    assert config is not None
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    report = run_scrape(
        bundle.settings,
        config=config,
        dry_run=dry_run,
        interactive=interactive,
        movies_only=movies_only,
        tvshows_only=tvshows_only,
        event_bus=app_context.event_bus,
        registry=app_context.provider_registry,
    )
    console.print(
        f"[bold]Scrape:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
    )
    if state["verbose"]:
        for detail in report.details:
            console.print(f"  {detail}")


@command_with_telemetry()
@handle_cli_errors
def verify(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying files"),
    movies_only: bool = typer.Option(False, "--movies-only", help="Process only movies"),
    tvshows_only: bool = typer.Option(False, "--tvshows-only", help="Process only TV shows"),
    check: list[str] = typer.Option(None, "--check", help="Run only the named check(s); repeatable"),
    list_checks: bool = typer.Option(False, "--list-checks", help="List available checks and exit"),
) -> None:
    """Verify and qualify scraped media before dispatch.

    The ``--list-checks`` listing and the unknown-``--check`` validation run
    **before** any lock/journal scaffold — a pure listing or an argument error
    must not take ``pipeline.lock`` nor write a ``pipeline_run`` row. Only once
    the arguments are accepted does the real work run inside the shared
    :func:`~personalscraper.cli_helpers.boundary` scaffold via
    :func:`_verify_run`.
    """
    console = state["console"]
    if list_checks:
        from personalscraper.verify.checks.base import CheckStage
        from personalscraper.verify.checks.catalog import list_checks as _list

        for spec in (s for s in _list() if s.stage == CheckStage.DISPATCH):
            fix = "fixable" if spec.fixable else "-"
            idx = "indexable" if spec.indexable else "-"
            console.print(
                f"  {spec.name:<34} [{spec.group}] "
                f"{spec.default_severity.value:<7} {fix:<8} {idx:<9} "
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
    _verify_run(ctx, dry_run=dry_run, movies_only=movies_only, tvshows_only=tvshows_only, only=only)


@boundary(stream_events=True, command="verify")
def _verify_run(
    ctx: typer.Context,
    *,
    dry_run: bool,
    movies_only: bool,
    tvshows_only: bool,
    only: frozenset[str] | None,
    bundle: CommandContext,
) -> None:
    """Run the verify step inside the shared boundary scaffold.

    Split out from :func:`verify` so the pre-lock ``--list-checks`` /
    unknown-check early exits stay OUTSIDE the lock + journal, byte-identical to
    the pre-boundary command. Journals under ``command="verify"``.

    Args:
        ctx: The Typer context (``ctx.obj.config`` holds the loaded config).
        dry_run: Preview without modifying files.
        movies_only: Restrict to movies.
        tvshows_only: Restrict to TV shows.
        only: The validated ``--check`` subset, or ``None`` for all checks.
        bundle: The boundary-injected service bundle (``needs="app"``).
    """
    from personalscraper.verify.run import run_verify

    config = ctx.obj.config
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    try:
        report, dispatchable = run_verify(
            bundle.settings,
            config,
            dry_run=dry_run,
            movies_only=movies_only,
            tvshows_only=tvshows_only,
            only=only,
            event_bus=app_context.event_bus,
        )
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"[bold]Verify:[/bold] {report.success_count} OK, {report.skip_count} blocked")
    console.print(f"  {len(dispatchable)} ready for dispatch")
    if state["verbose"]:
        for detail in report.details:
            console.print(f"  {detail}")


@command_with_telemetry()
@handle_cli_errors
def enforce(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying"),
    check: list[str] = typer.Option(None, "--check", help="Run only the named check(s); repeatable"),
    list_checks: bool = typer.Option(False, "--list-checks", help="List available checks and exit"),
) -> None:
    """Enforce staging conventions: sanitize filenames, validate structure, check coherence.

    ``--list-checks`` and the unknown-``--check`` validation run **before** the
    lock/journal scaffold (they must not take ``pipeline.lock`` nor journal a
    run); the accepted-argument path runs the real work inside the shared
    :func:`~personalscraper.cli_helpers.boundary` scaffold via :func:`_enforce_run`.
    """
    console = state["console"]
    if list_checks:
        from personalscraper.verify.checks.base import CheckStage
        from personalscraper.verify.checks.catalog import list_checks as _list

        for spec in (s for s in _list() if s.stage == CheckStage.STAGING):
            fix = "fixable" if spec.fixable else "-"
            idx = "indexable" if spec.indexable else "-"
            console.print(
                f"  {spec.name:<34} [{spec.group}] "
                f"{spec.default_severity.value:<7} {fix:<8} {idx:<9} "
                f"{spec.description}"
            )
        raise typer.Exit(0)
    only = frozenset(check) if check else None
    if only is not None:
        from personalscraper.verify.checks.base import CheckStage
        from personalscraper.verify.checks.catalog import list_checks as _list_checks

        _available = {s.name for s in _list_checks() if s.stage == CheckStage.STAGING}
        _unknown = only - _available
        if _unknown:
            raise typer.BadParameter(
                f"Unknown check(s): {sorted(_unknown)}. Available staging checks: {sorted(_available)}"
            )
    _enforce_run(ctx, dry_run=dry_run, only=only)


@boundary(stream_events=True, command="enforce")
def _enforce_run(
    ctx: typer.Context,
    *,
    dry_run: bool,
    only: frozenset[str] | None,
    bundle: CommandContext,
) -> None:
    """Run the enforce step inside the shared boundary scaffold.

    Split out from :func:`enforce` so the pre-lock ``--list-checks`` /
    unknown-check early exits stay OUTSIDE the lock + journal, byte-identical to
    the pre-boundary command. Journals under ``command="enforce"``.

    Args:
        ctx: The Typer context (``ctx.obj.config`` holds the loaded config).
        dry_run: Preview without modifying.
        only: The validated ``--check`` subset, or ``None`` for all checks.
        bundle: The boundary-injected service bundle (``needs="app"``).
    """
    from personalscraper.enforce.run import run_enforce

    config = ctx.obj.config
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    try:
        report = run_enforce(bundle.settings, config, dry_run=dry_run, only=only, event_bus=app_context.event_bus)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Enforce: {report.success_count} fixed, {report.skip_count} OK, {report.error_count} errors")
    if state["verbose"]:
        for detail in report.details:
            console.print(f"  {detail}")


@command_with_telemetry()
@handle_cli_errors
@boundary(stream_events=True)
def dispatch(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving"),
    no_post_maintenance: bool = typer.Option(
        False,
        "--no-post-maintenance",
        help="Skip automatic index maintenance after dispatch (scan/relink/fix).",
    ),
    *,
    bundle: CommandContext,
) -> None:
    """Move media to storage disks."""
    from personalscraper.dispatch.run import run_dispatch
    from personalscraper.pipeline_steps import resolve_dispatch_authority
    from personalscraper.subscribers.dispatch_reconcile import build_post_dispatch_reconcile_subscriber

    config = ctx.obj.config
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    # ACQUIRE-02: the post-dispatch reconcile subscriber closes owned wanted
    # rows + retires acquired films after the dispatch step's enrich scan
    # refreshes the library. Wired here (a dispatch composition root) so a plain
    # library-index scan never gains a reconciliation side effect. The app
    # bundle is destructured HERE (boundary rule) — the builder takes only the
    # narrow services it consumes (bus + acquire lobe handle).
    reconcile_sub = build_post_dispatch_reconcile_subscriber(
        app_context.event_bus,
        getattr(app_context, "acquire", None),
    )
    try:
        # F2 parity: resolve the SAME permit/recorder the full-run
        # DispatchStep injects, via the shared single owner.
        report, results = run_dispatch(
            bundle.settings,
            config=config,
            dry_run=dry_run,
            event_bus=app_context.event_bus,
            **resolve_dispatch_authority(app_context),
        )
    finally:
        if reconcile_sub is not None:
            reconcile_sub.close()

    # Post-dispatch index maintenance runs through the single owner
    # shared with the full-run DispatchStep (PIPELINE-CORE-01): the
    # enablement resolution, touched-disk collection, and dry-run guard
    # live in one place so both entry points behave identically.
    from personalscraper.dispatch.post_maintenance import maybe_run_post_dispatch_maintenance

    maybe_run_post_dispatch_maintenance(
        config,
        results,
        dry_run=dry_run,
        no_post_maintenance=no_post_maintenance,
    )

    console.print(
        f"[bold]Dispatch:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
    )
    if state["verbose"]:
        for detail in report.details:
            console.print(f"  {detail}")


@command_with_telemetry()
@handle_cli_errors
@boundary(stream_events=True)
def clean(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying"),
    *,
    bundle: CommandContext,
) -> None:
    """Run reclean + dedup only (process sub-step, SH-21 / AR-C).

    Standalone CLI surface around :func:`personalscraper.process.run.run_clean`.
    Useful for debugging the clean sub-step in isolation and for composition
    with other operator workflows (e.g. dry-run a clean pass before launching
    the full process step). The full pipeline still invokes ``run_clean``
    internally via ``run_process`` — this command does not alter that flow.
    """
    from personalscraper.process.run import run_clean

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    try:
        report = run_clean(
            bundle.settings,
            config=config,
            dry_run=dry_run,
            event_bus=app_context.event_bus,
        )
    except Exception as exc:
        console.print(f"[red]Clean failed: {type(exc).__name__}: {exc}[/red]")
        get_logger("pipeline").exception("clean_command_failed", error=str(exc))
        raise typer.Exit(1) from exc

    console.print(
        f"[bold]Clean:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
    )
    if state["verbose"]:
        for detail in report.details:
            console.print(f"  {detail}")


@command_with_telemetry()
@handle_cli_errors
@boundary(stream_events=True)
def cleanup(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without deleting"),
    *,
    bundle: CommandContext,
) -> None:
    """Run empty-directory cleanup only (process sub-step, SH-21 / AR-C).

    Standalone CLI surface around :func:`personalscraper.process.run.run_cleanup`.
    Removes empty directories left behind by previous steps. Distinct from
    ``clean`` (which performs reclean + dedup of polluted folder names); this
    command only operates on empty directories. Useful for tidying staging
    between manual operator interventions. The full pipeline still invokes
    ``run_cleanup`` internally via ``run_process`` — this command does not
    alter that flow.
    """
    from personalscraper.process.run import run_cleanup

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    try:
        report = run_cleanup(
            bundle.settings,
            config=config,
            dry_run=dry_run,
            event_bus=app_context.event_bus,
        )
    except Exception as exc:
        console.print(f"[red]Cleanup failed: {type(exc).__name__}: {exc}[/red]")
        get_logger("pipeline").exception("cleanup_command_failed", error=str(exc))
        raise typer.Exit(1) from exc

    console.print(f"[bold]Cleanup:[/bold] {report.success_count} removed")
    if state["verbose"]:
        for detail in report.details:
            console.print(f"  {detail}")


@command_with_telemetry()
@handle_cli_errors
@boundary(stream_events=True)
def process(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt for ambiguous matches"),
    *,
    bundle: CommandContext,
) -> None:
    """Run process phase only (reclean + dedup + scrape + cleanup)."""
    from personalscraper.process.run import run_process

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    try:
        clean, scrape, cleanup = run_process(
            bundle.settings,
            dry_run=dry_run,
            interactive=interactive,
            config=config,
            event_bus=app_context.event_bus,
            registry=app_context.provider_registry,
        )
    except Exception as exc:
        console.print(f"[red]Process failed: {type(exc).__name__}: {exc}[/red]")
        get_logger("pipeline").exception("process_command_failed", error=str(exc))
        raise typer.Exit(1) from exc

    for label, report in [("Clean", clean), ("Scrape", scrape), ("Cleanup", cleanup)]:
        console.print(
            f"[bold]{label}:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
        )
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")


#: Valid ``--trigger-reason`` values. MUST include every reason any web-side caller
#: passes to :func:`~personalscraper.web.pipeline_trigger.spawn_pipeline_run` — in
#: particular ``"scrape-resolve"`` (the §4 continuation after a manual resolve).
#: A missing value here makes the spawned continuation ``run`` crash on argv
#: validation, so the resolved media never dispatches (product-intent.md §4
#: dénaturation: "un média qui reste échoué en staging après résolution").
_VALID_TRIGGER_REASONS: frozenset[str] = frozenset({"", "completion", "safety_net", "manual", "web", "scrape-resolve"})


def _validate_trigger_reason(value: str) -> str:
    """Validate the ``--trigger-reason`` value against :data:`_VALID_TRIGGER_REASONS`.

    Args:
        value: Raw string from the CLI option.

    Returns:
        The validated value unchanged.

    Raises:
        typer.BadParameter: If *value* is not one of the allowed reasons.
    """
    if value not in _VALID_TRIGGER_REASONS:
        allowed = ", ".join(sorted(r for r in _VALID_TRIGGER_REASONS if r))
        raise typer.BadParameter(f"Must be one of: {allowed} (got '{value}')")
    return value


@command_with_telemetry("run", help=_run_help())
@handle_cli_errors
def run(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview full pipeline"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt for ambiguous matches"),
    skip_trailers: bool = typer.Option(
        False,
        "--skip-trailers",
        help="Skip the trailers pipeline step for this invocation.",
    ),
    continue_on_trailer_error: bool = typer.Option(
        False,
        "--continue-on-trailer-error",
        help="Do not abort dispatch when the trailers step crashes.",
    ),
    headless: bool = typer.Option(
        False,
        "--headless",
        help=(
            "Run with no subscribers (silent mode for cron / CI). "
            "Disables Rich console output and Telegram notifications."
        ),
    ),
    no_console: bool = typer.Option(
        False,
        "--no-console",
        help=(
            "Disable Rich console output (progress bars, live tables). "
            "Telegram notifications remain active. "
            "Used by the Watcher daemon (``personalscraper watch``) when "
            "spawning pipeline runs; contrast with ``--headless`` which "
            "disables both Rich and Telegram. If both are passed, "
            "``--headless`` wins."
        ),
    ),
    trigger_reason: str = typer.Option(
        "",
        "--trigger-reason",
        hidden=True,
        callback=_validate_trigger_reason,
        help="Set by the Watcher daemon to attribute this run.",
    ),
    no_post_maintenance: bool = typer.Option(
        False,
        "--no-post-maintenance",
        help="Skip automatic index maintenance after dispatch (scan/relink/fix).",
    ),
) -> None:
    """Execute all pipeline phases via ``Pipeline.run``.

    The step list displayed in ``--help`` is generated from
    :data:`~personalscraper.pipeline_steps.DEFAULT_STEPS` at import time via
    :func:`_run_help`, so it always reflects the actual registered steps.
    """
    from datetime import datetime

    import structlog.contextvars

    from personalscraper.api.notify.healthchecks import HealthcheckClient
    from personalscraper.api.notify.telegram import TelegramNotifier
    from personalscraper.api.transport._http import HttpTransport
    from personalscraper.logger import cleanup_old_logs
    from personalscraper.pipeline import Pipeline
    from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber
    from personalscraper.subscribers.debug_log import DebugLogSubscriber
    from personalscraper.subscribers.redis_stream import build_redis_publisher
    from personalscraper.subscribers.rich_console import RichConsoleSubscriber
    from personalscraper.subscribers.telegram import TelegramSubscriber

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    verbose = state["verbose"]
    _run_log = get_logger("pipeline")

    if not cli_helpers.acquire_pipeline_lock(
        config.paths.data_dir / "pipeline.lock",
        cli_helpers.scrape_locks_dir_for(config.paths.data_dir),
    ):
        console.print("[red]Another instance is running. Exiting.[/red]")
        _journal_lock_conflict(config, dry_run=dry_run)
        raise typer.Exit(1)

    try:
        settings = cli_helpers.get_settings()

        # The :class:`AppContext` is built once per invocation at the CLI
        # boundary via :func:`_build_app_context` (Sub-phase 2.4 — boundary-only
        # rule from DESIGN §Architecture, enforced by the AST allowlist landed
        # in Sub-phase 2.6). Constructed early so the healthcheck and Telegram
        # transports built below can plumb ``app_context.event_bus`` into their
        # circuit breakers (Sub-phase 4.1).
        # build_torrent_client=True: the full pipeline includes the ingest step,
        # which consumes ctx.torrent_client, so the client is resolved + validated
        # at boot here (DESIGN D3 fail-fast for the run path).
        app_context = _build_app_context(config, settings, build_torrent_client=True)

        # Healthcheck client (None if not configured — pings short-circuit at the call site).
        healthcheck: HealthcheckClient | None = None
        if HealthcheckClient.is_configured(settings):
            hc_transport = HttpTransport(
                HealthcheckClient.policy(settings.healthcheck_url),
                event_bus=app_context.event_bus,
            )
            healthcheck = HealthcheckClient(hc_transport)
            healthcheck.ping_start()

        # Pipeline outcome is set to "success" only on the clean-completion path; any other
        # exit (typer.Exit, TrailerStepFailed, unhandled exception) leaves it None and the
        # finally block fires healthcheck.ping_fail() — preserves the dead-man's-switch
        # contract per DESIGN §7.1.
        pipeline_outcome: str | None = None
        try:
            # Clean old logs and bind run context
            cleanup_old_logs()
            structlog.contextvars.clear_contextvars()
            run_id = datetime.now().isoformat(timespec="seconds")
            structlog.contextvars.bind_contextvars(run_id=run_id)

            _run_log.info("pipeline_started", dry_run=dry_run, run_id=run_id)

            # Resolve flag defaults from config when not explicitly set by the caller.
            effective_skip_trailers = skip_trailers or config.trailers.pipeline.skip
            effective_continue_on_trailer_error = (
                continue_on_trailer_error or config.trailers.pipeline.continue_on_error
            )

            from personalscraper.trailers.state import TrailerStepFailed  # noqa: PLC0415

            # Build subscribers — both self-subscribe in their constructors via the
            # shared AppContext bus. ``--headless`` skips subscriber construction
            # for silent cron / CI runs.
            #
            # ``--no-console`` (used by the Watcher daemon) disables the Rich
            # console subscriber but keeps Telegram subscribers active.
            # ``--headless`` disables both; if both flags are passed, ``--headless``
            # wins (the outer ``not headless`` gate prevents all subscriber
            # construction).
            rich_subscriber: RichConsoleSubscriber | None = None
            telegram_subscriber: TelegramSubscriber | None = None
            acq_telegram_subscriber: AcquisitionTelegramSubscriber | None = None
            # ``--verbose`` activates the DebugLogSubscriber which logs every
            # emitted event at DEBUG. Registered independently of ``--headless``
            # so verbose log streams work even in cron / CI contexts that
            # suppress Rich / Telegram output.
            debug_subscriber: DebugLogSubscriber | None = None
            # Redis event publisher (gate on web.enabled, fail-soft — Redis down
            # must never block the pipeline boot).
            redis_publisher = build_redis_publisher(app_context.event_bus, config.web)
            if verbose:
                debug_subscriber = DebugLogSubscriber(app_context.event_bus)
            if not headless:
                if not no_console:
                    rich_subscriber = RichConsoleSubscriber(
                        app_context.event_bus,
                        console=console,
                        verbose=verbose,
                        dry_run=dry_run,
                        run_id=run_id,
                    )
                if TelegramNotifier.is_configured(settings):
                    tg_transport = HttpTransport(
                        TelegramNotifier.policy(settings.telegram_bot_token),
                        event_bus=app_context.event_bus,
                    )
                    tg_notifier = TelegramNotifier(tg_transport, settings.telegram_chat_id)
                    telegram_subscriber = TelegramSubscriber(app_context.event_bus, tg_notifier)
                    acq_telegram_subscriber = AcquisitionTelegramSubscriber(
                        app_context.event_bus,
                        notifier=tg_notifier,
                        enabled=config.notify.acquire_notify_enabled,
                    )

            # Emit ``WatcherRunTriggered`` before ``PipelineStarted`` when the
            # run is spawned by the Watcher daemon (``--trigger-reason`` set).
            # Subscribers (Telegram, Rich console) are already wired at this
            # point, so they will observe and forward the event.
            if trigger_reason:
                from personalscraper.acquire.events import WatcherRunTriggered

                app_context.event_bus.emit(WatcherRunTriggered(reason=trigger_reason))

            # Build run-history writer (pipe-control sub-phase 1.3b).
            # The writer is an injected dependency — the CLI owns the DB
            # path resolution.  Fail-soft: if construction fails (missing
            # library.db, permission error, etc.) the pipeline runs without
            # history recording.
            history_writer: PipelineRunWriter | None = None
            try:
                from personalscraper.pipeline_history import PipelineRunWriter  # noqa: PLC0415

                history_writer = PipelineRunWriter(
                    db_path=config.indexer.db_path,
                )
            except Exception:
                _run_log.warning(
                    "pipeline_history_writer_init_failed",
                    exc_info=True,
                )

            # Capture the log tail for the durable run journal (universal run
            # journal, 2026-07-08): every trigger path — cli, web-spawned,
            # safety_net — routes through this command, so installing the
            # handler here gives all of them an ``output_tail``.
            tail_handler = LogTailHandler()
            tail_handler.install()

            pipeline = Pipeline(app_context)
            try:
                try:
                    report = pipeline.run(
                        dry_run=dry_run,
                        interactive=interactive,
                        verbose=verbose,
                        skip_trailers=effective_skip_trailers,
                        continue_on_trailer_error=effective_continue_on_trailer_error,
                        no_post_maintenance=no_post_maintenance,
                        trigger_reason=trigger_reason or "cli",
                        history_writer=history_writer,
                        output_tail_provider=tail_handler.tail,
                    )
                finally:
                    tail_handler.uninstall()
                    if rich_subscriber is not None:
                        rich_subscriber.close()
                    if telegram_subscriber is not None:
                        telegram_subscriber.close()
                    if acq_telegram_subscriber is not None:
                        acq_telegram_subscriber.close()
                    if debug_subscriber is not None:
                        debug_subscriber.close()
                    if redis_publisher is not None:
                        redis_publisher.close()
            except TrailerStepFailed as exc:
                # Trailers step failed and --continue-on-trailer-error was not set.
                # Exit with code 2 (distinct from generic pipeline error exit 1) so
                # scripts / launchd jobs can handle this case explicitly.
                console.print(f"[red]ABORTED: {exc}[/red]", highlight=False)
                _run_log.error("pipeline_aborted_trailer_step_failed", reason=str(exc))
                raise typer.Exit(code=2) from exc

            dur = report.duration()
            minutes = int(dur.total_seconds()) // 60
            seconds = int(dur.total_seconds()) % 60
            dur_str = f"{minutes}min {seconds:02d}s" if minutes else f"{seconds}s"
            _run_log.info("pipeline_finished", duration=dur_str)

            # Mark outcome BEFORE the typer.Exit so the finally block pings the right state.
            pipeline_outcome = "fail" if report.has_errors() else "success"
            if report.has_errors():
                raise typer.Exit(1)
        finally:
            # Dead-man's-switch: ping_fail on any non-clean exit (TrailerStepFailed, unexpected
            # exception, typer.Exit due to report errors). HealthcheckClient is itself fail-soft
            # so an unreachable hc-ping.com will not abort the lock release below.
            if healthcheck is not None:
                if pipeline_outcome == "success":
                    healthcheck.ping_success()
                else:
                    healthcheck.ping_fail()

    finally:
        cli_helpers.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


# Torrent-client listing (``torrents-list``) lives in
# :mod:`personalscraper.commands.torrents` (solidify — module-size relief).
