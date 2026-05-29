# Phase 2 — Scraper locked migration

> **Feature**: registry | **Version**: 0.15.1 → 0.16.0
> **Commit scope**: `(registry)`
> **Design ref**: DESIGN.md §4, §5.2, §6.4, §8.2, §8.3, §9 Phase 2

---

## Gate

Phase 1 must have produced:

- `self._tmdb` and `self._tvdb` fully removed from `personalscraper/scraper/orchestrator.py`.
- `rg "self\._tmdb|self\._tvdb" personalscraper/scraper/ --type py` returns zero matches.
- `make check` green.
- Characterization tests still green (equivalence proven via sub-phase 1.3).

---

## Goal

Migrate all remaining direct `TMDBClient` / `TVDBClient` references inside the
`scraper/` package to `registry.locked(...)` calls. Ship the `fan_out(RatingProvider)`
code path fully wired and unit-tested — but leave `indexer/backfill_ids.py` on its
current code path (deliberate out-of-scope per DESIGN §11). Add the HTTP-level
integration tests (DESIGN §8.3). After this phase, zero direct client references
remain anywhere in `personalscraper/scraper/`.

---

## Scope

**Modified:**

- `personalscraper/scraper/artwork.py` — replace direct `tmdb_client.get_artwork_urls()` with `registry.locked(ArtworkProvider, match)`
- `personalscraper/scraper/keywords_cache.py` — replace direct TMDB keywords call with `registry.locked(KeywordProvider, match)`
- `personalscraper/scraper/trailer_finder.py` — replace direct TMDB video call with `registry.locked(VideoProvider, match)`
- `personalscraper/scraper/classifier.py` — keywords via `registry.locked(KeywordProvider, match)`
- `personalscraper/scraper/existing_validator.py` — remove direct client reference; use registry for any ID validation needed
- `personalscraper/scraper/confidence.py` — remove direct client reference; pass `ProviderMatch` context instead of raw IDs
- `personalscraper/scraper/_tvdb_convert.py` — remove direct TVDBClient reference; accept typed data instead (see pre-flight in 2.3b)
- `personalscraper/scraper/scraper.py` — clean up any remaining direct client attribute references
- `tests/unit/scraper/` and `tests/integration/scraper/` — update fixtures for each migrated file

**Created:**

- `tests/integration/api/metadata/registry/test_registry_http.py` — HTTP-level integration tests (sub-phase 2.5)

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

### 2.3a — `existing_validator.py` + `confidence.py` migration

**Files:** `personalscraper/scraper/existing_validator.py`, `personalscraper/scraper/confidence.py`

Migrate the two ID-validation and scoring helpers:

1. Run `rg "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb" personalscraper/scraper/existing_validator.py personalscraper/scraper/confidence.py --type py` to see what needs removing.
2. Replace any `IDValidator` / `IDCrossRef` usage with `registry.get(provider_name).validate(id)` or `registry.cross_ref(match, target=...)`.
3. `confidence.py` — remove direct client reference; pass `ProviderMatch` context instead of raw IDs.

Update tests for each modified file.

Run: `pytest tests/unit/scraper/test_existing_validator.py tests/unit/scraper/test_confidence.py -q`
Expected: all pass.

Commit: `feat(registry): existing_validator + confidence migration`

---

### 2.3b — `_tvdb_convert.py` + `scraper.py` cleanup

**Files:** `personalscraper/scraper/_tvdb_convert.py`, `personalscraper/scraper/scraper.py`

**Pre-flight check** before modifying `_tvdb_convert.py`:

```bash
# Check whether _tvdb_convert.py holds any client reference at all.
rg "TMDB|TVDBClient|self\._tmdb|self\._tvdb" personalscraper/scraper/_tvdb_convert.py --type py | head -5
```

If no client reference is found, the file is type-conversion only. In that case,
mark this file as "no change required" in the sub-phase report and only migrate
`scraper.py`.

For `scraper.py` (the high-level coordinator):

- Remove any `self._tmdb = ...` / `self._tvdb = ...` storage.
- Ensure it passes `registry` down to each sub-service.

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

The `fan_out` semantic was implemented in Phase 0 sub-phase 0.5b. Verify the full
code path is exercised end-to-end with a fake `RatingProvider`. No real consumer
is migrated here (DESIGN §11 deliberate scope decision).

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

Commit: `feat(registry): fan_out(RatingProvider) code path wired and tested`

---

### 2.5 — Integration tests for registry semantics

**Files:** `tests/integration/api/metadata/registry/test_registry_http.py`

Write ~15 HTTP-level integration tests per DESIGN §8.3. Use `responses` or
`httpx_mock` to intercept HTTP at the transport layer (not mocking the registry
itself). Cover:

1. `CircuitBreakerOpened` event propagates to `registry.status()` after failures.
2. `CircuitBreakerHalfOpened` event propagates (circuit transitions to HALF_OPEN).
3. `CircuitBreakerClosed` event propagates (circuit transitions back to CLOSED).
4. `chain()` fallback on 5xx response — first provider returns 5xx, second succeeds.
5. `chain()` fallback on timeout — first provider times out, second succeeds.
6. `chain()` fallback on empty body — first provider returns empty, second succeeds.
7. **HALF_OPEN end-to-end probe behavior**: circuit in HALF_OPEN state, probe request
   succeeds → circuit transitions to CLOSED, subsequent calls use the provider.
8. **HALF_OPEN probe failure**: circuit in HALF_OPEN, probe request fails → circuit
   trips back to OPEN, registry falls through to next provider.
9. `NetworkError` from transport → `AttemptOutcome(reason="network")` in chain.
10. `locked()` with `cross_ref` via mocked HTTP — IDCrossRef translation succeeds.
11. `locked()` with `cross_ref` via mocked HTTP — IDCrossRef returns None, locked() returns None.
12. All providers in chain return 5xx → `ProviderExhausted` raised.
13. `fan_out()` with one provider returning 5xx, one succeeding → partial result + `RegistryFanOutCompleted`.
14. `RegistryBootValidated` event emitted after successful construction with real config.
15. Event bus failure during chain does not crash the registry (safe-emit).

Commit: `test(registry): add HTTP-level integration tests for chain/fan_out/locked semantics`

---

### 2.6 — Re-run characterization equivalence

**Files:** none (zero source changes — verification only)

Re-run the characterization tests against the code after locked/fan_out migration:

```bash
pytest tests/integration/scraper/test_legacy_fallback_snapshot.py -q
```

Expected: exit 0, all 6 tests pass.

This asserts equivalence still holds after Phase 2 migration (locked/fan_out added
on top of chain from Phase 1). If any characterization test fails, Phase 2 changes
have broken the pre-migration behavioral contract — do NOT proceed.

No commit produced (verification only).

---

## On gate failure

If `## Phase gate` fails, do NOT proceed to the next phase. Revert the failing
sub-phase's commit (`git revert <sha>` for the most recent commit, or
`git reset --hard HEAD~N` for multiple) and re-invoke `/implement:phase` to retry
the sub-phase. The phase gate must be green before any cross-phase work continues.

---

## Phase gate

From DESIGN §9 Phase 2:

> `make check`; `rg "TMDBClient|TVDBClient|self\._tmdb|self\._tvdb"
personalscraper/scraper/ -t py` returns zero hits.

---

## ACC criteria touched

- **ACC-03** — confirmed zero `self._tmdb`/`self._tvdb` in `scraper/` (all sub-phases)
- **ACC-09** — E2E pass count still matches baseline integer from `IMPLEMENTATION.md` (gate check)
- **ACC-13** — characterization tests still green after locked/fan_out migration (sub-phase 2.6)
