"""Sub-phase 2.5 invariants for ``personalscraper library-index`` CLI entry.

Verifies that the launchd command boundary in
``personalscraper.commands.library.scan`` builds an :class:`AppContext`
via ``_build_app_context``, binds ``current_correlation_id`` for the
duration of the scan, and threads the :class:`EventBus` (NOT the full
``AppContext``) to ``library_index_command``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus, current_correlation_id

runner = CliRunner()


def _patches():
    """Build a capturing wrapper around the real ``_build_app_context``.

    Returns:
        Tuple of (wrapped callable suitable for ``patch(..., side_effect=...)``,
        list that accumulates every constructed :class:`AppContext`).
    """
    real_app: list[AppContext] = []

    # Bind the real factory once OUTSIDE the wrapper. Using
    # ``from personalscraper.cli_helpers import _build_app_context`` inside
    # ``_capturing_build`` would resolve to the patched mock and recurse
    # infinitely, because the ``library_index`` command body re-imports the
    # name on every call.
    def _capturing_build(config, settings):  # type: ignore[no-untyped-def]
        ctx = AppContext(config=config, settings=settings, event_bus=EventBus())
        real_app.append(ctx)
        return ctx

    return _capturing_build, real_app


class TestLibraryIndexCommandAppContext:
    """The launchd ``library-index`` command builds an AppContext at its boundary."""

    def test_library_index_command_builds_app_context(self) -> None:
        """``_build_app_context`` is invoked exactly once per ``library-index`` run."""
        capturing, captured = _patches()
        with (
            patch("personalscraper.cli_helpers._build_app_context", side_effect=capturing),
            patch(
                "personalscraper.indexer.cli.library_index_command",
                return_value=0,
            ),
        ):
            result = runner.invoke(app, ["library-index", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert len(captured) == 1
        assert isinstance(captured[0], AppContext)
        assert isinstance(captured[0].event_bus, EventBus)

    def test_library_index_command_binds_correlation_id(self) -> None:
        """``current_correlation_id`` is set during the scan and reset on exit."""
        observed: list[str | None] = []

        def _spy_orchestrator(**kwargs) -> int:  # type: ignore[no-untyped-def]  # noqa: ANN003
            observed.append(current_correlation_id.get())
            return 0

        with patch(
            "personalscraper.indexer.cli.library_index_command",
            side_effect=_spy_orchestrator,
        ):
            assert current_correlation_id.get() is None
            result = runner.invoke(app, ["library-index", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert len(observed) == 1
        assert observed[0] is not None
        # 36-char UUID v4 string (8-4-4-4-12 hex).
        assert len(observed[0]) == 36
        # Reset to ``None`` after the command returns.
        assert current_correlation_id.get() is None

    def test_library_index_command_passes_event_bus_to_orchestrator(self) -> None:
        """``library_index_command`` receives ``event_bus`` (NOT the full AppContext)."""
        captured_kwargs: dict = {}

        def _spy(**kwargs) -> int:  # type: ignore[no-untyped-def]  # noqa: ANN003
            captured_kwargs.update(kwargs)
            return 0

        with patch(
            "personalscraper.indexer.cli.library_index_command",
            side_effect=_spy,
        ):
            result = runner.invoke(app, ["library-index", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "event_bus" in captured_kwargs
        assert isinstance(captured_kwargs["event_bus"], EventBus)
        # The orchestrator receives ONLY the bus, NOT the AppContext.
        assert not any(isinstance(v, AppContext) for v in captured_kwargs.values())


# A MagicMock-friendly assertion guard kept for completeness — see DESIGN
# §Testing strategy: cross-boundary contracts always assert on the exact
# type the receiver is expected to handle (``EventBus`` vs ``AppContext``).
_ = MagicMock
