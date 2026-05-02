"""Informational and setup Typer commands."""

from __future__ import annotations

import typer

from personalscraper.cli_app import app
from personalscraper.cli_state import state


@app.command()
def info(ctx: typer.Context) -> None:
    """Display version, config paths, and disk status."""
    from personalscraper.info.run import collect_info, format_info

    config = ctx.obj.config
    assert config is not None  # guaranteed non-None by callback
    console = state["console"]
    report = collect_info(config)
    console.print(format_info(report))
