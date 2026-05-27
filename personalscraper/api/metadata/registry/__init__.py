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
    cast,
    overload,
)

from personalscraper.api._contracts import ApiError, CircuitOpenError, MediaType
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
from personalscraper.api.metadata.registry._errors import (
    RegistryConfigError,
    UnknownProviderError,
    WrongSemanticBug,
)
from personalscraper.api.metadata.registry._events import (
    LockedCapabilityUnresolved,
    ProviderExhaustedEvent,
    ProviderFallbackTriggered,
    RegistryBootValidated,
    RegistryFanOutCompleted,
)
from personalscraper.api.metadata.registry._semantics import (
    CAPABILITY_KEYS,
    CHAIN_CAPABILITIES,
    FAN_OUT_CAPABILITIES,
    LOCKED_CAPABILITIES,
    mode_for,
)
from personalscraper.logger import get_logger

log = get_logger("registry")

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
# RegistryProviderName alias
#
# Open-string identifier for any provider name encountered by the registry.
# Intentionally distinct from ``personalscraper.api._contracts.ProviderName``
# (a closed ``str``-Enum of known providers). The registry accepts arbitrary
# names supplied by user config — including test-only synthetics — so a
# closed Enum would be too restrictive here. The previous shared name
# (``ProviderName`` was defined twice, once as Enum, once as NewType) caused
# silent type aliasing because Enum subclasses ``str``. See sub-phase 5.2
# of the registry tech-debt sweep.
# ---------------------------------------------------------------------------

RegistryProviderName = NewType("RegistryProviderName", str)

# ---------------------------------------------------------------------------
# Named Protocol
# ---------------------------------------------------------------------------


class Named(Protocol):
    """Every concrete provider exposes a stable string identifier.

    ``provider_name`` matches the config key (e.g. ``"tmdb"``, ``"tvdb"``) and is used
    in diagnostic events, logs, and the introspection API. The attribute name
    mirrors the ``provider_name: ClassVar[str]`` declared on the concrete
    ``MetadataClient`` family (see ``personalscraper/api/metadata/_base.py``)
    so the structural Protocol matches at type-check time without ``cast``s
    or ``type: ignore`` escape hatches.
    """

    provider_name: ClassVar[str]


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

    provider: RegistryProviderName
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

    provider: RegistryProviderName
    reason: Literal["circuit_open", "network", "empty_result", "other"]
    detail: str | None = None


@dataclass(frozen=True)
class ProviderStatus:
    """Per-provider runtime status snapshot.

    The ``provider_name`` field carries the same identifier that the
    concrete provider classes declare under ``provider_name: ClassVar[str]``
    (cf. ``MetadataClient`` family). It is intentionally named to mirror
    the Protocol attribute introduced by ``Named``.
    """

    provider_name: RegistryProviderName
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
    provider: RegistryProviderName | None
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
        event_bus: EventBus,
        cb_policy: CircuitPolicy,
        providers_config: ProvidersConfig,
    ) -> None:
        """Initialize the registry by instantiating providers and validating config.

        Args:
            settings: Project settings (for credentials).
            event_bus: EventBus for transport instrumentation (required per
                project architectural contract — event-bus 0.14.0).
            cb_policy: CircuitPolicy applied to all provider transports.
            providers_config: Parsed ProvidersConfig from config/providers.json5.

        Raises:
            RegistryConfigError: Aggregated config issues from validation.
        """
        from personalscraper.api.metadata.registry._factory import build_providers
        from personalscraper.api.metadata.registry._validation import validate_config

        self._event_bus = event_bus
        self._settings = settings
        self._cb_policy = cb_policy
        self._providers_config = providers_config

        # Collect all unique provider names from any section
        provider_names_set: set[str] = set()
        for section_name in CAPABILITY_KEYS:
            section = getattr(providers_config, section_name, {})
            provider_names_set.update(section.keys())
        provider_names = sorted(provider_names_set)

        # Instantiate providers with cleanup on failure
        instantiated: list[object] = []
        try:
            self._providers: dict[str, object] = build_providers(provider_names, settings, cb_policy, event_bus)
            instantiated.extend(self._providers.values())

            # Validate config — aggregated, never fail-fast
            issues = validate_config(providers_config, self._providers, settings)
            if issues:
                raise RegistryConfigError(issues)
        except BaseException:
            # Cleanup on failure (DESIGN §6.1.f)
            for p in instantiated:
                try:
                    close = getattr(p, "close", None)
                    if callable(close):
                        close()
                except Exception as e:
                    log.debug(
                        "registry_boot_cleanup_failed",
                        provider=getattr(p, "provider_name", "?"),
                        exc_type=type(e).__name__,
                    )
            raise

        # Build raw ordered index: capability → list of provider names (sorted by priority)
        self._index: dict[type, list[str]] = {}
        for section_key, capability_class in CAPABILITY_KEYS.items():
            section = getattr(providers_config, section_key, {})
            # Sort by priority (lower priority value = higher precedence)
            ordered = sorted(section.items(), key=lambda kv: kv[1])
            self._index[capability_class] = [name for name, _ in ordered]

        # Emit boot-validated event
        self._event_bus_safe_emit(
            RegistryBootValidated(
                providers=list(self._providers),
                capabilities={cap.__name__: list(names) for cap, names in self._index.items()},
            )
        )

        log.info(
            "registry_boot_loaded",
            providers_count=len(self._providers),
            capabilities_count=len(self._index),
        )

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
        from personalscraper.api.metadata.registry._factory import _eligible

        if capability not in CHAIN_CAPABILITIES:
            raise WrongSemanticBug(
                f"{capability.__name__} is not a chain capability — use the correct registry operation."
            )
        names = self._index.get(capability, [])
        result: list[Any] = []
        for n in names:
            if n not in self._providers:
                continue
            provider = self._providers[n]
            if not _eligible(provider):
                log.debug(
                    "registry_provider_skip",
                    provider=n,
                    capability=capability.__name__,
                    reason="circuit_open",
                )
                continue
            result.append(provider)
        return result

    def fan_out(self, capability: type[RatingProvider]) -> list[RatingProvider]:
        """All eligible providers for fan-out capabilities. May return [].

        Emits ``RegistryFanOutCompleted`` after every call (DESIGN §7.4, §7.5).

        Raises:
            WrongSemanticBug: if capability is not a fan_out capability.
        """
        from personalscraper.api.metadata.registry._factory import _eligible

        if capability not in FAN_OUT_CAPABILITIES:
            raise WrongSemanticBug(
                f"{capability.__name__} is not a fan_out capability — use the correct registry operation."
            )
        names = self._index.get(capability, [])
        eligible: list[Any] = []
        attempted: list[AttemptOutcome] = []
        for n in names:
            if n not in self._providers:
                continue
            provider_name = RegistryProviderName(n)
            provider = self._providers[n]
            if not _eligible(provider):
                log.debug(
                    "registry_provider_skip",
                    provider=n,
                    capability=capability.__name__,
                    reason="circuit_open",
                )
                attempted.append(AttemptOutcome(provider=provider_name, reason="circuit_open"))
                continue
            eligible.append(provider)

        log.info(
            "registry_fan_out_partial",
            capability=capability.__name__,
            providers_tried=len(names),
            providers_succeeded=len(eligible),
        )
        self._event_bus_safe_emit(
            RegistryFanOutCompleted(
                capability=capability.__name__,
                attempted=attempted,
                succeeded=len(eligible),
            )
        )
        return eligible

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

        Algorithm (DESIGN §6.4):
            1. Try match's own provider.
            2. Walk capability's index translating IDs via cross_ref.
            3. Return None + emit LockedCapabilityUnresolved if nothing found.

        Raises:
            WrongSemanticBug: if capability is not a locked capability.
        """
        from personalscraper.api.metadata.registry._factory import _eligible

        if capability not in LOCKED_CAPABILITIES:
            raise WrongSemanticBug(
                f"{capability.__name__} is not a locked capability — use the correct registry operation."
            )

        # 1. Match's own provider
        own = self._providers.get(match.provider)
        if own is not None and isinstance(own, capability) and _eligible(own):
            return _make_locked(
                provider=own,
                bound_id=match.id,
                source_match=match,
                translated_via=None,
            )

        # 2. Chain fallback with IDCrossRef
        for candidate_name in self._index.get(capability, []):
            if candidate_name == match.provider:
                continue  # already tried in step 1
            candidate = self._providers.get(candidate_name)
            if candidate is None or not isinstance(candidate, capability):
                continue
            if not _eligible(candidate):
                continue
            xref_id = self.cross_ref(match, target=candidate_name)
            if xref_id is None:
                continue
            log.debug(
                "registry_locked_xref",
                source_provider=match.provider,
                target_provider=candidate_name,
                xref_id=xref_id,
            )
            return _make_locked(
                provider=candidate,
                bound_id=xref_id,
                source_match=match,
                translated_via=match.provider,
            )

        # 3. Nothing found
        self._event_bus_safe_emit(
            LockedCapabilityUnresolved(
                capability=capability.__name__,
                match=match,
                chain_tried=list(self._index.get(capability, [])),
            )
        )
        log.warning(
            "registry_locked_unresolved",
            capability=capability.__name__,
            match=str(match),
        )
        return None

    # --- Direct dispatch ---

    def get(self, provider_name: str) -> Named:
        """Return a provider by name.

        Raises:
            UnknownProviderError: if name is not registered.
        """
        if provider_name not in self._providers:
            raise UnknownProviderError(provider_name)
        return cast(Named, self._providers[provider_name])

    def cross_ref(
        self,
        match: ProviderMatch,
        *,
        target: str,
    ) -> str | None:
        """Translate match's id to target provider's id space via IDCrossRef.

        Returns target-provider id, or None if no translation path exists:
        - target not in IDCrossRef section
        - match.provider has no IDCrossRef implementation
        - IDCrossRef call returns no entry for target / raises
        """
        if target == match.provider:
            return match.id

        source_provider = self._providers.get(match.provider)
        if source_provider is None:
            return None
        if not isinstance(source_provider, IDCrossRef):
            return None
        try:
            xref_dict = source_provider.get_cross_refs(match.id)
            return xref_dict.get(target)
        except (ApiError, CircuitOpenError) as e:
            log.warning(
                "registry_cross_ref_failed",
                source_provider=match.provider,
                target_provider=target,
                exc_type=type(e).__name__,
            )
            return None

    # --- Introspection ---

    def operations(self) -> dict[type, Mode]:
        """Capability → Mode map. Includes Mode.DIRECT for IDValidator/IDCrossRef."""
        return {capability: mode_for(capability) for capability in CAPABILITY_KEYS.values()}

    def status(self) -> dict[str, ProviderStatus]:
        """Per-provider circuit state snapshot."""
        result: dict[str, ProviderStatus] = {}
        for name, provider in self._providers.items():
            circuit = getattr(provider, "circuit", None)
            state = getattr(circuit, "state", "CLOSED") if circuit else "CLOSED"
            result[name] = ProviderStatus(
                provider_name=RegistryProviderName(name),
                circuit_state=state,  # type: ignore[arg-type]  # Literal validated by fuzzing
                failure_count_recent=(getattr(circuit, "failure_count_recent", 0) if circuit else 0),
                last_success_at=(getattr(circuit, "last_success_at", None) if circuit else None),
                last_failure_at=(getattr(circuit, "last_failure_at", None) if circuit else None),
            )
        return result

    def providers_for(self, capability: type) -> list[Named]:
        """Raw ordered list (no circuit filtering). For introspection only."""
        names = self._index.get(capability, [])
        return [cast(Named, self._providers[n]) for n in names if n in self._providers]

    def close(self) -> None:
        """Release per-provider resources. Safe to call multiple times."""
        for name, provider in list(self._providers.items()):
            try:
                close = getattr(provider, "close", None)
                if callable(close):
                    close()
            except Exception as e:
                log.debug(
                    "registry_provider_close_failed",
                    provider=name,
                    exc_type=type(e).__name__,
                )

    def _event_bus_safe_emit(self, event: object) -> None:
        """Emit event safely; catch and log any bus failure (never propagates).

        The bus is always a real EventBus per project architectural contract
        (event-bus 0.14.0): no None permitted. Tests pass a MockEventBus.
        """
        try:
            self._event_bus.emit(event)  # type: ignore[arg-type]
        except Exception as exc:
            log.warning(
                "registry_event_emit_failed",
                event_class=type(event).__name__,
                exc_type=type(exc).__name__,
            )

    # --- Chain iteration emit helpers (DESIGN §6.2 / §7.4) ---
    #
    # These two helpers centralise event construction for chain-iteration
    # call sites (movie_service, tv_service, existing_validator). Callers
    # iterate ``self._registry.chain(Capability)`` themselves; on each
    # per-provider skip they call ``_emit_provider_fallback`` with the
    # appropriate reason, and on full exhaustion they call
    # ``_emit_provider_exhausted`` before raising
    # :class:`ProviderExhausted`.
    #
    # Originally scheduled for sub-phase 7.3 of the registry plan, but
    # absorbed into 7.1 because the first chain-iteration site
    # (``MovieServiceMixin._match_movie_candidates``) depends on these
    # helpers. See commit body for the plan-ordering correction.

    def _emit_provider_fallback(
        self,
        *,
        capability: str,
        from_provider: str,
        reason: Literal["circuit_open", "network", "empty_result"],
        item: dict[str, Any],
        to_provider: str | None = None,
        exc_type: str | None = None,
    ) -> None:
        """Emit :class:`ProviderFallbackTriggered` from a chain iteration site.

        Args:
            capability: Capability Protocol name (e.g. ``"MovieDetailsProvider"``).
            from_provider: The provider being skipped.
            reason: Closed enum — must match ``ProviderFallbackTriggered.reason``.
            item: Item context for diagnostics (title/year/media_type).
            to_provider: Next provider in the chain, if known at emit time.
                The chain iterator typically does not know ``to_provider`` ahead
                of the next iteration; leave empty when unknown.
            exc_type: Exception class name when ``reason="network"``.
        """
        self._event_bus_safe_emit(
            ProviderFallbackTriggered(
                capability=capability,
                from_provider=from_provider,
                to_provider=to_provider or "",
                reason=reason,
                exc_type=exc_type,
                item=item,
            )
        )

    def _emit_provider_exhausted(
        self,
        *,
        capability: str,
        attempted: list[AttemptOutcome],
        item: dict[str, Any],
    ) -> None:
        """Emit :class:`ProviderExhaustedEvent` after all chain providers failed.

        Caller is responsible for raising
        :class:`personalscraper.api.metadata.registry._errors.ProviderExhausted`
        after this emission — the event is for observers, the exception is
        for control flow.

        Args:
            capability: Capability Protocol name.
            attempted: One row per attempted provider with its outcome.
            item: Item context (title/year/media_type) for diagnostics.
        """
        self._event_bus_safe_emit(
            ProviderExhaustedEvent(
                capability=capability,
                attempted=attempted,
                item=item,
            )
        )
