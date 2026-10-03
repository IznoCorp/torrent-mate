"""``personalscraper library catalogue-refresh`` — fill the aired catalogue.

Reads the shows of the library index (read only), asks the TVDB / TMDB clients
for what the politeness rule makes due (a continuing show once a week, an ended
show once) and writes ``acquire.db``'s catalogue. ``--max`` bounds the provider
calls of one run; the rest waits for the next one. The PM2 cron is the
operator's to add.

Import direction: commands/ imports acquire/, api/, core/, conf/ only.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import typer

from personalscraper import cli_helpers
from personalscraper.acquire.catalogue import CatalogueStore, ProviderClients, refresh_catalogue
from personalscraper.cli_app import app as _root_app
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary

# Typer sub-group; the plain ``library-*`` commands predate it and stay flat.
library_app = typer.Typer(help="Library commands.")

_DEFAULT_MAX_SHOWS = 50


@library_app.command("catalogue-refresh")
@handle_cli_errors
def library_catalogue_refresh(
    ctx: typer.Context,
    max_shows: int = typer.Option(
        _DEFAULT_MAX_SHOWS,
        "--max",
        min=1,
        help="Upper bound of shows polled at the providers in this run.",
    ),
) -> None:
    """Refresh the aired catalogue of the shows that are due, at most ``--max``.

    Prints a JSON summary (refreshed, failed, skipped, remaining). A provider
    failure on one show keeps that show's previous rows and the run goes on.

    Examples:
        personalscraper library catalogue-refresh --max 20
    """
    config = ctx.obj.config
    assert config is not None  # noqa: S101 — set by the CLI root callback
    if config.acquire.db_path is None or config.indexer.db_path is None:
        typer.echo("acquire.db_path and indexer.db_path must be configured", err=True)
        raise typer.Exit(code=1)

    settings = cli_helpers.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=False) as app_context:
        registry = app_context.provider_registry
        clients = ProviderClients(tvdb=registry.get("tvdb"), tmdb=registry.get("tmdb"))  # type: ignore[arg-type]
        store = CatalogueStore(Path(config.acquire.db_path))
        index = sqlite3.connect(f"file:{config.indexer.db_path}?mode=ro", uri=True)
        try:
            report = refresh_catalogue(store, index, clients, now=time.time(), max_shows=max_shows)
        finally:
            index.close()
            store.close()

    typer.echo(
        json.dumps(
            {
                "refreshed": report.refreshed,
                "failed": report.failed,
                "skipped": report.skipped,
                "remaining": report.remaining,
            }
        )
    )


# Register the library sub-group on the root Typer app (import side-effect, called by cli.py).
_root_app.add_typer(library_app, name="library")
