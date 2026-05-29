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
- Baseline pass count recorded in `IMPLEMENTATION.md` as a concrete integer
  (not a `${...}` placeholder — see Phase 0 sub-phase 0.7).

---

## Goal

Wire `ProviderRegistry` at pipeline boot and migrate `scraper/orchestrator.py` to use
`registry.chain(...)` for both movies and TV shows. Remove `self._tmdb` and
`self._tvdb` from `Scraper.__init__` in the **same commit** — no façade survives
(per `feedback_no_backcompat_before_v1` rule). All scraper E2E mocks pivot from
direct client attributes to registry injection in the same atomic commit.

---

## Scope

**Modified:**

- `personalscraper/scraper/orchestrator.py` — remove `self._tmdb`, `self._tvdb`; accept `registry: ProviderRegistry`; replace `process_movies`/`process_tvshows` circuit checks and fallback with `registry.chain(...)`
- `personalscraper/scraper/movie_service.py` — accept `registry` instead of `tmdb_client`; use `registry.chain(MovieDetailsProvider)`
- `personalscraper/scraper/tv_service.py` — accept `registry`; use `registry.chain(Searchable)` + `registry.chain(TvDetailsProvider)` + `registry.chain(EpisodeFetcher)`
- `personalscraper/core/pipeline.py` (or equivalent boot site) — instantiate `ProviderRegistry` before `Scraper`, pass it in; wrap in `finally: registry.close()`
- `tests/integration/scraper/` — pivot mocks from `self._tmdb`/`self._tvdb` to `registry` (same commit as source change — see C4)
- `tests/e2e/scrape/` — pivot mocks to registry injection (same commit as source change — see C4)

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

**Unit/integration test — ACC-04b boot assertion (C5)**:

Add a unit or integration test asserting that `RegistryConfigError` is raised at
boot when `TMDB_API_KEY` is unset. This is the Phase 1 equivalent assertion giving
confidence that the ACC-04b behavior is built, even though the CLI command
(`personalscraper info providers`) is not delivered until sub-phase 4.3:

```python
# tests/integration/api/metadata/registry/test_registry_boot.py
def test_boot_raises_registry_config_error_when_tmdb_key_missing(monkeypatch):
    """ACC-04b equivalent: RegistryConfigError raised at boot if TMDB_API_KEY absent."""
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    with pytest.raises(RegistryConfigError) as exc:
        ProviderRegistry(
            settings=Settings.from_env(),
            event_bus=None,
            cb_policy=default_policy(),
            providers_config=default_providers_config(),
        )
    assert any(i.code == "missing_credentials" and "tmdb" in (i.provider or "") for i in exc.value.issues)
```

Run: `python -c "import personalscraper"` — must exit 0.

Commit: `feat(registry): wire ProviderRegistry at pipeline boot`

---

### 1.2 — Atomic: orchestrator chain migration + E2E mock pivot

**Files:** `personalscraper/scraper/orchestrator.py`, `personalscraper/scraper/movie_service.py`, `personalscraper/scraper/tv_service.py`, `tests/integration/scraper/`, `tests/e2e/scrape/`

This is a **single atomic commit** — the orchestrator constructor change AND all
test mock pivots are committed together. No half-migrated state is committed: if
the orchestrator `self._tmdb`/`self._tvdb` are removed but the E2E fixtures still
reference them, the test suite will fail. Both halves must land in the same commit.

**Rationale (C4)**: between commits, the repo would be broken — the orchestrator
constructor signature has changed but the fixtures still pass `tmdb_client=...`.
Making 1.2 and the former 1.3 one atomic sub-phase eliminates this window.

Remove `self._tmdb` and `self._tvdb` from `Scraper.__init__` and pass `registry`
to services:

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

Replace line 150 (movies TMDB-only circuit check) with registry chain iteration.
Include the empty-result branch per DESIGN §6.2 (C8):

```python
# process_movies — AFTER migration (DESIGN §6.2 — empty-result is no longer silent):
providers = self._registry.chain(MovieDetailsProvider)
match = None
attempted: list[AttemptOutcome] = []

for provider in providers:
    try:
        result = provider.search(query)
        if not result:
            attempted.append(AttemptOutcome(provider.name, "empty_result"))
            log.debug("registry_provider_skip", provider=provider.name,
                      capability="MovieDetailsProvider", reason="empty_result")
            continue
        chosen = best_match(result, title, year)
        if chosen is None:
            attempted.append(AttemptOutcome(provider.name, "empty_result",
                                            detail="no candidate above confidence threshold"))
            continue
        match = ProviderMatch(provider.name, chosen.id, media_type)
        break
    except CircuitOpenError:
        attempted.append(AttemptOutcome(provider.name, "circuit_open"))
        log.debug("registry_provider_skip", provider=provider.name,
                  capability="MovieDetailsProvider", reason="circuit_open")
        continue
    except NetworkError as e:
        attempted.append(AttemptOutcome(provider.name, "network",
                                        detail=type(e).__name__))
        log.warning("registry_provider_fail", provider=provider.name,
                    capability="MovieDetailsProvider", exc_type=type(e).__name__)
        continue

if match is None:
    raise ProviderExhausted(MovieDetailsProvider, attempted=attempted, item_context={...})
```

Replace line 223 (TV both-circuits check) similarly with the same empty-result
branch pattern.

`movie_service.py` — replace `tmdb_client: TMDBClient` param with `registry: ProviderRegistry`.
`tv_service.py` — same pattern with `Searchable` + `TvDetailsProvider` + `EpisodeFetcher`.

**E2E and integration mock pivot** (in the SAME commit as the source change above):

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

Commit: `feat(registry): atomic — remove self._tmdb/_tvdb, chain migration + mock pivot`

---

### 1.3 — Characterization equivalence gate

**Files:** none (zero source changes — this sub-phase is verification only)

Run the characterization tests against the now-refactored orchestrator to assert
equivalence is preserved:

```bash
pytest tests/integration/scraper/test_legacy_fallback_snapshot.py -q
```

Expected: exit 0, all 6 tests pass.

This is the ACC-13 verification point for Phase 1. If any characterization test
fails here, registry semantics diverge from the pre-migration behavior — do NOT
proceed. Revert sub-phase 1.2 and investigate before retrying.

No commit is produced by this sub-phase (verification only). The Phase 1 gate
commit is produced by the preceding sub-phase 1.2.

---

## On gate failure

If `## Phase gate` fails, do NOT proceed to the next phase. Revert the failing
sub-phase's commit (`git revert <sha>` for the most recent commit, or
`git reset --hard HEAD~N` for multiple) and re-invoke `/implement:phase` to retry
the sub-phase. The phase gate must be green before any cross-phase work continues.

---

## Phase gate

From DESIGN §9 Phase 1:

> `make check`; scraper E2E green; characterization tests still green (equivalence
> proven); `rg "self\._tmdb|self\._tvdb" personalscraper/scraper/ -t py` returns zero.

The 6 characterization tests from Phase 0 sub-phase 0.6 must pass against the
refactored code. ACC-13 verified here.

---

## ACC criteria touched

- **ACC-03** — `rg "self\._tmdb|self\._tvdb" personalscraper/scraper/ -t py` returns empty (sub-phase 1.2)
- **ACC-09** — E2E pass count matches baseline integer from `IMPLEMENTATION.md` (sub-phase 1.3)
- **ACC-13** — characterization tests still green post-migration (sub-phase 1.3)
