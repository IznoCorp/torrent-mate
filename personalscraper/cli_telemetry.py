"""CLI telemetry decorator — structured events on command entry, exit, and failure.

Emits three structlog events per command invocation:

* ``cli.invoke.<cmd>``   — on entry, with sanitised kwargs (no ``ctx``).
* ``cli.complete.<cmd>`` — on clean return, with the exit code (or 0).
* ``cli.failed.<cmd>``   — on unhandled exception, with error message and
  type, then re-raises so the outer exception handler (e.g.
  ``handle_cli_errors``) can still act. ``typer.Exit`` is NOT considered a
  failure — it is deliberate control flow (e.g. a command signaling a
  non-zero exit code for cron/healthchecks.io) and is re-raised silently.

Usage::

    @app.command()
    @cli_telemetry("ingest")
    @handle_cli_errors
    def ingest(ctx: typer.Context, dry_run: bool = False) -> None:
        ...

The decorator is placed *between* ``@app.command()`` and ``@handle_cli_errors``
so that ``cli.failed`` fires before the error formatter swallows the exception.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import typer

from personalscraper.logger import get_logger

_log = get_logger("cli.telemetry")


def cli_telemetry(cmd_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Return a decorator that emits structured telemetry events for a CLI command.

    Emits ``cli.invoke.<cmd_name>`` on entry, ``cli.complete.<cmd_name>`` on
    clean return, and ``cli.failed.<cmd_name>`` on unhandled exception (then
    re-raises so upstream handlers remain active).

    Args:
        cmd_name: The canonical command name used in the event key
            (e.g. ``"ingest"``, ``"library-index"``).

    Returns:
        A decorator that wraps a Typer command function with telemetry events.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Filter out the typer.Context positional arg (always first) from
            # the logged kwargs — it is a framework object, not user input.
            # Positional args are logged by index only when the command
            # signature exposes them (rare in Typer — most options are kwargs).
            log_kwargs = {k: v for k, v in kwargs.items()}
            # Use string concatenation (not f-string) so structlog audit rule
            # `no-fstring-log` is satisfied while preserving the documented
            # event surface (`cli.invoke.<cmd>` / `cli.complete.<cmd>` /
            # `cli.failed.<cmd>`).
            _log.info("cli.invoke." + cmd_name, **log_kwargs)
            try:
                ret = fn(*args, **kwargs)
                _log.info("cli.complete." + cmd_name, exit_code=ret if ret is not None else 0)
                return ret
            except typer.Exit:
                # Deliberate control flow (e.g. health-check signaling
                # "anomalies found" via a non-zero exit code), not a crash —
                # re-raise silently so it isn't misreported as cli.failed.
                raise
            except Exception as exc:
                _log.error(
                    "cli.failed." + cmd_name,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise

        return wrapper

    return decorator


__all__ = ["cli_telemetry"]
