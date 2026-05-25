"""Shared Typer application instances for the PersonalScraper CLI."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

from personalscraper.cli_telemetry import cli_telemetry

app = typer.Typer(help="PersonalScraper — Media pipeline automation.", invoke_without_command=True)
config_app = typer.Typer(help="Configuration management commands.")


def command_with_telemetry(
    name: str | None = None,
    **typer_command_kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Combine ``@app.command(name)`` + ``@cli_telemetry(name)`` into a single decorator.

    The decorator wraps the function with ``@cli_telemetry`` first (so it
    sits between ``@app.command`` and ``@handle_cli_errors`` per the
    contract in ``cli_telemetry.py``), then registers it with Typer.

    Args:
        name: Public CLI command name (e.g. ``"torrents-list"``). If
            omitted, defaults to the wrapped function's ``__name__``
            (Typer's own default).
        **typer_command_kwargs: Additional kwargs forwarded to
            ``@app.command`` (e.g. ``help=`` for richer help text).

    Returns:
        A decorator that applies both ``@cli_telemetry(cmd_name)`` and
        ``@app.command(name, **kwargs)`` to the wrapped function.

    Example::

        @command_with_telemetry("torrents-list")
        @handle_cli_errors
        def torrents_list(ctx: typer.Context) -> None:
            ...
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        cmd_name = name if name is not None else fn.__name__
        telemetry_wrapped = cli_telemetry(cmd_name)(fn)
        return app.command(name, **typer_command_kwargs)(telemetry_wrapped)

    return decorator


__all__ = ["app", "config_app", "command_with_telemetry"]
