"""Unit tests for TrackerRegistry.transports() — the grab-seam transport map.

Verifies:
- A normal client's ``_transport`` is included.
- A client whose lazy ``_transport`` getter raises an OPERATIONAL exception
  (torr9's bootstrap-login property: bad creds / outage / tripped circuit) is
  skipped — the exception is logged, never propagated — so one tracker's auth
  failure cannot break the grab seam for the others.
- A client whose ``_transport`` getter raises an UNEXPECTED exception (a real
  programming bug) PROPAGATES — the narrowed except must not mask code bugs.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry


def _make_registry(trackers: dict) -> TrackerRegistry:
    return TrackerRegistry(
        trackers=trackers,
        priority=list(trackers),
        ranking=RankingConfig(),
    )


class _RaisingTransportClient:
    """Client whose ``_transport`` property raises an OPERATIONAL error on access.

    Mirrors torr9's lazy ``_transport`` property, which triggers a bootstrap
    login on first access — that login can fail operationally (bad creds /
    outage). ``ApiError`` is one of the narrow exceptions ``transports()``
    swallows; a truly-unexpected exception is exercised separately by
    :class:`_BuggyTransportClient`.
    """

    @property
    def _transport(self) -> object:
        raise ApiError(provider="torr9", http_status=401, message="bootstrap login failed")


class _BuggyTransportClient:
    """Client whose ``_transport`` getter raises an UNEXPECTED programming bug.

    ``RuntimeError`` is NOT in the narrow except-tuple, so ``transports()`` must
    let it propagate rather than mask it as ``tracker_transport_unavailable``.
    """

    @property
    def _transport(self) -> object:
        raise RuntimeError("genuine bug in the _transport getter")


class _NormalTransportClient:
    """Client carrying a plain (already-built) ``_transport`` attribute."""

    def __init__(self) -> None:
        self._transport = MagicMock()


class TestTrackerRegistryTransports:
    """Unit tests for TrackerRegistry.transports() resilience."""

    def test_normal_client_transport_included(self) -> None:
        """A client with a plain _transport is present in the map."""
        client = _NormalTransportClient()
        registry = _make_registry({"lacale": client})

        result = registry.transports()

        assert result == {"lacale": client._transport}

    def test_raising_transport_is_skipped_not_propagated(self) -> None:
        """A client whose _transport getter raises is skipped, not propagated."""
        registry = _make_registry({"torr9": _RaisingTransportClient()})

        result = registry.transports()  # must not raise

        assert result == {}

    def test_raising_transport_logs_warning(self) -> None:
        """The skipped tracker emits a tracker_transport_unavailable warning with error_type."""
        registry = _make_registry({"torr9": _RaisingTransportClient()})

        with patch("personalscraper.api.tracker._registry.log") as mock_log:
            registry.transports()

        warn_events = [c.args[0] for c in mock_log.warning.call_args_list if c.args]
        assert "tracker_transport_unavailable" in warn_events
        # The narrowed catch records the concrete exception class for diagnosis.
        unavailable_calls = [
            c for c in mock_log.warning.call_args_list if c.args and c.args[0] == "tracker_transport_unavailable"
        ]
        assert unavailable_calls[0].kwargs["error_type"] == "ApiError"

    def test_healthy_client_survives_a_raising_sibling(self) -> None:
        """A raising tracker must not stop a healthy sibling from being included."""
        healthy = _NormalTransportClient()
        registry = _make_registry({"torr9": _RaisingTransportClient(), "lacale": healthy})

        result = registry.transports()

        assert "torr9" not in result
        assert result["lacale"] is healthy._transport

    def test_unexpected_transport_exception_propagates(self) -> None:
        """An UNEXPECTED exception from the _transport getter propagates (not swallowed).

        Regression for the over-broad ``except Exception`` (BLE001): a genuine
        programming bug in a ``_transport`` getter used to be masked as
        ``tracker_transport_unavailable``, indistinguishable from a real lazy-login
        outage. After narrowing to the operational exception set, an unexpected
        ``RuntimeError`` must surface so the bug is not silently hidden.
        """
        registry = _make_registry({"torr9": _BuggyTransportClient()})

        with pytest.raises(RuntimeError, match="genuine bug"):
            registry.transports()
