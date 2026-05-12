"""Sub-phase 5.4 — wire ``personalscraper run --verbose`` to DebugLogSubscriber.

These integration tests drive the CLI through Typer's ``CliRunner`` against a
stubbed ``Pipeline`` that emits a deterministic event sequence. They verify
that the verbose flag — and only the verbose flag — registers a working
:class:`~personalscraper.subscribers.debug_log.DebugLogSubscriber` on the
process-scoped :class:`EventBus`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.models import PipelineReport, StepReport
from personalscraper.pipeline_events import (
    PipelineEnded,
    PipelineStarted,
    StepCompleted,
    StepStarted,
)

runner = CliRunner()


def _now() -> datetime:
    """Return a fixed UTC timestamp for deterministic report construction."""
    return datetime(2026, 5, 12, 17, 0, 0, tzinfo=timezone.utc)


def _expected_sequence() -> list[Any]:
    """Return the canonical 4-event sequence emitted by the stub Pipeline."""
    rep = PipelineReport(started_at=_now())
    started = PipelineStarted(report=rep)
    step_started = StepStarted(step="ingest")
    step_completed = StepCompleted(step="ingest", report=StepReport(name="ingest"), elapsed_s=1.23)
    ended = PipelineEnded(
        report=PipelineReport(started_at=_now(), steps={"ingest": StepReport(name="ingest")}),
    )
    return [started, step_started, step_completed, ended]


class _StubPipeline:
    """Stand-in :class:`Pipeline` that emits a known event sequence on its bus."""

    def __init__(self, app_context: Any) -> None:
        """Capture the :class:`AppContext` so ``run`` can emit on its bus."""
        self._app = app_context

    def run(self, **_kwargs: Any) -> PipelineReport:
        """Emit the expected sequence on ``self._app.event_bus``."""
        for ev in _expected_sequence():
            self._app.event_bus.emit(ev)
        return PipelineReport(started_at=_now(), steps={"ingest": StepReport(name="ingest")})


def _invoke_run(*, verbose: bool, monkeypatch: Any) -> tuple[Any, list[Any]]:
    """Run the CLI ``run`` command with / without ``--verbose`` and capture events.

    Patches ``DebugLogSubscriber.on_event`` so emitted events are appended to
    a per-call list (returned alongside the runner result). The Pipeline,
    config loading, and lock files are all stubbed so the CLI invocation
    exercises only the subscriber-wiring branch.
    """
    received: list[Any] = []

    from personalscraper.subscribers import debug_log as _dl

    def _on_event(_self: Any, event: Any) -> None:
        received.append(event)

    monkeypatch.setattr(_dl.DebugLogSubscriber, "on_event", _on_event)

    # Build a MagicMock Config that satisfies the run command's attribute
    # accesses (paths.data_dir, paths.staging_dir, trailers.pipeline.skip,
    # trailers.pipeline.continue_on_error). The lock and bootstrap layers
    # are mocked separately below.
    config = MagicMock()
    config.paths.data_dir = Path("/tmp/__phase5_4_test__")
    config.paths.staging_dir = Path("/tmp/__phase5_4_test__/staging")
    config.trailers.pipeline.skip = True
    config.trailers.pipeline.continue_on_error = False

    cmd = ["--verbose", "run", "--headless", "--skip-trailers"] if verbose else ["run", "--headless", "--skip-trailers"]

    with (
        patch("personalscraper.conf.loader.load_config", return_value=config),
        patch("personalscraper.conf.loader.resolve_config_path", return_value=Path("/tmp/cfg.json5")),
        patch("personalscraper.pipeline.Pipeline", _StubPipeline),
        patch("personalscraper.commands.pipeline.cli_compat.acquire_lock", return_value=True),
        patch("personalscraper.commands.pipeline.cli_compat.release_lock"),
        patch("personalscraper.commands.pipeline._bootstrap_staging"),
        patch("personalscraper.commands.pipeline.cli_compat.get_settings", return_value=MagicMock()),
        patch("personalscraper.commands.pipeline._build_app_context") as _build,
    ):
        # Build a real AppContext so its EventBus is a real bus (the subscriber
        # subscribes to it, the stub Pipeline emits on it).
        from personalscraper.core.app_context import AppContext
        from personalscraper.core.event_bus import EventBus

        _build.return_value = AppContext(config=config, settings=MagicMock(), event_bus=EventBus())
        result = runner.invoke(app, cmd)
    return result, received


def test_cli_run_verbose_registers_debug_log_subscriber(monkeypatch: Any) -> None:
    """``run --verbose`` registers a working :class:`DebugLogSubscriber`.

    Strict equality on the event-type sequence — soft cardinality
    (``len(received) >= 1``) is trivially evaded by a stub that emits nothing.
    """
    result, received = _invoke_run(verbose=True, monkeypatch=monkeypatch)

    assert result.exit_code == 0, f"exit={result.exit_code}\nstdout={result.stdout}\nstderr={result.stderr}"
    received_types = [type(e).__name__ for e in received]
    assert received_types == ["PipelineStarted", "StepStarted", "StepCompleted", "PipelineEnded"], (
        f"expected canonical 4-event sequence, got {received_types}"
    )


def test_cli_run_without_verbose_does_not_register_debug_log_subscriber(monkeypatch: Any) -> None:
    """Without ``--verbose``, no :class:`DebugLogSubscriber` is constructed."""
    result, received = _invoke_run(verbose=False, monkeypatch=monkeypatch)

    assert result.exit_code == 0, f"exit={result.exit_code}\nstdout={result.stdout}\nstderr={result.stderr}"
    types = [type(e).__name__ for e in received]
    assert received == [], f"DebugLogSubscriber received events without --verbose: {types}"
