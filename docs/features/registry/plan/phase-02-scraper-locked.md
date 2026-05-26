# Phase 2 — Scraper locked migration

> **Feature**: registry | **Version**: 0.15.1 → 0.16.0
> **Commit scope**: `(registry)`
> **Design ref**: DESIGN.md §4, §5.2, §6.4, §8.2, §9 Phase 2

---

## Gate

Phase 1 must have produced:

- `self._tmdb` and `self._tvdb` fully removed from `personalscraper/scraper/orchestrator.py`.
- `rg "self\._tmdb|self\._tvdb" personalscraper/scraper/ --type py` returns zero matches.
- `make check` green.
- Characterization tests still green (equivalence proven).

---

## Goal

Migrate all remaining direct `TMDBClient` / `TVDBClient` references inside the
`scraper/` package to `registry.locked(...)` calls. Ship the `fan_out(RatingProvider)`
code path fully wired and unit-tested — but leave `indexer/backfill_ids.py` on its
current code path (deliberate out-of-scope per DESIGN §11). After this phase, zero
direct client references remain anywhere in `personalscraper/scraper/`.

---

## Scope

**Modified:**

- `personalscraper/scraper/artwork.py` — replace direct `tmdb_client.get_artwork_urls()` with `registry.locked(ArtworkProvider, match)`
- `personalscraper/scraper/keywords_cache.py` — replace direct TMDB keywords call with `registry.locked(KeywordProvider, match)`
- `personalscraper/scraper/trailer_finder.py` — replace direct TMDB video call with `registry.locked(VideoProvider, match)`
- `personalscraper/scraper/classifier.py` — keywords via `registry.locked(KeywordProvider, match)`
- `personalscraper/scraper/existing_validator.py` — remove direct client reference; use registry for any ID validation needed
- `personalscraper/scraper/confidence.py` — remove direct client reference; pass `ProviderMatch` context instead of raw IDs
- `personalscraper/scraper/_tvdb_convert.py` — remove direct TVDBClient reference; accept typed data instead
- `personalscraper/scraper/scraper.py` — clean up any remaining direct client attribute references
- `tests/unit/scraper/` and `tests/integration/scraper/` — update fixtures for each migrated file

**Not modified in this phase:**

- `trailers/orchestrator.py`, `library/rescraper.py`, `commands/library/scan.py` — Phase 3.
- `indexer/backfill_ids.py` — deliberate out-of-scope (DESIGN §11).

---

## Sub-phases

### 2.1 — `artwork.py` + `trailer_finder.py` locked migration

**Files:** `personalscraper/scraper/artwork.py`, `personalscraper/scraper/trailer_finder.py`

Replace direct client calls with `registry.locked(...)`. Follow the caller pattern
from DESIGN §6.4 exactly:

```python
# personalscraper/scraper/artwork.py — after migration
from personalscraper.api.metadata._contracts import ArtworkProvider
from personalscraper.api.metadata.registry import ProviderMatch

def fetch_artwork(self, match: ProviderMatch) -> ArtworkResult:
    locked = self._registry.locked(ArtworkProvider, match)
    if locked is None:
        # Registry already emitted LockedCapabilityUnresolved + logged WARNING
        log.warning("artwork_unresolved", match=match)
        return ArtworkResult.empty()
    urls = locked.provider.get_artwork_urls(locked.bound_id, media_type=match.media_type)
    return ArtworkResult(urls=urls, translated_via=locked.translated_via)
```

```python
# personalscraper/scraper/trailer_finder.py — after migration
from personalscraper.api.metadata._contracts import VideoProvider

def find_trailers(self, match: ProviderMatch) -> list[TrailerInfo]:
    locked = self._registry.locked(VideoProvider, match)
    if locked is None:
        return []
    return locked.provider.get_video_urls(locked.bound_id, media_type=match.media_type)
```

Update the corresponding unit/integration tests to use `MagicMock(spec=ProviderRegistry)`
instead of direct client mocks.

Run: `pytest tests/unit/scraper/test_artwork.py tests/unit/scraper/test_trailer_finder.py -q`
Expected: all pass.

Commit: `feat(registry): artwork + trailer_finder locked migration`

---

### 2.2 — `keywords_cache.py` + `classifier.py` locked migration

**Files:** `personalscraper/scraper/keywords_cache.py`, `personalscraper/scraper/classifier.py`

Both use `KeywordProvider`. Migrate to `registry.locked(KeywordProvider, match)`:

```python
# personalscraper/scraper/keywords_cache.py — after migration
from personalscraper.api.metadata._contracts import KeywordProvider

def get_keywords(self, match: ProviderMatch) -> list[str]:
    locked = self._registry.locked(KeywordProvider, match)
    if locked is None:
        return []
    return locked.provider.get_keywords(locked.bound_id, media_type=match.media_type)
```

`classifier.py` calls into `keywords_cache` — no direct client reference to remove
there, but ensure it passes a `ProviderMatch` (not a raw TMDB ID string) to the
cache. Update constructor signature if `classifier.py` currently stores
`self._tmdb` directly.

Update tests accordingly.

Run: `pytest tests/unit/scraper/test_keywords_cache.py tests/unit/scraper/test_classifier.py -q`
Expected: all pass.

Commit: `feat(registry): keywords_cache + classifier locked migration`

---

### 2.3 — `existing_validator.py` + `confidence.py` + `_tvdb_convert.py` + `scraper.py` cleanup

**Files:** `personalscraper/scraper/existing_validator.py`, `personalscraper/scraper/confidence.py`, `personalscraper/scraper/_tvdb_convert.py`, `personalscraper/scraper/scraper.py`

These files may have lingering direct references used for ID validation or data
reshaping. For each:

1. Run `rg "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb" personalscraper/scraper/<file>.py --type py` to see what needs removing.
2. Replace any `IDValidator` / `IDCrossRef` usage with `registry.get(provider_name).validate(id)` or `registry.cross_ref(match, target=...)`.
3. `_tvdb_convert.py` likely just type-converts TVDB response shapes — if it holds no client reference, only verify and note.
4. `scraper.py` (the high-level coordinator) — remove any `self._tmdb = ...` / `self._tvdb = ...` storage; ensure it passes `registry` down to each sub-service.

Run verification grep after each file:

```bash
rg "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb" personalscraper/scraper/ --type py
```

Expected: zero matches.

Update tests for each modified file.

Run: `pytest tests/unit/scraper/ tests/integration/scraper/ -q`
Expected: all pass.

Commit: `feat(registry): cleanup remaining direct client refs in scraper package`

---

### 2.4 — fan_out(RatingProvider) code path wired + unit tests

**Files:** `personalscraper/api/metadata/registry/__init__.py` (ensure `fan_out` is fully wired), `tests/unit/api/metadata/registry/test_registry_fan_out.py`

The `fan_out` semantic was stubbed in Phase 0 unit tests. Verify the full code path
is exercised end-to-end with a fake `RatingProvider`. No real consumer is migrated
here (DESIGN §11 deliberate scope decision).

Add an integration smoke test asserting `RegistryFanOutCompleted` is always emitted:

```python
# tests/integration/api/metadata/registry/test_fan_out_event.py
def test_fan_out_always_emits_completed_event(registry_with_rating_provider, mock_bus):
    result = registry_with_rating_provider.fan_out(RatingProvider)
    assert any(isinstance(e, RegistryFanOutCompleted) for e in mock_bus.emitted)
    # Even when result is empty list, event is emitted
```

Run: `pytest tests/unit/api/metadata/registry/test_registry_fan_out.py tests/integration/api/metadata/registry/ -q`
Expected: all pass.

Run full gate:

```bash
make check
rg "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb" personalscraper/scraper/ --type py
```

Expected: `make check` exits 0. `rg` returns zero matches.

Commit: `feat(registry): fan_out(RatingProvider) code path wired and tested`

---

## Phase gate

From DESIGN §9 Phase 2:

> `make check`; `rg "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb"
personalscraper/scraper/ -t py` returns zero hits.

---

## ACC criteria touched

- **ACC-03** — confirmed zero `self._tmdb`/`self._tvdb` in `scraper/` (all sub-phases)
- **ACC-09** — E2E pass count still matches `${BASELINE_PASS_COUNT}` (gate check)
- **ACC-13** — characterization tests still green (run as part of `make check`)
