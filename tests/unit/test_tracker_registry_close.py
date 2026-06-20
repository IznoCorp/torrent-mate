"""Unit tests for TrackerRegistry.close() — tracker-wiring RP5a.

``close()`` peeks each client's NON-triggering ``_open_transport`` property
(NOT the login-triggering lazy ``_transport``), so teardown never fires a
bootstrap login.

Verifies:
- Empty registry closes as a no-op (no exception).
- close() calls ``close()`` on each client's materialized transport.
- A client with no ``_open_transport`` (peek → None) is skipped gracefully.
- A ``transport.close()`` that raises is swallowed (does not propagate).
- All transports are attempted even when one raises.
- A torr9-style client that has NOT logged in (``_open_transport`` is ``None``)
  is skipped WITHOUT ever accessing its login-triggering ``_transport`` —
  proving teardown peeks only and fires no spurious bootstrap login. The other
  plain-attribute clients are still closed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry


class _NotLoggedInClient:
    """torr9-style client that has NOT logged in yet.

    ``_open_transport`` is the non-triggering peek → ``None`` (no transport
    materialized). The login-triggering ``_transport`` property RAISES if the
    registry ever touches it — proving close() peeks only and never fires a
    spurious bootstrap login at teardown.
    """

    @property
    def _open_transport(self) -> object | None:
        return None

    @property
    def _transport(self) -> object:  # pragma: no cover — must never be accessed
        raise AssertionError("_transport (login-triggering) was accessed by close()")


def _make_registry(trackers: dict) -> TrackerRegistry:
    return TrackerRegistry(
        trackers=trackers,
        priority=list(trackers),
        ranking=RankingConfig(),
    )


def _stub_client(name: str) -> MagicMock:
    """Return a mock client whose _open_transport.close() is trackable.

    Both ``_transport`` and ``_open_transport`` resolve to the same materialized
    mock (mirroring an api-key client where the peek just returns ``_transport``).
    """
    client = MagicMock()
    transport = MagicMock()
    transport.close = MagicMock()
    client._transport = transport
    client._open_transport = transport
    return client


class TestTrackerRegistryClose:
    """Unit tests for TrackerRegistry.close()."""

    def test_empty_registry_closes_cleanly(self) -> None:
        """No trackers → close() is a no-op, no exception raised."""
        registry = _make_registry({})
        registry.close()  # must not raise

    def test_close_calls_transport_close_on_each_client(self) -> None:
        """close() must call transport.close() for every client in the registry."""
        lacale = _stub_client("lacale")
        c411 = _stub_client("c411")
        registry = _make_registry({"lacale": lacale, "c411": c411})
        registry.close()
        lacale._open_transport.close.assert_called_once()
        c411._open_transport.close.assert_called_once()

    def test_client_without_transport_is_skipped(self) -> None:
        """A client with no _open_transport attribute must not raise.

        MagicMock(spec=[]) rejects attribute access to anything not in the
        empty spec, so getattr(client, "_open_transport", None) returns None —
        matching the registry's getattr sentinel pattern.
        """
        client = MagicMock(spec=[])
        registry = _make_registry({"ghost": client})
        registry.close()  # must not raise

    def test_transport_close_exception_is_swallowed(self) -> None:
        """If transport.close() raises, the exception must not propagate."""
        client = _stub_client("lacale")
        client._open_transport.close.side_effect = RuntimeError("session already closed")
        registry = _make_registry({"lacale": client})
        registry.close()  # must not raise

    def test_all_transports_closed_even_when_one_raises(self) -> None:
        """A failing close on client A must not prevent client B from being closed."""
        lacale = _stub_client("lacale")
        lacale._open_transport.close.side_effect = RuntimeError("boom")
        c411 = _stub_client("c411")
        registry = _make_registry({"lacale": lacale, "c411": c411})
        registry.close()
        # c411 must still have been closed despite lacale raising:
        c411._open_transport.close.assert_called_once()

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
        transport = MagicMock()
        transport.close = 5  # present but NOT callable
        client._transport = transport
        client._open_transport = transport
        registry = _make_registry({"lacale": client})

        with patch("personalscraper.api.tracker._registry.log") as mock_log:
            registry.close()  # must not raise

        logged = [c.args[0] for c in mock_log.debug.call_args_list if c.args]
        assert "tracker_transport_close_failed" not in logged

    def test_not_logged_in_client_is_skipped_without_triggering_login(self) -> None:
        """A torr9-style not-logged-in client is skipped without accessing its _transport.

        torr9's ``_transport`` is a lazy PROPERTY that triggers a bootstrap login on
        first access. A read-only command can tear the registry down before torr9
        ever logged in. close() peeks ``_open_transport`` (→ None here), so the
        login-triggering ``_transport`` is NEVER accessed (it raises if touched) —
        proving NO spurious bootstrap login is fired at teardown. The other
        plain-attribute clients are STILL closed.
        """
        lazy = _NotLoggedInClient()
        healthy = _stub_client("lacale")
        registry = _make_registry({"torr9": lazy, "lacale": healthy})

        registry.close()  # must NOT raise and must NOT access torr9._transport

        # The healthy plain-attribute client was STILL closed:
        healthy._open_transport.close.assert_called_once()
