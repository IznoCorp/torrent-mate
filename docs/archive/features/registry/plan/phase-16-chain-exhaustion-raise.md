# Phase 16 — Align scraper chain exhaustion to DESIGN §6.2 (raise ProviderExhausted)

Created as the follow-up to Phase 7 sub-phases 7.1 + 7.2 concerns. The chain iteration in `movie_service._match_movie_candidates` and `tv_service._match_tvshow_candidates` sets `result.error` inline instead of raising `ProviderExhausted`, deviating from DESIGN §6.2 line 79 ("OnFailure: raise ProviderExhausted") and §10 line 787 ("Catch in caller, produce ScrapeResult").

## Gate

- Phase 7 complete (chain semantics in production).
- ACC-13 baseline (`tests/integration/scraper/test_legacy_fallback_snapshot.py`) green.

## Goal

Make the chain iteration sites raise `ProviderExhausted` and let the immediate caller (`scrape_movie` / `scrape_tvshow`) catch it and populate `result.error` / `result.action = "error"`. Preserve the existing observable behavior (action=error + original exception message) while restoring the DESIGN contract.

## Scope

- `personalscraper/scraper/movie_service.py` — `_match_movie_candidates` raises; caller catches.
- `personalscraper/scraper/tv_service.py` — `_match_tvshow_candidates` raises; caller catches.
- `personalscraper/api/metadata/registry/_errors.py` — `ProviderExhausted.__str__` may need to include the last exception's message so the caught `str(e)` matches the existing ACC-13 contract.
- `tests/scraper/test_scraper.py` — `test_error_on_match_failure` may need to adapt to the new error-message wording (or assert via the chained `__cause__`).
- `tests/integration/scraper/test_legacy_fallback_snapshot.py` (ACC-13) — must continue to PASS.

## Sub-phases

### 16.1 — Augment `ProviderExhausted` with last-exception preservation

Currently `ProviderExhausted(capability, attempted, item_context)` doesn't carry the last exception's message. Add it:

```python
class ProviderExhausted(RegistryError):
    def __init__(
        self,
        capability: type,
        attempted: list[AttemptOutcome],
        item_context: dict[str, Any],
        last_exception: Exception | None = None,
    ) -> None:
        self.capability = capability
        self.attempted = attempted
        self.item_context = item_context
        self.last_exception = last_exception
        last_msg = f": {last_exception}" if last_exception else ""
        super().__init__(
            f"Chain exhausted for {capability.__name__}{last_msg} "
            f"(attempted: {[a.provider for a in attempted]})"
        )
```

Add unit test: `test_provider_exhausted_str_carries_last_exception_message`.

Commit: `feat(registry): ProviderExhausted carries last_exception for error message preservation`

### 16.2 — `_match_movie_candidates` raises

Replace the existing "set result.error inline" branch with `raise ProviderExhausted(...)`. The caller (`scrape_movie`) catches it.

```python
# In _match_movie_candidates (currently sets result.error and returns None):
if attempted and any(a.reason in {"circuit_open", "network"} for a in attempted):
    self._registry._emit_provider_exhausted(
        capability="MovieDetailsProvider",
        attempted=attempted,
        item=item_context,
    )
    log.error("registry_chain_exhausted", ...)
    raise ProviderExhausted(
        capability=MovieDetailsProvider,
        attempted=attempted,
        item_context=item_context,
        last_exception=last_exception,
    )
# Otherwise (empty chain or all empty_result) — current "legacy no-match" path stays as None return.
```

In `scrape_movie` (or wherever match is consumed):

```python
try:
    match = self._match_movie_candidates(title, year, result)
except ProviderExhausted as e:
    result.error = f"Match failed: {e.last_exception or e}"
    result.action = "error"
    return result
```

The ACC-13 contract (`"API down" in result.error`) is preserved because `ProviderExhausted.last_exception` carries the original `ApiError("API down")`.

Commit: `refactor(scraper): movie_service raises ProviderExhausted; scrape_movie catches`

### 16.3 — `_match_tvshow_candidates` raises (symmetric to 16.2)

Apply the same refactor to tv_service.

Commit: `refactor(scraper): tv_service raises ProviderExhausted; scrape_tvshow catches`

### 16.4 — Verify ACC-13 contract preserved

```bash
python -m pytest tests/integration/scraper/test_legacy_fallback_snapshot.py -v
python -m pytest tests/scraper/test_scraper.py::test_error_on_match_failure -v
```

Both must pass. If `test_error_on_match_failure` breaks because the message format changed: adjust the assertion to match the new wording while still asserting "API down" appears somewhere in `result.error`.

Commit: `chore(scraper): verify chain exhaustion preserves ACC-13 contract (Phase 16 gate)`

## Phase gate

- `_match_movie_candidates` / `_match_tvshow_candidates` raise `ProviderExhausted` (no more inline result.error set).
- `scrape_movie` / `scrape_tvshow` catch and surface as `action="error"` with original message.
- ACC-13 (`test_legacy_fallback_snapshot.py`) green.
- `make test` exit 0.

## ACC criteria touched

- ACC-13 — must remain PASS.

## Cost estimate

- 16.1: ~10 min DeepSeek.
- 16.2: ~15 min DeepSeek (movie path).
- 16.3: ~15 min DeepSeek (tv path).
- 16.4: ~5 min verification.
- Total: ~45 min.

## Risk

Low. The contract restoration is a small refactor with strong test coverage (ACC-13 anchor + scraper unit tests).
