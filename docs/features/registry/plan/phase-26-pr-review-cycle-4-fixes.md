# Phase 26 — PR review cycle 4 fixes

Created from a 4-agent comprehensive review (2026-05-28) re-run after Phases 7–25
landed. **2 critical bugs** + **8 important / minor findings** uncovered. Two
agents (`code-reviewer` and `silent-failure-hunter`) **converged independently
on the same critical C1** (CircuitState enum vs string comparison), giving
high confidence that the finding is real.

Empirical verification done in-session:

- **C1** reproduced: `CircuitState.OPEN != "OPEN"` evaluates to `True` (value is
  lowercase `"open"`). All registry unit tests use string `state` via
  `SimpleNamespace` fakes (conftest.py:90–101), masking the bug.
- **C2** reproduced: `_check_idcrossref_cycles` raises
  `idcrossref_cycle` for `{tmdb, tvdb, imdb}` (3 IDCrossRef providers) — the
  docstring itself acknowledges the 3+ case is "inherent" but the body raises
  anyway. The template encourages users to add `imdb` once `OMDB_API_KEY` is set,
  so this is a denial-of-service on a valid config.

Local-instance discovery: `config/providers.json5` does NOT exist locally
(verified). The single-instance running `personalscraper info providers` boots
straight to `RegistryConfigError [empty_chain_section] x4`. Per user
memory rule _"modifs config/BDD/NFO ⇒ on fait évoluer en même temps qu'on code,
sur l'unique instance"_, this must be synced before merge.

## Gate

- Phases 0–25 complete (all [x] in IMPLEMENTATION.md).
- PR #27 currently `OPEN`, `mergeStateStatus=BLOCKED`.
- `make test` green (5649 passed, 4 skipped, 2 xfailed) before Phase 26 work
  begins — the new bugs are silent at the test layer.

## Goal

Close every finding from the cycle-4 review (2 critical + 8 important/minor +
3 housekeeping items), restore the registry's circuit-aware contract, and
re-align the local instance + acceptance baselines + docs so the PR can be
squashed into main with no leftover drift.

## Scope (the 10 review findings + 3 housekeeping)

### Critical (DESIGN-contract regressions)

- **C1** `personalscraper/api/metadata/registry/_factory.py:262` —
  `state != "OPEN"` compares enum to string; gate is a no-op in prod.
- **C2** `personalscraper/api/metadata/registry/_validation.py:265` —
  DFS on fully-connected ≥3-node IDCrossRef graph raises false-positive
  cycle issue.

### Important (silent failures + UX bugs)

- **I1** `personalscraper/api/metadata/registry/_events.py:76` +
  `__init__.py:498` — `RegistryFanOutCompleted.succeeded` field measures
  eligible-pre-call, contradicts its docstring.
- **I2** `personalscraper/api/metadata/registry/_errors.py:36-39` —
  `_format()` re-quotes the "did you mean" hint nested in itself.
- **I3** `personalscraper/commands/info.py:96` — interpolates
  `CircuitState.CLOSED` enum directly instead of `.value`.
- **I4** `personalscraper/scraper/existing_validator.py:548,594` —
  `registry.get("tmdb")` raises `UnknownProviderError` if tmdb not configured;
  swallowed by parent `except Exception`.
- **I7** `personalscraper/scraper/movie_service.py:480-489`,
  `personalscraper/scraper/tv_service.py:816-822` —
  `_family_to_client()` swallows `UnknownProviderError` returning `None`
  silently, no log.
- **I8** `personalscraper/scraper/tv_service.py:594` — catches only
  `(ValueError, TypeError, KeyError, AttributeError)`; DESIGN §6.2 says
  "unclassified Exception". A `RuntimeError` or custom-provider exception
  aborts the scrape unexpectedly. Asymmetric with `movie_service.py:857`
  which uses `except Exception`.
- **I9** `personalscraper/scraper/tv_service.py:1005` — episode NFO failure
  logged but not appended to `result.warnings`. Inconsistent with
  `_recover_movie_artwork` (`existing_validator.py:561`).

### Minor (polish, can be one-line fixes)

- **I5** `personalscraper/api/metadata/registry/__init__.py:280,281` +
  `_errors.py:75` + `_events.py:50,75` — `list[...]` on `frozen=True`
  dataclasses; should be `tuple[..., ...]`.
- **I6** `personalscraper/api/metadata/registry/__init__.py:119` vs
  `personalscraper/api/_contracts.py:124` — `Named` and `HasName` Protocols
  duplicate; neither is `@runtime_checkable`.
- **I10** `personalscraper/api/metadata/registry/__init__.py:627-637` —
  `cross_ref()` logs `ApiError`/`CircuitOpenError` but does not emit a
  `ProviderFallbackTriggered(reason="network", ...)` event.

### Housekeeping (drift + missing-docs items found alongside review)

- **H1** `config/providers.json5` missing on the local instance — must be
  created from `config.example/providers.json5` before merge.
- **H2** ACC-07 (55 → **56**) and ACC-09 (339 → **341**) drifted after
  Phases 25.2 + 25.3 + 25.4 added 3 regression tests; Phase 20 re-pin is now
  stale. Update `ACCEPTANCE.md` + `IMPLEMENTATION.md`.
- **H3** `docs/reference/commands.md` has no entry for the new
  `personalscraper info providers` sub-command (flagged by
  `scripts/audit-cli-coverage.py` during `make check`).

## Sub-phases

### 26.1 — C1 + C2 (production bugs)

Restore the circuit-aware gate and fix the false-positive cycle detection.

**Changes**:

1. `personalscraper/api/metadata/registry/_factory.py:262`:
   replace `return state != "OPEN"` with
   `return state is not CircuitState.OPEN` (and import `CircuitState` at the
   top of the module).
2. `personalscraper/api/metadata/registry/_validation.py:265`: after computing
   `nodes`, add `if len(nodes) >= 3: return issues` (the docstring already
   acknowledges this case is inherent — the function should match its
   contract).
3. **Pivot the test fakes** in `tests/unit/api/metadata/registry/conftest.py`
   to use the real `CircuitState` enum (replace `state="CLOSED"` /
   `state="OPEN"` / `state="HALF_OPEN"` literals with the corresponding
   enum members). This is the only way the existing 56 unit tests can
   catch C1-style regressions in the future.
4. Add regression tests:
   - `tests/unit/api/metadata/registry/test_registry_eligibility.py`:
     `test_eligible_real_circuit_open_rejected` — instantiates a real
     `CircuitBreaker`, drives it to OPEN, asserts `_eligible(...)` returns
     `False`.
   - `tests/unit/api/metadata/registry/test_registry_validation.py`:
     `test_no_cycle_false_positive_with_3_idcrossref_providers` — feeds 3
     IDCrossRef providers, asserts `_check_idcrossref_cycles` returns `[]`.

**Acceptance**: both new tests pass; the existing fan-out/chain/locked
unit tests still pass after the conftest pivot (some may need adjustment if
they relied on string identity).

Commits:

- `fix(registry): _eligible compares CircuitState enum (not string)`
- `fix(registry): allow 3+ IDCrossRef providers (inherent cycle is not a config error)`
- `refactor(tests): conftest fakes use real CircuitState enum`
- `test(registry): regression — _eligible rejects real OPEN CircuitBreaker`
- `test(registry): regression — 3 IDCrossRef providers do not trigger cycle false-positive`

### 26.2 — I8 + I7 + I9 (chain semantics + silent failures)

Align all chain-iteration catch blocks with DESIGN §6.2; surface previously
silent failures.

**Changes**:

1. `personalscraper/scraper/tv_service.py:594` — broaden to `except Exception
as e` (match `movie_service.py:857` and DESIGN §6.2). Update the
   `AttemptOutcome` `reason` if needed.
2. `personalscraper/scraper/movie_service.py:480-489` and
   `personalscraper/scraper/tv_service.py:816-822` — `_family_to_client()`
   add `log.warning("xref_family_unwired", family=family,
exc_type=type(e).__name__)` before returning `None`. (Do NOT raise — boot
   validation should already have caught this; the log is a forensic anchor
   for the impossible case.)
3. `personalscraper/scraper/tv_service.py:1005` — episode NFO failure:
   append to `result.warnings`. Mirror the
   `existing_validator.py:561` shape: `result.warnings.append(f"episode_nfo_failed: episode={ep.title} reason={e}")`.

**Acceptance**:

- New test in `tests/scraper/test_tv_service_extra.py`:
  `test_tv_chain_details_continues_on_runtime_error` — provider raises
  `RuntimeError` during details fetch, registry has 2 providers, chain
  continues, `ProviderFallbackTriggered(reason="other")` emitted.
- New test:
  `test_family_to_client_logs_warning_on_unknown_provider` — registry without
  tmdb, call `_family_to_client("tmdb")`, capture `caplog` for the warning.
- New test in `tests/scraper/test_tv_service_extra.py`:
  `test_episode_nfo_failure_appended_to_result_warnings` — episode write
  raises, scrape completes, `result.warnings` non-empty.

Commits:

- `fix(scraper): tv_service.py chain catches Exception (align DESIGN §6.2 with movie_service)`
- `fix(scraper): _family_to_client logs warning on UnknownProviderError`
- `fix(scraper): episode NFO failure surfaces in result.warnings`
- `test(scraper): regression — tv chain continues on RuntimeError`
- `test(scraper): regression — _family_to_client logs forensic warning`
- `test(scraper): regression — episode NFO failure in result.warnings`

### 26.3 — I3 + I2 (UX bugs)

CLI display + error-message cleanup.

**Changes**:

1. `personalscraper/commands/info.py:96` — replace `s.circuit_state` with
   `s.circuit_state.value` in the f-string. Update ACC-04a expected output
   if necessary (the grep is on `circuit=`, not the value, so it should
   still pass — confirm).
2. `personalscraper/api/metadata/registry/_errors.py:36-39` — drop the
   re-extraction of the "did you mean" hint; `issue.message` already
   contains it.

**Acceptance**:

- `personalscraper info providers --config config.example/providers.json5`
  output now shows `circuit=closed` (not `circuit=CircuitState.CLOSED`).
- A test feeding a misspelled provider name through `_format()` asserts
  the formatted output appears once, not twice (no nested re-quoting).

Commits:

- `fix(cli): info providers prints circuit state value, not enum repr`
- `fix(registry): RegistryConfigError no longer re-quotes did-you-mean hint`
- `test(registry): regression — _format does not nest did-you-mean`

### 26.4 — I1 + I10 (event correctness)

Make the EventBus semantics match their docstrings.

**Changes**:

1. `personalscraper/api/metadata/registry/_events.py:76` —
   `RegistryFanOutCompleted.succeeded` rename to `eligible` AND update
   docstring to "Number of providers that survived eligibility filtering
   (circuit CLOSED or HALF_OPEN), before the caller fans out." Update all
   call sites and tests.
2. `personalscraper/api/metadata/registry/__init__.py:627-637` — `cross_ref()`
   on `ApiError`/`CircuitOpenError` emit
   `ProviderFallbackTriggered(reason="network", from_provider=match.provider,
to_provider=None, exc_type=type(e).__name__)` before returning `None`.

**Acceptance**:

- New test in `tests/integration/api/metadata/registry/test_events.py`:
  `test_cross_ref_emits_provider_fallback_on_api_error`.
- Existing `test_fan_out_*` assertions on `succeeded` updated to
  `eligible` (mechanical rename).

Commits:

- `refactor(events): RegistryFanOutCompleted.succeeded → .eligible (docstring-truth)`
- `fix(registry): cross_ref emits ProviderFallbackTriggered on network failure`
- `test(events): regression — cross_ref network failure emits fallback event`

### 26.5 — I5 + I6 + I4 (type design + safety polish)

Tighten frozen-dataclass invariants, consolidate the `Named` Protocol, and
add a typed pre-check on the artwork-recovery `tmdb`-only path.

**Changes**:

1. **`list[...]` → `tuple[..., ...]`** on `frozen=True` dataclasses:
   - `personalscraper/api/metadata/registry/__init__.py:280,281` —
     `FanOutResult.values`, `.attempted`.
   - `personalscraper/api/metadata/registry/_errors.py:75` —
     `ProviderExhausted.attempted`.
   - `personalscraper/api/metadata/registry/_events.py:50,75` —
     `ProviderExhaustedEvent.attempted`, `RegistryFanOutCompleted.attempted`.
     Update all construction sites (`tuple(eligible)`, `tuple(attempted)`).
2. **`Named` ↔ `HasName` consolidation**:
   - Drop `Named` from `personalscraper/api/metadata/registry/__init__.py:119`.
   - Promote `HasName` (`personalscraper/api/_contracts.py:124`) to
     `@runtime_checkable` and rename to `Named` (canonical name). Export
     from `personalscraper/api/_contracts.py`.
   - Update all `Named` references in the registry to import from
     `personalscraper/api/_contracts`.
   - Drop `cast(Named, ...)` at `__init__.py:604` (now structurally checked).
3. `personalscraper/scraper/existing_validator.py:548,594` — pre-check
   `if "tmdb" not in self._registry.providers_for(MovieDetailsProvider): return`
   before `registry.get("tmdb")` (avoids the swallowed `UnknownProviderError`).

**Acceptance**:

- `make lint` green (mypy may surface the consumer-side `cast(Named, ...)`
  removals — adjust accordingly).
- New test: `test_recover_artwork_skipped_when_tmdb_not_configured`.
- All `FanOutResult(...)` / `ProviderExhausted(...)` / event constructors
  pass tuples — mechanical update.

Commits:

- `refactor(registry): frozen dataclasses use tuple (not list) for invariants`
- `refactor(registry): consolidate Named/HasName into one runtime_checkable Protocol`
- `fix(scraper): existing_validator pre-checks tmdb in registry before refetch`
- `test(scraper): regression — artwork recovery skipped when tmdb unconfigured`

### 26.6 — H1 + H2 + H3 (housekeeping)

Sync the local instance, re-pin acceptance baselines, document the new
CLI command.

**Changes**:

1. **H1** Create `config/providers.json5` by copying
   `config.example/providers.json5`. Adapt if the user's local TMDB/TVDB
   priorities differ — verify with the user before committing.
2. **H2** Re-measure ACC-07 and ACC-09 from the working tree
   (post-26.1–26.5 — new tests added). Update `ACCEPTANCE.md` pinned
   baseline section AND `IMPLEMENTATION.md` baseline measurements section.
3. **H3** Add a section to `docs/reference/commands.md` for
   `personalscraper info providers`. Include synopsis, options
   (`--config`), expected output sample, exit codes.
4. Mark Phase 26 [x] in `IMPLEMENTATION.md` and tick the
   `Phase 26 — PR review cycle 4 fixes` line in the phases table.

Note on H1: `config/` is gitignored — the commit will use `git add -f`
explicitly and the message will reference H1 housekeeping. Do NOT commit
any API keys.

Commits:

- `chore(config): sync local providers.json5 from template (H1)`
- `docs(registry): re-pin ACC-07 (56) + ACC-09 (341) post Phase 26 (H2)`
- `docs(reference): document personalscraper info providers (H3)`
- `chore(registry): phase 26 gate — PR review cycle 4 fixes complete`

## Phase gate

- `make check` green (lint + tests + module-size + audit-cli-coverage).
- `make test` 5649 + ~12 new tests passed (expect ~5661).
- ACC-01..13 all pass with the re-pinned ACC-07=56 and ACC-09=341.
- `personalscraper info providers --config config.example/providers.json5`
  prints `circuit=closed` (verifies I3).
- `personalscraper info providers` from a clean checkout WITHOUT
  `config/providers.json5` raises `RegistryConfigError` cleanly (ACC-04b).
- `personalscraper info providers --config <3-idcrossref-config>` boots
  successfully (verifies C2 fix).
- 6 sub-phase commits + 1 gate commit pushed to `feat/registry`.
- PR #27 CI green; `mergeStateStatus` transitions to `CLEAN`.

## ACC criteria touched

- **ACC-04a / ACC-04b / ACC-06**: output format change (`circuit=closed`
  not `circuit=CircuitState.CLOSED`); grep targets are stable (`circuit=`
  and provider names).
- **ACC-07**: re-pinned 55 → 56 (regression test added in 25.2, then
  Phase 26 adds at least 3 more registry unit tests → re-measure).
- **ACC-09**: re-pinned 339 → 341 → re-measure after Phase 26 test
  additions.

## Cost estimate

- 26.1 (C1 + C2 + conftest pivot + 2 regression tests): ~45 min Sonnet
- 26.2 (3 fixes + 3 regression tests): ~40 min Sonnet
- 26.3 (2 small fixes + 1 test): ~20 min DeepSeek
- 26.4 (2 fixes + rename across call sites + 1 test): ~35 min Sonnet
- 26.5 (type polish + Named consolidation + 1 test): ~50 min Sonnet
- 26.6 (housekeeping): ~25 min Sonnet
- **Total**: ~3h35 (matches "Tout" scope estimate).

## Risk

**Medium**. C1 + C2 are real production bugs; the conftest pivot in 26.1
may surface latent string-comparison assumptions in other tests. Plan
contingency: if conftest pivot breaks > 5 tests, split 26.1 into a
"fakes pivot" sub-phase that lands BEFORE the fix, so the regression
tests pass against the broken code first (true TDD red→green).

I5 + I6 (type-design polish) is the most invasive change of the phase —
the `Named`/`HasName` consolidation crosses module boundaries. Roll
back 26.5 isolated if mypy errors compound.
