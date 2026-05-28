# Design — Provider Registry (Scraper Orchestrator Decoupling)

> **Status**: Draft (brainstorm output) — pending user review then plan generation.
> **Date**: 2026-05-26
> **Roadmap item**: P1 — Provider Registry (Scraper Orchestrator Decoupling)
> **Version bump target**: 0.15.1 → 0.16.0 (minor)

---

## 1. Context & Problem

### 1.1 Current state

`personalscraper/scraper/orchestrator.py` instantiates metadata clients directly and embeds ad-hoc fallback logic per use-case:

- Line 80–98: `self._tmdb = TMDBClient(...)` + `self._tvdb = TVDBClient(...)` constructed from `settings`, `event_bus`, and `CircuitPolicy`.
- Line 150 (`process_movies`): `if not self._tmdb.circuit.can_proceed(): skip` — TMDB only, no fallback.
- Line 223 (`process_tvshows`): `if not self._tvdb.can_proceed() and not self._tmdb.can_proceed(): skip both` — TVDB primary, TMDB fallback hardcoded inside `match_tvshow`.

Thirteen files across the codebase consume `TMDBClient` / `TVDBClient` directly:

```
scraper/  (10):  orchestrator.py, scraper.py, movie_service.py, tv_service.py,
                 classifier.py, existing_validator.py, keywords_cache.py,
                 trailer_finder.py, confidence.py, _tvdb_convert.py

trailers/ (1):   trailers/orchestrator.py
library/  (1):   library/rescraper.py
commands/ (1):   commands/library/scan.py
```

Adding a new metadata provider (IMDB, SensCritique from the ROADMAP matrix) means modifying every consumer plus the orchestrator's hardcoded fallback. This is the explicit blocker called out in `ROADMAP.md` §P1.

### 1.2 What blocks downstream

- **Third-Party API Consumer Unification** (P0, completed in 0.11.0 partially): the unified clients need a registry to plug into.
- **Provider matrix expansion**: IMDB, SensCritique, and any future provider.

### 1.3 Existing groundwork (already in place)

The tech-debt 0.16.0 cycle (just merged) introduced the **atomic capability Protocols** at `personalscraper/api/metadata/_contracts.py`:

```
Searchable, MovieDetailsProvider, TvDetailsProvider, EpisodeFetcher,
RatingProvider, IDValidator, IDCrossRef, ArtworkProvider,
KeywordProvider, VideoProvider, RecommendationProvider
```

Each concrete provider (TMDBClient, TVDBClient, IMDBClient, OMDbClient, TraktClient, RottenTomatoesClient) implements a subset of these Protocols. **The registry reuses these Protocols as its capability keys**; it does not introduce a separate capability system.

---

## 2. Goals

1. Introduce a `ProviderRegistry` class that owns provider instantiation and exposes ordered, capability-keyed access to providers, replacing the hardcoded `self._tmdb` / `self._tvdb` pattern across all 13 consumers.
2. Make provider ordering **config-driven** per capability Protocol (`config/providers.json5`), not hardcoded.
3. Make the registry **circuit-breaker aware**: providers whose circuit is OPEN are skipped from the eligible-list returned by registry operations.
4. Expose **three operations** matching the actual call patterns: `chain` (ordered fallback), `fan_out` (parallel aggregation), `locked` (identity-bound to the match's provider, with `IDCrossRef` escape hatch).
5. Validate strictly at boot: every provider listed in config must implement the Protocol of its section, and its credentials must be present in the environment. Otherwise the process refuses to start.
6. Provide an **introspection API** (`status()`, `operations()`, `providers_for()`) usable by a future Web UI and the existing CLI.
7. Eliminate every direct reference to `TMDBClient` / `TVDBClient` outside `api/metadata/`. After this feature, those classes are only instantiated by the registry.

## 3. Non-goals (explicit, validated during brainstorm)

- **Runtime provider hot-swap**. The pipeline runs by batch; config changes take effect on next launch.
- **Active health scoring beyond the existing circuit breaker**. No rolling latency scores, no adaptive reordering, no quality scoring. The existing `CircuitPolicy` (`failure_threshold` + `cooldown_seconds`) remains the sole automated reaction to provider failure.
- **Aggregating fuzzy-score / partial-response handling at the registry level**. Score-below-threshold and incomplete-field fallback stay in the scrape layer (where domain logic lives). Registry triggers fallback on three deterministic events only: circuit OPEN, network exception, empty result.
- **Health passive metrics** (success/failure counters per provider exposed for user-driven reordering). Out of scope — could be added later as a separate small feature, but not bundled here.
- **CLI tooling beyond a minimal `info providers` listing**. The Web UI is the planned surface for richer interaction; CLI stays minimal.

---

## 4. Capability semantics — the three modes

Not every Protocol behaves the same way under multi-provider conditions. The registry imposes the correct semantic per capability:

| Mode          | Protocols                                                                       | Behavior                                                                                                                                                             | Return on exhaustion                            |
| ------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **`chain`**   | `Searchable`, `MovieDetailsProvider`, `TvDetailsProvider`, `EpisodeFetcher`     | Try providers in config order; first one that returns a usable result wins.                                                                                          | `raise ProviderExhausted`                       |
| **`fan_out`** | `RatingProvider`                                                                | Call **all** eligible providers, aggregate results.                                                                                                                  | Return empty list (no error — best-effort data) |
| **`locked`**  | `ArtworkProvider`, `KeywordProvider`, `VideoProvider`, `RecommendationProvider` | Use the provider that produced the original match. If it lacks the capability, translate the match's ID via `IDCrossRef` to a provider that has it, in config order. | Return `None`                                   |
| **`direct`**  | `IDValidator`, `IDCrossRef`                                                     | No semantic. Dispatched by explicit provider name (`registry.get("tmdb").validate(id)`).                                                                             | N/A                                             |

The mode-per-capability mapping is **code-owned**, not config-owned. Source of truth: `api/metadata/registry/_semantics.py`. A user cannot change a capability's mode through config — they only configure the ordered list of providers.

Rationale (validated during brainstorm): the mode is an intrinsic property of the capability (e.g. ratings ARE inherently fan-out; you don't take "the first TMDB rating and stop"). Exposing it as a user choice creates false flexibility — the user would always pick the same value because there is no useful alternative. A future Web UI obtains the mode via `registry.operations()` introspection rather than reading it from config.

---

## 5. Architecture

### 5.1 Module layout

```
personalscraper/
├── api/
│   └── metadata/
│       ├── _contracts.py             (existing — capability Protocols)
│       ├── tmdb.py / tvdb.py / ...   (existing — provider concretes, unchanged)
│       └── registry/                 (NEW)
│           ├── __init__.py           ProviderRegistry (public class)
│           ├── _semantics.py         Capability → Mode mapping (chain/fan_out/locked/direct)
│           ├── _factory.py           Provider-name → class, instantiation from settings
│           ├── _validation.py        Boot validators (Protocol, credentials, semantic coherence)
│           └── _errors.py            RegistryError + subclasses
└── conf/
    └── models/
        ├── config.py                 (modified — adds `providers: ProvidersConfig`)
        └── providers.py              (NEW — Pydantic ProvidersConfig)

config.example/
└── providers.json5                   (NEW — config template with defaults)
```

Total new code estimated at ~520 LOC. Largest single file (`__init__.py`) under 200 LOC, well within the project's 800-LOC soft-warning ceiling.

### 5.2 Class shape

The registry exposes generic, statically-typed operations. The chain/fan_out/locked
partition is encoded in the type system via `@overload` so that mypy refuses
`chain(RatingProvider)` at type-check time. `WrongSemanticBug` (§7.1) becomes a
belt-and-suspenders runtime guard, not the primary safety net.

A small `Named` Protocol gives every provider a stable `.name` accessor used by
diagnostic events (§7.4) and the introspection API.

```python
# api/metadata/registry/__init__.py

# --- Mode-typed capability unions (mirrors §4, source of truth: _semantics.py) ---

ChainCapability = Searchable | MovieDetailsProvider | TvDetailsProvider | EpisodeFetcher
FanOutCapability = RatingProvider
LockedCapability = ArtworkProvider | KeywordProvider | VideoProvider | RecommendationProvider
DirectCapability = IDValidator | IDCrossRef

# --- Provider name carrier ---

class Named(Protocol):
    """Every concrete provider implements this — `name` is the stable string used
    in config keys, events, logs, and introspection (e.g. `"tmdb"`, `"tvdb"`)."""
    name: ClassVar[str]

# Aliased ProviderName carries provider-identity intent at the type level.
ProviderName = NewType("ProviderName", str)


class ProviderRegistry:
    """Registry of metadata providers, capability-keyed and circuit-aware.

    Instantiated once at pipeline boot from settings + providers_config.
    Validates config at construction; refuses to construct on any inconsistency.
    Immutable post-construction (no hot-swap — see §3 non-goals).
    """

    def __init__(
        self,
        *,
        settings: Settings,
        event_bus: EventBus,
        cb_policy: CircuitPolicy,
        providers_config: ProvidersConfig,
    ) -> None:
        ...   # see Section 6 for boot sequence

    # --- The three semantic operations — statically-typed via overloads ---

    @overload
    def chain[C: ChainCapability](self, capability: type[C]) -> list[C]: ...
    def chain(self, capability):
        """Ordered list of eligible providers for chain capabilities.

        An eligible provider has a circuit state of CLOSED or HALF_OPEN
        (HALF_OPEN is included as a probe — see §7.6).

        Stable ordering: subsequent calls with the same capability return providers
        in the same order (modulo circuit-state changes between calls).

        Raises:
            WrongSemanticBug: if capability is not a chain capability
                (caught at static type check; runtime guard only).
        """

    @overload
    def fan_out[C: FanOutCapability](self, capability: type[C]) -> list[C]: ...
    def fan_out(self, capability):
        """All eligible providers (circuit CLOSED or HALF_OPEN), in config order,
        for fan-out capabilities. May return an empty list — `[]` is not an error;
        the caller decides whether absence of data matters.

        Raises:
            WrongSemanticBug: if capability is not a fan_out capability.
        """

    @overload
    def locked[C: LockedCapability](
        self,
        capability: type[C],
        match: ProviderMatch,
    ) -> LockedProvider[C] | None: ...
    def locked(self, capability, match):
        """Provider bound to the match's id (post-IDCrossRef translation if needed).

        Algorithm:
          1. If the match's provider implements `capability` and its circuit is
             eligible (CLOSED or HALF_OPEN), return it wrapped with the match's id.
          2. Otherwise, walk `chain(capability)` in config order; for each candidate
             provider, attempt `IDCrossRef` translation of the match id via the
             match's provider. First successful translation → return wrapped
             `LockedProvider`. Emit `registry_locked_xref` DEBUG.
          3. No translation path exists → return None and emit
             `LockedCapabilityUnresolved` on the EventBus (§7.4) so callers'
             absence of data is observable, not silent.

        Raises:
            WrongSemanticBug: if capability is not a locked capability.
        """

    # --- Direct dispatch (IDValidator, IDCrossRef) ---

    def get(self, provider_name: str) -> Named:
        """Return a provider by name.

        Raises:
            UnknownProviderError: if the name is not registered. (Inherits from
            RegistryError — never a bare KeyError; see §7.1.)
        """

    def cross_ref(
        self,
        match: ProviderMatch,
        *,
        target: str,
    ) -> str | None:
        """Translate a match's id to another provider's id space via IDCrossRef.

        Returns the target-provider id, or None if no translation path exists
        (provider missing from config, no IDCrossRef capability, or upstream
        empty response).
        """

    # --- Introspection (Web UI / CLI) ---

    def operations(self) -> dict[type[Protocol], Mode]:
        """Map every known capability to its semantic mode (chain / fan_out /
        locked / direct). Mode.DIRECT is included for completeness; the Web UI
        treats DIRECT specially (no ordered fallback, just provider-name dispatch
        via `get()`)."""

    def status(self) -> dict[str, ProviderStatus]:
        """Per-provider circuit state and recent counters. Snapshot at call time;
        not live-subscribable (subscribe to CircuitBreakerOpened/Closed/HalfOpened
        on the EventBus for live updates)."""

    def providers_for(self, capability: type[Protocol]) -> list[Named]:
        """Raw ordered list (no circuit filtering). Used by introspection only —
        callers wanting eligible-only providers must use chain / fan_out / locked."""

    def close(self) -> None:
        """Release any per-provider resources (HTTP sessions, etc.). Called by the
        pipeline boot site's `finally` block. Safe to call multiple times."""
```

### 5.3 Data structures

```python
# api/metadata/registry/__init__.py

class Mode(StrEnum):
    """Capability dispatch mode. Source of truth: api/metadata/registry/_semantics.py."""
    CHAIN = "chain"
    FAN_OUT = "fan_out"
    LOCKED = "locked"
    DIRECT = "direct"


@dataclass(frozen=True)
class ProviderMatch:
    """Identifies a media item by (provider, id) pair. Invariants enforced in
    __post_init__: `provider` must be non-empty; `id` must be non-empty. The
    registry validates that `provider` corresponds to a configured provider at
    every call site that accepts a ProviderMatch."""
    provider: ProviderName   # NewType("ProviderName", str)
    id: str
    media_type: MediaType

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError("ProviderMatch.provider must be non-empty")
        if not self.id:
            raise ValueError("ProviderMatch.id must be non-empty")


@dataclass(frozen=True)
class LockedProvider[C]:
    """A provider bound to a specific id with full provenance.

    Construction is package-private: only `ProviderRegistry.locked()` creates
    instances (see `_make_locked` in `_factory.py`). Callers may NOT construct
    LockedProvider directly — `__init__` raises if called outside the registry's
    module.

    The provenance (source_match + translated_via) lets diagnostic events and
    the future Web UI render "TVDB→TMDB cross-ref" without re-deriving it.
    """
    provider: C                        # carries the capability Protocol
    bound_id: str                      # the id usable directly with `provider`
    source_match: ProviderMatch        # the original match this locked instance derives from
    translated_via: str | None         # provider name that performed the IDCrossRef,
                                       # or None if `provider` is the match's own provider


@dataclass(frozen=True)
class AttemptOutcome:
    """One row of `ProviderExhausted.attempted` — used for diagnostics and metrics.

    `reason` is a closed Literal so downstream consumers (ScrapeResult, metrics,
    EventBus event payloads) can dispatch on a stable enum, not free-form strings.
    """
    provider: ProviderName
    reason: Literal["circuit_open", "network", "empty_result", "other"]
    detail: str | None = None          # exc_type or human-readable extra context


@dataclass(frozen=True)
class ProviderStatus:
    """Per-provider runtime status snapshot."""
    name: ProviderName
    circuit_state: Literal["CLOSED", "OPEN", "HALF_OPEN"]
    failure_count_recent: int
    last_success_at: datetime | None
    last_failure_at: datetime | None

    def __post_init__(self) -> None:
        if self.failure_count_recent < 0:
            raise ValueError("ProviderStatus.failure_count_recent must be ≥ 0")


@dataclass(frozen=True)
class ConfigIssue:
    """One structured row inside RegistryConfigError (see §7.1).

    Carries a stable `code` so tests can assert on a closed set of issue codes
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
    section: str                       # e.g. "Searchable"
    provider: ProviderName | None      # e.g. "rotten_tomatoes" (None when section-level)
    message: str                       # human-readable detail, includes "did you mean" suggestion
                                       # via difflib.get_close_matches when applicable


@dataclass(frozen=True)
class FanOutResult[C]:
    """Result of a fan_out call — carries values AND attempted-outcome provenance.

    Empty `values` is not an error, but the caller can still distinguish
    "0 providers tried" from "3 providers tried, 0 succeeded" via `attempted`.
    """
    values: list[C]
    attempted: list[AttemptOutcome]    # one row per provider in the eligible list at call time


# Convention used in §6.x and elsewhere
type Capability = type[Protocol]   # alias for clarity in signatures
```

**Naming/enum convention** (per type-design review): `Mode` is an enum for
registry-owned state (`operations()` introspection); `Literal[...]` is reserved
for snapshot/serialization views (e.g. `circuit_state` mirrors the underlying
HttpTransport string wire-format, not a registry-owned enum).

**Provider name dual surface** (per type-design sub-phase 8.4, Option B): the
project uses TWO distinct provider-name types at different architectural layers:

- `personalscraper.api._contracts.ProviderName` — a **closed `str`-Enum** of the
  real providers known to the transport-config layer (TMDB, TVDB, OMDB, TRAKT,
  QBITTORRENT, TRANSMISSION, LACALE, C411, TELEGRAM, HEALTHCHECKS). Code that
  builds `Settings`, constructs `HttpTransport`, or dispatches on a fixed
  provider family uses this Enum.

- `personalscraper.api.metadata.registry.RegistryProviderName` — an **open
  `NewType` over `str`** for the registry layer. The registry is a capability-
  keyed dispatch framework that accepts any provider name supplied by user
  config (`config/providers.json5`), including names that do not correspond to
  a transport-layer provider (e.g. synthetic test fixtures using `"multi"` /
  `"xref"`). A closed Enum would be too restrictive here — the registry does
  not own the set of valid provider names; user config does.

The boundary is explicit: code in `personalscraper/api/` (transport contracts,
settings, HTTP policy) uses the Enum; code in `personalscraper/api/metadata/
registry/` (capability dispatch, provider iteration, introspection) uses the
NewType. The two coexist by design — the registry is layered above transport.
Cycle 1 review caught a single-name conflict (both were called `ProviderName`
at one point, causing silent type aliasing because Enum subclasses `str`).
Option A (unify all names on the Enum) was rejected because it would pollute the
production Enum with test-only synthetic members. Option B retains both types
with the explicit layering boundary documented here.

### 5.4 Config shape

`config/providers.json5` — per capability Protocol, integer priority (lower = higher priority):

```json5
{
  // Chain capabilities — ordered fallback
  Searchable: { tvdb: 1, tmdb: 2, imdb: 3 },
  MovieDetailsProvider: { tmdb: 1, tvdb: 2 },
  TvDetailsProvider: { tvdb: 1, tmdb: 2, imdb: 3 },
  EpisodeFetcher: { tvdb: 1, tmdb: 2 },

  // Fan-out capabilities — aggregation order
  RatingProvider: { tmdb: 1, omdb: 2, rotten_tomatoes: 3, trakt: 4 },

  // Locked capabilities — fallback order when IDCrossRef must be used
  ArtworkProvider: { tmdb: 1, tvdb: 2 },
  KeywordProvider: { tmdb: 1 },
  VideoProvider: { tmdb: 1 },
  RecommendationProvider: { tmdb: 1, trakt: 2 },

  // Direct-dispatch capabilities — list of providers that can perform direct lookup
  IDValidator: { tmdb: 1, tvdb: 2, imdb: 3, trakt: 4 },
  IDCrossRef: { tmdb: 1, tvdb: 2, imdb: 3, trakt: 4 },
}
```

`conf/models/providers.py` parses this into a typed `ProvidersConfig` with Pydantic:

```python
# conf/models/providers.py

# Stable string → Protocol mapping. The string keys are FROZEN — renaming a
# Protocol class never changes the user-facing config key. Source of truth lives
# in api/metadata/registry/_semantics.py and is re-exported here for parsing.
CAPABILITY_KEYS: dict[str, type[Protocol]] = {
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


class ProvidersConfig(BaseModel):
    """Pydantic root model for config/providers.json5.

    Strict: unknown sections raise (extra=forbid). Each section maps provider
    name (str) → priority (positive int). Priority uniqueness within a section
    is validated.
    """
    model_config = ConfigDict(extra="forbid")

    Searchable:             dict[str, PositiveInt] = Field(default_factory=dict)
    MovieDetailsProvider:   dict[str, PositiveInt] = Field(default_factory=dict)
    TvDetailsProvider:      dict[str, PositiveInt] = Field(default_factory=dict)
    EpisodeFetcher:         dict[str, PositiveInt] = Field(default_factory=dict)
    RatingProvider:         dict[str, PositiveInt] = Field(default_factory=dict)
    ArtworkProvider:        dict[str, PositiveInt] = Field(default_factory=dict)
    KeywordProvider:        dict[str, PositiveInt] = Field(default_factory=dict)
    VideoProvider:          dict[str, PositiveInt] = Field(default_factory=dict)
    RecommendationProvider: dict[str, PositiveInt] = Field(default_factory=dict)
    IDValidator:            dict[str, PositiveInt] = Field(default_factory=dict)
    IDCrossRef:             dict[str, PositiveInt] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _no_duplicate_priorities(self) -> "ProvidersConfig":
        for name, section in self.model_dump().items():
            priorities = list(section.values())
            if len(priorities) != len(set(priorities)):
                raise ValueError(
                    f"Section {name!r} has duplicate priority values: {priorities}"
                )
        return self
```

Renaming `Searchable` to `SearchCapability` in the future would require updating
`CAPABILITY_KEYS` and the `ProvidersConfig` field name; the legacy string key
can be deprecated with a Pydantic alias if needed. The point of the stable
mapping is that the JSON key is independent of Python class identity changes
within a release cycle.

---

## 6. Data flow

### 6.1 Boot sequence

```
core/pipeline.py (or equivalent boot site)
    1. settings = Settings.from_env()
    2. config   = Config.from_files(...)
    3. event_bus = EventBus()
    4. registry = ProviderRegistry(
           settings=settings,
           event_bus=event_bus,
           cb_policy=CircuitPolicy.from_thresholds(config.thresholds),
           providers_config=config.providers,
       )
       # Inside __init__:
       a. Instantiate every provider mentioned in any config section once.
          Track instantiated providers in a list as they are created.
       b. For each section, verify every listed provider implements the Protocol
          (uses runtime_checkable isinstance — cheap, ~66 checks for 6×11).
          Complement: a mypy-driven test (assert_type at the Protocol level)
          checks signatures during CI, since runtime_checkable only checks
          attribute presence.
       c. For each instantiated provider, verify credentials present in settings.
       d. Verify each `locked` capability has an IDCrossRef path from every
          **configured match-provider** — that is, providers listed in any chain
          capability (Searchable, Movie/Tv/EpisodeDetailsProvider). Not the
          combinatorial product of all known providers; only those a real match
          can come from. Also detect cycles in the IDCrossRef graph (e.g.
          tmdb→tvdb→tmdb) and report them as the `idcrossref_cycle` ConfigIssue.
       e. Build the **raw ordered index** `dict[Capability, list[provider_name]]`.
          This index is static; per-call circuit filtering is applied on top by
          chain/fan_out/locked.
       f. Accumulate all issues into `list[ConfigIssue]`. If non-empty, close all
          previously-instantiated providers via `provider.close()` (best-effort,
          swallow per-provider close errors but log them), then raise a single
          RegistryConfigError carrying the structured issue list. Issue ordering
          in the message is grouped by section, then by code, then by provider —
          so typos and "did you mean" suggestions appear next to each other.
    5. orchestrator = Scraper(settings, patterns, registry=registry, ...)
    6. try: pipeline.run(...)
       finally: registry.close()
```

Step (f)'s aggregated message uses `difflib.get_close_matches(unknown, known, n=1, cutoff=0.7)`
to render "did you mean" suggestions for `unknown_provider` issues.

### 6.2 Runtime — `chain` (TV match)

```python
# scraper/tv_service.py
providers = self._registry.chain(Searchable)        # mypy: list[Searchable]
attempted: list[AttemptOutcome] = []
match: ProviderMatch | None = None

for provider in providers:
    try:
        candidates = provider.search("Breaking Bad")
        if not candidates:
            # Empty-result is a fallback trigger — log it explicitly so the
            # chain-shrinking signal is never silent (§7.3 fix).
            attempted.append(AttemptOutcome(
                ProviderName(provider.name), "empty_result"))
            log.debug("registry_provider_skip", provider=provider.name,
                      capability="Searchable", reason="empty_result")
            continue
        chosen = best_match(candidates, "Breaking Bad", 2008)
        if chosen is None:
            attempted.append(AttemptOutcome(
                ProviderName(provider.name), "empty_result",
                detail="no candidate met confidence threshold"))
            continue
        match = ProviderMatch(
            provider=ProviderName(provider.name),
            id=chosen.id,
            media_type=MediaType.TV,
        )
        break
    except CircuitOpenError as e:
        attempted.append(AttemptOutcome(
            ProviderName(provider.name), "circuit_open"))
        log.debug("registry_provider_skip", provider=provider.name,
                  capability="Searchable", reason="circuit_open")
        continue
    except NetworkError as e:
        attempted.append(AttemptOutcome(
            ProviderName(provider.name), "network",
            detail=type(e).__name__))
        log.warning("registry_provider_fail", provider=provider.name,
                    capability="Searchable", exc_type=type(e).__name__)
        continue

if match is None:
    raise ProviderExhausted(
        capability=Searchable,
        attempted=attempted,
        item_context={"title": "Breaking Bad", "year": 2008, "media_type": "tv"},
    )
```

Note: `HALF_OPEN` circuits are eligible (treated as probe by `HttpTransport`).
A probe failure raises `NetworkError` from the transport and falls through to
the next provider in the same iteration — no special handling at the registry
level. See §7.6.

### 6.3 Runtime — `fan_out` (ratings — illustrative shape)

The only current consumer of `get_notations` is `indexer/backfill_ids.py`, which lives
in the indexer package and is **outside the Big Bang scope** of this feature (see §11).
The registry ships fan_out semantics fully wired and unit-tested with fake consumers;
migrating `indexer/backfill_ids.py` to `registry.fan_out(RatingProvider)` is a deliberate
follow-up feature. The example below is illustrative of the intended usage shape.

```python
# Illustrative — not a file created by this feature.
providers = self._registry.fan_out(RatingProvider)   # mypy: list[RatingProvider]
collected: list[Notations] = []
attempted: list[AttemptOutcome] = []

for provider in providers:
    try:
        # Determine the id usable with this provider.
        if match.provider == provider.name:
            local_id = match.id
        else:
            local_id = self._registry.cross_ref(match, target=provider.name)
            if local_id is None:
                attempted.append(AttemptOutcome(
                    ProviderName(provider.name), "empty_result",
                    detail="idcrossref returned None"))
                continue
        rating = provider.get_notations(local_id, media_type=match.media_type)
        if rating is None:
            attempted.append(AttemptOutcome(
                ProviderName(provider.name), "empty_result"))
            continue
        collected.append(rating)
        attempted.append(AttemptOutcome(
            ProviderName(provider.name), "other",
            detail="ok"))
    except CircuitOpenError:
        attempted.append(AttemptOutcome(
            ProviderName(provider.name), "circuit_open"))
    except NetworkError as e:
        attempted.append(AttemptOutcome(
            ProviderName(provider.name), "network",
            detail=type(e).__name__))

# Always emit registry_fan_out_partial — even on full success — so the EventBus
# carries a complete provenance row for every fan_out call. The caller may
# inspect `attempted` for diagnostics without log-scraping.
self._registry._emit_fan_out_partial(
    capability=RatingProvider,
    attempted=attempted,
    succeeded=len(collected),
)
return FanOutResult(values=collected, attempted=attempted)
```

`cross_ref()` is the registry method declared in §5.2 — the caller never knows
which provider performed the translation, only the resulting id (or None).

### 6.4 Runtime — `locked` (artwork)

```python
# scraper/artwork.py (caller side)
locked = self._registry.locked(ArtworkProvider, match)   # mypy: LockedProvider[ArtworkProvider] | None
if locked is None:
    # The registry has already emitted LockedCapabilityUnresolved on the EventBus
    # AND logged registry_locked_unresolved at WARNING — the caller is free to
    # treat absence as "best-effort missing" without scraping logs.
    log.warning("artwork_unresolved", match=match)
    return ArtworkResult.empty()

# Provenance is available on the locked instance for diagnostics:
#   locked.source_match    → original match
#   locked.translated_via  → name of the IDCrossRef provider, or None
#   locked.bound_id        → the id usable directly with locked.provider
urls = locked.provider.get_artwork_urls(locked.bound_id, media_type=match.media_type)
```

Internal algorithm of `ProviderRegistry.locked()` (declared in §5.2):

```python
# Pseudocode — actual implementation lives in api/metadata/registry/_factory.py
def locked(self, capability, match):
    # 1. Try the match's own provider
    own = self._providers.get(match.provider)
    if own is not None and isinstance(own, capability) and self._eligible(own):
        return _make_locked(
            provider=own,
            bound_id=match.id,
            source_match=match,
            translated_via=None,
        )

    # 2. Walk the configured chain for this capability, translating ids via IDCrossRef
    for candidate in self.chain(capability):
        if candidate.name == match.provider:
            continue
        xref_id = self.cross_ref(match, target=candidate.name)
        if xref_id is None:
            continue
        return _make_locked(
            provider=candidate,
            bound_id=xref_id,
            source_match=match,
            translated_via=match.provider,
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

`LockedProvider` is constructed exclusively via `_make_locked` inside the registry's
package (module-private). External callers cannot construct `LockedProvider` directly
(construction check in `__init__`), which is the only way to guarantee the invariant
that `bound_id` is usable with `provider` and the provenance reflects reality.

### 6.5 Introspection (for Web UI / CLI)

```python
>>> registry.status()
{
  "tmdb": ProviderStatus(circuit_state="CLOSED", failure_count_recent=0, ...),
  "tvdb": ProviderStatus(circuit_state="HALF_OPEN", failure_count_recent=3, ...),
  "imdb": ProviderStatus(circuit_state="OPEN", ...),
}

>>> registry.operations()
{
  Searchable:             Mode.CHAIN,
  MovieDetailsProvider:   Mode.CHAIN,
  TvDetailsProvider:      Mode.CHAIN,
  EpisodeFetcher:         Mode.CHAIN,
  RatingProvider:         Mode.FAN_OUT,
  ArtworkProvider:        Mode.LOCKED,
  KeywordProvider:        Mode.LOCKED,
  VideoProvider:          Mode.LOCKED,
  RecommendationProvider: Mode.LOCKED,
  IDValidator:            Mode.DIRECT,
  IDCrossRef:             Mode.DIRECT,
}
```

---

## 7. Error handling

### 7.1 Exception hierarchy

```python
class RegistryError(Exception): ...

class RegistryConfigError(RegistryError):
    """Config inconsistency detected at boot. Pipeline must not start.
    Carries a structured `list[ConfigIssue]` (§5.3) so tests assert on `code`
    rather than substring-matching the human message."""
    issues: list[ConfigIssue]

    def __init__(self, issues: list[ConfigIssue]) -> None:
        self.issues = issues
        super().__init__(self._format(issues))

    @staticmethod
    def _format(issues: list[ConfigIssue]) -> str:
        """Group by (section, code), render with did-you-mean suggestions next to typos."""
        ...

class UnknownProviderError(RegistryError):
    """`registry.get(name)` was called with a name that is not registered.
    Replaces the generic KeyError so all registry failures share a base class."""
    name: str

class ProviderExhausted(RegistryError):
    """All chain providers failed for an item.
    Carries the attempted list (structured AttemptOutcome, §5.3) and item context."""
    capability: type[Protocol]
    attempted: list[AttemptOutcome]
    item_context: dict[str, Any] | None

class WrongSemanticBug(RegistryError):
    """Caller invoked the wrong registry operation for a capability.
    Programmer bug — must NOT be caught. The name "Bug" (not "Error") signals
    to readers and to a project lint rule that this exception is never recoverable.
    Type overloads in §5.2 catch most of these at mypy time; this runtime exception
    is the belt-and-suspenders backstop."""
```

A project-level lint rule will forbid `except WrongSemanticBug` and `except RegistryError`
around `registry.*` call sites (a `ruff` custom rule or a grep-based pre-commit check).

### 7.2 Boot-time errors (aggregated)

Six families of `RegistryConfigError` causes, all detected and reported in a single multi-line message:

1. **Missing credentials**: provider listed but `*_API_KEY` not in environment.
2. **Protocol mismatch**: provider listed under a section it doesn't implement.
3. **Unknown provider name**: typo, with "did you mean" suggestion.
4. **Empty chain section**: any `chain` capability with zero providers is fatal (orchestrator depends on it).
5. **Locked-capability orphan**: provider in `MovieDetailsProvider` whose ID can't be translated to any provider in `ArtworkProvider`/`KeywordProvider`/etc. via the configured `IDCrossRef`.
6. **Empty config sections for required-by-code use cases**: any capability with zero providers but required by code paths.

### 7.3 Runtime behavior matrix

| Error                  | When             | Behavior                                                                                                                                       |
| ---------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `RegistryConfigError`  | Boot             | Process dies, all issues listed                                                                                                                |
| `WrongSemanticBug`     | Runtime per-call | Fail-loud (programmer bug); never caught. Project lint rule forbids `except` around `registry.*` call sites.                                   |
| `UnknownProviderError` | Runtime per-call | Fail-loud (caller bug); never silent fallback.                                                                                                 |
| `ProviderExhausted`    | Runtime per-item | Catch in caller, produce `ScrapeResult(action="error")`, pipeline continues to next item                                                       |
| `CircuitOpenError`     | Runtime per-call | DEBUG-log `registry_provider_skip` (reason=circuit_open) + add to `attempted`; try next. Already observable via `CircuitBreakerOpened` event.  |
| `NetworkError`         | Runtime per-call | WARN-log `registry_provider_fail` + add to `attempted`; try next. Higher log level because circuit hasn't tripped yet — degraded but not down. |
| Empty-result           | Runtime per-call | DEBUG-log `registry_provider_skip` (reason=empty_result) + add to `attempted`; try next. **No longer silent** — fixes the chain-shrinking gap. |

### 7.4 EventBus integration

The registry emits structured events for observability. Every event class
specifies its payload fields below — the type of `reason` mirrors
`AttemptOutcome.reason` (§5.3) so consumers dispatch on a closed Literal.

| Event class                  | When                                                | Payload                                                                                                                                                                  |
| ---------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ProviderFallbackTriggered`  | A `chain` moved from one provider to the next       | `capability: str`, `from_provider: str`, `to_provider: str`, `reason: Literal["circuit_open","network","empty_result"]`, `exc_type: str \| None`, `item: dict[str, Any]` |
| `ProviderExhaustedEvent`     | All providers in a chain failed for an item         | `capability: str`, `attempted: list[AttemptOutcome]`, `item: dict[str, Any]`                                                                                             |
| `LockedCapabilityUnresolved` | `locked()` could not bind a provider via IDCrossRef | `capability: str`, `match: ProviderMatch`, `chain_tried: list[str]`                                                                                                      |
| `RegistryFanOutCompleted`    | `fan_out` returned (always, even on full success)   | `capability: str`, `attempted: list[AttemptOutcome]`, `succeeded: int`                                                                                                   |
| `RegistryBootValidated`      | Boot completed successfully                         | `providers: list[str]`, `capabilities: dict[str, list[str]]`                                                                                                             |

Circuit-breaker events (`CircuitBreakerOpened`/`Closed`/`HalfOpened`) keep flowing
from the underlying `HttpTransport`; the registry does not re-emit them.

**EventBus failure mode**: all emissions go through `_event_bus_safe_emit` which
catches any exception from `bus.emit()` and logs `registry_event_emit_failed` at
WARNING. A broken bus never crashes the registry. The bus is always a real
EventBus per the project architectural contract (event-bus 0.14.0); tests pass a
MockEventBus or FailingEventBus rather than None.

### 7.5 Logging conventions

Per `docs/reference/logging.md`:

| Event name                   | Level   | Context fields                                                                                 |
| ---------------------------- | ------- | ---------------------------------------------------------------------------------------------- |
| `registry_boot_loaded`       | INFO    | providers_count, capabilities_count                                                            |
| `registry_provider_skip`     | DEBUG   | provider, capability, reason (Literal: circuit_open/empty_result)                              |
| `registry_provider_fail`     | WARNING | provider, capability, exc_type, item                                                           |
| `registry_chain_exhausted`   | ERROR   | capability, attempted (structured), item                                                       |
| `registry_fan_out_partial`   | INFO    | capability, providers_tried, providers_eligible (emitted on EVERY fan_out, success or partial) |
| `registry_locked_xref`       | DEBUG   | source_provider, target_provider, xref_id                                                      |
| `registry_locked_unresolved` | WARNING | capability, match, chain_tried                                                                 |
| `registry_event_emit_failed` | WARNING | event_class, exc_type — emitted when the EventBus fails to deliver                             |

### 7.6 Circuit state — chain/fan_out/locked eligibility rule

Eligibility for chain/fan_out/locked: a provider is eligible if its circuit
state is `CLOSED` OR `HALF_OPEN`. `OPEN` is the only ineligible state.

`HALF_OPEN` is treated as a probe: the underlying `HttpTransport` lets exactly
one request through; if it fails, the transport raises `NetworkError` and
trips the circuit back to `OPEN`. The registry catches the `NetworkError`,
logs `registry_provider_fail`, and falls through to the next provider in the
same iteration. The HALF_OPEN provider does not "burn" the current item — the
next eligible provider gets the call.

If the probe succeeds, the transport flips to `CLOSED`. Subsequent items see
a healthy provider.

---

## 8. Testing strategy

### 8.1 Levels

| Level            | Cible                                               | Location                                                     | Volume                                                      |
| ---------------- | --------------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------- |
| Unit             | Pure registry logic with fake providers             | `tests/unit/api/metadata/registry/`                          | ~45 tests                                                   |
| Integration      | Registry + real clients with HTTP mocked            | `tests/integration/api/metadata/registry/`                   | ~15 tests                                                   |
| Characterization | Lock-in current orchestrator behavior pre-refactor  | `tests/integration/scraper/test_legacy_fallback_snapshot.py` | ~6 tests (Phase 0 deliverable)                              |
| E2E pipeline     | Existing scrape/trailer E2E with registry injection | `tests/e2e/scrape/`, `tests/e2e/trailers/`, etc.             | Measured at Phase 0 (replaces "~40–60" estimate — see §8.5) |

### 8.2 Unit test coverage (by file)

- `test_registry_chain.py` —
  - ordering, circuit-OPEN skip, network exception skip, empty-result skip
  - HALF_OPEN included in eligible list (probe semantics, §7.6)
  - HALF_OPEN provider raises NetworkError → fallback to next within same iteration
  - `WrongSemanticBug` raised when called on non-chain capability (e.g. `chain(RatingProvider)`)
  - `chain(C)` returns identical-order list across repeated calls (stable-ordering guarantee)
  - Provider flips CLOSED→OPEN mid-iteration → next provider receives the call
- `test_registry_fan_out.py` —
  - all-eligible iteration, circuit-OPEN exclusion
  - `[]` when zero eligible providers (no error — caller decides)
  - `[]` when every provider is excluded by capability filter (caller must not crash)
  - `WrongSemanticBug` raised on non-fan-out capability
  - `RegistryFanOutCompleted` event ALWAYS emitted (even on full success)
- `test_registry_locked.py` —
  - match-provider path (no xref needed)
  - IDCrossRef escape: xref translation succeeds, returns wrapped LockedProvider with correct `translated_via`
  - circuit-OPEN along xref chain — first eligible candidate wins
  - `None` when match's provider lacks capability AND every fallback path blocked
  - `LockedCapabilityUnresolved` event emitted when returning None
  - `LockedProvider` construction outside the registry module raises
- `test_registry_validation.py` —
  - Each of the 6 `ConfigIssue.code` families triggered in isolation
  - All 6 families triggered simultaneously → single `RegistryConfigError` with structured `issues: list[ConfigIssue]`
  - `idcrossref_cycle` (e.g. tmdb→tvdb→tmdb) reported, no infinite loop
  - Partial-validity boot: when validation fails, NO operation is callable on the registry (it never finished constructing)
  - Boot cleanup: on validation failure, providers instantiated before the failing one have `.close()` called
  - Unknown-provider message includes a `difflib.get_close_matches` suggestion
- `test_registry_introspection.py` —
  - `operations()`, `status()`, `providers_for()` return expected shapes
  - `operations()` includes Mode.DIRECT entries with documented contract
- `test_registry_get.py` —
  - `registry.get(known_name)` returns provider
  - `registry.get(unknown_name)` raises `UnknownProviderError` (NOT bare KeyError)
- `test_registry_event_bus.py` —
  - `event_bus=None` accepted (test context, no-op emit)
  - When `event_bus.emit()` raises, the registry logs `registry_event_emit_failed` at WARNING and continues — no propagated exception

### 8.3 Integration tests

- HTTP intercepted via `responses` / `httpx_mock`.
- Verify `CircuitBreakerOpened`/`HalfOpened`/`Closed` events propagate to `registry.status()`.
- Verify chain triggers fallback correctly on 5xx / timeout / empty body.
- HALF_OPEN probe behavior end-to-end (transport-driven, not mocked at registry level).

### 8.4 Characterization tests (Phase 0 deliverable)

Locks in the current `scraper/orchestrator.py` behavior at lines 150 (movies)
and 223 (TV) BEFORE Phase 2 migration, so ACC-09 has a concrete equivalence
anchor. Six tests:

- TMDB circuit OPEN during `process_movies` → ScrapeResult action=error.
- TMDB raises `CircuitOpenError` mid-item → ScrapeResult action=error with err string.
- TVDB circuit OPEN but TMDB available → `match_tvshow` falls back to TMDB.
- Both TVDB and TMDB circuits OPEN during `process_tvshows` → action=error.
- TMDB raises `NetworkError` during a movie scrape → action=error.
- TVDB returns empty search → currently no fallback (lock-in).

These tests RUN unchanged after Phase 2; if any breaks, registry semantics
diverge from current behavior — either design intent or an unintended regression.

### 8.5 E2E impact

13 consumer files migrated. The "~40–60 tests touched" estimate is replaced by
a Phase 0 measurement:

```bash
rg -l "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb" tests/ --type py | wc -l
```

The exact count is recorded in `IMPLEMENTATION.md` as the baseline. ACC-09 then
asserts `pytest tests/e2e/ ...` matches the pinned pass count after migration.

### 8.6 Test-de-régression-par-bug rule

User memory `feedback_regression_test_per_bug.md` applies: any bug discovered
during implementation in the previous ad-hoc fallback logic must get a reproducer
test landed alongside the fix. This is distinct from §8.4 characterization tests:

- Characterization tests = equivalence anchors for the refactor (Phase 0, before-change snapshot).
- Regression-per-bug tests = reproducer for bugs SURFACED during the refactor.

No known bug ⇒ no pre-required regression test. If implementation surfaces an
oddity in `orchestrator.py:150` or `:223`, a test for it is mandatory before the
fix can be merged.

### 8.7 Out of scope (YAGNI)

- Performance tests on the registry (it's O(1) dispatch post-init, not a hot path).
- Thread-safety tests (registry is immutable post-init; hot-swap is a non-goal).
- Hot-reload tests (non-goal).
- Health-scoring tests (non-goal).

---

## 9. Implementation phasing

The Big Bang scope (13 files) is sliced into 5 reviewable phases (the legacy
"facade" Phase 1 has been collapsed into the chain-migration phase — keeping a
temporary `self._tmdb = registry.get("tmdb")` would violate the
`feedback_no_backcompat_before_v1` discipline). Phase numbering below reflects
the collapse.

### Phase 0 — New types, shells, characterization tests

- `api/metadata/registry/{_errors, _semantics, _factory, _validation, __init__}.py`
- `conf/models/providers.py` + `config.example/providers.json5`
- `providers: ProvidersConfig` field added to `Config`
- Unit tests (~45) for the registry (TDD)
- **Characterization tests** (`tests/integration/scraper/test_legacy_fallback_snapshot.py`, §8.4) — locks in current orchestrator behavior at lines 150 (movies) and 223 (TV) for ACC-09 equivalence anchoring.
- **`tests/fixtures/bad_providers.json5`** — synthetic broken-config fixture required by ACC-05.
- **Baseline measurements recorded in `IMPLEMENTATION.md`** (per §8.5):
  - `rg -l "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb" tests/ --type py | wc -l` (test-file count)
  - `pytest tests/e2e/ tests/integration/ -q | tail -1` (pinned pass count for ACC-09)

**Phase gate**: `make check` passes; `ProviderRegistry` is unreferenced outside its own package + its tests; characterization tests run against the unchanged orchestrator and pass.

### Phase 1 — Boot wiring + chain migration (collapsed from former phases 1+2)

- Pipeline boot site instantiates `ProviderRegistry` and passes it to `Scraper`.
- `Scraper.__init__` is reshaped: `self._registry = registry`. `self._tmdb` and `self._tvdb` are **removed in the same commit** — no façade survives.
- `process_movies` and `process_tvshows`: ad-hoc fallback replaced by `registry.chain(...)` iteration.
- `match_movie` / `match_tvshow` use `registry.chain(Searchable)` + provider-bound details fetch.
- Scraper E2E mocks pivot from `self._tmdb` to `self._registry` in the same commit (no half-migrated mocks).

**Phase gate**: `make check`; scraper E2E green; characterization tests still green (equivalence proven); `rg "self\._tmdb|self\._tvdb" personalscraper/scraper/ -t py` returns zero.

### Phase 2 — Scraper locked migration (fan_out semantics shipped but not connected)

- `artwork.py`, `keywords_cache.py`, `trailer_finder.py`: `registry.locked(...)`.
- `classifier.py`: keywords via `registry.locked(KeywordProvider, match)`.
- `existing_validator.py`, `confidence.py`, `_tvdb_convert.py`, `scraper.py`: cleanup of remaining direct client references.
- `fan_out(RatingProvider)`: code path EXISTS (semantics from §5.2 + unit tests from §8.2). No real consumer is migrated here — the only candidate (`indexer/backfill_ids.py`) stays on its current code path and is queued for a follow-up (§11). This is justified scope: a Web UI in P2 will introspect `operations()` and expose `RatingProvider` as a future entry; shipping the semantics now avoids retro-fit later.

**Phase gate**: `make check`; `rg "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb" personalscraper/scraper/ -t py` returns zero hits.

### Phase 3 — Out-of-scraper consumers

- `trailers/orchestrator.py` receives `registry` instead of `tmdb_client`.
- `library/rescraper.py` migrated.
- `commands/library/scan.py` constructs registry instead of direct clients.
- Associated tests updated.

**Phase gate**: `make check`; `rg "TMDBClient|TVDBClient" personalscraper/ -t py` returns hits only inside `api/metadata/`.

### Phase 4 — Cleanup, observability, docs

- EventBus events wired (`ProviderFallbackTriggered`, `ProviderExhaustedEvent`, `LockedCapabilityUnresolved`, `RegistryFanOutCompleted`, `RegistryBootValidated`) per §7.4 with full payloads.
- Structured logging events (`registry_*`) at the levels documented in §7.5.
- `docs/reference/architecture.md` — Provider Registry section.
- `docs/reference/scraping.md` — three semantics documented.
- CLI `personalscraper info providers` (minimal, prints `registry.status()`).
- `CHANGELOG.md` 0.16.0 entry.

**Phase gate**: `make check`; docs updated; `ACCEPTANCE.md` criteria all PASS.

### Phase 5 — Feature PR + review (auto-invoked)

`/implement:feature-pr` + `/implement:pr-review` per the standard lifecycle.

### 9.1 Phase / risk matrix

| Phase | Risk     | Reversible | LOC delta (est.) |
| ----- | -------- | ---------- | ---------------- |
| 0     | Very low | Yes        | +750 / -0        |
| 1     | Medium   | Yes        | +250 / -160      |
| 2     | Medium   | Yes        | +250 / -200      |
| 3     | Low      | Yes        | +100 / -80       |
| 4     | Very low | Trivial    | +150 / -20       |

---

## 10. Acceptance criteria

Each criterion below is an executable shell command with **deterministic expected
output**, per the SH-16 / 0.16.0 rule. "Expected" lists both the exit code and a
substring/count assertion. `${N}` placeholders are filled in `IMPLEMENTATION.md`
at Phase 0 measurement time (see §8.5).

| #       | Criterion                                             | Command                                                                                                            | Expected                                                                                  |
| ------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| ACC-01  | `make check` green                                    | `make check`                                                                                                       | exit 0                                                                                    |
| ACC-02  | No direct TMDB/TVDB client outside `api/metadata/`    | `rg -e TMDBClient -e TVDBClient -t py personalscraper/ -l \| grep -v api/metadata/`                                | exit non-zero (grep finds nothing) AND empty stdout                                       |
| ACC-03  | No `self._tmdb` / `self._tvdb` in `scraper/`          | `rg -e "self\._tmdb" -e "self\._tvdb" -t py personalscraper/scraper/`                                              | exit non-zero AND empty stdout                                                            |
| ACC-04a | Boot positive control with TMDB credentials present   | `TMDB_API_KEY=dummy_key personalscraper info providers >/dev/null 2>&1`                                            | exit 0                                                                                    |
| ACC-04b | Boot crashes when TMDB credentials missing            | `env -u TMDB_API_KEY personalscraper info providers 2>&1 \| grep -c "RegistryConfigError.*tmdb"`                   | command exit non-zero; grep stdout `1` (exactly one matching line)                        |
| ACC-05a | Synthetic broken config fixture exists                | `test -f tests/fixtures/bad_providers.json5`                                                                       | exit 0                                                                                    |
| ACC-05b | Broken config triggers aggregated RegistryConfigError | `personalscraper info providers --config tests/fixtures/bad_providers.json5 2>&1 \| grep -c "RegistryConfigError"` | exit non-zero; grep stdout `1`                                                            |
| ACC-06  | `info providers` lists every configured provider      | `personalscraper info providers \| grep -cE "^(tmdb\|tvdb\|imdb\|omdb\|trakt\|rotten_tomatoes)\s"`                 | exit 0; stdout `${N_PROVIDERS}` (e.g. `6` — pinned from `config.example/providers.json5`) |
| ACC-07  | Registry unit tests count                             | `pytest tests/unit/api/metadata/registry/ --collect-only -q \| tail -1 \| grep -oE "^[0-9]+"`                      | exit 0; stdout `${REGISTRY_UNIT_TEST_COUNT}` (≥45 expected — pinned in IMPLEMENTATION.md) |
| ACC-08  | EventBus snapshot test passes                         | `pytest tests/integration/api/metadata/registry/test_events.py -q`                                                 | exit 0                                                                                    |
| ACC-09  | E2E behavior preserved (count anchor)                 | `pytest tests/e2e/ tests/integration/ -q 2>&1 \| tail -1 \| grep -oE "[0-9]+ passed" \| awk '{print $1}'`          | exit 0; stdout `${BASELINE_PASS_COUNT}` (pinned at Phase 0 — see §8.5)                    |
| ACC-10  | Version bump                                          | `cat VERSION`                                                                                                      | exit 0; stdout `0.16.0`                                                                   |
| ACC-11  | CHANGELOG entry                                       | `grep -c "^## \[0.16.0\]" CHANGELOG.md`                                                                            | exit 0; stdout `1`                                                                        |
| ACC-12  | Module-size guardrail                                 | `python3 scripts/check-module-size.py`                                                                             | exit 0                                                                                    |
| ACC-13  | Characterization tests pass against refactored code   | `pytest tests/integration/scraper/test_legacy_fallback_snapshot.py -q`                                             | exit 0 (equivalence anchor preserved through Phase 1+2)                                   |

---

## 11. Out-of-scope explicit (and where they could land later)

> Each item below is now tracked outside this feature. See `ROADMAP.md` for the
> follow-up entries, or the registry feature's own Phases 11–17 for the deferrals
> that surfaced during implementation.

- **Indexer migration to the registry** (notably `indexer/backfill_ids.py`, the only current consumer of `RatingProvider.get_notations`). The registry's `fan_out` semantics are wired and unit-tested here. Indexer migration is delivered in **Phase 11 of this feature plan** (`docs/features/registry/plan/phase-11-indexer-migration.md`), pairing logically with the P1 Library/Indexer Consolidation roadmap item.
- **Runtime hot-swap** (signal-driven or watcher-driven config reload). Tracked at [ROADMAP P3 — Hot-Swap Provider Configuration](../../../ROADMAP.md#p3--hot-swap-provider-configuration).
- **Active health scoring / adaptive ordering**. Tracked at [ROADMAP P3 — Active Health Scoring (Registry)](../../../ROADMAP.md#p3--active-health-scoring-registry).
- **Passive health metrics for user-driven reordering** (counters / avg latency per provider). Folded into the Active Health Scoring entry above.
- **Web UI integration**. The introspection API (`status()`, `operations()`) is shipped here as a foundation; the UI consumer is tracked at [ROADMAP P2 — Web UI Registry Consumer](../../../ROADMAP.md#p2--web-ui-registry-consumer) (sibling to the broader P2 Web Management UI).

---

## 12. Open questions to confirm before plan generation

None at this stage — all questions raised during brainstorm have been decided and recorded in the sections above. Any new question that surfaces during the plan-writing step (`/implement:plan`) will be brought back to the user for decision rather than resolved unilaterally.

---

## 13. References

- ROADMAP entry: `ROADMAP.md` §P1 — Provider Registry (lines 21–37).
- Existing Protocols: `personalscraper/api/metadata/_contracts.py` (tech-debt 0.16.0 — atomic capability Protocols).
- Current orchestrator: `personalscraper/scraper/orchestrator.py` lines 80–98 (instantiation), 150 (movies TMDB-only fallback), 223 (TV TVDB+TMDB fallback).
- Project rule (CLAUDE.md): SH-16 — ACCEPTANCE criteria must be executable shell commands with documented expected output.
- Project rule (CLAUDE.md): module-size soft warning 800 LOC / hard ceiling 1000 LOC.
- Memory: `feedback_no_backcompat_before_v1.md` (Big Bang + no façades + no migration scripts).
- Memory: `feedback_regression_test_per_bug.md` (test-per-bug discipline — distinct from characterization tests, see §8.6).
- Memory: `feedback_multi_provider_ids_separation.md` (provider family separation).
- Reference doc: `docs/reference/event-bus.md` (EventBus contract — fail-soft).
- Reference doc: `docs/reference/logging.md` (structured logging conventions).
