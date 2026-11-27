"""``personalscraper acquisition-suggestions-refresh`` — rebuild the suggestions deck.

Seeds the configured recommendation providers with the titles the follows and the library hold
(the library read through the index, never ``library.db`` by SQL) and replaces the deck in
``acquire.db``. Polite, as ``library-catalogue-refresh`` is: a deck younger than six days is not
asked again (``--force`` lifts it) and ``--max`` bounds the seeds asked in one run, the least
recently asked first. Meant to run under ``personalscraper schedule`` (weekly).

Examples:
    personalscraper acquisition-suggestions-refresh --max 10
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import cast

import typer

from personalscraper import cli_helpers
from personalscraper.acquire.store import build_acquire_store
from personalscraper.acquire.suggestions_refresh import DEFAULT_MAX_SEEDS, Recommender, refresh_suggestions
from personalscraper.api.metadata._contracts import RecommendationProvider
from personalscraper.app.acquisition.held_titles import held_titles
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.commands._cli_run_row import cli_run_row
from personalscraper.i18n import t
from personalscraper.indexer.library_view import LibraryIndex


@command_with_telemetry("acquisition-suggestions-refresh", help=t("cli_acquisition.suggestions_refresh.command_help"))
@handle_cli_errors
def acquisition_suggestions_refresh(
    ctx: typer.Context,
    max_seeds: int = typer.Option(
        DEFAULT_MAX_SEEDS,
        "--max",
        min=1,
        help=t("cli_acquisition.suggestions_refresh.max_help"),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=t("cli_acquisition.suggestions_refresh.force_help"),
    ),
) -> None:
    """Rebuild the suggestions deck from the providers' recommendations, at most ``--max`` seeds.

    Prints a JSON summary (asked, failed, stored, remaining, fresh). A provider failure on one
    seed is counted and the run goes on; a run in which no provider answered leaves the previous
    deck as it was.

    Args:
        ctx: Typer context carrying the loaded configuration.
        max_seeds: The most seeds asked in this run.
        force: Ask even when the deck was refreshed less than six days ago.

    Raises:
        typer.Exit: Code 1 when ``acquire.db_path`` or ``indexer.db_path`` is not configured.
    """
    config = ctx.obj.config
    assert config is not None  # set by the CLI root callback
    if config.acquire.db_path is None or config.indexer.db_path is None:
        typer.echo(t("cli_acquisition.suggestions_refresh.db_paths_not_configured"), err=True)
        raise typer.Exit(code=1)

    settings = cli_helpers.get_settings()
    with (
        cli_run_row(config, "acquisition-suggestions-refresh") as run_rec,
        per_step_boundary(config, settings, build_torrent_client=False) as app_context,
    ):
        # The registry's unfiltered list: a provider whose circuit is open fails its ask, which
        # the refresh counts and goes on from.
        providers = cast("list[Recommender]", list(app_context.provider_registry.providers_for(RecommendationProvider)))
        if not providers:
            typer.echo(t("cli_acquisition.suggestions_refresh.no_provider"), err=True)
        index = LibraryIndex(Path(config.indexer.db_path))
        store = build_acquire_store(config.acquire)
        try:
            report = refresh_suggestions(
                store,
                lambda: held_titles(index),
                providers,
                now=int(time.time()),
                max_seeds=max_seeds,
                force=force,
            )
        finally:
            store.close()

        summary = {
            "asked": report.asked,
            "failed": report.failed,
            "stored": report.stored,
            "remaining": report.remaining,
            "fresh": report.fresh,
        }
        typer.echo(json.dumps(summary))
        run_rec.record_counts({k: int(v) for k, v in summary.items()})
