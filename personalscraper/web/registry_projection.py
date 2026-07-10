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
from datetime import datetime
from typing import Any

from personalscraper.logger import get_logger

logger = get_logger(__name__)


def _parse_event_epoch(raw: Any) -> float:
    """Parse an event's ``timestamp`` into a Unix-epoch float.

    Every :class:`~personalscraper.core.event_bus.Event` carries a UTC-aware
    ``timestamp`` that serializes into the WS ``data`` dict as an ISO-8601
    string (e.g. ``"2026-07-10T14:07:12.177891+00:00"``).  Using the event's
    own time — not the web process's apply time — keeps ``last_success_at`` /
    ``last_failure_at`` honest across the boot warm-up replay, and lets the
    reducer order events (see :meth:`RegistryHealthProjection.apply`).

    Args:
        raw: The ``data["timestamp"]`` value (ISO string, or ``None`` /
            malformed on a hand-built payload).

    Returns:
        Epoch seconds parsed from *raw*, or ``time.time()`` when *raw* is
        absent or unparseable (defensive — real events always carry it).
    """
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw).timestamp()
        except ValueError:
            return time.time()
    return time.time()


class RegistryHealthProjection:
    """In-memory per-provider health state derived from the event stream.

    Accumulates :class:`CircuitBreakerOpened` / ``Closed`` / ``HalfOpened``
    and :class:`ProviderCallCompleted` events into a dict keyed by provider
    name.  The reducer is :meth:`apply`; consumers read via :meth:`snapshot`.

    Events are applied in **event-timestamp order** per provider: an event
    older than the newest one already applied for that provider is skipped, so
    the boot warm-up replay can never overwrite a fresher live event with stale
    state (the warm-up-vs-relay race).

    Attributes:
        _providers: Internal ``{provider_name: {circuit_state, …}}`` dict.
        _last_event_ts: Newest event epoch applied per provider (ordering guard).
    """

    def __init__(self) -> None:
        """Initialize an empty projection."""
        self._providers: dict[str, dict[str, Any]] = {}
        self._last_event_ts: dict[str, float] = {}

    # -- Reducer ---------------------------------------------------------------

    def apply(self, event_type: str, data: dict[str, Any]) -> None:
        """Reduce a single event into the projection, in event-time order.

        The provider key is ``data["breaker"]`` for ``CircuitBreaker*`` events
        and ``data["provider"]`` for ``ProviderCallCompleted``.  An event whose
        ``timestamp`` predates the newest one already applied for that provider
        is dropped (ordering guard).  Timestamps are stamped from the *event's*
        time, not the web process's apply time.  Unknown event types are
        silently ignored (forward-compatible).

        Args:
            event_type: Event class name (e.g. ``"CircuitBreakerOpened"``).
            data: The event's ``data`` dict from the WS message envelope.
        """
        if event_type.startswith("CircuitBreaker"):
            provider = data.get("breaker") or ""
        elif event_type == "ProviderCallCompleted":
            provider = data.get("provider") or ""
        else:
            return  # unknown / non-health event — ignore
        if not provider:
            return

        event_ts = _parse_event_epoch(data.get("timestamp"))
        # Ordering guard: never let an older (e.g. replayed) event overwrite a
        # newer one already applied for this provider.
        if event_ts < self._last_event_ts.get(provider, 0.0):
            return

        entry = self._ensure_provider(provider)

        if event_type == "CircuitBreakerOpened":
            entry["circuit_state"] = "open"
            entry["failure_count_recent"] = data.get("failure_count", 0)
            entry["last_failure_at"] = event_ts
        elif event_type == "CircuitBreakerClosed":
            entry["circuit_state"] = "closed"
            entry["failure_count_recent"] = 0
            entry["last_success_at"] = event_ts
        elif event_type == "CircuitBreakerHalfOpened":
            entry["circuit_state"] = "half_open"
        elif event_type == "ProviderCallCompleted":
            entry["last_latency_ms"] = data.get("latency_ms")
            if data.get("ok"):
                entry["last_success_at"] = event_ts
            else:
                entry["last_failure_at"] = event_ts

        self._last_event_ts[provider] = event_ts

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
