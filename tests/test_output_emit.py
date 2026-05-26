"""Tests for personalscraper.cli_helpers.output.emit().

Covers the fail-soft contract for rich_renderer: a callback that raises
must NOT escape the emit call, the exception must be logged as
``emit_rich_renderer_failed`` at error level, and the payload must be
re-printed via the fallback ``console.print(payload)`` path.
"""

from __future__ import annotations

from io import StringIO
from typing import Any
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from personalscraper.cli_helpers.output import emit
from personalscraper.cli_state import state


@pytest.fixture
def rich_state(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Set CLI state to rich format with an in-memory console."""
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=80)
    monkeypatch.setitem(state, "format", "rich")
    monkeypatch.setitem(state, "console", console)
    return {"console": console, "buffer": buffer}


class TestEmitRichRendererFailSoft:
    """rich_renderer raising must not escape emit() — SF-M4 regression."""

    def test_renderer_exception_does_not_escape(self, rich_state: dict[str, Any]) -> None:
        """A RuntimeError inside rich_renderer is swallowed and logged."""
        payload = {"answer": 42}

        def renderer() -> None:
            raise RuntimeError("renderer blew up")

        # Must not raise — emit() is the boundary between CLI commands and
        # the user; a renderer bug must not abort the whole command.
        emit(payload, rich_renderer=renderer)

    def test_renderer_exception_logged_at_error_level(
        self,
        rich_state: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Renderer failure produces an emit_rich_renderer_failed log line at ERROR."""
        import logging

        caplog.set_level(logging.ERROR, logger="cli.output")

        def renderer() -> None:
            raise RuntimeError("renderer blew up")

        emit({"k": "v"}, rich_renderer=renderer)

        matching = [
            record
            for record in caplog.records
            if "emit_rich_renderer_failed" in record.getMessage() and record.levelname == "ERROR"
        ]
        if not matching:
            observed = [(r.levelname, r.getMessage()) for r in caplog.records]
            raise AssertionError(f"Expected an ERROR-level emit_rich_renderer_failed log; got: {observed}")

    def test_renderer_exception_falls_back_to_console_print(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When renderer raises, console.print(payload) is invoked as fallback."""
        # Use a MagicMock console so we can assert call args without parsing Rich output.
        mock_console = MagicMock()
        payload = {"answer": 42}

        # monkeypatch.setitem cleanly restores prior state (including absence) via
        # pytest's finalizer — manual save/restore leaked when the key did not pre-exist.
        monkeypatch.setitem(state, "format", "rich")
        monkeypatch.setitem(state, "console", mock_console)

        def renderer() -> None:
            raise RuntimeError("renderer blew up")

        emit(payload, rich_renderer=renderer)

        mock_console.print.assert_called_once_with(payload)

    def test_successful_renderer_does_not_trigger_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When renderer succeeds, console.print(payload) is NOT called."""
        mock_console = MagicMock()

        monkeypatch.setitem(state, "format", "rich")
        monkeypatch.setitem(state, "console", mock_console)

        renderer_called: list[bool] = []

        def renderer() -> None:
            renderer_called.append(True)

        emit({"k": "v"}, rich_renderer=renderer)

        assert renderer_called == [True], "renderer should have been invoked"
        mock_console.print.assert_not_called()
