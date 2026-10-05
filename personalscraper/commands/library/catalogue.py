"""``personalscraper library-catalogue-refresh`` — fill the aired catalogue.

Reads the shows of the library index (read only), asks the TVDB / TMDB clients
for what the politeness rule makes due (a continuing show once a week, an ended
show once) and writes ``acquire.db``'s catalogue. ``--max`` bounds the shows
attempted in one run (each costs one ``get_tv`` and one ``get_episodes`` per
season); the rest waits for the next one. The PM2 cron is the operator's to add.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import cast

import typer

from personalscraper import cli_helpers
from personalscraper.acquire.catalogue import CatalogueStore, ProviderClients, TvCatalogueClient, refresh_catalogue
from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.api.metadata.registry._errors import UnknownProviderError
from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.i18n import t

_DEFAULT_MAX_SHOWS = 50


def _client_of(registry: ProviderRegistry, name: str) -> TvCatalogueClient | None:
    """Return the registered provider ``name`` as a catalogue client, or ``None``.

    An unconfigured provider is not an error here: its shows are reported skipped.

    Args:
        registry: The provider registry.
        name: ``"tvdb"`` or ``"tmdb"``.

    Returns:
        The provider, or ``None`` when the registry does not hold it.
    """
    try:
        return cast(TvCatalogueClient, registry.get(name))
    except UnknownProviderError:
        return None


@app.command("library-catalogue-refresh", help=t("cli_library.catalogue.library_catalogue_refresh_help"))
@handle_cli_errors
def library_catalogue_refresh(
    ctx: typer.Context,
    max_shows: int = typer.Option(
        _DEFAULT_MAX_SHOWS,
        "--max",
        min=1,
        help=t("cli_library.catalogue.library_catalogue_refresh_max_shows_help"),
    ),
) -> None:
    """Refresh the aired catalogue of the shows that are due, at most ``--max``.

    Prints a JSON summary (refreshed, failed, skipped, remaining). A provider
    failure on one show keeps that show's previous rows and the run goes on.

    Examples:
        personalscraper library-catalogue-refresh --max 20
    """
    config = ctx.obj.config
    assert config is not None  # noqa: S101 — set by the CLI root callback
    if config.acquire.db_path is None or config.indexer.db_path is None:
        typer.echo(t("cli_library.catalogue.db_paths_not_configured"), err=True)
        raise typer.Exit(code=1)

    settings = cli_helpers.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=False) as app_context:
        registry = app_context.provider_registry
        clients = ProviderClients(tvdb=_client_of(registry, "tvdb"), tmdb=_client_of(registry, "tmdb"))
        store = CatalogueStore(Path(config.acquire.db_path))
        index = sqlite3.connect(f"file:{config.indexer.db_path}?mode=ro", uri=True)
        try:
            apply_pragmas(index)
        except sqlite3.Error:
            pass  # Read-only connection — pragmas that require writes are harmless to skip.
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
