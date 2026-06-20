"""Unit tests for TrackerRegistry.transports() — the grab-seam transport map.

``transports()`` peeks each client's NON-triggering ``_open_transport`` property
(NOT the login-triggering lazy ``_transport``), so building the map never fires a
bootstrap login.

Verifies:
- A normal client's materialized ``_open_transport`` is included.
- A torr9-style client that has NOT logged in (``_open_transport`` is ``None``)
  is NOT included — AND its login-triggering ``_transport`` is NEVER accessed
  (peek only). A class whose ``_transport`` raises if touched proves the seam
  never triggers a login.
- A torr9-style client that HAS logged in (``_open_transport`` returns a real
  transport) IS included.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry


def _make_registry(trackers: dict) -> TrackerRegistry:
    return TrackerRegistry(
        trackers=trackers,
        priority=list(trackers),
        ranking=RankingConfig(),
    )


class _NotLoggedInClient:
    """torr9-style client that has NOT logged in yet.

    ``_open_transport`` is the non-triggering peek → ``None`` (no transport
    materialized). The login-triggering ``_transport`` property RAISES if the
    registry ever touches it — proving ``transports()`` peeks only and never
    fires a spurious bootstrap login.
    """

    @property
    def _open_transport(self) -> object | None:
        return None

    @property
    def _transport(self) -> object:  # pragma: no cover — must never be accessed
        raise AssertionError("_transport (login-triggering) was accessed by transports()")


class _LoggedInClient:
    """torr9-style client that HAS logged in — ``_open_transport`` returns the cached transport."""

    def __init__(self) -> None:
        self._materialized = MagicMock()

    @property
    def _open_transport(self) -> object:
        return self._materialized


class _PlainTransportClient:
    """lacale/c411-style client: ``_open_transport`` returns the always-materialized ``_transport``."""

    def __init__(self) -> None:
        self._transport = MagicMock()

    @property
    def _open_transport(self) -> object:
        return self._transport


class TestTrackerRegistryTransports:
    """Unit tests for TrackerRegistry.transports() peek behavior."""

    def test_plain_client_transport_included(self) -> None:
        """A plain api-key client (always materialized) is present in the map."""
        client = _PlainTransportClient()
        registry = _make_registry({"lacale": client})

        result = registry.transports()

        assert result == {"lacale": client._transport}

    def test_not_logged_in_client_is_omitted_without_triggering_login(self) -> None:
        """A torr9-style not-logged-in client is omitted AND its _transport is never accessed.

        ``_open_transport`` returns None, so the client is absent from the map.
        Its login-triggering ``_transport`` property would raise if touched —
        the test passing proves the seam peeks only (no spurious login fired).
        """
        registry = _make_registry({"torr9": _NotLoggedInClient()})

        result = registry.transports()  # must not raise (no _transport access)

        assert result == {}

    def test_logged_in_client_transport_included(self) -> None:
        """A torr9-style client that already logged in exposes its materialized transport."""
        client = _LoggedInClient()
        registry = _make_registry({"torr9": client})

        result = registry.transports()

        assert result == {"torr9": client._materialized}

    def test_not_logged_in_client_does_not_drop_a_logged_in_sibling(self) -> None:
        """A not-logged-in tracker must not stop a logged-in sibling from being included."""
        healthy = _PlainTransportClient()
        registry = _make_registry({"torr9": _NotLoggedInClient(), "lacale": healthy})

        result = registry.transports()

        assert "torr9" not in result
        assert result["lacale"] is healthy._transport
