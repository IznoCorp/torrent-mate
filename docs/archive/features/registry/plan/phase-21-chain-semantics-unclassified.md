# Phase 21 — Restore chain fallback on unclassified Exception (C2/C3)

Created from `silent-failure-hunter` audit finding C2 + C3 (2026-05-27).

DESIGN §6.2 promises chain fallback semantics: "Try providers in config order;
first one that returns a usable result wins." But the Phase 7+16 chain
implementations include a final broad `except Exception:` that **sets
`result.error` and returns None — short-circuiting the chain instead of
continuing to the next provider**.

Concrete case (movie_service.py:599, tv_service.py:594, tv_service_episodes.py:188):
A `ValueError` from JSON parsing in TMDB causes the chain to skip TVDB entirely,
without emitting any `ProviderFallbackTriggered` event. Observers see no signal
that a fallback was bypassed.

Same pattern in `backfill_ids.py` (lines 536, 681): broad `except Exception`
without `ProviderFallbackTriggered` emission — operators lose provenance.

`AttemptOutcome.reason` Literal already accepts `"other"` (registry/**init**.py:197)
but no production site emits it.

## Gate

- Phase 16 complete (chain exhaustion raises ProviderExhausted).
- `AttemptOutcome.reason` Literal includes `"other"`.

## Goal

Every unclassified exception in chain iteration:

1. Emits `ProviderFallbackTriggered(reason="other", exc_type=type(exc).__name__)`.
2. Records `AttemptOutcome(reason="other", detail=type(exc).__name__)`.
3. Continues to the next provider (preserving DESIGN §6.2 fallback promise).
4. Only raises `ProviderExhausted` if every provider attempted failed.

`backfill_ids.py` broad-except sites emit `ProviderFallbackTriggered` for
parity with chain sites.

## Scope

- `personalscraper/scraper/movie_service.py::_match_movie_candidates` + the
  details-fetch site (line 834).
- `personalscraper/scraper/tv_service.py::_match_tvshow_candidates` + `_lookup_series` details.
- `personalscraper/scraper/tv_service_episodes.py::match_tvshow_candidates`.
- `personalscraper/indexer/scanner/_modes/backfill_ids.py::_fetch_cross_provider_ids` (line 536).
- `personalscraper/indexer/scanner/_modes/backfill_ids.py::_call_rating_provider` (line 681).
- Tests: add regression test asserting fallback-on-unclassified semantics.

## Sub-phases

### 21.1 — movie_service unclassified Exception → fallback

Replace `except Exception as exc:` short-circuit branch with:

```python
except Exception as exc:
    last_exception = exc
    attempted.append(
        AttemptOutcome(
            provider=RegistryProviderName(provider_name),
            reason="other",
            detail=type(exc).__name__,
        )
    )
    log.warning(
        "registry_provider_fail",
        provider=provider_name,
        capability="MovieDetailsProvider",
        exc_type=type(exc).__name__,
    )
    self._registry.emit_provider_fallback(  # (or _emit_… per Phase 22)
        capability="MovieDetailsProvider",
        from_provider=provider_name,
        reason="other",
        exc_type=type(exc).__name__,
        item=item_context,
    )
    continue
```

Add unit test: `test_chain_unclassified_exception_continues_to_next_provider`
that mocks one provider to raise `ValueError` and asserts the next provider
is consulted + the event fired.

Commit: `fix(scraper): movie_service chain continues on unclassified Exception (DESIGN §6.2)`

### 21.2 — tv_service + tv_service_episodes unclassified → fallback

Symmetric refactor for both tv_service sites + the episode chain.

Commit: `fix(scraper): tv_service + episodes chain continues on unclassified Exception`

### 21.3 — backfill_ids unclassified → emit fallback

In `_fetch_cross_provider_ids` (line 536) and `_call_rating_provider` (line 681),
before returning `{}` or skipping the provider, emit
`ProviderFallbackTriggered(reason="other", exc_type=...)` for parity with the
classified branches. The broad-except `# noqa: BLE001` stays (fail-soft is
intentional) but the bus signal is restored.

Commit: `fix(indexer): backfill_ids emits ProviderFallbackTriggered on unclassified Exception`

### 21.4 — Regression tests

- `tests/scraper/test_chain_fallback_unclassified.py` (NEW): asserts movie/tv
  chain continues to next provider on `ValueError` / `KeyError` / generic Exception.
- `tests/integration/api/metadata/registry/test_events.py`: add assertion that
  `ProviderFallbackTriggered(reason="other")` is emitted on the unclassified path.
- `tests/indexer/scanner/test_backfill_ids_mode.py`: add similar for backfill_ids.

Commit: `test(registry): regression coverage for unclassified-exception chain fallback`

## Phase gate

- `make test` 5636+ passed (new tests bump count).
- `rg --type py "except Exception" personalscraper/scraper/ personalscraper/indexer/scanner/_modes/backfill_ids.py` shows every site emits a `ProviderFallbackTriggered` or has a documented rationale.
- DESIGN §6.2 fallback promise honored.

## ACC criteria touched

- None directly; this hardens chain semantics behind ACC-13 + ACC-09 anchors.

## Cost estimate

- 21.1–21.3: ~10–15 min each (Opus 1M for movie/tv changes due to test coupling).
- 21.4 tests: ~15 min DeepSeek.
- Total: ~45–60 min.

## Risk

Medium. Existing tests may assume the old fail-soft contract (where TMDB
ValueError → action="error" without fallback). Mitigate by re-running ACC-13
characterization tests after each commit. If a test breaks, decide whether the
test encodes a real contract (revert + update plan) or an accidental behavior
(update the test).
