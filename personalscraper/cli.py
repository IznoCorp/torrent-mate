"""Typer CLI entry point for PersonalScraper.

Defines the main app with global options (--verbose, --quiet, --version)
and stub commands for each pipeline step (ingest, sort, scrape, verify, dispatch, run).
Each command is implemented in its respective version (V1-V6).
"""

import typer
from rich.console import Console
from rich.traceback import install as install_traceback

from personalscraper import __version__
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
    state["console"].print("[bold]ingest[/bold] — not yet implemented (V1)")


@app.command()
def sort(dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving")) -> None:
    """Sort and clean media files."""
    state["console"].print("[bold]sort[/bold] — not yet implemented (V2)")


@app.command()
def scrape(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt for ambiguous matches"),
) -> None:
    """Scrape metadata and artwork from TMDB/TVDB."""
    state["console"].print("[bold]scrape[/bold] — not yet implemented (V3)")


@app.command()
def verify(dry_run: bool = typer.Option(False, "--dry-run", help="Preview without fixing")) -> None:
    """Verify and qualify scraped media before dispatch."""
    state["console"].print("[bold]verify[/bold] — not yet implemented (V4)")


@app.command()
def dispatch(dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving")) -> None:
    """Move media to storage disks."""
    state["console"].print("[bold]dispatch[/bold] — not yet implemented (V5)")


@app.command()
def run(dry_run: bool = typer.Option(False, "--dry-run", help="Preview full pipeline")) -> None:
    """Run full pipeline (ingest → sort → scrape → verify → dispatch)."""
    state["console"].print("[bold]run[/bold] — not yet implemented (V6)")
