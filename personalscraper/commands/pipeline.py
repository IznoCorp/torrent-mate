"""Pipeline-related Typer commands."""

from __future__ import annotations

import typer

from personalscraper import cli as cli_compat
from personalscraper.cli_app import app
from personalscraper.cli_helpers import _bootstrap_staging, handle_cli_errors
from personalscraper.cli_state import state
from personalscraper.conf.staging import find_ingest_dir, staging_path
from personalscraper.logger import get_logger


@app.command()
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
        report = cli_compat.run_ingest(
            settings,
            dry_run=dry_run,
            ingest_dir=ingest_dir,
            staging_dir=staging_dir,
            config=config,
        )
        console.print(
            f"[bold]Ingest:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
        )
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@app.command()
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
        report = run_sort(settings, staging_dir=config.paths.staging_dir, dry_run=dry_run, config=config)
        console.print(
            f"[bold]Sort:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
        )
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@app.command()
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
        report = run_scrape(
            settings,
            config=config,
            dry_run=dry_run,
            interactive=interactive,
            movies_only=movies_only,
            tvshows_only=tvshows_only,
        )
        console.print(
            f"[bold]Scrape:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
        )
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@app.command()
@handle_cli_errors
def verify(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying files"),
    movies_only: bool = typer.Option(False, "--movies-only", help="Process only movies"),
    tvshows_only: bool = typer.Option(False, "--tvshows-only", help="Process only TV shows"),
) -> None:
    """Verify and qualify scraped media before dispatch."""
    from personalscraper.verify.run import run_verify

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        _bootstrap_staging(ctx)
        settings = cli_compat.get_settings()
        report, dispatchable = run_verify(
            settings,
            config,
            dry_run=dry_run,
            movies_only=movies_only,
            tvshows_only=tvshows_only,
        )
        console.print(f"[bold]Verify:[/bold] {report.success_count} OK, {report.error_count} blocked")
        console.print(f"  {len(dispatchable)} ready for dispatch")
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@app.command()
@handle_cli_errors
def enforce(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying"),
) -> None:
    """Enforce staging conventions: sanitize filenames, validate structure, check coherence."""
    from personalscraper.enforce.run import run_enforce

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        _bootstrap_staging(ctx)
        settings = cli_compat.get_settings()
        report = run_enforce(settings, config, dry_run=dry_run)
        console.print(f"Enforce: {report.success_count} fixed, {report.skip_count} OK, {report.error_count} errors")
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@app.command()
@handle_cli_errors
def dispatch(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving"),
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
        report = run_dispatch(settings, config=config, dry_run=dry_run)
        console.print(
            f"[bold]Dispatch:[/bold] {report.success_count} OK, "
            f"{report.skip_count} skipped, {report.error_count} errors"
        )
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        cli_compat.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


@app.command()
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
            clean, scrape, cleanup = run_process(settings, dry_run=dry_run, interactive=interactive, config=config)
        except Exception as exc:
            console.print(f"[red]Process failed: {type(exc).__name__}: {exc}[/red]")
            get_logger("pipeline").exception("process_command_failed", error=str(exc))
            raise typer.Exit(1)

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


@app.command()
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
            "Run with no observers (silent mode for cron / CI). "
            "Disables Rich console output and Telegram notifications."
        ),
    ),
) -> None:
    """Run full pipeline (ingest -> sort -> process -> verify -> dispatch)."""
    from datetime import datetime

    import structlog.contextvars

    from personalscraper.api.notify.healthchecks import HealthcheckClient
    from personalscraper.api.notify.telegram import TelegramNotifier
    from personalscraper.api.transport._http import HttpTransport
    from personalscraper.logger import cleanup_old_logs
    from personalscraper.observers.rich_console import RichConsoleObserver
    from personalscraper.pipeline import Pipeline
    from personalscraper.pipeline_observer import PipelineObserver

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    verbose = state["verbose"]
    _run_log = get_logger("pipeline")

    if not cli_compat.acquire_lock(lock_file=config.paths.data_dir / "pipeline.lock"):
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)

    try:
        settings = cli_compat.get_settings()

        # Healthcheck client (None if not configured — pings short-circuit at the call site).
        healthcheck: HealthcheckClient | None = None
        if HealthcheckClient.is_configured(settings):
            hc_transport = HttpTransport(HealthcheckClient.policy(settings.healthcheck_url))
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

            from personalscraper.observers.telegram import TelegramObserver
            from personalscraper.trailers.state import TrailerStepFailed  # noqa: PLC0415

            # Build observer list — RichConsoleObserver now prints the banner in
            # on_pipeline_start, replacing the inline console.print that was here.
            # --headless skips all observer registration for silent cron/CI runs.
            pipeline_observers: list[PipelineObserver] = []
            if not headless:
                pipeline_observers.append(
                    RichConsoleObserver(console=console, verbose=verbose, dry_run=dry_run, run_id=run_id)
                )
                if TelegramNotifier.is_configured(settings):
                    tg_transport = HttpTransport(TelegramNotifier.policy(settings.telegram_bot_token))
                    tg_notifier = TelegramNotifier(tg_transport, settings.telegram_chat_id)
                    pipeline_observers.append(TelegramObserver(tg_notifier))

            # Delegate to Pipeline orchestrator (9-step sequential flow)
            pipeline = Pipeline(
                config,
                settings,
                dry_run=dry_run,
                interactive=interactive,
                verbose=verbose,
                observers=pipeline_observers,
                skip_trailers=effective_skip_trailers,
                continue_on_trailer_error=effective_continue_on_trailer_error,
            )
            try:
                report = pipeline.run()
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


# --- Library maintenance commands ---
