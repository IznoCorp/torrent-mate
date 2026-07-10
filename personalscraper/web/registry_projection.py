"""Server-side health projection for the provider registry (S6 reg-health).

An in-memory :class:`RegistryHealthProjection` fed by the Redis event stream
(live relay + boot warm-up replay).  It accumulates the last-known per-provider
circuit state, failure count, latency, and success/failure timestamps so the
REST ``GET /api/registry/status`` endpoint can serve meaningful health data
without reaching into the pipeline process's in-memory registry
(DESIGN §3.1b / §3.4).

Thread-safety: the projection is mutated by a single asyncio relay task and
read by request threads via :meth:`snapshot`, which returns an independent
deep copy.  No lock is needed under that single-writer pattern.
"""

from __future__ import annotations

import copy
import time
from typing import Any

from personalscraper.logger import get_logger

logger = get_logger(__name__)


class RegistryHealthProjection:
    """In-memory per-provider health state derived from the event stream.

    Accumulates :class:`CircuitBreakerOpened` / ``Closed`` / ``HalfOpened``
    and :class:`ProviderCallCompleted` events into a dict keyed by provider
    name.  The reducer is :meth:`apply`; consumers read via :meth:`snapshot`.

    Attributes:
        _providers: Internal ``{provider_name: {circuit_state, …}}`` dict.
    """

    def __init__(self) -> None:
        """Initialize an empty projection."""
        self._providers: dict[str, dict[str, Any]] = {}

    # -- Reducer ---------------------------------------------------------------

    def apply(self, event_type: str, data: dict[str, Any]) -> None:
        """Reduce a single event into the projection.

        Unknown event types are silently ignored so the projection is
        forward-compatible with new events added to the stream.

        Args:
            event_type: Event class name (e.g. ``"CircuitBreakerOpened"``).
            data: The event's ``data`` dict from the WS message envelope.
        """
        now = time.time()

        if event_type == "CircuitBreakerOpened":
            provider = data.get("breaker", "")
            entry = self._ensure_provider(provider)
            entry["circuit_state"] = "open"
            entry["failure_count_recent"] = data.get("failure_count", 0)
            entry["last_failure_at"] = now

        elif event_type == "CircuitBreakerClosed":
            provider = data.get("breaker", "")
            entry = self._ensure_provider(provider)
            entry["circuit_state"] = "closed"
            entry["failure_count_recent"] = 0
            entry["last_success_at"] = now

        elif event_type == "CircuitBreakerHalfOpened":
            provider = data.get("breaker", "")
            entry = self._ensure_provider(provider)
            entry["circuit_state"] = "half_open"

        elif event_type == "ProviderCallCompleted":
            provider = data.get("provider", "")
            entry = self._ensure_provider(provider)
            entry["last_latency_ms"] = data.get("latency_ms")
            if data.get("ok"):
                entry["last_success_at"] = now
            else:
                entry["last_failure_at"] = now

        # Unknown event types are intentionally ignored — the projection is
        # forward-compatible (new events added to the stream don't break it).

    # -- Read ------------------------------------------------------------------

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return an independent deep copy of the current projection.

        Callers (REST routes on the request thread) can mutate the returned
        dict freely without affecting the projection.

        Returns:
            ``{provider_name: {circuit_state, failure_count_recent,
            last_success_at, last_failure_at, last_latency_ms}}``.
        """
        return copy.deepcopy(self._providers)

    # -- Internal --------------------------------------------------------------

    def _ensure_provider(self, name: str) -> dict[str, Any]:
        """Return (and create if absent) the entry dict for *name*.

        New entries start with a neutral baseline: ``circuit_state="closed"``,
        zero ``failure_count_recent``, and all optional fields ``None``.

        Args:
            name: Provider name key.

        Returns:
            The existing or freshly-initialised entry dict.
        """
        if name not in self._providers:
            self._providers[name] = {
                "circuit_state": "closed",
                "failure_count_recent": 0,
                "last_success_at": None,
                "last_failure_at": None,
                "last_latency_ms": None,
            }
        return self._providers[name]
