"""Typer CLI entry point for PersonalScraper.

Defines the main app with global options (--verbose, --quiet, --version)
and commands for each pipeline step. Lock is acquired per-command to
prevent concurrent executions.
"""

from __future__ import annotations

import functools
import logging

import typer
from pydantic import ValidationError
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


def _format_validation(exc: ValidationError) -> str:
    """Format pydantic ValidationError as a user-friendly one-liner.

    Extracts field names and error messages from pydantic's structured
    errors, joining them with semicolons.

    Args:
        exc: The pydantic ValidationError to format.

    Returns:
        Formatted string like "qbit_port: Input should be a valid integer".
    """
    parts = []
    for err in exc.errors():
        field = " → ".join(str(loc) for loc in err["loc"])
        parts.append(f"{field}: {err['msg']}")
    return "; ".join(parts)


def handle_cli_errors(func):
    """Catch configuration errors, display user-friendly messages.

    Wraps CLI commands to intercept pydantic ValidationError (from
    get_settings()), showing clear messages instead of raw tracebacks.

    Only catches ValidationError — other exceptions (including
    FileNotFoundError from pipeline steps) propagate normally so that
    StepReport, Telegram notifications, and healthcheck pings are
    not bypassed.

    Args:
        func: The CLI command function to wrap.

    Returns:
        Wrapped function with error handling applied.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as exc:
            msg = _format_validation(exc)
            logging.getLogger("cli").error("Configuration error: %s", msg)
            state["console"].print(
                f"[red]Configuration error:[/red] {msg}"
            )
            raise typer.Exit(1)

    return wrapper


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
@handle_cli_errors
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
@handle_cli_errors
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
@handle_cli_errors
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
@handle_cli_errors
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
        if fix:
            console.print(
                "[yellow]Warning: --fix is deprecated. "
                "Use 'personalscraper enforce' before verify instead.[/yellow]"
            )
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
@handle_cli_errors
def enforce(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying"),
) -> None:
    """Enforce staging conventions: sanitize filenames, validate structure, check coherence."""
    from personalscraper.enforce.run import run_enforce

    console = state["console"]
    if not acquire_lock():
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        settings = get_settings()
        report = run_enforce(settings, dry_run=dry_run)
        console.print(
            f"Enforce: {report.success_count} fixed, "
            f"{report.skip_count} OK, {report.error_count} errors"
        )
        if state["verbose"]:
            for detail in report.details:
                console.print(f"  {detail}")
    finally:
        release_lock()


@app.command()
@handle_cli_errors
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
@handle_cli_errors
def process(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt for ambiguous matches"),
) -> None:
    """Run process phase only (reclean + dedup + scrape + cleanup)."""
    from personalscraper.process.run import run_process

    console = state["console"]
    if not acquire_lock():
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        settings = get_settings()
        try:
            clean, scrape, cleanup = run_process(settings, dry_run=dry_run, interactive=interactive)
        except Exception as exc:
            console.print(f"[red]Process failed: {type(exc).__name__}: {exc}[/red]")
            logging.getLogger("pipeline").exception("Process command failed")
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
        release_lock()


@app.command()
@handle_cli_errors
def run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview full pipeline"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt for ambiguous matches"),
) -> None:
    """Run full pipeline (ingest -> sort -> process -> verify -> dispatch)."""
    from datetime import datetime

    import structlog.contextvars
    from rich.panel import Panel
    from rich.table import Table

    from personalscraper.logger import cleanup_old_logs
    from personalscraper.notifier import TelegramNotifier, ping_healthcheck
    from personalscraper.pipeline import Pipeline

    console = state["console"]
    verbose = state["verbose"]
    log = logging.getLogger("pipeline")

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

        mode = "[yellow]DRY-RUN[/yellow]" if dry_run else "[green]LIVE[/green]"
        console.print(
            f"[bold]PersonalScraper Pipeline[/bold] {mode}  [dim]{run_id}[/dim]",
            highlight=False,
        )
        log.info("Pipeline started (dry_run=%s, run_id=%s)", dry_run, run_id)

        # Delegate to Pipeline orchestrator (8-step sequential flow)
        pipeline = Pipeline(
            settings,
            dry_run=dry_run,
            interactive=interactive,
            verbose=verbose,
            console=console,
        )
        report = pipeline.run()

        dur = report.duration()
        minutes = int(dur.total_seconds()) // 60
        seconds = int(dur.total_seconds()) % 60
        dur_str = f"{minutes}min {seconds:02d}s" if minutes else f"{seconds}s"
        log.info("Pipeline finished (duration=%s)", dur_str)

        # Final summary table (8 steps)
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


# --- Library maintenance commands ---


@app.command()
@handle_cli_errors
def library_scan(
    disk: str = typer.Option(None, "--disk", help="Scan only this disk (Disk1-4)"),
    category: str = typer.Option(None, "--category", help="Scan only this category"),
) -> None:
    """Scan library structure and metadata on storage disks.

    Lightweight scan: reads directories and NFOs, no ffprobe.
    Produces library_scan.json in .personalscraper/.

    Examples:
        personalscraper library-scan
        personalscraper library-scan --disk Disk1
        personalscraper library-scan --category films
    """
    from personalscraper.dispatch.disk_scanner import get_disk_configs
    from personalscraper.library.models import write_json
    from personalscraper.library.scanner import scan_library

    console = state["console"]
    settings = get_settings()
    disk_configs = get_disk_configs(settings)

    console.print("[bold]Scanning library...[/bold]")
    result = scan_library(
        disk_configs,
        disk_filter=disk,
        category_filter=category,
    )

    output_path = settings.data_dir / "library_scan.json"
    write_json(result, output_path)

    console.print(
        f"[green]Scan complete:[/green] {result.item_count} items → {output_path}"
    )


@app.command()
@handle_cli_errors
def library_clean(
    apply: bool = typer.Option(False, "--apply", help="Actually delete (default: dry-run)"),
    only: str = typer.Option(None, "--only", help="Only clean: actors, empty, junk, release"),
    disk: str = typer.Option(None, "--disk", help="Clean only this disk (Disk1-4)"),
    category: str = typer.Option(None, "--category", help="Clean only this category"),
) -> None:
    """Remove .actors/, empty dirs, junk files from storage disks.

    Dry-run by default — shows what would be deleted without deleting.
    Use --apply to actually execute deletions.
    Use --only to target specific cleanup types.

    Examples:
        personalscraper library-clean
        personalscraper library-clean --apply
        personalscraper library-clean --apply --only actors
        personalscraper library-clean --disk Disk1
    """
    from personalscraper.dispatch.disk_scanner import get_disk_configs
    from personalscraper.library.disk_cleaner import clean_library

    console = state["console"]
    settings = get_settings()
    disk_configs = get_disk_configs(settings)

    # Acquire lock only when applying changes
    if apply:
        if not acquire_lock():
            console.print("[red]Another instance is running. Exiting.[/red]")
            raise typer.Exit(1)

    try:
        mode = "[bold red]APPLY[/bold red]" if apply else "[bold yellow]DRY-RUN[/bold yellow]"
        console.print(f"[bold]Cleaning library ({mode})...[/bold]")

        result = clean_library(
            disk_configs,
            apply=apply,
            only=only,
            disk_filter=disk,
            category_filter=category,
        )

        if result.dry_run:
            console.print(
                f"[yellow]DRY-RUN:[/yellow] Would delete {result.deleted_count} items "
                f"({result.freed_bytes / 1024 / 1024:.1f} MB)"
            )
        else:
            console.print(
                f"[green]Deleted:[/green] {result.deleted_count} items "
                f"({result.freed_bytes / 1024 / 1024:.1f} MB freed)"
            )
            if result.error_count:
                console.print(
                    f"[red]Errors:[/red] {result.error_count} deletions failed (NTFS)"
                )
                for err in result.errors:
                    console.print(f"  {err}")
    finally:
        if apply:
            release_lock()


@app.command()
@handle_cli_errors
def library_validate(
    disk: str = typer.Option(None, "--disk", help="Validate only this disk"),
    category: str = typer.Option(None, "--category", help="Validate only this category"),
    level: str = typer.Option("full", "--level", help="Validation level: quick or full"),
    fix: bool = typer.Option(False, "--fix", help="Attempt automatic fixes"),
    apply: bool = typer.Option(False, "--apply", help="Apply fixes (requires --fix)"),
) -> None:
    """Validate NFO, artwork, naming conformity of library items.

    Checks each media item on storage disks against quality rules.
    Use --fix --apply to attempt automatic corrections.

    Examples:
        personalscraper library-validate
        personalscraper library-validate --disk Disk1 --level quick
        personalscraper library-validate --fix --apply
    """
    from personalscraper.dispatch.disk_scanner import get_disk_configs
    from personalscraper.library.models import write_json
    from personalscraper.library.validator import validate_library

    console = state["console"]
    settings = get_settings()
    disk_configs = get_disk_configs(settings)

    if apply and not fix:
        console.print("[red]--apply requires --fix[/red]")
        raise typer.Exit(1)

    if fix and apply:
        if not acquire_lock():
            console.print("[red]Another instance is running. Exiting.[/red]")
            raise typer.Exit(1)

    try:
        console.print("[bold]Validating library...[/bold]")
        result = validate_library(
            disk_configs,
            disk_filter=disk,
            category_filter=category,
            level=level,
        )

        output_path = settings.data_dir / "library_validation.json"
        write_json(result, output_path)

        console.print(
            f"[green]Valid:[/green] {result.valid_count}  "
            f"[yellow]Fixed:[/yellow] {result.fixed_count}  "
            f"[red]Blocked:[/red] {result.blocked_count}  "
            f"→ {output_path}"
        )
    finally:
        if fix and apply:
            release_lock()


@app.command()
@handle_cli_errors
def library_analyze(
    disk: str = typer.Option(None, "--disk", help="Analyze only this disk"),
    category: str = typer.Option(None, "--category", help="Analyze only this category"),
    incremental: bool = typer.Option(False, "--incremental", help="Skip already-analyzed files"),
    max_items: int = typer.Option(None, "--max-items", help="Limit number of items to analyze"),
) -> None:
    """Deep scan video files with ffprobe (codec, audio, subtitles).

    Most I/O-intensive command — schedule during off-peak hours.
    Use --incremental to skip files that haven't changed since last analysis.

    Examples:
        personalscraper library-analyze --incremental
        personalscraper library-analyze --disk Disk2 --category series
        personalscraper library-analyze --max-items 50
    """
    from personalscraper.dispatch.disk_scanner import get_disk_configs
    from personalscraper.library.analyzer import analyze_library
    from personalscraper.library.models import read_json, write_json

    console = state["console"]
    settings = get_settings()
    disk_configs = get_disk_configs(settings)

    # Load existing analysis for incremental mode
    existing: dict[str, int] = {}
    analysis_path = settings.data_dir / "library_analysis.json"
    if incremental and analysis_path.exists():
        try:
            data = read_json(analysis_path)
            for item in data.get("items", []):
                for f in item.get("files", []):
                    path = f.get("path", "")
                    size_bytes = int(f.get("size_gb", 0) * 1024 ** 3)
                    existing[path] = size_bytes
        except (OSError, KeyError):
            pass

    console.print("[bold]Analyzing library (ffprobe)...[/bold]")
    result = analyze_library(
        disk_configs,
        disk_filter=disk,
        category_filter=category,
        incremental=incremental,
        existing_sizes=existing if incremental else None,
        max_items=max_items,
    )

    write_json(result, analysis_path)

    console.print(
        f"[green]Analysis complete:[/green] {result.item_count} items, "
        f"{result.file_count} files → {analysis_path}"
    )
