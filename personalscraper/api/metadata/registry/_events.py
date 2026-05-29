"""EventBus event dataclasses for the provider registry (DESIGN §7.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

# ``AttemptOutcome`` / ``ProviderMatch`` are imported at RUNTIME (not under
# ``TYPE_CHECKING``) from the leaf ``_types`` module so that
# ``typing.get_type_hints`` can resolve the string annotations on
# ``ProviderExhaustedEvent`` / ``RegistryFanOutCompleted`` / ``LockedCapabilityUnresolved``
# during ``event_from_envelope`` round-trip. ``_types`` is a leaf (it does not
# import the registry package ``__init__``), so this import does NOT cycle even
# though ``__init__`` imports this module (arch-cleanup-2 Phase 5).
from personalscraper.api.metadata.registry._types import AttemptOutcome, ProviderMatch
from personalscraper.core.event_bus import Event


@dataclass(frozen=True, kw_only=True)
class ProviderFallbackTriggered(Event):
    """Emitted when a chain moves from one provider to the next.

    Attributes:
        capability: The capability being chained (Protocol name).
        from_provider: Name of the provider that failed.
        to_provider: Name of the provider being tried next.
        reason: Why the fallback occurred — closed enum:
            ``circuit_open`` (provider tripped),
            ``network`` (ApiError / requests / OSError),
            ``empty_result`` (provider returned None / empty payload),
            ``other`` (unclassified Exception — DESIGN §6.2 fallback on
            unknown failure, Phase 21).
        exc_type: Exception type name if an error caused the fallback
            (populated for ``network`` and ``other`` reasons).
        item: Dict with item context (title, year, media_type, etc.).
    """

    capability: str
    from_provider: str
    to_provider: str
    reason: Literal["circuit_open", "network", "empty_result", "other"]
    exc_type: str | None
    item: dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class ProviderExhaustedEvent(Event):
    """Emitted when all providers in a chain failed for an item.

    Attributes:
        capability: The capability being chained (Protocol name).
        attempted: Per-provider outcomes for the exhausted chain, stored
            as a ``tuple`` so the frozen-dataclass invariant is honoured
            (PR review cycle 4, finding I5).
        item: Dict with item context (title, year, media_type, etc.).
    """

    capability: str
    attempted: tuple[AttemptOutcome, ...]
    item: dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class LockedCapabilityUnresolved(Event):
    """Emitted when ``locked()`` cannot bind a provider via IDCrossRef.

    Attributes:
        capability: The locked capability being resolved (Protocol name).
        match: The ``ProviderMatch`` that could not be resolved.
        chain_tried: Tuple of providers tried for IDCrossRef translation.
    """

    capability: str
    match: ProviderMatch
    chain_tried: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class RegistryFanOutCompleted(Event):
    """Always emitted after ``fan_out`` returns (even on full success).

    Attributes:
        capability: The capability that was fanned out (Protocol name).
        attempted: Per-provider outcomes for the fan-out, stored as a
            ``tuple`` so the frozen-dataclass invariant is honoured
            (PR review cycle 4, finding I5).
        eligible: Number of providers that survived eligibility filtering
            (circuit CLOSED or HALF_OPEN), before the caller fans out.
    """

    capability: str
    attempted: tuple[AttemptOutcome, ...]
    eligible: int


@dataclass(frozen=True, kw_only=True)
class RegistryBootValidated(Event):
    """Emitted when boot completed successfully.

    Attributes:
        providers: Sorted tuple of registered provider names.
        capabilities: Map of capability name → tuple of provider names.
    """

    providers: tuple[str, ...]
    capabilities: dict[str, tuple[str, ...]]
