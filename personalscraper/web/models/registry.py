"""Pydantic models for the registry status API (reg-health feature).

See docs/features/reg-health/DESIGN.md §3.3 for the route contracts these
models serve.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProviderStatusItem(BaseModel):
    """Health snapshot for a single provider.

    Returned as part of the :class:`RegistryStatusResponse` list.  Fields that
    have never been observed (no event stream history) are ``None`` and
    ``live`` is ``False``.

    Attributes:
        provider_name: The provider identifier (e.g. ``"tmdb"``, ``"tvdb"``).
        circuit_state: Last-known circuit-breaker state —
            ``"closed"``, ``"open"``, or ``"half_open"``.
        failure_count_recent: Consecutive failures that triggered the
            current circuit state.  Zero when the circuit is closed.
        last_success_at: Epoch seconds of the last successful call, or
            ``None`` when no success has been observed.
        last_failure_at: Epoch seconds of the last failed call, or
            ``None`` when no failure has been observed.
        last_latency_ms: Wall-clock latency in milliseconds of the last
            call, or ``None`` when no call has been observed.
        live: ``True`` when the projection has observed at least one event
            for this provider (so the state reflects real history rather
            than an optimistic baseline).
    """

    provider_name: str
    circuit_state: Literal["closed", "open", "half_open"]
    failure_count_recent: int
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_latency_ms: float | None = None
    live: bool


class RegistryStatusResponse(BaseModel):
    """Response for ``GET /api/registry/status``.

    Attributes:
        providers: One :class:`ProviderStatusItem` per configured or
            observed provider, sorted by name for stable output.
    """

    providers: list[ProviderStatusItem]
