"""Characterization tests of :func:`personalscraper.app.supervisor.execution.execute_run`.

Each test pins one behaviour of today's pipeline run that no other test decides, so the
supervisor worker that becomes the production caller cannot lose it silently. ``Pipeline`` is a
fake that does what the real one does with the arguments ``execute_run`` hands it (writes its
``pipeline_run`` row through the history writer, asks the tail provider for the output tail);
the event bus, the migrated indexer DB and the log root are real, every client is faked.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from personalscraper.acquire.events import WatcherRunTriggered
from personalscraper.app.supervisor import execution
from personalscraper.app.supervisor.execution import RunOptions, execute_run
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.indexer import migrations
from personalscraper.indexer.db import apply_migrations
from personalscraper.models import PipelineReport, StepReport
from personalscraper.pipeline_events import PipelineStarted

_TAIL_MARKER = "a line the run logged while it ran"


class _Harness:
    """What a test reads back after one :func:`execute_run` call.

    Attributes:
        bus: The event bus the run was built over.
        run_kwargs: The keyword arguments the fake ``Pipeline.run`` received.
        db_path: The migrated indexer DB the history writer points at.
        root_handlers_during_run: The root logger's handlers when ``Pipeline.run`` was called.
        events: Every event the bus carried.
        closed: Names of the closeable subscribers that were closed, in order.
    """

    def __init__(self, db_path: Path) -> None:
        """Start empty.

        Args:
            db_path: The migrated indexer DB.
        """
        self.bus = EventBus()
        self.run_kwargs: dict[str, object] = {}
        self.db_path = db_path
        self.root_handlers_during_run: list[logging.Handler] = []
        self.events: list[object] = []
        self.closed: list[str] = []

    def rows(self) -> list[tuple[str, str, str | None]]:
        """The ``(trigger, outcome, output_tail)`` of every ``pipeline_run`` row."""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT trigger, outcome, output_tail FROM pipeline_run").fetchall()


def _report() -> PipelineReport:
    """A clean report: no errors, one second long."""
    report = PipelineReport(started_at=datetime(2026, 1, 1))
    report.add_step("ingest", StepReport(name="ingest"))
    report.finished_at = datetime(2026, 1, 1) + timedelta(seconds=1)
    return report


def _closeable(harness: _Harness, name: str) -> MagicMock:
    """A subscriber double that records its ``close`` in *harness*."""
    double = MagicMock(name=name)
    double.close.side_effect = lambda: harness.closed.append(name)
    return double


@pytest.fixture
def harness(test_config, monkeypatch: pytest.MonkeyPatch) -> _Harness:
    """Replace everything ``execute_run`` reaches outside the process, keep the bus, DB and log root real."""
    db_path = test_config.indexer.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        apply_migrations(conn, Path(migrations.__file__).parent)
    h = _Harness(db_path)
    h.bus.subscribe(Event, h.events.append)

    monkeypatch.setattr(execution, "build_app_context", lambda config, settings, **kw: SimpleNamespace(event_bus=h.bus))
    monkeypatch.setattr("personalscraper.logger.cleanup_old_logs", lambda: None)
    monkeypatch.setattr("personalscraper.api.notify.healthchecks.HealthcheckClient.is_configured", lambda s: False)
    monkeypatch.setattr("personalscraper.api.notify.telegram.TelegramNotifier.is_configured", lambda s: False)
    monkeypatch.setattr("personalscraper.subscribers.plex.build_plex_subscriber", lambda bus, settings: None)
    monkeypatch.setattr("personalscraper.subscribers.redis_stream.build_redis_publisher", lambda bus, web: None)

    class _FakePipeline:
        """Does with ``run``'s arguments what the real pipeline does: one row, the tail, the events."""

        def __init__(self, app: object) -> None:
            self._app = app

        def run(self, **kwargs: object) -> PipelineReport:
            h.run_kwargs = kwargs
            h.root_handlers_during_run = list(logging.root.handlers)
            report = _report()
            self._app.event_bus.emit(PipelineStarted(report=report))
            logging.getLogger("tests.execute_run").warning(_TAIL_MARKER)
            writer = kwargs["history_writer"]
            if writer is not None:
                writer.insert("run-1", str(kwargs["trigger_reason"]), bool(kwargs["dry_run"]), pid=1)
                writer.finalize("run-1", "success", output_tail=kwargs["output_tail_provider"]())
            return report

    monkeypatch.setattr("personalscraper.pipeline.Pipeline", _FakePipeline)
    return h


def _run(config, trigger: str = "", console: Console | None = None, **kwargs: object) -> int:
    """Call ``execute_run`` with a settings double and the flags a test varies."""
    settings = SimpleNamespace(telegram_bot_token="unused", telegram_chat_id="unused", healthcheck_url="")
    return execute_run(config, settings, RunOptions(), trigger=trigger, console=console, verbose=False, **kwargs)


def test_a_run_writes_its_pipeline_run_history_row(harness: _Harness, test_config) -> None:
    """The pipeline gets a history writer on the configured DB, and the row it writes is there."""
    assert _run(test_config) == 0

    assert harness.run_kwargs["history_writer"] is not None
    assert [(trigger, outcome) for trigger, outcome, _ in harness.rows()] == [("cli", "success")]


@pytest.mark.parametrize("reason", ["watcher", "safety_net"])
def test_the_trigger_reason_is_recorded_as_given(harness: _Harness, test_config, reason: str) -> None:
    """A watcher or safety-net run is not recorded as a plain CLI run."""
    assert _run(test_config, trigger=reason) == 0

    assert harness.run_kwargs["trigger_reason"] == reason
    assert [trigger for trigger, _, _ in harness.rows()] == [reason]


def test_no_console_keeps_the_rich_console_silent(harness: _Harness, test_config) -> None:
    """``no_console`` builds no Rich subscriber: an event the run emits prints nothing."""
    printed = StringIO()
    console = Console(file=printed, force_terminal=False)

    assert _run(test_config, console=console, no_console=True) == 0

    assert printed.getvalue() == ""
    # Control: the same run without the flag does print, so the silence above is the flag's doing.
    assert _run(test_config, console=console) == 0
    assert printed.getvalue() != ""


def test_a_watcher_triggered_run_emits_watcher_run_triggered(harness: _Harness, test_config) -> None:
    """The trigger reason reaches the bus before the pipeline starts; a plain run emits nothing."""
    assert _run(test_config) == 0
    assert not [e for e in harness.events if isinstance(e, WatcherRunTriggered)]
    harness.events.clear()

    assert _run(test_config, trigger="safety_net") == 0

    triggered = [e for e in harness.events if isinstance(e, WatcherRunTriggered)]
    assert [e.reason for e in triggered] == ["safety_net"]
    assert harness.events.index(triggered[0]) < harness.events.index(
        next(e for e in harness.events if isinstance(e, PipelineStarted))
    )


def test_the_log_tail_is_captured_for_the_run_row_and_the_handler_is_removed(harness: _Harness, test_config) -> None:
    """The row carries an ``output_tail`` and no tail handler stays on the root logger afterwards."""
    handlers_before = list(logging.root.handlers)

    assert _run(test_config) == 0

    assert len(harness.root_handlers_during_run) == len(handlers_before) + 1
    assert logging.root.handlers == handlers_before
    ((_, _, output_tail),) = harness.rows()
    assert output_tail is not None and _TAIL_MARKER in output_tail


def test_the_publisher_and_the_subscribers_are_closed_when_the_run_ends(
    harness: _Harness, test_config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The redis publisher, the rich and the telegram subscribers are closed, so a long-lived caller leaks none."""
    monkeypatch.setattr(
        "personalscraper.subscribers.redis_stream.build_redis_publisher",
        lambda bus, web: _closeable(harness, "redis"),
    )
    monkeypatch.setattr(
        "personalscraper.subscribers.rich_console.RichConsoleSubscriber",
        lambda *a, **kw: _closeable(harness, "rich"),
    )
    monkeypatch.setattr("personalscraper.api.notify.telegram.TelegramNotifier.is_configured", lambda s: True)
    monkeypatch.setattr("personalscraper.api.notify.telegram.TelegramNotifier.policy", staticmethod(lambda token: None))
    monkeypatch.setattr("personalscraper.api.transport.HttpTransport", lambda *a, **kw: MagicMock())
    monkeypatch.setattr(
        "personalscraper.subscribers.telegram.TelegramSubscriber",
        lambda *a, **kw: _closeable(harness, "telegram"),
    )
    monkeypatch.setattr(
        "personalscraper.subscribers.acquire.AcquisitionTelegramSubscriber",
        lambda *a, **kw: _closeable(harness, "acquire_telegram"),
    )

    assert _run(test_config, console=Console(file=StringIO())) == 0

    assert sorted(harness.closed) == ["acquire_telegram", "redis", "rich", "telegram"]
