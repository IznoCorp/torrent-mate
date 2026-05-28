"""EventBus event dataclasses for the provider registry (DESIGN §7.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import AttemptOutcome, ProviderMatch


@dataclass(frozen=True)
class ProviderFallbackTriggered:
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


@dataclass(frozen=True)
class ProviderExhaustedEvent:
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


@dataclass(frozen=True)
class LockedCapabilityUnresolved:
    """Emitted when ``locked()`` cannot bind a provider via IDCrossRef.

    Attributes:
        capability: The locked capability being resolved (Protocol name).
        match: The ``ProviderMatch`` that could not be resolved.
        chain_tried: Names of providers tried for IDCrossRef translation.
    """

    capability: str
    match: ProviderMatch
    chain_tried: list[str]


@dataclass(frozen=True)
class RegistryFanOutCompleted:
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


@dataclass(frozen=True)
class RegistryBootValidated:
    """Emitted when boot completed successfully.

    Attributes:
        providers: Sorted list of registered provider names.
        capabilities: Map of capability name → list of provider names.
    """

    providers: list[str]
    capabilities: dict[str, list[str]]
