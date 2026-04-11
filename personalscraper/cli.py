"""Typer CLI entry point for PersonalScraper.

Defines the main app with global options (--verbose, --quiet, --version)
and commands for each pipeline step. Lock is acquired per-command to
prevent concurrent executions.
"""

import typer
from rich.console import Console
from rich.traceback import install as install_traceback

from personalscraper import __version__
from personalscraper.config import get_settings
from personalscraper.ingest.ingest import run_ingest
from personalscraper.lock import acquire_lock, release_lock
from personalscraper.logger import configure_logging

# Rich tracebacks for readable error output
install_traceback(show_locals=False)

app = typer.Typer(help="PersonalScraper — Media pipeline automation.", invoke_without_command=True)

# Global state shared between commands (set by the callback)
state = {"console": Console(), "verbose": False, "quiet": False}


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable DEBUG logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
) -> None:
    """PersonalScraper — Media pipeline automation."""
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    state["console"] = Console(quiet=quiet)
    state["verbose"] = verbose
    state["quiet"] = quiet
    configure_logging(verbose=verbose, quiet=quiet)


@app.command()
def ingest(dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving")) -> None:
    """Ingest completed torrents from qBittorrent."""
    console = state["console"]
    if not acquire_lock():
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        settings = get_settings()
        report = run_ingest(settings, dry_run=dry_run)
        console.print(
            f"[bold]Ingest:[/bold] {report.success_count} OK, "
            f"{report.skip_count} skipped, {report.error_count} errors"
        )
    finally:
        release_lock()


@app.command()
def sort(dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving")) -> None:
    """Sort and clean media files."""
    from personalscraper.sorter.run import run_sort

    console = state["console"]
    if not acquire_lock():
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        settings = get_settings()
        report = run_sort(settings, dry_run=dry_run)
        console.print(
            f"[bold]Sort:[/bold] {report.success_count} OK, "
            f"{report.skip_count} skipped, {report.error_count} errors"
        )
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        release_lock()


@app.command()
def scrape(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt for ambiguous matches"),
    movies_only: bool = typer.Option(False, "--movies-only", help="Process only movies"),
    tvshows_only: bool = typer.Option(False, "--tvshows-only", help="Process only TV shows"),
) -> None:
    """Scrape metadata and artwork from TMDB/TVDB."""
    from personalscraper.scraper.run import run_scrape

    console = state["console"]
    if not acquire_lock():
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        settings = get_settings()
        report = run_scrape(
            settings,
            dry_run=dry_run,
            interactive=interactive,
            movies_only=movies_only,
            tvshows_only=tvshows_only,
        )
        console.print(
            f"[bold]Scrape:[/bold] {report.success_count} OK, "
            f"{report.skip_count} skipped, {report.error_count} errors"
        )
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        release_lock()


@app.command()
def verify(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without fixing"),
    fix: bool = typer.Option(True, "--fix/--no-fix", help="Attempt auto-fixes (default: True)"),
    movies_only: bool = typer.Option(False, "--movies-only", help="Process only movies"),
    tvshows_only: bool = typer.Option(False, "--tvshows-only", help="Process only TV shows"),
) -> None:
    """Verify and qualify scraped media before dispatch."""
    from personalscraper.verify.run import run_verify

    console = state["console"]
    if not acquire_lock():
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        settings = get_settings()
        report, dispatchable = run_verify(
            settings,
            dry_run=dry_run,
            fix=fix,
            movies_only=movies_only,
            tvshows_only=tvshows_only,
        )
        console.print(
            f"[bold]Verify:[/bold] {report.success_count} OK, "
            f"{report.error_count} blocked"
        )
        console.print(f"  {len(dispatchable)} ready for dispatch")
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        release_lock()


@app.command()
def dispatch(dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving")) -> None:
    """Move media to storage disks."""
    from personalscraper.dispatch.run import run_dispatch

    console = state["console"]
    if not acquire_lock():
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        settings = get_settings()
        report = run_dispatch(settings, dry_run=dry_run)
        console.print(
            f"[bold]Dispatch:[/bold] {report.success_count} OK, "
            f"{report.skip_count} skipped, {report.error_count} errors"
        )
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        release_lock()


@app.command()
def run(dry_run: bool = typer.Option(False, "--dry-run", help="Preview full pipeline")) -> None:
    """Run full pipeline (ingest -> sort -> scrape -> verify -> dispatch)."""
    import logging as _logging
    from datetime import datetime

    import structlog.contextvars
    from rich.panel import Panel
    from rich.table import Table

    from personalscraper.dispatch.run import run_dispatch
    from personalscraper.logger import cleanup_old_logs
    from personalscraper.models import PipelineReport, StepReport
    from personalscraper.notifier import TelegramNotifier, ping_healthcheck
    from personalscraper.scraper.run import run_scrape
    from personalscraper.sorter.run import run_sort
    from personalscraper.verify.run import run_verify

    console = state["console"]
    log = _logging.getLogger("pipeline")

    if not acquire_lock():
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)

    try:
        settings = get_settings()

        # Healthcheck start ping
        ping_healthcheck(settings.healthcheck_url, "/start")

        # Clean old logs and bind run context
        cleanup_old_logs()
        structlog.contextvars.clear_contextvars()
        run_id = datetime.now().isoformat(timespec="seconds")
        structlog.contextvars.bind_contextvars(run_id=run_id)

        report = PipelineReport(started_at=datetime.now())
        log.info("Pipeline started (dry_run=%s, run_id=%s)", dry_run, run_id)

        # V1 — Ingest
        try:
            report.add_step("ingest", run_ingest(settings, dry_run=dry_run))
        except Exception:
            log.exception("Ingest step failed fatally")
            report.add_step("ingest", StepReport(
                name="ingest", error_count=1,
                details=["Fatal exception — see logs"],
            ))

        # V2 — Sort
        try:
            report.add_step("sort", run_sort(settings, dry_run=dry_run))
        except Exception:
            log.exception("Sort step failed fatally")
            report.add_step("sort", StepReport(
                name="sort", error_count=1,
                details=["Fatal exception — see logs"],
            ))

        # V3 — Scrape
        try:
            report.add_step("scrape", run_scrape(settings, dry_run=dry_run))
        except Exception:
            log.exception("Scrape step failed fatally")
            report.add_step("scrape", StepReport(
                name="scrape", error_count=1,
                details=["Fatal exception — see logs"],
            ))

        # V4 — Verify (returns StepReport + dispatchable list)
        verified = None
        try:
            step_report, verified = run_verify(settings, dry_run=dry_run)
            report.add_step("verify", step_report)
        except Exception:
            log.exception("Verify step failed fatally")
            report.add_step("verify", StepReport(
                name="verify", error_count=1,
                details=["Fatal exception — see logs"],
            ))

        # V5 — Dispatch (pass verified items from V4)
        try:
            report.add_step("dispatch", run_dispatch(settings, dry_run=dry_run, verified=verified))
        except Exception:
            log.exception("Dispatch step failed fatally")
            report.add_step("dispatch", StepReport(
                name="dispatch", error_count=1,
                details=["Fatal exception — see logs"],
            ))

        report.finished_at = datetime.now()
        log.info("Pipeline finished (duration=%s)", report.duration())

        # Console summary using rich Panel + Table
        table = Table(show_header=True, header_style="bold")
        table.add_column("Step")
        table.add_column("OK", justify="right")
        table.add_column("Skip", justify="right")
        table.add_column("Err", justify="right")
        for name, step in report.steps.items():
            err_style = "red" if step.error_count else ""
            table.add_row(
                name.capitalize(),
                str(step.success_count),
                str(step.skip_count),
                f"[{err_style}]{step.error_count}[/{err_style}]" if err_style else str(step.error_count),
            )
        dur = report.duration()
        minutes = int(dur.total_seconds()) // 60
        seconds = int(dur.total_seconds()) % 60
        dur_str = f"{minutes}min {seconds:02d}s" if minutes else f"{seconds}s"
        status_text = "[green]OK[/green]" if not report.has_errors() else "[red]ERRORS[/red]"
        console.print(Panel(table, title=f"Pipeline {status_text} — {dur_str}", border_style="bold"))

        # Telegram notification (if configured)
        if TelegramNotifier.is_configured(settings):
            notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
            notifier.send_report(report)

        # Healthcheck end ping
        ping_healthcheck(
            settings.healthcheck_url,
            "" if not report.has_errors() else "/fail",
        )

        if report.has_errors():
            raise typer.Exit(1)

    finally:
        release_lock()
