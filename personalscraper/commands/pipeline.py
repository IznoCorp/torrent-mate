"""Pipeline-related Typer commands."""

from __future__ import annotations

import typer

from personalscraper import cli as cli_compat
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import (
    _bootstrap_staging,
    _build_app_context,
    handle_cli_errors,
    per_step_boundary,
)
from personalscraper.cli_state import state
from personalscraper.conf.staging import find_ingest_dir, staging_path
from personalscraper.logger import get_logger


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
def ingest(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving"),
) -> None:
    """Ingest completed torrents from qBittorrent."""
    config = ctx.obj.config
    assert config is not None  # guaranteed non-None by callback
    console = state["console"]
    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        _bootstrap_staging(ctx)
        settings = cli_compat.get_settings()
        staging_dir = config.paths.staging_dir
        ingest_dir = staging_path(config, find_ingest_dir(config))
        with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
            report = cli_compat.run_ingest(
                settings,
                dry_run=dry_run,
                ingest_dir=ingest_dir,
                staging_dir=staging_dir,
                config=config,
                event_bus=app_context.event_bus,
                torrent_client=app_context.torrent_client,
            )
        console.print(
            f"[bold]Ingest:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
        )
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@command_with_telemetry()
@handle_cli_errors
def sort(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving"),
) -> None:
    """Sort and clean media files."""
    from personalscraper.sorter.run import run_sort

    config = ctx.obj.config
    console = state["console"]
    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        _bootstrap_staging(ctx)
        settings = cli_compat.get_settings()
        with per_step_boundary(config, settings) as app_context:
            report = run_sort(
                settings,
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
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@command_with_telemetry()
@handle_cli_errors
def scrape(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt for ambiguous matches"),
    movies_only: bool = typer.Option(False, "--movies-only", help="Process only movies"),
    tvshows_only: bool = typer.Option(False, "--tvshows-only", help="Process only TV shows"),
) -> None:
    """Scrape metadata and artwork from TMDB/TVDB."""
    from personalscraper.scraper.run import run_scrape

    config = ctx.obj.config  # Guaranteed non-None by callback.
    assert config is not None
    console = state["console"]
    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        _bootstrap_staging(ctx)
        settings = cli_compat.get_settings()
        with per_step_boundary(config, settings) as app_context:
            report = run_scrape(
                settings,
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
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


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
    """Verify and qualify scraped media before dispatch."""
    from personalscraper.verify.run import run_verify

    config = ctx.obj.config  # Guaranteed non-None by callback.
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
    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        _bootstrap_staging(ctx)
        settings = cli_compat.get_settings()
        with per_step_boundary(config, settings) as app_context:
            try:
                report, dispatchable = run_verify(
                    settings,
                    config,
                    dry_run=dry_run,
                    movies_only=movies_only,
                    tvshows_only=tvshows_only,
                    only=only,
                    event_bus=app_context.event_bus,
                )
            except KeyError as exc:
                raise typer.BadParameter(str(exc)) from exc
        console.print(f"[bold]Verify:[/bold] {report.success_count} OK, {report.error_count} blocked")
        console.print(f"  {len(dispatchable)} ready for dispatch")
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@command_with_telemetry()
@handle_cli_errors
def enforce(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying"),
    check: list[str] = typer.Option(None, "--check", help="Run only the named check(s); repeatable"),
    list_checks: bool = typer.Option(False, "--list-checks", help="List available checks and exit"),
) -> None:
    """Enforce staging conventions: sanitize filenames, validate structure, check coherence."""
    from personalscraper.enforce.run import run_enforce

    config = ctx.obj.config  # Guaranteed non-None by callback.
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
    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        _bootstrap_staging(ctx)
        settings = cli_compat.get_settings()
        with per_step_boundary(config, settings) as app_context:
            try:
                report = run_enforce(settings, config, dry_run=dry_run, only=only, event_bus=app_context.event_bus)
            except KeyError as exc:
                raise typer.BadParameter(str(exc)) from exc
        console.print(f"Enforce: {report.success_count} fixed, {report.skip_count} OK, {report.error_count} errors")
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@command_with_telemetry()
@handle_cli_errors
def dispatch(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving"),
    no_post_maintenance: bool = typer.Option(
        False,
        "--no-post-maintenance",
        help="Skip automatic index maintenance after dispatch (scan/relink/fix).",
    ),
) -> None:
    """Move media to storage disks."""
    from personalscraper.dispatch.run import run_dispatch

    config = ctx.obj.config
    console = state["console"]
    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        _bootstrap_staging(ctx)
        settings = cli_compat.get_settings()
        with per_step_boundary(config, settings) as app_context:
            report, results = run_dispatch(settings, config=config, dry_run=dry_run, event_bus=app_context.event_bus)

        # Collect touched disks from DispatchResult objects (index-sync DESIGN).
        touched_disks: set[str] = {
            r.disk for r in results if r.disk is not None and r.action in ("moved", "merged", "replaced")
        }

        # Resolve post-maintenance enablement: flag > config > default(true).
        maintenance_enabled = not no_post_maintenance
        if maintenance_enabled:
            maintenance_enabled = config.indexer.post_dispatch_maintenance.enabled

        if touched_disks:
            from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance

            run_post_dispatch_maintenance(config, touched_disks, enabled=maintenance_enabled)

        console.print(
            f"[bold]Dispatch:[/bold] {report.success_count} OK, "
            f"{report.skip_count} skipped, {report.error_count} errors"
        )
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@command_with_telemetry()
@handle_cli_errors
def clean(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying"),
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
    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        _bootstrap_staging(ctx)
        settings = cli_compat.get_settings()
        try:
            with per_step_boundary(config, settings) as app_context:
                report = run_clean(
                    settings,
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
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@command_with_telemetry()
@handle_cli_errors
def cleanup(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without deleting"),
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
    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        _bootstrap_staging(ctx)
        settings = cli_compat.get_settings()
        try:
            with per_step_boundary(config, settings) as app_context:
                report = run_cleanup(
                    settings,
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
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@command_with_telemetry()
@handle_cli_errors
def process(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt for ambiguous matches"),
) -> None:
    """Run process phase only (reclean + dedup + scrape + cleanup)."""
    from personalscraper.process.run import run_process

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        _bootstrap_staging(ctx)
        settings = cli_compat.get_settings()
        try:
            with per_step_boundary(config, settings) as app_context:
                clean, scrape, cleanup = run_process(
                    settings,
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
                f"[bold]{label}:[/bold] {report.success_count} OK, "
                f"{report.skip_count} skipped, {report.error_count} errors"
            )
            if state["verbose"]:
                for detail in report.details:
                    console.print(f"  {detail}")
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


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
    from personalscraper.subscribers.rich_console import RichConsoleSubscriber
    from personalscraper.subscribers.telegram import TelegramSubscriber

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    verbose = state["verbose"]
    _run_log = get_logger("pipeline")

    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)

    try:
        settings = cli_compat.get_settings()

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
            rich_subscriber: RichConsoleSubscriber | None = None
            telegram_subscriber: TelegramSubscriber | None = None
            acq_telegram_subscriber: AcquisitionTelegramSubscriber | None = None
            # ``--verbose`` activates the DebugLogSubscriber which logs every
            # emitted event at DEBUG. Registered independently of ``--headless``
            # so verbose log streams work even in cron / CI contexts that
            # suppress Rich / Telegram output.
            debug_subscriber: DebugLogSubscriber | None = None
            if verbose:
                debug_subscriber = DebugLogSubscriber(app_context.event_bus)
            if not headless:
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

            pipeline = Pipeline(app_context)
            try:
                try:
                    report = pipeline.run(
                        dry_run=dry_run,
                        interactive=interactive,
                        verbose=verbose,
                        skip_trailers=effective_skip_trailers,
                        continue_on_trailer_error=effective_continue_on_trailer_error,
                    )
                finally:
                    if rich_subscriber is not None:
                        rich_subscriber.close()
                    if telegram_subscriber is not None:
                        telegram_subscriber.close()
                    if acq_telegram_subscriber is not None:
                        acq_telegram_subscriber.close()
                    if debug_subscriber is not None:
                        debug_subscriber.close()
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
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@command_with_telemetry("torrents-list")
@handle_cli_errors
def torrents_list(ctx: typer.Context) -> None:
    """List completed torrents from the active qBittorrent client.

    Prints one line per completed torrent (state / progress / size /
    seeding / name) and a summary count. Exits 2 with a friendly
    message when the torrent client is unreachable (auth lockout, IP
    ban, daemon down) so monitoring tools can branch on the exit
    code. Used by the ``pipeline-monitor`` skill's GATE 0 inventory.

    Output format respects the global ``--format`` flag.
    """
    from personalscraper.api.torrent._errors import TORRENT_LISTING_ERRORS  # noqa: PLC0415
    from personalscraper.cli_helpers.output import emit  # noqa: PLC0415

    config = ctx.obj.config
    assert config is not None
    console = state["console"]
    settings = cli_compat.get_settings()

    # Torrent client is boot-wired into AppContext (DESIGN D3) and read here
    # rather than built inline. None when no torrent client is configured
    # (DESIGN D9) — exit 2 so monitoring tools can branch on the code.
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        client = app_context.torrent_client
        if client is None:
            console.print("[yellow]No torrent client configured (set torrent.active in torrent.json5).[/yellow]")
            raise typer.Exit(2)

        try:
            torrents = client.get_completed()
            active_hashes = client.get_all_hashes()
        except TORRENT_LISTING_ERRORS as exc:
            console.print(f"[yellow]Torrent listing failed:[/yellow] {exc}")
            raise typer.Exit(2) from exc

        payload = {
            "torrents": [
                {
                    "name": t.name,
                    "state": t.state,
                    "progress": t.progress,
                    "size_gb": t.size_bytes / (1024**3),
                    "seeding": client.is_seeding(t),
                }
                for t in torrents
            ],
            "completed": len(torrents),
            "tracked": len(active_hashes),
        }
        emit(payload, rich_renderer=lambda: _print_torrents_rich(payload))


def _print_torrents_rich(payload: dict[str, object]) -> None:
    """Render the torrent list via Rich console.

    Args:
        payload: Dict with ``torrents`` list and ``completed``/``tracked`` counts.
    """
    from typing import cast  # noqa: PLC0415

    console = state["console"]
    torrents = cast("list[dict[str, object]]", payload.get("torrents", []))
    for t in torrents:
        seeding = "seeding" if t.get("seeding") else "idle"
        t_progress = cast(float, t.get("progress", 0))
        t_size_gb = cast(float, t.get("size_gb", 0))
        t_name = cast(str, t.get("name", ""))
        t_state = cast(str, t.get("state", ""))
        console.print(f"  {t_state:<14} {t_progress * 100:5.1f}%  {t_size_gb:7.2f} GB  {seeding:8}  {t_name}")
    console.print(f"[bold]Total:[/bold] {payload['completed']} completed (of {payload['tracked']} tracked torrents)")


# --- Library maintenance commands ---
