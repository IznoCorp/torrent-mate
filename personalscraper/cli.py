"""Typer CLI entry point for PersonalScraper.

Defines the main app with global options (--verbose, --quiet, --version,
--config) and commands for each pipeline step. Lock is acquired per-command
to prevent concurrent executions. Config is loaded eagerly at the callback
and stored in ``ctx.obj`` (AppCtx) for all subcommands.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.traceback import install as install_traceback

from personalscraper import __version__
from personalscraper.conf.models import Config
from personalscraper.config import get_settings
from personalscraper.ingest.ingest import run_ingest
from personalscraper.lock import acquire_lock, release_lock
from personalscraper.logger import configure_logging

logger = logging.getLogger(__name__)


@dataclass
class AppCtx:
    """Application context passed through Typer's ctx.obj.

    Attributes:
        config: Loaded and validated Config instance. None only for init-config.
        config_override: Path passed via --config CLI option, if any.
    """

    config: Config | None
    config_override: Path | None


# Rich tracebacks for readable error output
install_traceback(show_locals=False)

app = typer.Typer(help="PersonalScraper — Media pipeline automation.", invoke_without_command=True)


class _State(TypedDict):
    """Typed shape of the global CLI state dict.

    Attributes:
        console: Rich console used for all CLI output.
        verbose: Whether verbose (DEBUG) logging is enabled.
        quiet: Whether console output is suppressed.
    """

    console: Console
    verbose: bool
    quiet: bool


# Global state shared between commands (set by the callback)
state: _State = {"console": Console(), "verbose": False, "quiet": False}


def _format_validation(exc: ValidationError) -> str:
    """Format pydantic ValidationError as a user-friendly one-liner.

    Extracts field names and error messages from pydantic's structured
    errors, joining them with semicolons.

    Args:
        exc: The pydantic ValidationError to format.

    Returns:
        Formatted string like "qbit_port: Input should be a valid integer".
    """
    parts: list[str] = []
    for err in exc.errors():
        field = " → ".join(str(loc) for loc in err["loc"])
        parts.append(f"{field}: {err['msg']}")
    return "; ".join(parts)


def handle_cli_errors(func: Callable[..., Any]) -> Callable[..., Any]:
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
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except ValidationError as exc:
            msg = _format_validation(exc)
            logging.getLogger("cli").error("Configuration error: %s", msg)
            state["console"].print(f"[red]Configuration error:[/red] {msg}")
            raise typer.Exit(1)

    return wrapper


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable DEBUG logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help=(
            "Path to config.json5 (overrides ./config.json5 and "
            "$PERSONALSCRAPER_CONFIG). Must be placed BEFORE the subcommand."
        ),
    ),
) -> None:
    """PersonalScraper — Media pipeline automation."""
    from personalscraper.conf.loader import (
        ConfigNotFoundError,
        ConfigValidationError,
        load_config,
        resolve_config_path,
    )

    if version:
        typer.echo(__version__)
        raise typer.Exit()
    state["console"] = Console(quiet=quiet)
    state["verbose"] = verbose
    state["quiet"] = quiet
    configure_logging(verbose=verbose, quiet=quiet)

    # init-config bypasses eager load: config.json5 may not exist yet.
    if ctx.invoked_subcommand == "init-config":
        ctx.obj = AppCtx(config=None, config_override=config)
        return

    try:
        cfg = load_config(resolve_config_path(config))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    ctx.obj = AppCtx(config=cfg, config_override=config)


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
            f"[bold]Ingest:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
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
            f"[bold]Sort:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
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
            f"[bold]Scrape:[/bold] {report.success_count} OK, {report.skip_count} skipped, {report.error_count} errors"
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
                "[yellow]Warning: --fix is deprecated. Use 'personalscraper enforce' before verify instead.[/yellow]"
            )
        report, dispatchable = run_verify(
            settings,
            dry_run=dry_run,
            fix=fix,
            movies_only=movies_only,
            tvshows_only=tvshows_only,
        )
        console.print(f"[bold]Verify:[/bold] {report.success_count} OK, {report.error_count} blocked")
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
        console.print(f"Enforce: {report.success_count} fixed, {report.skip_count} OK, {report.error_count} errors")
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

    console.print(f"[green]Scan complete:[/green] {result.item_count} items → {output_path}")


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

    # Validate --only parameter
    valid_only = {"actors", "empty", "junk", "release"}
    if only and only not in valid_only:
        console.print(f"[red]Invalid --only value '{only}'. Valid: {', '.join(sorted(valid_only))}[/red]")
        raise typer.Exit(1)

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
                console.print(f"[red]Errors:[/red] {result.error_count} deletions failed (NTFS)")
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
    fix: bool = typer.Option(False, "--fix", help="Attempt automatic fixes"),
    apply: bool = typer.Option(False, "--apply", help="Apply fixes (requires --fix)"),
) -> None:
    """Validate NFO, artwork, naming conformity of library items.

    Checks each media item on storage disks against quality rules.
    Use --fix --apply to attempt automatic corrections.

    Examples:
        personalscraper library-validate
        personalscraper library-validate --disk Disk1
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
            fix=fix,
            apply=apply,
        )

        output_path = settings.data_dir / "library_validation.json"
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

    # Load existing analysis for incremental mode (compare size_gb with tolerance)
    existing: dict[str, float] = {}
    analysis_path = settings.data_dir / "library_analysis.json"
    if incremental and analysis_path.exists():
        try:
            data = read_json(analysis_path)
            for item in data.get("items", []):
                for f in item.get("files", []):
                    path = f.get("path", "")
                    existing[path] = f.get("size_gb", 0.0)
        except (OSError, KeyError, ValueError, TypeError) as exc:
            logger.warning("Cannot load existing analysis for incremental mode: %s", exc)
            console.print(f"[yellow]Warning:[/yellow] Cannot read existing analysis ({exc}), re-analyzing all files.")
            existing = {}

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
        f"[green]Analysis complete:[/green] {result.item_count} items, {result.file_count} files → {analysis_path}"
    )


@app.command()
@handle_cli_errors
def library_recommend(
    sort: str = typer.Option("priority", "--sort", help="Sort by: priority, size, codec"),
    export: str = typer.Option(None, "--export", help="Export format: csv"),
    disk: str = typer.Option(None, "--disk", help="Filter to this disk"),
    category: str = typer.Option(None, "--category", help="Filter to this category"),
) -> None:
    """Generate re-download recommendations from library analysis.

    Requires library-analyze to have been run first.
    Reads library_analysis.json and library_preferences.json.

    Examples:
        personalscraper library-recommend
        personalscraper library-recommend --sort size
        personalscraper library-recommend --export csv
    """
    import csv

    from personalscraper.library.analyzer import _reconstruct_analysis_items
    from personalscraper.library.models import read_json, write_json
    from personalscraper.library.preferences import LibraryPreferences
    from personalscraper.library.recommender import generate_recommendations

    console = state["console"]
    settings = get_settings()

    # Validate --sort parameter
    valid_sorts = {"priority", "size", "codec"}
    if sort not in valid_sorts:
        console.print(f"[red]Invalid --sort value '{sort}'. Valid: {', '.join(sorted(valid_sorts))}[/red]")
        raise typer.Exit(1)

    # Load analysis
    analysis_path = settings.data_dir / "library_analysis.json"
    if not analysis_path.exists():
        console.print("[red]No analysis found. Run library-analyze first.[/red]")
        raise typer.Exit(1)

    analysis_data = read_json(analysis_path)

    # Load preferences
    prefs_path = settings.data_dir / settings.library_preferences_file
    if prefs_path.exists():
        prefs = LibraryPreferences.model_validate_json(prefs_path.read_text())
    else:
        prefs = LibraryPreferences()
        console.print("[yellow]No preferences file found, using defaults.[/yellow]")

    items = _reconstruct_analysis_items(analysis_data)
    result = generate_recommendations(items, prefs)

    # Sort
    sort_keys = {
        "priority": lambda r: {"high": 0, "medium": 1, "low": 2}.get(r.priority, 3),
        "size": lambda r: -(r.estimated_savings_gb or 0),
        "codec": lambda r: r.current.codec,
    }
    if sort in sort_keys:
        result.items.sort(key=sort_keys[sort])

    # Write JSON
    output_path = settings.data_dir / "library_recommendations.json"
    write_json(result, output_path)

    # CSV export
    if export == "csv":
        csv_path = settings.data_dir / "library_recommendations.csv"
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
        personalscraper library-rescrape --disk Disk1 --max-items 50
        personalscraper library-rescrape --interactive
    """
    from personalscraper.dispatch.disk_scanner import get_disk_configs
    from personalscraper.library.models import write_json
    from personalscraper.library.rescraper import rescrape_library

    console = state["console"]
    settings = get_settings()
    disk_configs = get_disk_configs(settings)

    valid_only = {"nfo", "artwork", "episodes"}
    if only and only not in valid_only:
        console.print(f"[red]Invalid --only value '{only}'. Valid: {', '.join(sorted(valid_only))}[/red]")
        raise typer.Exit(1)

    if not dry_run:
        if not acquire_lock():
            console.print("[red]Another instance is running. Exiting.[/red]")
            raise typer.Exit(1)

    try:
        mode = "[bold yellow]DRY-RUN[/bold yellow]" if dry_run else "[bold green]LIVE[/bold green]"
        console.print(f"[bold]Rescraping library ({mode})...[/bold]")

        result = rescrape_library(
            disk_configs,
            settings,
            disk_filter=disk,
            category_filter=category,
            only=only,
            interactive=interactive,
            dry_run=dry_run,
            max_items=max_items,
        )

        output_path = settings.data_dir / "library_rescrape.json"
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
            release_lock()


@app.command()
@handle_cli_errors
def library_report(
    format: str = typer.Option("text", "--format", help="Output format: text or json"),
) -> None:
    """Display library statistics and health report.

    Aggregates data from scan, analysis, validation, and recommendations.
    Run other library commands first to populate the data.

    Examples:
        personalscraper library-report
        personalscraper library-report --format json
    """
    from personalscraper.dispatch.disk_scanner import get_disk_configs, get_disk_status
    from personalscraper.library.models import read_json, write_json
    from personalscraper.library.reporter import format_report_text, generate_report

    console = state["console"]
    settings = get_settings()

    # Load available data
    def _load(name: str) -> dict[str, Any] | None:
        path = settings.data_dir / name
        if path.exists():
            try:
                return read_json(path)
            except (OSError, ValueError) as exc:
                logger.warning("Cannot load %s: %s", name, exc)
                console.print(f"[yellow]Warning: {name} corrupted ({exc}), skipping.[/yellow]")
                return None
        return None

    scan_data = _load("library_scan.json")
    analysis_data = _load("library_analysis.json")
    validation_data = _load("library_validation.json")
    recommendation_data = _load("library_recommendations.json")
    rescrape_data = _load("library_rescrape.json")

    if not any([scan_data, analysis_data, validation_data, recommendation_data, rescrape_data]):
        console.print("[yellow]No library data found. Run library-scan or library-analyze first.[/yellow]")
        raise typer.Exit(1)

    # Get live disk free space
    disk_configs = get_disk_configs(settings)
    disk_statuses = [get_disk_status(dc) for dc in disk_configs]

    report = generate_report(
        scan_data,
        analysis_data,
        validation_data,
        recommendation_data,
        disk_statuses=disk_statuses,
        rescrape_data=rescrape_data,
    )

    if format == "json":
        output_path = settings.data_dir / "library_report.json"
        write_json(report, output_path)
        console.print(f"[green]Report written to {output_path}[/green]")
    else:
        console.print(format_report_text(report))


# ── Setup commands ────────────────────────────────────────────────────────────


@app.command("init-config")
def init_config_cmd(
    example: Path = typer.Option(
        Path("config.example.json5"),
        help="Path to the example template to read from.",
    ),
    output: Path = typer.Option(
        Path("config.json5"),
        help="Destination path for the generated config.json5.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--yes",
        help="Skip interactive prompts and accept all defaults.",
    ),
    from_current: bool = typer.Option(
        False,
        "--from-current",
        help="Bootstrap config from the existing V14 .env file.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite output file if it already exists.",
    ),
) -> None:
    """Create config.json5 from the example template or from a V14 .env migration.

    Run without arguments for interactive mode (prompts for each value).
    Use --from-current to migrate an existing V14 .env automatically.
    Use --yes to skip all prompts and accept defaults.

    Examples:
        personalscraper init-config
        personalscraper init-config --from-current --yes
        personalscraper init-config --output /custom/path/config.json5 --force
    """
    from personalscraper.commands.init_config import init_config

    init_config(example, output, interactive=not non_interactive, from_current=from_current, force=force)
