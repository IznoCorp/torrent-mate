# Phase 3 — Out-of-scraper consumers

> **Feature**: registry | **Version**: 0.15.1 → 0.16.0
> **Commit scope**: `(registry)`
> **Design ref**: DESIGN.md §1.1, §9 Phase 3

---

## Gate

Phase 2 must have produced:

- `rg "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb" personalscraper/scraper/ --type py`
  returns zero matches.
- `make check` green.
- `fan_out(RatingProvider)` code path wired and tested.

---

## Goal

Migrate the three out-of-scraper consumers — `trailers/orchestrator.py`,
`library/rescraper.py`, and `commands/library/scan.py` — from direct
`TMDBClient`/`TVDBClient` instantiation to registry injection. After this phase,
the only files allowed to reference `TMDBClient`/`TVDBClient` by name are inside
`personalscraper/api/metadata/`.

---

## Scope

**Modified:**

- `personalscraper/trailers/orchestrator.py` — accept `registry: ProviderRegistry` instead of `tmdb_client`; use `registry.chain(...)` or `registry.locked(...)` as appropriate
- `personalscraper/library/rescraper.py` — accept `registry`; replace direct client calls
- `personalscraper/commands/library/scan.py` — construct `ProviderRegistry` at command entry point instead of constructing direct clients; or receive it from the app context
- `tests/` for each of the three files — pivot mocks to registry injection

**Not modified:**

- `personalscraper/api/metadata/` — client classes stay here, registry is already done
- `personalscraper/indexer/backfill_ids.py` — deliberate out-of-scope (DESIGN §11)

---

## Sub-phases

### 3.1 — `trailers/orchestrator.py` migration

**Files:** `personalscraper/trailers/orchestrator.py`, associated tests

Identify what capabilities `trailers/orchestrator.py` uses. Typical pattern:
TMDB video search for trailers → `VideoProvider`. Migrate:

```python
# personalscraper/trailers/orchestrator.py — after migration
from personalscraper.api.metadata._contracts import VideoProvider
from personalscraper.api.metadata.registry import ProviderRegistry, ProviderMatch

class TrailersOrchestrator:
    def __init__(self, *, registry: ProviderRegistry, ...) -> None:
        self._registry = registry
        # self._tmdb_client removed

    def find_trailer(self, match: ProviderMatch) -> TrailerInfo | None:
        locked = self._registry.locked(VideoProvider, match)
        if locked is None:
            return None
        videos = locked.provider.get_video_urls(locked.bound_id, media_type=match.media_type)
        return self._pick_best_trailer(videos)
```

If `trailers/orchestrator.py` also uses `Searchable` for title-based discovery,
use `registry.chain(Searchable)` in the same pattern as Phase 1.

Update the call site that constructs `TrailersOrchestrator` — pass `registry`
(already available at the pipeline boot site from Phase 1).

Update all tests that mock `trailers_orchestrator._tmdb` to use
`MagicMock(spec=ProviderRegistry)` instead.

Run: `pytest tests/unit/trailers/ tests/integration/trailers/ -q`
Expected: all pass.

Commit: `feat(registry): trailers/orchestrator migrated to registry`

---

### 3.2 — `library/rescraper.py` migration

**Files:** `personalscraper/library/rescraper.py`, associated tests

`library/rescraper.py` re-scrapes existing media items. It likely uses both
`Searchable` and detail providers. Migrate following the same chain/locked pattern:

```python
# personalscraper/library/rescraper.py — after migration
from personalscraper.api.metadata._contracts import Searchable, MovieDetailsProvider, TvDetailsProvider
from personalscraper.api.metadata.registry import ProviderRegistry, ProviderMatch, ProviderExhausted

class LibraryRescraper:
    def __init__(self, *, registry: ProviderRegistry, ...) -> None:
        self._registry = registry

    def rescrape_movie(self, media_dir: Path) -> ScrapeResult:
        providers = self._registry.chain(Searchable)
        attempted = []
        for provider in providers:
            try:
                candidates = provider.search(media_dir.name)
                if candidates:
                    match = ProviderMatch(
                        provider=provider.name,
                        id=candidates[0].id,
                        media_type=MediaType.MOVIE,
                    )
                    detail_providers = self._registry.chain(MovieDetailsProvider)
                    # ... fetch details ...
                    return ScrapeResult(...)
                attempted.append(AttemptOutcome(provider.name, "empty_result"))
            except NetworkError as exc:
                attempted.append(AttemptOutcome(provider.name, "network", detail=type(exc).__name__))
        raise ProviderExhausted(Searchable, attempted)
```

Update the call site that constructs `LibraryRescraper` — pass `registry`.

Update all tests.

Run: `pytest tests/unit/library/ tests/integration/library/ -q`
Expected: all pass.

Commit: `feat(registry): library/rescraper migrated to registry`

---

### 3.3 — `commands/library/scan.py` migration + full ACC-02 verification

**Files:** `personalscraper/commands/library/scan.py`, associated tests

`commands/library/scan.py` is a CLI command entry point. It currently constructs
`TMDBClient`/`TVDBClient` directly. Migrate: receive `registry` from the app
context (if the app context already carries it from Phase 1 boot wiring), or
construct `ProviderRegistry` explicitly at command entry:

```python
# personalscraper/commands/library/scan.py — after migration
from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.conf.models.config import Config

@app.command()
def scan(ctx: typer.Context, ...) -> None:
    config: Config = ctx.obj["config"]
    settings: Settings = ctx.obj["settings"]
    event_bus: EventBus = ctx.obj["event_bus"]
    registry: ProviderRegistry = ctx.obj["registry"]  # injected from boot

    rescraper = LibraryRescraper(registry=registry, ...)
    rescraper.run(...)
```

If `registry` is not yet carried in the app context, add it in the root command
setup (same boot sequence as Phase 1's pipeline boot site).

After migrating all three consumers, run the definitive ACC-02 grep:

```bash
rg -e TMDBClient -e TVDBClient --type py personalscraper/ -l | grep -v api/metadata/
```

Expected: empty stdout (exit non-zero from grep = no lines found outside `api/metadata/`).

Run: `make check`
Expected: exit 0.

Commit: `feat(registry): commands/library/scan migrated — ACC-02 verified`

---

## Phase gate

From DESIGN §9 Phase 3:

> `make check`; `rg "TMDBClient|TVDBClient" personalscraper/ -t py` returns hits
> only inside `api/metadata/`.

---

## ACC criteria touched

- **ACC-02** — `rg -e TMDBClient -e TVDBClient -t py personalscraper/ -l | grep -v api/metadata/` returns empty (sub-phase 3.3)
- **ACC-09** — E2E pass count still matches `${BASELINE_PASS_COUNT}` (gate `make check`)
- **ACC-13** — characterization tests still green (included in `make check`)
