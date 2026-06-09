"""Unit tests for TrackerRegistry.close() — tracker-wiring RP5a.

Verifies:
- Empty registry closes as a no-op (no exception).
- close() calls _transport.close() on each client.
- A client with no _transport attribute is skipped gracefully.
- A _transport.close() that raises is swallowed (does not propagate).
- All transports are attempted even when one raises.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry


def _make_registry(trackers: dict) -> TrackerRegistry:
    return TrackerRegistry(
        trackers=trackers,
        priority=list(trackers),
        ranking=RankingConfig(),
    )


def _stub_client(name: str) -> MagicMock:
    """Return a mock client whose _transport.close() is trackable."""
    client = MagicMock()
    client._transport = MagicMock()
    client._transport.close = MagicMock()
    return client


class TestTrackerRegistryClose:
    """Unit tests for TrackerRegistry.close()."""

    def test_empty_registry_closes_cleanly(self) -> None:
        """No trackers → close() is a no-op, no exception raised."""
        registry = _make_registry({})
        registry.close()  # must not raise

    def test_close_calls_transport_close_on_each_client(self) -> None:
        """close() must call _transport.close() for every client in the registry."""
        lacale = _stub_client("lacale")
        c411 = _stub_client("c411")
        registry = _make_registry({"lacale": lacale, "c411": c411})
        registry.close()
        lacale._transport.close.assert_called_once()
        c411._transport.close.assert_called_once()

    def test_client_without_transport_is_skipped(self) -> None:
        """A client with no _transport attribute must not raise.

        MagicMock(spec=[]) rejects attribute access to anything not in the
        empty spec, so getattr(client, "_transport", None) returns None —
        matching the Factory's getattr sentinel pattern.
        """
        client = MagicMock(spec=[])
        registry = _make_registry({"ghost": client})
        registry.close()  # must not raise

    def test_transport_close_exception_is_swallowed(self) -> None:
        """If _transport.close() raises, the exception must not propagate."""
        client = _stub_client("lacale")
        client._transport.close.side_effect = RuntimeError("session already closed")
        registry = _make_registry({"lacale": client})
        registry.close()  # must not raise

    def test_all_transports_closed_even_when_one_raises(self) -> None:
        """A failing close on client A must not prevent client B from being closed."""
        lacale = _stub_client("lacale")
        lacale._transport.close.side_effect = RuntimeError("boom")
        c411 = _stub_client("c411")
        registry = _make_registry({"lacale": lacale, "c411": c411})
        registry.close()
        # c411 must still have been closed despite lacale raising:
        c411._transport.close.assert_called_once()

    def test_existing_dict_ctor_still_works(self) -> None:
        """Regression guard: __init__ signature unchanged — no keyword-only drift."""
        from unittest.mock import MagicMock as MM

        stub = MM()
        stub.search = MM(return_value=[])
        r = TrackerRegistry(
            trackers={"lacale": stub},
            priority=["lacale"],
            ranking=RankingConfig(),
            priority_by_media_type={"movie": ["lacale"]},
        )
        assert r._priority == ["lacale"]

    def test_non_callable_close_attr_is_skipped(self) -> None:
        """A non-callable `close` attr is skipped by the callable() guard WITHOUT entering try/except.

        Isolates the guard (not just "close() doesn't raise"): with the guard, the non-callable
        close is skipped silently — no `tracker_transport_close_failed` debug log. Without the
        guard, `5()` raises a TypeError that the broad except catches AND logs, so asserting the
        failure log is absent pins the guard specifically.
        """
        client = MagicMock()
        client._transport = MagicMock()
        client._transport.close = 5  # present but NOT callable
        registry = _make_registry({"lacale": client})

        with patch("personalscraper.api.tracker._registry.log") as mock_log:
            registry.close()  # must not raise

        logged = [c.args[0] for c in mock_log.debug.call_args_list if c.args]
        assert "tracker_transport_close_failed" not in logged
