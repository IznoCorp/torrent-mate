"""Unit tests for TrackerRegistry.transports() — the grab-seam transport map.

Verifies:
- A normal client's ``_transport`` is included.
- A client whose lazy ``_transport`` getter RAISES (torr9's bootstrap-login
  property) is skipped — the exception is logged, never propagated — so one
  tracker's auth failure cannot break the grab seam for the others.
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


class _RaisingTransportClient:
    """Client whose ``_transport`` property raises on access (lazy login fails).

    Mirrors torr9's lazy ``_transport`` property, which triggers a bootstrap
    login on first access — that login can fail (bad creds / outage).
    """

    @property
    def _transport(self) -> object:
        raise RuntimeError("bootstrap login failed")


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
        """The skipped tracker emits a tracker_transport_unavailable warning."""
        registry = _make_registry({"torr9": _RaisingTransportClient()})

        with patch("personalscraper.api.tracker._registry.log") as mock_log:
            registry.transports()

        warn_events = [c.args[0] for c in mock_log.warning.call_args_list if c.args]
        assert "tracker_transport_unavailable" in warn_events

    def test_healthy_client_survives_a_raising_sibling(self) -> None:
        """A raising tracker must not stop a healthy sibling from being included."""
        healthy = _NormalTransportClient()
        registry = _make_registry({"torr9": _RaisingTransportClient(), "lacale": healthy})

        result = registry.transports()

        assert "torr9" not in result
        assert result["lacale"] is healthy._transport
