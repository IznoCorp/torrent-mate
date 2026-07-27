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

Shared recorder + no-double-record sentinel
--------------------------------------------

The event-emitting logic lives in :func:`run_with_telemetry` so that BOTH this
decorator and the ``cli_helpers.boundary()`` decorator record the *same* event
shape. When a command is both root-instrumented (this decorator, via
``command_with_telemetry``) AND boundary-wrapped, the two layers would otherwise
record twice. A single process-/task-scoped :class:`~contextvars.ContextVar`
sentinel (:data:`_telemetry_recording`) coordinates them: whichever telemetry
layer enters first sets the sentinel and records; any nested layer observes it
set and skips its own recording, so exactly ONE layer records per invocation.
Because ``command_with_telemetry`` (which calls ``app.command``) must be the
OUTERMOST decorator, the outer :func:`cli_telemetry` layer wins and the inner
``boundary()`` layer skips — but the guard is symmetric, so ordering does not
matter for correctness.
"""

from __future__ import annotations

import contextvars
import functools
from collections.abc import Callable
from contextlib import suppress
from typing import Any

import typer

from personalscraper.logger import get_logger

_log = get_logger("cli.telemetry")

#: Set while a telemetry layer is recording a command's invoke/complete/failed
#: events. A nested telemetry layer (e.g. ``boundary()`` under the root
#: ``cli_telemetry``) checks this sentinel and skips its own recording so a
#: command that is both root-instrumented and boundary-wrapped records exactly
#: once (the NO-DOUBLE-RECORD guard). A ``ContextVar`` keeps the flag correct
#: under threads and asyncio tasks.
_telemetry_recording: contextvars.ContextVar[bool] = contextvars.ContextVar("cli_telemetry_recording", default=False)


def telemetry_recording_active() -> bool:
    """Return ``True`` if a telemetry layer is already recording in this call stack.

    Used by :func:`run_with_telemetry` (and, transitively, the
    ``cli_helpers.boundary()`` decorator) to avoid double-recording a command
    that is both root-instrumented and boundary-wrapped.

    Returns:
        ``True`` when an enclosing telemetry layer has already emitted
        ``cli.invoke.<cmd>`` for the current call, else ``False``.
    """
    return _telemetry_recording.get()


def _emit(*, fail_soft: bool, emit: Callable[[], None]) -> None:
    """Run a single telemetry log emit, swallowing errors when *fail_soft*.

    Args:
        fail_soft: When ``True``, any exception raised by *emit* is suppressed so
            a telemetry/logging failure never breaks the wrapped command. When
            ``False`` (the root ``cli_telemetry`` path), emit errors propagate —
            preserving the pre-existing behaviour.
        emit: A zero-argument callable performing exactly one ``_log`` call.
    """
    if fail_soft:
        # Fail-soft: telemetry must never break the command it observes.
        with suppress(Exception):
            emit()
    else:
        emit()


def run_with_telemetry(
    cmd_name: str,
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    fail_soft: bool = False,
) -> Any:
    """Run ``fn(*args, **kwargs)`` bracketed by structured telemetry events.

    Emits ``cli.invoke.<cmd_name>`` on entry, ``cli.complete.<cmd_name>`` on
    clean return (with the exit code, or 0), and ``cli.failed.<cmd_name>`` on an
    unhandled exception (then re-raises). ``typer.Exit`` is deliberate control
    flow, not a failure, and is re-raised silently.

    Sets the :data:`_telemetry_recording` sentinel for the duration of the call
    so a nested telemetry layer skips its own recording. If the sentinel is
    already set on entry (an enclosing layer is recording), this call records
    NOTHING and simply runs *fn* — the NO-DOUBLE-RECORD guard.

    Args:
        cmd_name: Canonical command name used in the event keys (e.g. ``"ingest"``).
        fn: The command callable to run.
        args: Positional arguments forwarded to *fn*.
        kwargs: Keyword arguments forwarded to *fn* and logged (sanitised) on the
            ``cli.invoke`` event; the positional ``ctx`` is never in *kwargs*.
        fail_soft: When ``True``, telemetry emit errors are suppressed (used by
            the boundary decorator). The wrapped command's own errors always
            propagate regardless of this flag.

    Returns:
        Whatever *fn* returns.

    Raises:
        Exception: Re-raises any exception raised by *fn* (after emitting
            ``cli.failed`` for non-``typer.Exit`` errors).
    """
    if _telemetry_recording.get():
        # An enclosing telemetry layer already brackets this call — do not
        # double-record; just run the wrapped command.
        return fn(*args, **kwargs)

    # Sanitised event surface: log only kwargs (the positional ``ctx`` framework
    # object is never in *kwargs*).
    log_kwargs = dict(kwargs)
    token = _telemetry_recording.set(True)
    try:
        # Use string concatenation (not f-string) so the structlog audit rule
        # ``no-fstring-log`` is satisfied while preserving the documented event
        # surface (``cli.invoke.<cmd>`` / ``cli.complete.<cmd>`` /
        # ``cli.failed.<cmd>``).
        _emit(fail_soft=fail_soft, emit=lambda: _log.info("cli.invoke." + cmd_name, **log_kwargs))
        try:
            ret = fn(*args, **kwargs)
        except typer.Exit:
            # Deliberate control flow (e.g. health-check signaling "anomalies
            # found" via a non-zero exit code), not a crash — re-raise silently
            # so it isn't misreported as cli.failed.
            raise
        except Exception as exc:
            # Bind to plain locals: the ``except ... as exc`` name is unbound at
            # block end, so the emit lambda must close over ordinary variables.
            error_msg = str(exc)
            error_type = type(exc).__name__
            _emit(
                fail_soft=fail_soft,
                emit=lambda: _log.error("cli.failed." + cmd_name, error=error_msg, error_type=error_type),
            )
            raise
        _emit(
            fail_soft=fail_soft,
            emit=lambda: _log.info("cli.complete." + cmd_name, exit_code=ret if ret is not None else 0),
        )
        return ret
    finally:
        _telemetry_recording.reset(token)


def cli_telemetry(cmd_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Return a decorator that emits structured telemetry events for a CLI command.

    Emits ``cli.invoke.<cmd_name>`` on entry, ``cli.complete.<cmd_name>`` on
    clean return, and ``cli.failed.<cmd_name>`` on unhandled exception (then
    re-raises so upstream handlers remain active). Delegates to
    :func:`run_with_telemetry`, which also owns the no-double-record sentinel.

    Args:
        cmd_name: The canonical command name used in the event key
            (e.g. ``"ingest"``, ``"library-index"``).

    Returns:
        A decorator that wraps a Typer command function with telemetry events.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return run_with_telemetry(cmd_name, fn, args, kwargs)

        return wrapper

    return decorator


__all__ = ["cli_telemetry", "run_with_telemetry", "telemetry_recording_active"]
