# Phase 6 — PR fixes cycle 2

> Fixes from `/implement:pr-review` cycle 2 (PR #199, 3-lens re-review of the cycle-1 delta). Cycle-1 fixes confirmed correct + complete; 2 medium test-only findings retained (pin the cycle-1 fixes). No code change.

**Goal:** Add a regression test that pins the F-C observability fix (per the repo rule "Test de régression par bug"), and a test that pins the DESIGN §4 error-then-fallback chain branch (resolving the GAP-2 two-layer ambiguity). Test-only — `acquire/airing.py` is unchanged and already verified correct.

---

## Gate

Phase 5 complete: `make check` green (6763 passed), cycle-1 fixes pushed, CI green on PR #199. All 22 airing tests pass.

---

## Sub-phase 6.1 — Two regression/coverage tests (`tests/acquire/test_airing.py`)

**Files:** Modify `tests/acquire/test_airing.py` only. Do NOT touch `personalscraper/acquire/airing.py` (it is correct as-is).

### Task 1 — pin the F-C observability fix + the error-then-fallback branch

- [ ] **F-I — observability regression test (repo rule: "Test de régression par bug").**
      First find the project's existing pattern for asserting a structlog warning (the logger is `personalscraper.logger.get_logger`, a `structlog.stdlib.BoundLogger`). Look at `tests/scraper/test_tv_service_extra.py` (it asserts `show_season_empty` / `show_season_fetch_failed` warnings) and mirror whatever capture mechanism it uses (`caplog`, a structlog capture fixture, or similar). Add `test_poll_aired_logs_warning_when_season_fails`:
  - Build a 1-season show whose single `EpisodeFetcher.get_episodes` raises `ApiError(provider='tvdb', http_status=500, message='boom')` (so the chain exhausts and the season yields nothing).
  - Assert a **WARNING**-level log record is emitted with the event `acquire.airing.season_provider_error` (assert the level is WARNING specifically — a future revert to `debug` MUST make this test fail; that is the regression-protection point).
  - Add a second assertion (same or sibling test) for the bare-`Exception` arm: make `get_episodes` raise a generic `RuntimeError` → assert the WARNING record carries traceback info (`exc_info` present / `record.exc_info is not None`), pinning the `exc_info=True` half of F-C.
  - **Non-vacuity check (do this, report it):** temporarily revert the `season_provider_error` log to `log.debug` in a working copy, run this test, confirm it FAILS, then `git checkout personalscraper/acquire/airing.py` (do NOT commit the revert). If it does not fail on the revert, the capture mechanism is wrong — fix the test.

- [ ] **F-J — error-then-fallback chain test (DESIGN §4 "errors OR returns empty").**
      Add `test_poll_aired_chain_fallthrough_on_primary_error`: registry `chain(EpisodeFetcher)` → `[primary, secondary]`; `primary.get_episodes` RAISES `ApiError(...)` (not returns empty), `secondary.get_episodes` returns `[_make_episode(1, 1, '2023-01-01')]`. Assert the secondary's episode IS surfaced AND `secondary.get_episodes.call_count >= 1` — proving the inner per-season swallow tries the NEXT fetcher on a raised error (the load-bearing inner layer, distinct from the empty-fall-through test).
  - **Non-vacuity check (report it):** this fails against a mutant where `_fetch_season_with_fallback`'s inner `except` does not `continue` to the next fetcher.

- [ ] **Gate 6.1:** `python -m pytest tests/acquire/test_airing.py -q` → 24 passed (22 + 2 new); `python -m ruff check tests/acquire/test_airing.py` clean; `python -m ruff format --check tests/acquire/test_airing.py` formatted. Both new tests assert WHICH (level/event/episode/call_count), never `len > 0` alone.
- [ ] **Commit:** `test(airing): pin F-C warning+exc_info observability + error-then-fallback chain branch`

---

## Final gate (main session, phase 6 milestone)

`make check` green + `python -c "import personalscraper"` smoke (no docs/feature_map change → design-gaps unchanged). Then mark phase 6 `[x]`.
