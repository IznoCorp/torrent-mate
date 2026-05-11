"""Sub-phase 2.5 invariants for the four ``personalscraper trailers`` commands.

Verifies that each of the four trailers subcommands (``scan``,
``download``, ``verify``, ``purge``) builds an :class:`AppContext` at
its CLI boundary via ``_build_app_context`` and binds
``current_correlation_id`` for the duration of its body. Only
``download`` actually constructs a :class:`TrailersOrchestrator`, so the
"passes ``event_bus`` to orchestrator" assertion applies only to
``download``; the other three commands have no orchestrator and the bus
remains a Phase-4 plumbing hook.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus, current_correlation_id

runner = CliRunner()

_ALL_COMMANDS = ("scan", "download", "verify", "purge")


def _capturing_factory() -> tuple:
    """Build a capturing wrapper around the real ``_build_app_context``.

    Returns:
        Tuple of (wrapped factory, accumulator list, helper context manager
        that patches every external dependency a trailers command needs).
    """
    captured: list[AppContext] = []

    def _factory(config, settings):  # type: ignore[no-untyped-def]
        ctx = AppContext(config=config, settings=settings, event_bus=EventBus())
        captured.append(ctx)
        return ctx

    @contextmanager
    def _stubs(empty_scan: bool = True):
        """Patch every external dependency so the command bodies are inert."""
        empty_items: list = []
        stub_orchestrator = object()
        with (
            patch("personalscraper.trailers.cli._build_app_context", side_effect=_factory),
            # Trailers scan/download/verify/purge all touch the Scanner;
            # stub it to return zero items so the bodies stay short and
            # deterministic (no real filesystem traversal).
            patch(
                "personalscraper.trailers.cli.Scanner",
                return_value=type(
                    "_StubScanner",
                    (),
                    {
                        "scan_staging": lambda self, *_a, **_kw: empty_items,
                        "scan_library": lambda self, *_a, **_kw: empty_items,
                    },
                )(),
            ),
            # Stub the verify command's sqlite open + state store.
            patch("personalscraper.indexer.db.open_db", return_value=sqlite3.connect(":memory:")),
            patch(
                "personalscraper.trailers.cli.TrailerStateStore",
                return_value=type(
                    "_StubStateStore",
                    (),
                    {"all_entries": lambda self: {}, "purge_orphans": lambda self: 0},
                )(),
            ),
            # Stub the download orchestrator so we can assert on its kwargs.
            patch(
                "personalscraper.trailers.cli.TrailersOrchestrator",
                return_value=type(
                    "_StubOrchestrator",
                    (),
                    {"run": lambda self, *_a, **_kw: {"ok": 0}},
                )(),
            ) as orch_mock,
        ):
            yield captured, orch_mock, stub_orchestrator

    return _factory, captured, _stubs


@pytest.mark.parametrize("cmd", _ALL_COMMANDS)
def test_trailers_command_builds_app_context(cmd: str) -> None:
    """Each trailers subcommand invokes ``_build_app_context`` exactly once.

    Args:
        cmd: One of ``scan``, ``download``, ``verify``, ``purge``.
    """
    _, captured, stubs = _capturing_factory()
    with stubs():
        result = runner.invoke(app, ["trailers", cmd])
    assert result.exit_code in {0, 2, 4}, result.output  # 0=clean, 2=verify issues, 4=ffprobe (none here)
    assert len(captured) == 1
    assert isinstance(captured[0], AppContext)
    assert isinstance(captured[0].event_bus, EventBus)


@pytest.mark.parametrize("cmd", _ALL_COMMANDS)
def test_trailers_command_binds_correlation_id(cmd: str) -> None:
    """Each trailers subcommand sets ``current_correlation_id`` and resets it.

    Args:
        cmd: One of ``scan``, ``download``, ``verify``, ``purge``.
    """
    observed: list[str | None] = []
    _, captured, stubs = _capturing_factory()

    def _spy_factory(config, settings):  # type: ignore[no-untyped-def]
        # Capture the ContextVar AFTER ``_build_app_context`` returns but
        # before the rest of the body runs. The ContextVar is set
        # ``after`` the AppContext is built (see ``_trailers_boundary``)
        # — to capture during body execution we read it on the next stub
        # invocation (Scanner.scan_staging) below.
        return AppContext(config=config, settings=settings, event_bus=EventBus())

    def _scan_spy(self, *_a, **_kw):  # type: ignore[no-untyped-def]
        observed.append(current_correlation_id.get())
        return []

    with (
        patch("personalscraper.trailers.cli._build_app_context", side_effect=_spy_factory),
        patch(
            "personalscraper.trailers.cli.Scanner",
            return_value=type(
                "_StubScanner",
                (),
                {
                    "scan_staging": _scan_spy,
                    "scan_library": _scan_spy,
                },
            )(),
        ),
        patch("personalscraper.indexer.db.open_db", return_value=sqlite3.connect(":memory:")),
        patch(
            "personalscraper.trailers.cli.TrailerStateStore",
            return_value=type(
                "_StubStateStore",
                (),
                {"all_entries": lambda self: {}, "purge_orphans": lambda self: 0},
            )(),
        ),
        patch(
            "personalscraper.trailers.cli.TrailersOrchestrator",
            return_value=type("_StubOrch", (), {"run": lambda self, *_a, **_kw: {"ok": 0}})(),
        ),
    ):
        # ``purge`` doesn't invoke Scanner; capture from the state-store
        # ``all_entries`` call instead.
        if cmd == "purge":

            def _capture_purge(self):  # type: ignore[no-untyped-def]
                observed.append(current_correlation_id.get())
                return {}

            with patch(
                "personalscraper.trailers.cli.TrailerStateStore",
                return_value=type("_StubStateStore2", (), {"all_entries": _capture_purge})(),
            ):
                assert current_correlation_id.get() is None
                result = runner.invoke(app, ["trailers", cmd])
        else:
            assert current_correlation_id.get() is None
            result = runner.invoke(app, ["trailers", cmd])

    assert result.exit_code in {0, 2, 4}, result.output
    assert len(observed) >= 1
    # 36-char UUID v4 string captured during the command body.
    assert observed[0] is not None
    assert len(observed[0]) == 36
    # ContextVar must reset after the command returns.
    assert current_correlation_id.get() is None


def test_trailers_download_passes_event_bus_to_orchestrator() -> None:
    """``download`` constructs :class:`TrailersOrchestrator` with ``event_bus=app.event_bus``.

    The three other commands (``scan``, ``verify``, ``purge``) have no
    orchestrator construction site — the bus exists in their AppContext
    purely as Phase-4 plumbing. ``download`` is the only Phase-2 site
    that actually wires the bus into the orchestrator.
    """
    captured: list[AppContext] = []

    def _factory(config, settings):  # type: ignore[no-untyped-def]
        ctx = AppContext(config=config, settings=settings, event_bus=EventBus())
        captured.append(ctx)
        return ctx

    orchestrator_kwargs: dict = {}

    def _capture_orch_init(**kwargs):  # type: ignore[no-untyped-def]
        orchestrator_kwargs.update(kwargs)
        return type("_StubOrch", (), {"run": lambda self, *_a, **_kw: {"ok": 0}})()

    with (
        patch("personalscraper.trailers.cli._build_app_context", side_effect=_factory),
        patch(
            "personalscraper.trailers.cli.Scanner",
            return_value=type(
                "_StubScanner",
                (),
                {"scan_staging": lambda self, *_a, **_kw: []},
            )(),
        ),
        patch(
            "personalscraper.trailers.cli.TrailersOrchestrator",
            side_effect=_capture_orch_init,
        ),
    ):
        result = runner.invoke(app, ["trailers", "download"])
    assert result.exit_code == 0, result.output
    # The orchestrator received the bus carried by the AppContext built at the boundary.
    assert "event_bus" in orchestrator_kwargs
    assert orchestrator_kwargs["event_bus"] is captured[0].event_bus
