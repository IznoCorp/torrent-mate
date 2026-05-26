"""Informational and setup Typer commands."""

from __future__ import annotations

import dataclasses

import typer

from personalscraper.cli_app import app
from personalscraper.cli_state import state


@app.command()
def info(ctx: typer.Context) -> None:
    """Display version, config paths, and disk status.

    Output format respects the global ``--format`` flag
    (e.g. ``personalscraper --format json info``).

    Examples:
        personalscraper info
        personalscraper --format json info
    """
    from personalscraper.cli_helpers.output import emit  # noqa: PLC0415
    from personalscraper.info.run import collect_info, format_info

    config = ctx.obj.config
    assert config is not None  # guaranteed non-None by callback
    console = state["console"]
    report = collect_info(config)
    emit(
        dataclasses.asdict(report),
        rich_renderer=lambda: console.print(format_info(report)),
    )
