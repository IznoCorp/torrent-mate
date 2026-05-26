# Phase 1 — Boot wiring + chain migration

> **Feature**: registry | **Version**: 0.15.1 → 0.16.0
> **Commit scope**: `(registry)`
> **Design ref**: DESIGN.md §6.1, §6.2, §9 Phase 1

---

## Gate

Phase 0 must have produced:

- `ProviderRegistry` fully implemented, all ≥45 unit tests passing.
- `make check` green on `feat/registry` branch.
- Characterization tests (`tests/integration/scraper/test_legacy_fallback_snapshot.py`)
  passing against the **unchanged** orchestrator.
- Baseline pass count recorded in `IMPLEMENTATION.md` (`${BASELINE_PASS_COUNT}`).

---

## Goal

Wire `ProviderRegistry` at pipeline boot and migrate `scraper/orchestrator.py` to use
`registry.chain(...)` for both movies and TV shows. Remove `self._tmdb` and
`self._tvdb` from `Scraper.__init__` in the **same commit** — no façade survives
(per `feedback_no_backcompat_before_v1` rule). All scraper E2E mocks pivot from
direct client attributes to registry injection in the same commit.

---

## Scope

**Modified:**

- `personalscraper/scraper/orchestrator.py` — remove `self._tmdb`, `self._tvdb`; accept `registry: ProviderRegistry`; replace `process_movies`/`process_tvshows` circuit checks and fallback with `registry.chain(...)`
- `personalscraper/scraper/movie_service.py` — accept `registry` instead of `tmdb_client`; use `registry.chain(MovieDetailsProvider)`
- `personalscraper/scraper/tv_service.py` — accept `registry`; use `registry.chain(Searchable)` + `registry.chain(TvDetailsProvider)` + `registry.chain(EpisodeFetcher)`
- `personalscraper/core/pipeline.py` (or equivalent boot site) — instantiate `ProviderRegistry` before `Scraper`, pass it in; wrap in `finally: registry.close()`
- `tests/integration/scraper/` — pivot mocks from `self._tmdb`/`self._tvdb` to `registry`
- `tests/e2e/scrape/` — pivot mocks to registry injection (same commit as source change)

**Not modified in this phase:**

- `scraper/artwork.py`, `scraper/keywords_cache.py`, `scraper/trailer_finder.py`, `scraper/classifier.py`, `scraper/existing_validator.py`, `scraper/confidence.py`, `scraper/_tvdb_convert.py`, `scraper/scraper.py` — these retain direct client references until Phase 2.
- `trailers/`, `library/`, `commands/` — out-of-scraper consumers, Phase 3.

---

## Sub-phases

### 1.1 — Pipeline boot wiring

**Files:** `personalscraper/core/pipeline.py` (or equivalent boot site)

Add `ProviderRegistry` instantiation in the pipeline boot sequence (DESIGN §6.1):

```python
# In the pipeline boot site (core/pipeline.py or equivalent)
from personalscraper.api.metadata.registry import ProviderRegistry

# After settings and config are loaded:
registry = ProviderRegistry(
    settings=settings,
    event_bus=event_bus,
    cb_policy=CircuitPolicy.from_thresholds(config.thresholds),
    providers_config=config.providers,
)

# Pass registry to Scraper (new kwarg — see 1.2)
orchestrator = Scraper(settings, patterns, registry=registry, ...)

try:
    pipeline.run(...)
finally:
    registry.close()
```

Also load `config.providers` from `config/providers.json5` in `Config.from_files()`:

```python
# In personalscraper/conf/models/config.py or the config loader
providers_path = config_dir / "providers.json5"
if providers_path.exists():
    providers = ProvidersConfig.model_validate(load_json5(providers_path))
else:
    providers = ProvidersConfig()  # empty defaults — validation will flag missing chains
```

Copy `config.example/providers.json5` to `config/providers.json5` if not present
(or document in `personalscraper init-config` that it creates it).

Run: `python -c "import personalscraper"` — must exit 0.

Commit: `feat(registry): wire ProviderRegistry at pipeline boot`

---

### 1.2 — Orchestrator: remove self.\_tmdb / self.\_tvdb, accept registry

**Files:** `personalscraper/scraper/orchestrator.py`, `personalscraper/scraper/movie_service.py`, `personalscraper/scraper/tv_service.py`

This is a **single atomic commit** — no half-migrated state is committed. Remove
`self._tmdb` and `self._tvdb` from `Scraper.__init__` and pass `registry` to services.

```python
# personalscraper/scraper/orchestrator.py — new __init__ signature
def __init__(
    self,
    settings: Settings,
    patterns: PatternsConfig,
    *,
    registry: ProviderRegistry,
    config: Config | None = None,
    event_bus: EventBus | None = None,
) -> None:
    ...
    self._registry = registry
    # self._tmdb and self._tvdb are GONE — not stored at all
```

Replace line 150 (movies TMDB-only circuit check) with registry chain iteration:

```python
# process_movies — BEFORE (line 150):
if not self._tmdb.circuit.can_proceed():
    ...error...

# AFTER — delegate circuit awareness to registry:
providers = self._registry.chain(MovieDetailsProvider)
# registry.chain() already filters OPEN circuits; empty list → ProviderExhausted
try:
    result = self._movie_service.scrape(movie_dir, providers)
except ProviderExhausted as exc:
    results.append(ScrapeResult(
        media_path=movie_dir,
        media_type="movie",
        action="error",
        error=str(exc),
    ))
    continue
```

Replace line 223 (TV both-circuits check) similarly:

```python
# process_tvshows — BEFORE (line 223):
if not self._tvdb.circuit.can_proceed() and not self._tmdb.circuit.can_proceed():
    ...error...

# AFTER — registry.chain handles fallback ordering from config:
providers = self._registry.chain(Searchable)
try:
    result = self._tv_service.scrape(show_dir, providers)
except ProviderExhausted as exc:
    results.append(ScrapeResult(
        media_path=show_dir,
        media_type="tvshow",
        action="error",
        error=str(exc),
    ))
    continue
```

`movie_service.py` — replace `tmdb_client: TMDBClient` param with `registry: ProviderRegistry`:

```python
def scrape(self, media_dir: Path, providers: list[MovieDetailsProvider]) -> ScrapeResult:
    # Iterate providers in the order registry.chain() returned them
    attempted: list[AttemptOutcome] = []
    for provider in providers:
        try:
            ...fetch details from provider...
            return ScrapeResult(...)
        except NetworkError as exc:
            attempted.append(AttemptOutcome(provider.name, "network", detail=type(exc).__name__))
    raise ProviderExhausted(MovieDetailsProvider, attempted)
```

`tv_service.py` — same pattern with `Searchable` + `TvDetailsProvider` + `EpisodeFetcher`.

Commit: `feat(registry): remove self._tmdb/_tvdb from Scraper, chain migration atomic`

---

### 1.3 — Pivot E2E and integration mocks to registry injection

**Files:** `tests/integration/scraper/`, `tests/e2e/scrape/`

Replace all test fixtures that mock `orchestrator._tmdb` / `orchestrator._tvdb`
with registry injection. The pattern: construct a fake `ProviderRegistry` (or use
`unittest.mock.MagicMock(spec=ProviderRegistry)`) and pass it to `Scraper(..., registry=...)`.

```python
# Typical fixture migration pattern:
# BEFORE:
@pytest.fixture
def orchestrator(settings, patterns):
    orc = Scraper(settings, patterns)
    orc._tmdb = MagicMock(spec=TMDBClient)
    return orc

# AFTER:
@pytest.fixture
def mock_registry():
    reg = MagicMock(spec=ProviderRegistry)
    reg.chain.return_value = [MagicMock(spec=MovieDetailsProvider)]
    return reg

@pytest.fixture
def orchestrator(settings, patterns, mock_registry):
    return Scraper(settings, patterns, registry=mock_registry)
```

Verify characterization tests are still green (equivalence proof):

```bash
pytest tests/integration/scraper/test_legacy_fallback_snapshot.py -q
```

Expected: all 6 characterization tests pass.

Run full check:

```bash
make check
rg "self\._tmdb|self\._tvdb" personalscraper/scraper/ --type py
```

Expected: `make check` exits 0. `rg` returns no matches.

Commit: `test(registry): pivot scraper mocks to registry injection`

---

## Phase gate

From DESIGN §9 Phase 1:

> `make check`; scraper E2E green; characterization tests still green (equivalence
> proven); `rg "self\._tmdb|self\._tvdb" personalscraper/scraper/ -t py` returns zero.

---

## ACC criteria touched

- **ACC-03** — `rg "self\._tmdb|self\._tvdb" personalscraper/scraper/ -t py` returns empty (sub-phase 1.2)
- **ACC-04a** — boot positive control: `ProviderRegistry` constructed with credentials → exit 0 (sub-phase 1.1)
- **ACC-04b** — boot crashes when credentials missing → `RegistryConfigError` (sub-phase 1.1)
- **ACC-09** — E2E pass count matches `${BASELINE_PASS_COUNT}` (sub-phase 1.3)
- **ACC-13** — characterization tests still green post-migration (sub-phase 1.3)
