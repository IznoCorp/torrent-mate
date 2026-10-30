"""Typer CLI entry point for PersonalScraper.

Defines the main app with global options (--verbose, --quiet, --version,
--config). Command bodies live in personalscraper.commands.* modules and
register themselves against the shared Typer app imported here.

This module is the system boundary that resolves and loads the typed
JSON5 :class:`Config`. Commands that need the process-scoped service
bundle wrap the loaded ``Config`` + env-var ``Settings`` into an
:class:`AppContext` at their own boundary — see
``personalscraper.commands.pipeline.build_app_context`` for the pipeline
command, and ``personalscraper.commands.library.scan`` /
``personalscraper.trailers.cli`` for the launchd + trailers entrypoints.
Internal components MUST NOT receive an ``AppContext`` "for convenience" —
``tests/architecture/test_app_context_boundary.py`` enforces the
boundary-only rule from DESIGN §Architecture.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.traceback import install as install_traceback

from personalscraper import __version__
from personalscraper.cli_app import app, config_app
from personalscraper.cli_helpers import _bootstrap_staging, _format_validation, _resolve_category, handle_cli_errors
from personalscraper.cli_state import AppCtx, State, state
from personalscraper.commands.info import info_app
from personalscraper.i18n import t
from personalscraper.logger import configure_logging, get_logger

# Rich tracebacks for readable error output.
install_traceback(show_locals=False)

log = get_logger("cli")

# Mount trailers sub-app (personalscraper trailers <subcommand>).
from personalscraper.trailers.cli import app as trailers_app  # noqa: E402

app.add_typer(trailers_app, name="trailers")
app.add_typer(config_app, name="config")
app.add_typer(info_app, name="info")


@app.callback(help=t("cli_core.main.help"))
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help=t("cli_core.main.verbose_help")),
    quiet: bool = typer.Option(False, "--quiet", "-q", help=t("cli_core.main.quiet_help")),
    version: bool = typer.Option(False, "--version", help=t("cli_core.main.version_help")),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help=t("cli_core.main.format_help"),
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help=t("cli_core.main.config_help"),
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

    if output_format not in ("rich", "plain", "json"):
        typer.echo(t("cli_core.main.invalid_format", value=output_format), err=True)
        raise typer.Exit(code=2)

    state["console"] = Console(quiet=quiet)
    state["verbose"] = verbose
    state["quiet"] = quiet
    state["format"] = output_format
    configure_logging(verbose=verbose, quiet=quiet)

    # init-config and config sub-app bypass eager load: config/ may not exist
    # yet, and config maintenance commands load their own paths. ``schedule`` loads
    # nothing itself: each job it runs is a fresh process that loads its own config.
    if ctx.invoked_subcommand in {"init-config", "config", "schedule"}:
        ctx.obj = AppCtx(config=None, config_override=config)
        return

    try:
        cfg = load_config(resolve_config_path(config))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(t("cli_core.main.config_error", error=str(exc)), err=True)
        raise typer.Exit(code=2) from exc
    ctx.obj = AppCtx(config=cfg, config_override=config)


# Import command modules after the callback is registered.  Import side effects
# attach commands to the shared Typer app.
import personalscraper.commands.config  # noqa: E402
import personalscraper.commands.cross_seed  # noqa: E402
import personalscraper.commands.follow  # noqa: E402
import personalscraper.commands.grab  # noqa: E402
import personalscraper.commands.health_check  # noqa: E402
import personalscraper.commands.library  # noqa: E402 — re-exports from library/{scan,query,maintenance,audit,analyze}
import personalscraper.commands.pipeline  # noqa: E402
import personalscraper.commands.plex_guard  # noqa: E402
import personalscraper.commands.schedule  # noqa: E402
import personalscraper.commands.scrape_resolve  # noqa: E402
import personalscraper.commands.search  # noqa: E402
import personalscraper.commands.seed  # noqa: E402
import personalscraper.commands.spine  # noqa: E402
import personalscraper.commands.supervise  # noqa: E402
import personalscraper.commands.torrents  # noqa: E402
import personalscraper.commands.watch  # noqa: E402,F401

# Web is a Typer sub-app (bare ``web`` boots the daemon via its callback;
# ``web set-password`` hangs off the same group), so it is mounted with
# add_typer like the other sub-apps rather than registered as a flat command.
from personalscraper.commands.web import web_app  # noqa: E402

app.add_typer(web_app, name="web")

from personalscraper.commands.accounts import accounts_app  # noqa: E402

app.add_typer(accounts_app, name="accounts")

__all__ = [
    "AppCtx",
    "State",
    "_bootstrap_staging",
    "_format_validation",
    "_resolve_category",
    "app",
    "config_app",
    "handle_cli_errors",
    "main",
    "state",
]
