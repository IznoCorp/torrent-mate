"""Provider registry for capability-keyed, circuit-aware metadata provider dispatch.

The registry owns provider instantiation and exposes ordered, capability-keyed
access to providers. It replaces the hardcoded ``self._tmdb`` / ``self._tvdb``
pattern across all consumers (DESIGN §1.1, §5.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Literal,
    NewType,
    Protocol,
    TypeVar,
    overload,
)

from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._contracts import (
    ArtworkProvider,
    EpisodeFetcher,
    IDCrossRef,
    IDValidator,
    KeywordProvider,
    MovieDetailsProvider,
    RatingProvider,
    RecommendationProvider,
    Searchable,
    TvDetailsProvider,
    VideoProvider,
)

if TYPE_CHECKING:
    from personalscraper.api.transport._policy import CircuitPolicy
    from personalscraper.conf.models.providers import ProvidersConfig
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus

# ---------------------------------------------------------------------------
# Module-private sentinel — never exported
# ---------------------------------------------------------------------------

_INTERNAL_TOKEN = object()

# ---------------------------------------------------------------------------
# ProviderName alias
# ---------------------------------------------------------------------------

ProviderName = NewType("ProviderName", str)

# ---------------------------------------------------------------------------
# Named Protocol
# ---------------------------------------------------------------------------


class Named(Protocol):
    """Every concrete provider exposes a stable string identifier.

    ``name`` matches the config key (e.g. ``"tmdb"``, ``"tvdb"``) and is used
    in diagnostic events, logs, and the introspection API.
    """

    name: ClassVar[str]


# ---------------------------------------------------------------------------
# Mode enum
# ---------------------------------------------------------------------------


class Mode(str, Enum):
    """Capability dispatch mode. Source of truth: ``_semantics.py``."""

    CHAIN = "chain"
    FAN_OUT = "fan_out"
    LOCKED = "locked"
    DIRECT = "direct"


# ---------------------------------------------------------------------------
# Capability unions (mirrors §4 — source of truth: _semantics.py)
# ---------------------------------------------------------------------------

ChainCapability = Searchable | MovieDetailsProvider | TvDetailsProvider | EpisodeFetcher
FanOutCapability = RatingProvider
LockedCapability = ArtworkProvider | KeywordProvider | VideoProvider | RecommendationProvider
DirectCapability = IDValidator | IDCrossRef

# ---------------------------------------------------------------------------
# Frozen dataclasses (DESIGN §5.3)
# ---------------------------------------------------------------------------

C = TypeVar("C")


@dataclass(frozen=True)
class ProviderMatch:
    """Identifies a media item by (provider, id) pair.

    Invariants enforced in ``__post_init__``: ``provider`` and ``id`` must be
    non-empty. The registry validates that ``provider`` corresponds to a
    configured provider at every call site that accepts a ``ProviderMatch``.
    """

    provider: ProviderName
    id: str
    media_type: MediaType

    def __post_init__(self) -> None:
        """Validate non-empty provider and id after frozen dataclass init."""
        if not self.provider:
            raise ValueError("ProviderMatch.provider must be non-empty")
        if not self.id:
            raise ValueError("ProviderMatch.id must be non-empty")


@dataclass(frozen=True)
class AttemptOutcome:
    """One row of ``ProviderExhausted.attempted`` — used for diagnostics and metrics.

    ``reason`` is a closed ``Literal`` so downstream consumers (ScrapeResult,
    metrics, EventBus event payloads) can dispatch on a stable enum, not
    free-form strings.
    """

    provider: ProviderName
    reason: Literal["circuit_open", "network", "empty_result", "other"]
    detail: str | None = None


@dataclass(frozen=True)
class ProviderStatus:
    """Per-provider runtime status snapshot."""

    name: ProviderName
    circuit_state: Literal["CLOSED", "OPEN", "HALF_OPEN"]
    failure_count_recent: int
    last_success_at: datetime | None
    last_failure_at: datetime | None

    def __post_init__(self) -> None:
        """Validate failure_count_recent >= 0 after frozen dataclass init."""
        if self.failure_count_recent < 0:
            raise ValueError("ProviderStatus.failure_count_recent must be ≥ 0")


@dataclass(frozen=True)
class ConfigIssue:
    """One structured row inside ``RegistryConfigError`` (see §7.1).

    Carries a stable ``code`` so tests can assert on a closed set of issue codes
    rather than substring-matching the human message.
    """

    code: Literal[
        "missing_credentials",
        "protocol_mismatch",
        "unknown_provider",
        "empty_chain_section",
        "locked_capability_orphan",
        "idcrossref_cycle",
    ]
    section: str
    provider: ProviderName | None
    message: str


@dataclass(frozen=True)
class LockedProvider(Generic[C]):
    """Provider bound to a specific id with full provenance.

    Construction is package-private: only ``_make_locked()`` builds instances.
    Calling ``LockedProvider(...)`` directly raises ``TypeError``.
    """

    provider: C
    bound_id: str
    source_match: ProviderMatch
    translated_via: str | None
    _token: object = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate sentinel token to block direct construction."""
        if self._token is not _INTERNAL_TOKEN:
            raise TypeError("LockedProvider can only be constructed via the registry's internal _make_locked() helper.")


@dataclass(frozen=True)
class FanOutResult(Generic[C]):
    """Result of a ``fan_out`` call — values + per-provider provenance.

    Empty ``values`` is not an error; caller may inspect ``attempted`` to
    distinguish "0 providers eligible" from "N tried, none returned data".
    """

    values: list[C]
    attempted: list[AttemptOutcome]


# ---------------------------------------------------------------------------
# Package-private LockedProvider constructor
# ---------------------------------------------------------------------------


def _make_locked(
    *,
    provider: C,
    bound_id: str,
    source_match: ProviderMatch,
    translated_via: str | None,
) -> LockedProvider[C]:
    """Package-private constructor for ``LockedProvider``.

    Only called by ``ProviderRegistry.locked()``.
    """
    return LockedProvider(
        provider=provider,
        bound_id=bound_id,
        source_match=source_match,
        translated_via=translated_via,
        _token=_INTERNAL_TOKEN,
    )


# ---------------------------------------------------------------------------
# ProviderRegistry public shell
# ---------------------------------------------------------------------------


class ProviderRegistry:
    """Registry of metadata providers, capability-keyed and circuit-aware.

    Instantiated once at pipeline boot from settings + providers_config.
    Validates config at construction; refuses to construct on any
    inconsistency. Immutable post-construction (no hot-swap — DESIGN §3).
    """

    def __init__(
        self,
        *,
        settings: Settings,
        event_bus: EventBus | None,
        cb_policy: CircuitPolicy,
        providers_config: ProvidersConfig,
    ) -> None:
        """Initialise registry with settings, event bus, and provider config."""
        raise NotImplementedError

    # --- The three semantic operations ---

    @overload
    def chain(self, capability: type[Searchable]) -> list[Searchable]: ...
    @overload
    def chain(self, capability: type[MovieDetailsProvider]) -> list[MovieDetailsProvider]: ...
    @overload
    def chain(self, capability: type[TvDetailsProvider]) -> list[TvDetailsProvider]: ...
    @overload
    def chain(self, capability: type[EpisodeFetcher]) -> list[EpisodeFetcher]: ...
    def chain(self, capability: type) -> list[Any]:
        """Ordered list of eligible providers for chain capabilities.

        Eligible = circuit CLOSED or HALF_OPEN (HALF_OPEN is probe — see DESIGN §7.6).

        Raises:
            WrongSemanticBug: if capability is not a chain capability.
        """
        raise NotImplementedError

    def fan_out(self, capability: type[RatingProvider]) -> list[RatingProvider]:
        """All eligible providers for fan-out capabilities. May return [].

        Raises:
            WrongSemanticBug: if capability is not a fan_out capability.
        """
        raise NotImplementedError

    @overload
    def locked(
        self,
        capability: type[ArtworkProvider],
        match: ProviderMatch,
    ) -> LockedProvider[ArtworkProvider] | None: ...
    @overload
    def locked(
        self,
        capability: type[KeywordProvider],
        match: ProviderMatch,
    ) -> LockedProvider[KeywordProvider] | None: ...
    @overload
    def locked(
        self,
        capability: type[VideoProvider],
        match: ProviderMatch,
    ) -> LockedProvider[VideoProvider] | None: ...
    @overload
    def locked(
        self,
        capability: type[RecommendationProvider],
        match: ProviderMatch,
    ) -> LockedProvider[RecommendationProvider] | None: ...
    def locked(self, capability: type, match: ProviderMatch) -> LockedProvider[Any] | None:
        """Provider bound to match's id (IDCrossRef escape if needed).

        Algorithm: see DESIGN §6.4.

        Raises:
            WrongSemanticBug: if capability is not a locked capability.
        """
        raise NotImplementedError

    # --- Direct dispatch ---

    def get(self, provider_name: str) -> Named:
        """Return a provider by name.

        Raises:
            UnknownProviderError: if name is not registered.
        """
        raise NotImplementedError

    def cross_ref(
        self,
        match: ProviderMatch,
        *,
        target: str,
    ) -> str | None:
        """Translate match's id to target provider's id space via IDCrossRef.

        Returns target-provider id, or None if no translation path exists.
        """
        raise NotImplementedError

    # --- Introspection ---

    def operations(self) -> dict[type, Mode]:
        """Capability → Mode map. Includes Mode.DIRECT for IDValidator/IDCrossRef."""
        raise NotImplementedError

    def status(self) -> dict[str, ProviderStatus]:
        """Per-provider circuit state snapshot."""
        raise NotImplementedError

    def providers_for(self, capability: type) -> list[Named]:
        """Raw ordered list (no circuit filtering). For introspection only."""
        raise NotImplementedError

    def close(self) -> None:
        """Release per-provider resources. Safe to call multiple times."""
        raise NotImplementedError
