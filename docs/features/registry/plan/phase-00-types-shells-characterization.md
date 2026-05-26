# Phase 0 — New types, shells, characterization tests

> **Feature**: registry | **Version**: 0.15.1 → 0.16.0
> **Commit scope**: `(registry)`
> **Design ref**: DESIGN.md §5, §6.1, §7, §8.1–8.6, §9 Phase 0

---

## Gate

No previous phase. This is the starting phase. The `feat/registry` branch must be
checked out and `pip install -e ".[dev]"` must pass cleanly.

---

## Goal

Introduce all new types, the `ProviderRegistry` shell, the Pydantic config model,
and the broken-config fixture — then lock in the current orchestrator behavior via
characterization tests. No consumer file is modified. After this phase the registry
exists and its unit tests pass; the orchestrator is untouched.

---

## Scope

**Created:**

- `personalscraper/api/metadata/registry/__init__.py` — `ProviderRegistry` public class + `Mode`, `ProviderMatch`, `LockedProvider`, `AttemptOutcome`, `ProviderStatus`, `ConfigIssue`, `FanOutResult` data structures
- `personalscraper/api/metadata/registry/_errors.py` — `RegistryError`, `RegistryConfigError`, `UnknownProviderError`, `ProviderExhausted`, `WrongSemanticBug`
- `personalscraper/api/metadata/registry/_events.py` — all 5 EventBus event dataclasses: `ProviderFallbackTriggered`, `ProviderExhaustedEvent`, `LockedCapabilityUnresolved`, `RegistryFanOutCompleted`, `RegistryBootValidated`
- `personalscraper/api/metadata/registry/_semantics.py` — `CHAIN_CAPABILITIES`, `FAN_OUT_CAPABILITIES`, `LOCKED_CAPABILITIES`, `DIRECT_CAPABILITIES` sets + `mode_for(capability)` helper
- `personalscraper/api/metadata/registry/_factory.py` — `build_providers()`, `_make_locked()` (package-private), `_eligible()` circuit filter
- `personalscraper/api/metadata/registry/_validation.py` — `validate_config()` — all six `ConfigIssue.code` families
- `personalscraper/conf/models/providers.py` — `ProvidersConfig` Pydantic model + `CAPABILITY_KEYS`
- `config.example/providers.json5` — template with defaults from DESIGN §5.4
- `tests/fixtures/bad_providers.json5` — synthetic broken config (ACC-05a)
- `tests/unit/api/metadata/registry/test_registry_chain.py`
- `tests/unit/api/metadata/registry/test_registry_fan_out.py`
- `tests/unit/api/metadata/registry/test_registry_locked.py`
- `tests/unit/api/metadata/registry/test_registry_validation.py`
- `tests/unit/api/metadata/registry/test_registry_introspection.py`
- `tests/unit/api/metadata/registry/test_registry_get.py`
- `tests/unit/api/metadata/registry/test_registry_event_bus.py`
- `tests/integration/scraper/test_legacy_fallback_snapshot.py` — characterization tests (§8.4)

**Modified:**

- `personalscraper/conf/models/config.py` — add `providers: ProvidersConfig` field

---

## Sub-phases

Each sub-phase = one commit.

### 0.1 — Error types + event dataclasses + semantics map

**Files:** `_errors.py`, `_events.py`, `_semantics.py`

Define the full exception hierarchy (DESIGN §7.1), all five EventBus event
dataclasses (DESIGN §7.4), and the capability→mode mapping (DESIGN §4, §5.1).

```python
# personalscraper/api/metadata/registry/_errors.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from personalscraper.api.metadata._contracts import (
        Searchable, MovieDetailsProvider, TvDetailsProvider, EpisodeFetcher,
        RatingProvider, ArtworkProvider, KeywordProvider, VideoProvider,
        RecommendationProvider, IDValidator, IDCrossRef,
    )

class RegistryError(Exception):
    """Base class for all registry errors."""

class RegistryConfigError(RegistryError):
    """Config inconsistency detected at boot. Carries structured issues list."""
    def __init__(self, issues: list[ConfigIssue]) -> None:
        self.issues = issues
        super().__init__(self._format(issues))

    @staticmethod
    def _format(issues: list[ConfigIssue]) -> str:
        lines = ["RegistryConfigError — provider config is invalid:"]
        for issue in issues:
            suggestion = f" (did you mean {issue.message!r}?)" if "did you mean" in issue.message else ""
            lines.append(f"  [{issue.code}] section={issue.section} provider={issue.provider}: {issue.message}{suggestion}")
        return "\n".join(lines)

class UnknownProviderError(RegistryError):
    """registry.get(name) called with unregistered name."""
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Unknown provider: {name!r}")

class ProviderExhausted(RegistryError):
    """All chain providers failed for an item."""
    def __init__(
        self,
        capability: type,
        attempted: list[AttemptOutcome],
        item_context: dict[str, Any] | None = None,
    ) -> None:
        self.capability = capability
        self.attempted = attempted
        self.item_context = item_context
        super().__init__(
            f"All providers exhausted for {capability.__name__}: "
            f"{[a.provider for a in attempted]}"
        )

class WrongSemanticBug(RegistryError):
    """Caller invoked wrong registry operation for a capability. Never catch."""
```

```python
# personalscraper/api/metadata/registry/_events.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Literal
# Import AttemptOutcome and ProviderMatch at runtime via TYPE_CHECKING to avoid
# circular import (they are defined in __init__.py which imports _events.py).
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import AttemptOutcome, ProviderMatch

@dataclass(frozen=True)
class ProviderFallbackTriggered:
    """Emitted when a chain moves from one provider to the next."""
    capability: str
    from_provider: str
    to_provider: str
    reason: Literal["circuit_open", "network", "empty_result"]
    exc_type: str | None
    item: dict[str, Any]

@dataclass(frozen=True)
class ProviderExhaustedEvent:
    """Emitted when all providers in a chain failed for an item."""
    capability: str
    attempted: list  # list[AttemptOutcome] — avoid circular at runtime
    item: dict[str, Any]

@dataclass(frozen=True)
class LockedCapabilityUnresolved:
    """Emitted when locked() cannot bind a provider via IDCrossRef."""
    capability: str
    match: object  # ProviderMatch — avoid circular at runtime
    chain_tried: list[str]

@dataclass(frozen=True)
class RegistryFanOutCompleted:
    """Always emitted after fan_out returns (even on full success)."""
    capability: str
    attempted: list  # list[AttemptOutcome]
    succeeded: int

@dataclass(frozen=True)
class RegistryBootValidated:
    """Emitted when boot completed successfully."""
    providers: list[str]
    capabilities: dict[str, list[str]]
```

> **Note on circular imports**: `_events.py` uses `object` / `list` type hints at
> runtime for `ProviderMatch` and `AttemptOutcome` to avoid a circular import with
> `__init__.py`. The TYPE_CHECKING guard provides proper types for mypy/editors.
> `LockedCapabilityUnresolved` is used in Phase 0 sub-phase 0.4 tests and sub-phase
> 0.5b implementation — defining it here ensures the import never fails.

```python
# personalscraper/api/metadata/registry/_semantics.py
from __future__ import annotations
from typing import TYPE_CHECKING
from personalscraper.api.metadata.registry._errors import WrongSemanticBug
from personalscraper.api.metadata._contracts import (
    Searchable, MovieDetailsProvider, TvDetailsProvider, EpisodeFetcher,
    RatingProvider, ArtworkProvider, KeywordProvider, VideoProvider,
    RecommendationProvider, IDValidator, IDCrossRef,
)

# Frozen sets — adding a new Protocol requires updating ONE place here.
CHAIN_CAPABILITIES: frozenset[type] = frozenset({
    Searchable, MovieDetailsProvider, TvDetailsProvider, EpisodeFetcher,
})
FAN_OUT_CAPABILITIES: frozenset[type] = frozenset({RatingProvider})
LOCKED_CAPABILITIES: frozenset[type] = frozenset({
    ArtworkProvider, KeywordProvider, VideoProvider, RecommendationProvider,
})
DIRECT_CAPABILITIES: frozenset[type] = frozenset({IDValidator, IDCrossRef})

ALL_CAPABILITIES: frozenset[type] = (
    CHAIN_CAPABILITIES | FAN_OUT_CAPABILITIES | LOCKED_CAPABILITIES | DIRECT_CAPABILITIES
)

# Stable string key → Protocol (used by ProvidersConfig parser)
CAPABILITY_KEYS: dict[str, type] = {
    "Searchable":             Searchable,
    "MovieDetailsProvider":   MovieDetailsProvider,
    "TvDetailsProvider":      TvDetailsProvider,
    "EpisodeFetcher":         EpisodeFetcher,
    "RatingProvider":         RatingProvider,
    "ArtworkProvider":        ArtworkProvider,
    "KeywordProvider":        KeywordProvider,
    "VideoProvider":          VideoProvider,
    "RecommendationProvider": RecommendationProvider,
    "IDValidator":            IDValidator,
    "IDCrossRef":             IDCrossRef,
}

def mode_for(capability: type) -> "Mode":
    """Return the dispatch mode for a capability. Raises WrongSemanticBug if unknown."""
    from personalscraper.api.metadata.registry import Mode
    if capability in CHAIN_CAPABILITIES:
        return Mode.CHAIN
    if capability in FAN_OUT_CAPABILITIES:
        return Mode.FAN_OUT
    if capability in LOCKED_CAPABILITIES:
        return Mode.LOCKED
    if capability in DIRECT_CAPABILITIES:
        return Mode.DIRECT
    raise WrongSemanticBug(f"{capability.__name__} is not a known registry capability")
```

Commit: `feat(registry): error types + event dataclasses + capability semantics map`

---

### 0.2 — Data structures + `ProviderRegistry` public shell

**Files:** `__init__.py` (new), `personalscraper/conf/models/providers.py` (new)

Implement all data structures from DESIGN §5.3 and the `ProviderRegistry` class
skeleton with all public methods raising `NotImplementedError`. Include `Mode` enum
and `Named` protocol.

Key data structures to include verbatim from DESIGN §5.3:

- `Mode(StrEnum)` with CHAIN/FAN_OUT/LOCKED/DIRECT
- `ProviderMatch` (frozen dataclass: `provider`, `id`, `media_type`, with `__post_init__` validation)
- `LockedProvider[C]` (frozen dataclass: `provider`, `bound_id`, `source_match`, `translated_via`, `_token` sentinel — see I3 below)
- `AttemptOutcome` (frozen dataclass: `provider`, `reason` Literal, `detail`)
- `ProviderStatus` (frozen dataclass: with `failure_count_recent ≥ 0` validation)
- `ConfigIssue` (frozen dataclass: `code` Literal with 6 values, `section`, `provider`, `message`)
- `FanOutResult[C]` (frozen dataclass: `values`, `attempted`)

**Sentinel-token mechanism for `LockedProvider` (DESIGN §6.4 — I3)**:
`LockedProvider` can only be constructed via the registry's internal `_make_locked()`
helper. To enforce this in plain Python (where frozen dataclasses have no private
constructors), use a module-private sentinel object:

```python
# api/metadata/registry/__init__.py
_INTERNAL_TOKEN = object()  # module-private sentinel — never exported

@dataclass(frozen=True)
class LockedProvider[C]:
    provider: C
    bound_id: str
    source_match: ProviderMatch
    translated_via: str | None
    _token: object = field(repr=False)

    def __post_init__(self) -> None:
        if self._token is not _INTERNAL_TOKEN:
            raise TypeError(
                "LockedProvider can only be constructed via the registry's "
                "internal _make_locked() helper."
            )

def _make_locked(*, provider, bound_id, source_match, translated_via) -> "LockedProvider":
    """Package-private constructor. Only called by ProviderRegistry.locked()."""
    return LockedProvider(
        provider=provider, bound_id=bound_id,
        source_match=source_match, translated_via=translated_via,
        _token=_INTERNAL_TOKEN,
    )
```

The test `test_LockedProvider_construction_outside_registry_module_raises` asserts
`TypeError` when `LockedProvider(...)` is called without `_token=_INTERNAL_TOKEN`.

`ProviderRegistry.__init__` signature (from DESIGN §5.2):

```python
def __init__(
    self,
    *,
    settings: Settings,
    event_bus: EventBus | None,
    cb_policy: CircuitPolicy,
    providers_config: ProvidersConfig,
) -> None:
    raise NotImplementedError
```

All other public methods (`chain`, `fan_out`, `locked`, `get`, `cross_ref`,
`operations`, `status`, `providers_for`, `close`) also raise `NotImplementedError`.

Also write `ProvidersConfig` in `conf/models/providers.py` (from DESIGN §5.4):

- Strict Pydantic model (`extra="forbid"`)
- 11 `dict[str, PositiveInt]` fields (one per capability key)
- `@model_validator` that checks priority uniqueness within each section

Add `providers: ProvidersConfig` field to `personalscraper/conf/models/config.py`
(import + field with `default_factory=ProvidersConfig`).

Commit: `feat(registry): ProviderRegistry shell + ProvidersConfig model`

---

### 0.3 — `_factory.py` + `_validation.py` + config template

**Files:** `_factory.py`, `_validation.py`, `config.example/providers.json5`

`_factory.py` — provider instantiation helpers:

```python
# personalscraper/api/metadata/registry/_factory.py
from __future__ import annotations

# Provider name → class lookup (frozen at import time)
PROVIDER_CLASSES: dict[str, type] = {
    "tmdb":             "personalscraper.api.metadata.tmdb:TMDBClient",
    "tvdb":             "personalscraper.api.metadata.tvdb:TVDBClient",
    # Additional providers resolved lazily so missing optional deps don't break boot
}

def resolve_provider_class(name: str) -> type:
    """Import and return the provider class for `name`. Raises ImportError on failure."""
    ...

def build_providers(
    provider_names: list[str],
    settings: "Settings",
    cb_policy: "CircuitPolicy",
    event_bus: "EventBus | None",
) -> dict[str, object]:
    """Instantiate each named provider once. Returns name → instance dict.
    Propagates ImportError / TypeError as RegistryConfigError issue."""
    ...

def _eligible(provider: object) -> bool:
    """Return True if provider circuit is CLOSED or HALF_OPEN (eligible for calls).

    HALF_OPEN eligibility (DESIGN §7.6): a provider is eligible if its circuit is
    CLOSED OR HALF_OPEN. The HALF_OPEN state acts as a probe — the underlying
    HttpTransport lets one request through; if it fails, the transport raises
    NetworkError which the registry catches and falls through to the next provider
    in the same iteration. Do NOT implement as state == "CLOSED" only — that
    excludes valid probes.

    Providers without a `.circuit` attribute are always eligible (e.g. fake providers).
    """
    circuit = getattr(provider, "circuit", None)
    if circuit is None:
        return True
    state = getattr(circuit, "state", None)
    # OPEN is the only ineligible state — CLOSED and HALF_OPEN both qualify
    return state != "OPEN"
```

`_validation.py` — boot validators covering all six `ConfigIssue.code` families
(DESIGN §7.2): `missing_credentials`, `protocol_mismatch`, `unknown_provider`,
`empty_chain_section`, `locked_capability_orphan`, `idcrossref_cycle`. Uses
`difflib.get_close_matches` for `unknown_provider` suggestions.

**Validation aggregation (DESIGN §7.2 — C11)**: the validator MUST accumulate ALL
`ConfigIssue` entries into a single list across all six checks before raising.
Do NOT raise on the first issue (fail-fast is FORBIDDEN here — the user must learn
all problems at once). The test `test_all_six_issue_families_in_one_error` validates
this; a fail-fast implementation will fail that test.

**IDCrossRef cycle detection (I2)**: use DFS with a `visited: set[str]` per starting
provider. For each provider P in the chain capabilities, walk
`IDCrossRef[P] → IDCrossRef[next] → ...`. If a node is revisited before terminal,
report a `ConfigIssue(code="idcrossref_cycle", ...)`. Never enter the cycle a second
time — a caller of `cross_ref()` would loop otherwise.

```python
# _validation.py — sketch of aggregated validation
def validate_config(
    providers_config: ProvidersConfig,
    providers: dict[str, object],
) -> list[ConfigIssue]:
    """Collect ALL config issues across all six families. Never raises directly."""
    issues: list[ConfigIssue] = []
    issues.extend(_check_missing_credentials(providers, ...))
    issues.extend(_check_protocol_mismatch(providers_config, providers))
    issues.extend(_check_unknown_providers(providers_config, providers))
    issues.extend(_check_empty_chain_sections(providers_config))
    issues.extend(_check_locked_capability_orphans(providers_config, providers))
    issues.extend(_check_idcrossref_cycles(providers_config, providers))
    return issues
```

`config.example/providers.json5` — exact content from DESIGN §5.4.

Commit: `feat(registry): factory, boot validation, config.example/providers.json5`

---

### 0.4 — Unit tests (TDD — all ~45 tests, DESIGN §8.2)

**Files:** all seven `tests/unit/api/metadata/registry/test_*.py`

Write tests first (they will fail until 0.5a/b/c implements the real logic). Each
test file covers the cases listed in DESIGN §8.2 verbatim. Use fake provider classes:

```python
# Shared fake provider fixture (place in conftest.py or inline)
from personalscraper.api.metadata._contracts import Searchable, MovieDetailsProvider

class FakeSearchable:
    """Fake provider that implements Searchable for unit tests."""
    name: ClassVar[str] = "fake_searchable"
    def __init__(self, *, results=None, circuit_state="CLOSED"):
        self._results = results or []
        self._circuit = SimpleNamespace(state=circuit_state, can_proceed=lambda: circuit_state != "OPEN")

    @property
    def circuit(self):
        return self._circuit

    def search(self, query: str) -> list:
        return self._results
```

Key tests to include (examples from DESIGN §8.2 — see Appendix A for full checklist):

```python
# test_registry_chain.py
def test_chain_ordering_is_stable_across_calls(registry_with_two_providers):
    """chain() returns same order across repeated calls (DESIGN §5.2 stable-ordering guarantee)."""
    first  = registry_with_two_providers.chain(Searchable)
    second = registry_with_two_providers.chain(Searchable)
    assert [p.name for p in first] == [p.name for p in second]

def test_chain_skips_open_circuit(registry_with_open_provider):
    providers = registry_with_open_provider.chain(Searchable)
    assert all(p.circuit.state != "OPEN" for p in providers)

def test_chain_includes_half_open_providers(registry_with_half_open_provider):
    """HALF_OPEN providers are eligible (probe semantics, DESIGN §7.6).
    Do NOT implement _eligible() as state == 'CLOSED' only."""
    providers = registry_with_half_open_provider.chain(Searchable)
    assert any(p.circuit.state == "HALF_OPEN" for p in providers)

def test_chain_provider_flips_to_open_mid_iteration(registry, mock_transport):
    """A provider that trips to OPEN after chain() is called still triggers fallback."""
    # Simulate: chain() returns [p1, p2]; p1 raises CircuitOpenError mid-call
    ...

def test_chain_wrong_semantic_raises(registry):
    with pytest.raises(WrongSemanticBug):
        registry.chain(RatingProvider)  # RatingProvider is fan_out, not chain
```

```python
# test_registry_validation.py
def test_missing_credentials_issue():
    with pytest.raises(RegistryConfigError) as exc:
        build_registry(settings_without_tmdb_key)
    assert any(i.code == "missing_credentials" for i in exc.value.issues)

def test_all_six_issue_families_in_one_error(bad_config):
    """Validation MUST aggregate all issues — fail-fast is FORBIDDEN (DESIGN §7.2 / C11)."""
    with pytest.raises(RegistryConfigError) as exc:
        build_registry(bad_config)
    codes = {i.code for i in exc.value.issues}
    assert codes == {
        "missing_credentials", "protocol_mismatch", "unknown_provider",
        "empty_chain_section", "locked_capability_orphan", "idcrossref_cycle",
    }

def test_idcrossref_cycle_detected_and_reported(cyclic_config):
    """DFS cycle detection must report and terminate — never infinite loop."""
    with pytest.raises(RegistryConfigError) as exc:
        build_registry(cyclic_config)
    assert any(i.code == "idcrossref_cycle" for i in exc.value.issues)

def test_boot_cleanup_on_validation_failure(partial_config, spy_provider_close):
    """Providers instantiated before validation fails must have .close() called."""
    with pytest.raises(RegistryConfigError):
        build_registry(partial_config)
    assert spy_provider_close.called
```

```python
# test_registry_locked.py
def test_locked_returns_none_emits_LockedCapabilityUnresolved_event(registry, match, mock_bus):
    result = registry.locked(ArtworkProvider, match)
    assert result is None
    assert any(isinstance(e, LockedCapabilityUnresolved) for e in mock_bus.emitted)

def test_LockedProvider_construction_outside_registry_module_raises():
    """Sentinel-token mechanism prevents external construction (DESIGN §6.4 / I3)."""
    with pytest.raises(TypeError):
        LockedProvider(provider=object(), bound_id="x", source_match=..., translated_via=None,
                       _token=object())  # wrong token
```

```python
# test_registry_fan_out.py
def test_RegistryFanOutCompleted_always_emitted_even_on_success(registry, mock_bus):
    """RegistryFanOutCompleted is emitted even when every provider succeeds."""
    registry.fan_out(RatingProvider)
    assert any(isinstance(e, RegistryFanOutCompleted) for e in mock_bus.emitted)
```

```python
# test_registry_get.py
def test_get_unknown_name_raises_UnknownProviderError(registry):
    """registry.get() raises UnknownProviderError, NOT a bare KeyError."""
    with pytest.raises(UnknownProviderError):
        registry.get("does_not_exist")
```

Commit: `test(registry): unit tests for all registry operations (TDD — expect failures)`

---

### 0.5a — Registry core: chain / get / operations / status / providers_for

**Files:** `__init__.py` (implement constructor + core methods), no other source files

Replace `NotImplementedError` stubs with real logic for:

- `__init__` (constructor with `_event_bus_safe_emit` method + `close()`)
- `chain()` — ordered eligible providers for chain capabilities
- `get()` — provider by name or `UnknownProviderError`
- `operations()` — capability → Mode map
- `status()` — per-provider circuit state snapshot
- `providers_for()` — raw ordered list (no circuit filtering)

**`_event_bus_safe_emit` (DESIGN §7.4 / C1)**: this method MUST be on `ProviderRegistry`
from this sub-phase onward — it is used by sub-phase 0.5b (`fan_out`, `locked`) and
referenced in unit tests from 0.4:

```python
def _event_bus_safe_emit(self, event: object) -> None:
    """Emit an event; catch and log any bus failure. Never propagates.

    When event_bus=None (test context), this is a no-op — no error raised.
    """
    if self._event_bus is None:
        return  # test context — no-op
    try:
        self._event_bus.emit(event)
    except Exception as exc:
        log.warning(
            "registry_event_emit_failed",
            event_class=type(event).__name__,
            exc_type=type(exc).__name__,
        )
```

**HALF_OPEN eligibility (DESIGN §7.6 / C9)**: a provider is eligible if its circuit
is `CLOSED` OR `HALF_OPEN`. The `HALF_OPEN` state acts as a probe — the underlying
`HttpTransport` lets one request through; if it fails, the transport raises
`NetworkError` which the registry catches and falls through to the next provider
in the same iteration. **Do NOT implement `_eligible()` as `state == "CLOSED"` only**
— that excludes valid probes. The unit test `test_chain_includes_half_open_providers`
will catch this mistake.

Key implementation notes:

- `chain(capability)`: verify capability ∈ `CHAIN_CAPABILITIES` (else `WrongSemanticBug`); filter `self._index[capability]` through `_eligible()`; return ordered list.
- `get(name)`: return `self._providers[name]` or raise `UnknownProviderError` — never a bare `KeyError`.

Run: `pytest tests/unit/api/metadata/registry/test_registry_chain.py tests/unit/api/metadata/registry/test_registry_get.py tests/unit/api/metadata/registry/test_registry_introspection.py tests/unit/api/metadata/registry/test_registry_event_bus.py -q`
Expected: all corresponding tests pass.

Commit: `feat(registry): implement registry core — chain/get/operations/status/providers_for`

---

### 0.5b — Registry fan_out / locked + cross_ref + LockedProvider mechanics

**Files:** `__init__.py` (implement fan_out, locked, cross_ref, \_make_locked)

Replace `NotImplementedError` stubs with real logic for:

- `fan_out(capability)` — all eligible providers for fan-out capabilities
- `locked(capability, match)` — 3-step algorithm from DESIGN §6.4
- `cross_ref(match, *, target)` — ID translation via IDCrossRef

The `_make_locked()` function (defined in sub-phase 0.2 as a module-level helper
in `__init__.py`) must be called exclusively by `locked()` — never exported.

`locked()` implementation pseudocode (DESIGN §6.4):

```python
def locked(self, capability, match):
    # 1. Try the match's own provider
    own = self._providers.get(match.provider)
    if own is not None and isinstance(own, capability) and _eligible(own):
        return _make_locked(
            provider=own, bound_id=match.id,
            source_match=match, translated_via=None,
        )

    # 2. Walk configured chain, translating ids via IDCrossRef
    for candidate in self.chain(capability):
        if candidate.name == match.provider:
            continue
        xref_id = self.cross_ref(match, target=candidate.name)
        if xref_id is None:
            continue
        log.debug("registry_locked_xref", source_provider=match.provider,
                  target_provider=candidate.name, xref_id=xref_id)
        return _make_locked(
            provider=candidate, bound_id=xref_id,
            source_match=match, translated_via=match.provider,
        )

    # 3. Nothing found — emit + log + return None
    self._event_bus_safe_emit(LockedCapabilityUnresolved(
        capability=capability.__name__,
        match=match,
        chain_tried=[p.name for p in self.chain(capability)],
    ))
    log.warning("registry_locked_unresolved",
                capability=capability.__name__, match=match)
    return None
```

Run: `pytest tests/unit/api/metadata/registry/test_registry_fan_out.py tests/unit/api/metadata/registry/test_registry_locked.py -q`
Expected: all corresponding tests pass.

Commit: `feat(registry): implement registry fan_out/locked/cross_ref + LockedProvider mechanics`

---

### 0.5c — Boot validation + factory + cleanup discipline

**Files:** `_factory.py` (complete), `_validation.py` (complete), `__init__.py` (wire validation into `__init__`)

Complete the factory (provider-name → class mapping + builder) and validation
(all 6 ConfigIssue families + IDCrossRef cycle DFS + aggregation). Wire validation
into `ProviderRegistry.__init__` with the cleanup discipline.

**Cleanup discipline (DESIGN §6.1.f / C10)**: provider instantiation in `__init__`
MUST be wrapped in try/finally semantics so that if validation fails after some
providers are built, every already-instantiated provider has `.close()` called
(best-effort, swallow per-close exceptions but log at DEBUG
`registry_boot_cleanup_failed`). Failure to do this leaks open HTTP sessions on
every boot retry.

```python
def __init__(self, *, settings, event_bus, cb_policy, providers_config):
    self._event_bus = event_bus
    self._providers: dict[str, MetadataProvider] = {}
    instantiated: list[MetadataProvider] = []
    try:
        for name in self._collect_provider_names(providers_config):
            provider = self._factory.build(name, settings, event_bus, cb_policy)
            self._providers[name] = provider
            instantiated.append(provider)
        issues = self._validate(providers_config, self._providers)
        if issues:
            raise RegistryConfigError(issues)
    except BaseException:
        for p in instantiated:
            try:
                p.close()
            except Exception as e:
                log.debug("registry_boot_cleanup_failed",
                          provider=p.name, exc_type=type(e).__name__)
        raise
    self._raw_index = self._build_index(providers_config)
```

**Validation aggregation (DESIGN §7.2 / C11)**: the validator MUST accumulate ALL
`ConfigIssue` entries across all six checks before raising. Do NOT raise on the
first issue (fail-fast is FORBIDDEN here — the user must learn all problems at once).
The test `test_all_six_issue_families_in_one_error` validates this; a fail-fast
implementation will fail that test.

**IDCrossRef cycle detection (I2)**: use DFS with a `visited: set[str]` per starting
provider. For each provider P, walk `IDCrossRef[P] → IDCrossRef[next] → ...`. If a
node is revisited before terminal, report `ConfigIssue(code="idcrossref_cycle", ...)`.
Never enter the cycle a second time — a caller of `cross_ref()` would loop otherwise.

Run: `pytest tests/unit/api/metadata/registry/test_registry_validation.py -q`
Expected: all tests pass.

Run: `pytest tests/unit/api/metadata/registry/ -q`
Expected: all ≥45 tests pass.

Commit: `feat(registry): boot validation + factory complete — all unit tests pass`

---

### 0.6 — Characterization tests + bad_providers fixture + baseline measurement

**Files:**

- `tests/integration/scraper/test_legacy_fallback_snapshot.py`
- `tests/fixtures/bad_providers.json5`

Six characterization tests from DESIGN §8.4 (run against the UNCHANGED orchestrator):

```python
# tests/integration/scraper/test_legacy_fallback_snapshot.py
"""
Characterization tests: lock in current orchestrator.py behavior at lines 150
(movies TMDB-only) and 223 (TV TVDB+TMDB) BEFORE Phase 1 migration.
These tests must remain green throughout Phase 1 and Phase 2.
If any breaks, registry semantics diverge from current behavior.
"""

def test_movies_tmdb_circuit_open_produces_error(mock_orchestrator_with_open_tmdb):
    result = mock_orchestrator_with_open_tmdb.process_movies(movies_dir)
    assert result[0].action == "error"
    assert "circuit" in result[0].error.lower()

def test_movies_tmdb_circuit_open_mid_item_produces_error(mock_orchestrator):
    # Simulate CircuitOpenError raised during scrape call
    mock_orchestrator._tmdb.circuit.can_proceed.side_effect = CircuitOpenError(...)
    result = mock_orchestrator.process_movies(movies_dir)
    assert result[0].action == "error"

def test_tvshows_tvdb_open_tmdb_available_uses_tmdb(mock_orchestrator_tvdb_open):
    result = mock_orchestrator_tvdb_open.process_tvshows(shows_dir)
    # Should fall back to TMDB, not error
    assert result[0].action != "error"

def test_tvshows_both_open_produces_error(mock_orchestrator_both_open):
    result = mock_orchestrator_both_open.process_tvshows(shows_dir)
    assert result[0].action == "error"

def test_movies_network_error_produces_error(mock_orchestrator_network_fail):
    result = mock_orchestrator_network_fail.process_movies(movies_dir)
    assert result[0].action == "error"

def test_tvshows_tvdb_empty_search_no_fallback(mock_orchestrator_tvdb_empty):
    # Lock in current no-fallback behavior when TVDB returns empty
    result = mock_orchestrator_tvdb_empty.process_tvshows(shows_dir)
    assert result[0].action == "error"
```

**Pre-flight check before writing `tests/fixtures/bad_providers.json5` (I8)**:

```bash
# Pre-flight: confirm TMDBClient does NOT implement EpisodeFetcher,
# otherwise pick a guaranteed mismatch for the fixture.
python -c "
from personalscraper.api.metadata.tmdb import TMDBClient
from personalscraper.api.metadata._contracts import EpisodeFetcher
assert not isinstance(TMDBClient.__new__(TMDBClient), EpisodeFetcher), \
    'TMDB does implement EpisodeFetcher — pick another mismatch'
print('Confirmed: TMDBClient does NOT implement EpisodeFetcher')
"
```

Once the pre-flight confirms the mismatch, write the fixture concretely (remove
ambiguous comments):

`tests/fixtures/bad_providers.json5` — synthetic broken config that triggers all
six issue families simultaneously (needed for ACC-05b):

```json5
{
  // unknown_provider: "nobody" does not exist
  Searchable: { nobody: 1, tmdb: 2 },
  // empty_chain_section: no providers for MovieDetailsProvider
  MovieDetailsProvider: {},
  // protocol_mismatch: TMDBClient does not implement EpisodeFetcher (confirmed by pre-flight)
  EpisodeFetcher: { tmdb: 1 },
  // Remaining sections configured to trigger locked_capability_orphan + idcrossref_cycle
  TvDetailsProvider: { tvdb: 1 },
  RatingProvider: {},
  ArtworkProvider: { tmdb: 1 },
  KeywordProvider: {},
  VideoProvider: {},
  RecommendationProvider: {},
  // IDCrossRef cycle: tmdb → tvdb → tmdb
  IDValidator: { tmdb: 1, tvdb: 2 },
  IDCrossRef: { tmdb: 1, tvdb: 2 },
}
```

Record baseline measurements:

```bash
# Run and record outputs — the ACTUAL integers must be written to IMPLEMENTATION.md
# in sub-phase 0.7 (do NOT leave ${...} placeholders).
rg -l "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb" tests/ --type py | wc -l
pytest tests/e2e/ tests/integration/ -q 2>&1 | tail -1
pytest tests/unit/api/metadata/registry/ --collect-only -q | tail -1 | grep -oE "^[0-9]+"
```

Run: `make check`
Expected: exit 0. `ProviderRegistry` unreferenced outside its own package + tests.
Characterization tests pass against unchanged orchestrator.

Commit: `test(registry): characterization tests + bad_providers fixture + baseline measurements`

---

### 0.7 — Pin baseline values into IMPLEMENTATION.md and ACCEPTANCE.md

**Files:** `IMPLEMENTATION.md`, `ACCEPTANCE.md` (if exists at project root or
`docs/features/registry/ACCEPTANCE.md`)

Read the bash measurements recorded in sub-phase 0.6 and replace every
`${REGISTRY_UNIT_TEST_COUNT}` and `${BASELINE_PASS_COUNT}` placeholder with the
concrete integers. These placeholders violate the SH-16 deterministic-output rule
if left as-is in ACC-07 and ACC-09 command lines.

Steps:

1. Read the actual numbers produced by the bash commands in 0.6.
2. Edit `IMPLEMENTATION.md` to add a "Baseline measurements" section with the
   pinned counts (e.g. `REGISTRY_UNIT_TEST_COUNT=47`, `BASELINE_PASS_COUNT=1234`).
3. Edit `ACCEPTANCE.md` (or wherever ACC-07 / ACC-09 appear) to replace the
   `${...}` shell expansions with literal integers in the command expected-output
   column.

Example edit in ACCEPTANCE.md or IMPLEMENTATION.md:

```
# Before:
ACC-07 expected: ${REGISTRY_UNIT_TEST_COUNT}
ACC-09 expected: ${BASELINE_PASS_COUNT}

# After (with real numbers from 0.6):
ACC-07 expected: 47
ACC-09 expected: 1234
```

Commit: `chore(registry): pin baseline test counts into IMPL.md and ACC.md`

---

## On gate failure

If `## Phase gate` fails, do NOT proceed to the next phase. Revert the failing
sub-phase's commit (`git revert <sha>` for the most recent commit, or
`git reset --hard HEAD~N` for multiple) and re-invoke `/implement:phase` to retry
the sub-phase. The phase gate must be green before any cross-phase work continues.

---

## Phase gate

From DESIGN §9 Phase 0:

> `make check` passes; `ProviderRegistry` is unreferenced outside its own package
>
> - its tests; characterization tests run against the unchanged orchestrator and pass.

---

## ACC criteria touched

- **ACC-05a** — `tests/fixtures/bad_providers.json5` created (sub-phase 0.6)
- **ACC-05b** — broken config triggers aggregated `RegistryConfigError` (tested in 0.4/0.5c)
- **ACC-07** — unit test count ≥ 45 collected (sub-phases 0.5a/b/c); pinned in 0.7
- **ACC-09** — baseline pass count recorded in `IMPLEMENTATION.md` (sub-phase 0.6); pinned in 0.7
- **ACC-13** — characterization tests written and passing (sub-phase 0.6)

---

## Appendix A: Test name checklist (DESIGN §8.2)

Canonical list of unit test names the implementer must produce in sub-phase 0.4.
Each `[ ]` must be checked before the phase gate commit.

### `test_registry_chain.py`

- [ ] `test_chain_ordering_is_stable_across_calls`
- [ ] `test_chain_skips_open_circuit`
- [ ] `test_chain_includes_half_open_providers`
- [ ] `test_chain_half_open_raises_network_error_falls_to_next`
- [ ] `test_chain_wrong_semantic_raises` (e.g. `chain(RatingProvider)`)
- [ ] `test_chain_provider_flips_to_open_mid_iteration`
- [ ] `test_chain_empty_when_all_open`
- [ ] `test_chain_network_exception_skip`
- [ ] `test_chain_empty_result_skip`

### `test_registry_fan_out.py`

- [ ] `test_fan_out_all_eligible_iteration`
- [ ] `test_fan_out_excludes_open_circuit`
- [ ] `test_fan_out_empty_when_no_eligible`
- [ ] `test_fan_out_empty_when_all_capability_filtered`
- [ ] `test_fan_out_wrong_semantic_raises`
- [ ] `test_RegistryFanOutCompleted_always_emitted_even_on_success`

### `test_registry_locked.py`

- [ ] `test_locked_match_provider_path_no_xref`
- [ ] `test_locked_idcrossref_escape_xref_succeeds`
- [ ] `test_locked_circuit_open_along_xref_chain`
- [ ] `test_locked_returns_none_when_all_paths_blocked`
- [ ] `test_locked_returns_none_emits_LockedCapabilityUnresolved_event`
- [ ] `test_LockedProvider_construction_outside_registry_module_raises`

### `test_registry_validation.py`

- [ ] `test_missing_credentials_issue`
- [ ] `test_protocol_mismatch_issue`
- [ ] `test_unknown_provider_issue`
- [ ] `test_unknown_provider_includes_did_you_mean_suggestion`
- [ ] `test_empty_chain_section_issue`
- [ ] `test_locked_capability_orphan_issue`
- [ ] `test_idcrossref_cycle_detected_and_reported`
- [ ] `test_all_six_issue_families_in_one_error`
- [ ] `test_partial_boot_no_operation_callable`
- [ ] `test_boot_cleanup_on_validation_failure`

### `test_registry_introspection.py`

- [ ] `test_operations_returns_expected_shape`
- [ ] `test_operations_includes_mode_direct_entries`
- [ ] `test_status_returns_expected_shape`
- [ ] `test_providers_for_returns_raw_ordered_list`

### `test_registry_get.py`

- [ ] `test_get_known_name_returns_provider`
- [ ] `test_get_unknown_name_raises_UnknownProviderError`

### `test_registry_event_bus.py`

- [ ] `test_event_bus_none_accepted_no_op`
- [ ] `test_event_bus_emit_failure_does_not_propagate`
- [ ] `test_event_bus_emit_failure_logs_warning`
