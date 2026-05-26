"""EventBus event dataclasses for the provider registry (DESIGN §7.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class ProviderFallbackTriggered:
    """Emitted when a chain moves from one provider to the next.

    Attributes:
        capability: The capability being chained (Protocol name).
        from_provider: Name of the provider that failed.
        to_provider: Name of the provider being tried next.
        reason: Why the fallback occurred (circuit_open, network, empty_result).
        exc_type: Exception type name if a network error caused the fallback.
        item: Dict with item context (title, year, media_type, etc.).
    """

    capability: str
    from_provider: str
    to_provider: str
    reason: Literal["circuit_open", "network", "empty_result"]
    exc_type: str | None
    item: dict[str, Any]


@dataclass(frozen=True)
class ProviderExhaustedEvent:
    """Emitted when all providers in a chain failed for an item.

    Attributes:
        capability: The capability being chained (Protocol name).
        attempted: List of ``AttemptOutcome`` for each tried provider.
        item: Dict with item context (title, year, media_type, etc.).
    """

    capability: str
    attempted: list  # type: ignore[type-arg]  # list[AttemptOutcome] — avoid circular import at runtime
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
    match: object  # ProviderMatch — avoid circular import at runtime
    chain_tried: list[str]


@dataclass(frozen=True)
class RegistryFanOutCompleted:
    """Always emitted after ``fan_out`` returns (even on full success).

    Attributes:
        capability: The capability that was fanned out (Protocol name).
        attempted: List of ``AttemptOutcome`` for each tried provider.
        succeeded: Number of providers that returned a non-empty result.
    """

    capability: str
    attempted: list  # type: ignore[type-arg]  # list[AttemptOutcome] — avoid circular import at runtime
    succeeded: int


@dataclass(frozen=True)
class RegistryBootValidated:
    """Emitted when boot completed successfully.

    Attributes:
        providers: Sorted list of registered provider names.
        capabilities: Map of capability name → list of provider names.
    """

    providers: list[str]
    capabilities: dict[str, list[str]]
