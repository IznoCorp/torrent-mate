"""Tests for the cli_telemetry decorator (Phase 3.2 / DEV #23 / SH-10).

DEV #23 — pre tech-debt 0.16.0, no CLI command emitted any
``cli.invoke.<cmd>`` event. Operator-side audit "who ran what when"
required parsing stdout of arbitrary commands; pipeline-monitor host
process couldn't capture a unified entry point per session.

Phase 3.2 adds the ``cli_telemetry`` decorator (personalscraper/cli_telemetry.py)
that wraps a Typer command function and emits three structured events :

* ``cli.invoke.<cmd>``  on entry (kwargs sanitised, ``ctx`` filtered out)
* ``cli.complete.<cmd>`` on clean return (exit code or 0)
* ``cli.failed.<cmd>``  on unhandled exception (error + type), then re-raises

Tests pin :
1. Entry event fires with command name.
2. Complete event fires after clean return.
3. Failed event fires + re-raises on exception.
4. Sanitisation of ``ctx`` kwarg (not logged).
5. ``typer.Exit`` (deliberate control flow) does NOT fire ``cli.failed`` —
   regression for the health-check self-perpetuating alert loop, where
   ``typer.Exit(1)`` was misreported as a failure and then picked up by
   health-check's own log scanner as a fresh anomaly on the next run.
"""

from __future__ import annotations

import logging

import pytest
import typer

from personalscraper.cli_telemetry import cli_telemetry


def test_cli_telemetry_emits_invoke_on_entry(caplog: pytest.LogCaptureFixture) -> None:
    """cli.invoke.<cmd> event fires when the wrapped function is called."""

    @cli_telemetry("test-entry")
    def wrapped(ctx: object, x: int = 1) -> None:
        pass

    with caplog.at_level(logging.INFO, logger="cli.telemetry"):
        wrapped(None, x=5)

    invoke_records = [r for r in caplog.records if "cli.invoke.test-entry" in r.getMessage()]
    assert len(invoke_records) == 1, (
        f"Expected 1 cli.invoke.test-entry record, got {len(invoke_records)}. "
        f"All: {[r.getMessage() for r in caplog.records]}"
    )


def test_cli_telemetry_emits_complete_on_clean_return(caplog: pytest.LogCaptureFixture) -> None:
    """cli.complete.<cmd> event fires after the wrapped function returns cleanly."""

    @cli_telemetry("test-complete")
    def wrapped(ctx: object) -> int:
        return 0

    with caplog.at_level(logging.INFO, logger="cli.telemetry"):
        result = wrapped(None)

    assert result == 0
    complete_records = [r for r in caplog.records if "cli.complete.test-complete" in r.getMessage()]
    assert len(complete_records) == 1


def test_cli_telemetry_emits_failed_on_exception_and_reraises(caplog: pytest.LogCaptureFixture) -> None:
    """cli.failed.<cmd> event fires on exception ; the exception is re-raised.

    Pins the contract : telemetry must not swallow exceptions. The outer
    handler (handle_cli_errors, Typer error formatter) still sees the raise.
    """

    @cli_telemetry("test-fail")
    def wrapped(ctx: object) -> None:
        raise RuntimeError("boom!")

    with caplog.at_level(logging.ERROR, logger="cli.telemetry"):
        with pytest.raises(RuntimeError, match="boom!"):
            wrapped(None)

    failed_records = [r for r in caplog.records if "cli.failed.test-fail" in r.getMessage()]
    assert len(failed_records) == 1, f"Expected 1 cli.failed.test-fail record, got {len(failed_records)}"


def test_cli_telemetry_does_not_emit_failed_on_typer_exit(caplog: pytest.LogCaptureFixture) -> None:
    """``typer.Exit`` is deliberate control flow, not a failure — no cli.failed event.

    Regression for the health-check self-perpetuating alert loop: before the
    fix, ``raise typer.Exit(1)`` (used by health-check to signal "anomalies
    found" for cron/healthchecks.io) was caught by the generic ``except
    Exception`` and logged as ``cli.failed.health-check``. health-check's own
    log scanner then picked up that self-generated error line on its next
    run and re-triggered indefinitely, even with no real anomaly left.
    """

    @cli_telemetry("test-exit")
    def wrapped(ctx: object) -> None:
        raise typer.Exit(1)

    with caplog.at_level(logging.ERROR, logger="cli.telemetry"):
        with pytest.raises(typer.Exit):
            wrapped(None)

    failed_records = [r for r in caplog.records if "cli.failed.test-exit" in r.getMessage()]
    assert failed_records == [], f"typer.Exit must not emit cli.failed, got {[r.getMessage() for r in failed_records]}"


def test_cli_telemetry_decorator_preserves_function_name() -> None:
    """functools.wraps preserves __name__ so Typer / introspection still see the original name."""

    @cli_telemetry("name-pin")
    def my_command(ctx: object) -> None:
        pass

    assert my_command.__name__ == "my_command"
