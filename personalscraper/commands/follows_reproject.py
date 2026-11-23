"""Re-project every follow's requesters onto the row the engine reads (``acquisition-follows-reproject``).

A write maintenance action: the floor in force and the pause in force of each follow its requesters
put settings on are written again on its ``followed_series`` row, read from the roles as they stand.
``AccountRightsChanged`` does this for the follows of the accounts a role change touched; this action
repairs a projection a missed event left stale (K3 DESIGN § 4). Run as the system actor.

Examples:
    personalscraper acquisition-follows-reproject
"""

from __future__ import annotations

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.i18n import t


@app.command("acquisition-follows-reproject", help=t("cli_acquisition.follows_reproject.command_help"))
@handle_cli_errors
def acquisition_follows_reproject(ctx: typer.Context) -> None:
    """Re-project every follow with requesters; print how many were written.

    Args:
        ctx: Typer context carrying the loaded configuration.

    Raises:
        typer.Exit: Code 1 when the system actor is refused the act (a read-only instance).
    """
    from personalscraper.app.composition import build_app_services
    from personalscraper.app.errors import AppRefusal
    from personalscraper.config import get_settings
    from personalscraper.core.event_bus import EventBus

    services = build_app_services(ctx.obj.config, get_settings(), event_bus=EventBus())
    try:
        count = services.acquisition.follows.reproject(services.credentials.system_actor())
    except AppRefusal as exc:
        typer.echo(t("cli_acquisition.follows_reproject.refused", code=str(exc.code)), err=True)
        raise typer.Exit(code=1) from exc
    finally:
        services.close()
    emit({"reprojected": count})
