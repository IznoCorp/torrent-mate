"""Typer CLI entry point for PersonalScraper.

Defines the main app with global options (--verbose, --quiet, --version,
--config). Command bodies live in personalscraper.commands.* modules and
register themselves against the shared Typer app imported here.

This module is the system boundary that resolves and loads the typed
JSON5 :class:`Config`. Commands that need the process-scoped service
bundle wrap the loaded ``Config`` + env-var ``Settings`` into an
:class:`AppContext` at their own boundary — see
``personalscraper.commands.pipeline._build_app_context`` for the pipeline
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
from personalscraper.config import get_settings
from personalscraper.ingest.ingest import run_ingest
from personalscraper.lock import acquire_lock, release_lock
from personalscraper.logger import configure_logging, get_logger

# Rich tracebacks for readable error output.
install_traceback(show_locals=False)

log = get_logger("cli")

# Mount trailers sub-app (personalscraper trailers <subcommand>).
from personalscraper.trailers.cli import app as trailers_app  # noqa: E402

app.add_typer(trailers_app, name="trailers")
app.add_typer(config_app, name="config")
app.add_typer(info_app, name="info")


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable DEBUG logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format: rich (default), plain, or json.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help=(
            "Path to a split-config directory (containing config.json5 + "
            "overlays). Overrides ./config/ and "
            "$PERSONALSCRAPER_CONFIG. Must be placed BEFORE the subcommand."
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

    if output_format not in ("rich", "plain", "json"):
        typer.echo(f"Invalid --format '{output_format}'. Choose rich, plain, or json.", err=True)
        raise typer.Exit(code=2)

    state["console"] = Console(quiet=quiet)
    state["verbose"] = verbose
    state["quiet"] = quiet
    state["format"] = output_format
    configure_logging(verbose=verbose, quiet=quiet)

    # init-config and config sub-app bypass eager load: config/ may not exist
    # yet, and config maintenance commands load their own paths.
    if ctx.invoked_subcommand in {"init-config", "config"}:
        ctx.obj = AppCtx(config=None, config_override=config)
        return

    try:
        cfg = load_config(resolve_config_path(config))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    ctx.obj = AppCtx(config=cfg, config_override=config)


# Import command modules after the callback is registered.  Import side effects
# attach commands to the shared Typer app.
import personalscraper.commands.config  # noqa: E402,F401
import personalscraper.commands.cross_seed  # noqa: E402,F401
import personalscraper.commands.follow  # noqa: E402,F401
import personalscraper.commands.grab  # noqa: E402,F401
import personalscraper.commands.health_check  # noqa: E402,F401
import personalscraper.commands.library  # noqa: E402,F401 — re-exports from library/{scan,query,maintenance,audit,analyze}
import personalscraper.commands.pipeline  # noqa: E402,F401
import personalscraper.commands.seed  # noqa: E402,F401
import personalscraper.commands.watch  # noqa: E402,F401
import personalscraper.commands.web  # noqa: E402,F401

__all__ = [
    "AppCtx",
    "State",
    "_bootstrap_staging",
    "_format_validation",
    "_resolve_category",
    "acquire_lock",
    "app",
    "config_app",
    "get_settings",
    "handle_cli_errors",
    "main",
    "release_lock",
    "run_ingest",
    "state",
]
