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

### 0.1 — Error types + semantics map

**Files:** `_errors.py`, `_semantics.py`

Define the full exception hierarchy (DESIGN §7.1) and the capability→mode mapping (DESIGN §4, §5.1).

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

Commit: `feat(registry): error types + capability semantics map`

---

### 0.2 — Data structures + `ProviderRegistry` public shell

**Files:** `__init__.py` (new), `personalscraper/conf/models/providers.py` (new)

Implement all data structures from DESIGN §5.3 and the `ProviderRegistry` class
skeleton with all public methods raising `NotImplementedError`. Include `Mode` enum
and `Named` protocol.

Key data structures to include verbatim from DESIGN §5.3:

- `Mode(StrEnum)` with CHAIN/FAN_OUT/LOCKED/DIRECT
- `ProviderMatch` (frozen dataclass: `provider`, `id`, `media_type`, with `__post_init__` validation)
- `LockedProvider[C]` (frozen dataclass: `provider`, `bound_id`, `source_match`, `translated_via`)
- `AttemptOutcome` (frozen dataclass: `provider`, `reason` Literal, `detail`)
- `ProviderStatus` (frozen dataclass: with `failure_count_recent ≥ 0` validation)
- `ConfigIssue` (frozen dataclass: `code` Literal with 6 values, `section`, `provider`, `message`)
- `FanOutResult[C]` (frozen dataclass: `values`, `attempted`)

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
from personalscraper.api.metadata.registry import LockedProvider, ProviderMatch

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

def _make_locked(
    *,
    provider: object,
    bound_id: str,
    source_match: ProviderMatch,
    translated_via: str | None,
) -> LockedProvider:
    """Package-private constructor for LockedProvider.
    External callers cannot construct LockedProvider directly."""
    return LockedProvider(
        provider=provider,
        bound_id=bound_id,
        source_match=source_match,
        translated_via=translated_via,
    )

def _eligible(provider: object) -> bool:
    """Return True if provider circuit is CLOSED or HALF_OPEN (eligible for calls).
    Providers without a `.circuit` attribute are always eligible (e.g. fake providers)."""
    circuit = getattr(provider, "circuit", None)
    if circuit is None:
        return True
    state = getattr(circuit, "state", None)
    return state != "OPEN"
```

`_validation.py` — boot validators covering all six `ConfigIssue.code` families
(DESIGN §7.2): `missing_credentials`, `protocol_mismatch`, `unknown_provider`,
`empty_chain_section`, `locked_capability_orphan`, `idcrossref_cycle`. Uses
`difflib.get_close_matches` for `unknown_provider` suggestions.

`config.example/providers.json5` — exact content from DESIGN §5.4.

Commit: `feat(registry): factory, boot validation, config.example/providers.json5`

---

### 0.4 — Unit tests (TDD — all ~45 tests, DESIGN §8.2)

**Files:** all seven `tests/unit/api/metadata/registry/test_*.py`

Write tests first (they will fail until 0.5 implements the real logic). Each test
file covers the cases listed in DESIGN §8.2 verbatim. Use fake provider classes:

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

Key tests to include (examples from DESIGN §8.2):

```python
# test_registry_chain.py
def test_chain_ordering_stable(registry_with_two_providers):
    """chain() returns same order across repeated calls."""
    first  = registry_with_two_providers.chain(Searchable)
    second = registry_with_two_providers.chain(Searchable)
    assert [p.name for p in first] == [p.name for p in second]

def test_chain_skips_open_circuit(registry_with_open_provider):
    providers = registry_with_open_provider.chain(Searchable)
    assert all(p.circuit.state != "OPEN" for p in providers)

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
    with pytest.raises(RegistryConfigError) as exc:
        build_registry(bad_config)
    codes = {i.code for i in exc.value.issues}
    assert codes == {
        "missing_credentials", "protocol_mismatch", "unknown_provider",
        "empty_chain_section", "locked_capability_orphan", "idcrossref_cycle",
    }
```

```python
# test_registry_locked.py
def test_locked_returns_none_emits_event(registry, match, mock_bus):
    result = registry.locked(ArtworkProvider, match)
    assert result is None
    assert any(isinstance(e, LockedCapabilityUnresolved) for e in mock_bus.emitted)

def test_locked_provider_cannot_be_constructed_externally():
    with pytest.raises(Exception):
        LockedProvider(provider=..., bound_id="x", source_match=..., translated_via=None)
```

Commit: `test(registry): unit tests for all registry operations (TDD — expect failures)`

---

### 0.5 — Real implementation of `ProviderRegistry`

**Files:** `__init__.py` (implement all methods), `_factory.py` (complete), `_validation.py` (complete)

Replace all `NotImplementedError` stubs with real logic. The implementation must
make all unit tests from 0.4 pass. Key implementation notes:

- `chain(capability)`: verify capability ∈ `CHAIN_CAPABILITIES` (else `WrongSemanticBug`); filter `self._index[capability]` through `_eligible()`; return ordered list.
- `fan_out(capability)`: verify ∈ `FAN_OUT_CAPABILITIES`; return all eligible providers.
- `locked(capability, match)`: implement the 3-step algorithm from DESIGN §6.4 pseudocode.
- `get(name)`: return `self._providers[name]` or raise `UnknownProviderError`.
- `__init__`: run the full boot sequence from DESIGN §6.1 steps a–f; raise `RegistryConfigError` with all accumulated issues if any.
- `_event_bus_safe_emit`: catch all exceptions from `bus.emit()`, log `registry_event_emit_failed` at WARNING, never propagate.

Run: `pytest tests/unit/api/metadata/registry/ -q`
Expected: all ≥45 tests pass.

Commit: `feat(registry): implement ProviderRegistry — all unit tests pass`

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

`tests/fixtures/bad_providers.json5` — synthetic broken config that triggers all
six issue families simultaneously (needed for ACC-05b):

```json5
{
  // unknown_provider: "nobody" does not exist
  Searchable: { nobody: 1, tmdb: 2 },
  // empty_chain_section: no providers for MovieDetailsProvider
  MovieDetailsProvider: {},
  // protocol_mismatch: tmdb does not implement EpisodeFetcher (if it doesn't)
  EpisodeFetcher: { fake_wrong: 1 },
  // Remaining sections empty — triggers locked_capability_orphan + idcrossref_cycle
  TvDetailsProvider: { tvdb: 1 },
  RatingProvider: {},
  ArtworkProvider: { tmdb: 1 },
  KeywordProvider: {},
  VideoProvider: {},
  RecommendationProvider: {},
  IDValidator: {},
  IDCrossRef: {},
}
```

Record baseline measurements in `IMPLEMENTATION.md` (fill in the `${N}` placeholders):

```bash
# Run and record outputs:
rg -l "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb" tests/ --type py | wc -l
pytest tests/e2e/ tests/integration/ -q 2>&1 | tail -1
pytest tests/unit/api/metadata/registry/ --collect-only -q | tail -1 | grep -oE "^[0-9]+"
```

Run: `make check`
Expected: exit 0. `ProviderRegistry` unreferenced outside its own package + tests.
Characterization tests pass against unchanged orchestrator.

Commit: `test(registry): characterization tests + bad_providers fixture + baseline measurements`

---

## Phase gate

From DESIGN §9 Phase 0:

> `make check` passes; `ProviderRegistry` is unreferenced outside its own package
>
> - its tests; characterization tests run against the unchanged orchestrator and pass.

---

## ACC criteria touched

- **ACC-05a** — `tests/fixtures/bad_providers.json5` created (sub-phase 0.6)
- **ACC-05b** — broken config triggers aggregated `RegistryConfigError` (tested in 0.4/0.5)
- **ACC-07** — unit test count ≥ 45 collected (sub-phase 0.5)
- **ACC-09** — baseline pass count recorded in `IMPLEMENTATION.md` (sub-phase 0.6)
- **ACC-13** — characterization tests written and passing (sub-phase 0.6)
