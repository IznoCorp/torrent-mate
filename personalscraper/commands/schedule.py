"""``personalscraper schedule`` — the self-managed cron loop behind PM2's scheduled jobs.

``ecosystem.config.js`` runs one ``schedule --cron EXPR -- JOB...`` app per job instead
of PM2's ``cron_restart``, which fires twice at a boundary and kills the run it started
(see :mod:`personalscraper.scheduler`).
"""

from __future__ import annotations

import typer

from personalscraper import scheduler
from personalscraper.cli_app import app


@app.command("schedule", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def schedule(
    ctx: typer.Context,
    cron: str = typer.Option(..., "--cron", help="5-field cron expression, local time (e.g. '15 * * * *')."),
) -> None:
    """Run a personalscraper command at every boundary of a cron expression, forever.

    The job is everything after ``--``: ``personalscraper schedule --cron '15 * * * *' -- health-check``.
    One run at a time, never started early, never cut by a second tick; stops on SIGINT/SIGTERM.

    Args:
        ctx: Typer context; its extra arguments are the job's CLI arguments.
        cron: The 5-field cron expression.

    Raises:
        typer.Exit: Code 2 when the expression is malformed or no job follows ``--``.
    """
    job = list(ctx.args)
    if not job:
        typer.echo("schedule: no job given after '--'", err=True)
        raise typer.Exit(code=2)
    try:
        scheduler.serve(cron, job)
    except ValueError as exc:
        typer.echo(f"schedule: {exc}", err=True)
        raise typer.Exit(code=2) from exc
