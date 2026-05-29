# Phase 25 — Test coverage gaps

Created from `pr-test-analyzer` audit (2026-05-27). 5 gaps identified:

1. **ACC-04b** over-mocks (`test_info_providers_exits_nonzero_on_missing_creds`):
   monkeypatches `ProviderRegistry` to raise `RegistryConfigError([])` — would
   still pass if env validation were silently removed.
2. **ACC-05b** similar: the committed `bad_providers.json5` fixture is checked
   for existence but never fed through the real validator.
3. **Phase 16 chain-exhaustion end-to-end** missing: no scraper-level test
   asserting that when all chain providers raise network errors, `result.error`
   reaches the legacy shape via the new `OnFailure: raise` contract.
4. **ProviderExhaustedEvent emission** has no end-to-end integration test
   (only the helper has a unit test).
5. **Phase 15 failure-path** missing: no test asserts behavior when
   `load_config` legitimately raises (e.g. malformed user config).

## Gate

- Phases 7–24 complete.
- Phase 21 (chain semantics fix) and Phase 22 (emit helpers public) may shift
  the exact assertion targets — coordinate test names accordingly.

## Goal

Each gap closed with a dedicated test that would catch the regression class
the agent identified.

## Scope

- `tests/commands/test_info_providers.py` — replace over-mocked ACC-04b/05b
  tests with real subprocess-style tests.
- `tests/integration/scraper/` — new chain-exhaustion end-to-end test.
- `tests/integration/api/metadata/registry/test_events.py` — assert
  `ProviderExhaustedEvent` emitted from production chain path.
- `tests/commands/` — failure-path test for malformed config.

## Sub-phases

### 25.1 — ACC-04b: real subprocess test

Replace mocked test with a CliRunner-based test that:

- Sets up a real `make_typed_settings_stub()` minus the TMDB_API_KEY field
  (or removes the env var via `os.environ.pop`).
- Invokes `personalscraper info providers`.
- Asserts exit code non-zero AND
  `"RegistryConfigError" in result.stderr` AND
  `"tmdb" in result.stderr`.

Catches: a regression where env validation in `_validation.py` is bypassed.

Commit: `test(commands): ACC-04b real-validation test (no over-mocking)`

### 25.2 — ACC-05b: real fixture exercise

Add a test that:

- Loads `tests/fixtures/bad_providers.json5` via the real
  `ProviderRegistry(providers_config=...)` constructor.
- Asserts the raised `RegistryConfigError.issues` contains the 6 expected
  family codes (unknown_provider, empty_chain_section, protocol_mismatch,
  missing_credentials, locked_capability_orphan, idcrossref_cycle).

Catches: drift between the fixture file and the validator's accepted schema.

Commit: `test(registry): ACC-05b exercises bad_providers fixture through real validator`

### 25.3 — Phase 16 chain-exhaustion end-to-end

New test in `tests/integration/scraper/`:

- Configure registry with 2 movie providers, both mocked to raise `ApiError`.
- Invoke `scrape_movie(...)` (or movie_service equivalent).
- Assert `result.action == "error"` AND
  `result.error` contains the LAST provider's exception message AND
  `ProviderExhaustedEvent` was emitted on the bus.

Catches: silent regression where exhaustion swallows the original cause and
the user sees `result.error = None`.

Commit: `test(scraper): regression — chain exhaustion preserves last_exception in result.error`

### 25.4 — ProviderExhaustedEvent integration emission

In `tests/integration/api/metadata/registry/test_events.py`, add:

- A test that drives `registry.chain(MovieDetailsProvider)` to exhaustion with
  all providers raising network errors.
- Captures bus events, asserts `ProviderExhaustedEvent` appears with the
  correct `capability` + non-empty `attempted` list + non-empty `item` dict.

Catches: refactor where chain raises but forgets to emit the observability
event (or the emit helper is renamed and a call site missed — Phase 22 risk).

Commit: `test(events): ProviderExhaustedEvent fires from production chain path`

### 25.5 — Phase 15 failure-path: malformed config

In `tests/commands/`, add:

- A test that invokes `personalscraper info providers --config <malformed.json5>`
  (or a similar CLI command) without mocking the config loader.
- Asserts the user gets a typer-friendly error (exit code non-zero,
  human-readable message in stderr — not a Python traceback).

If Phase 21's I3 finding (library_backfill_ids no try/except wrapping
RegistryConfigError) is fixed in a separate phase, this test also covers it.

Catches: a new CLI command accidentally short-circuits real config loading.

Commit: `test(commands): failure-path for malformed --config + real load`

### 25.6 — Test-count baseline re-pin

After 25.1–25.5 land, re-measure ACC-07 and ACC-09 baselines and update
`ACCEPTANCE.md` + `IMPLEMENTATION.md`. Coordinate with Phase 20's re-pin
sub-phases (this is a follow-up tick).

Commit: `docs(registry): re-pin ACC-07 + ACC-09 baselines post Phase 25 test additions`

## Phase gate

- `make test` 5636+ passed (expect +5 to +10 new tests).
- Each new test fails if its target regression is introduced (verify by
  temporary code-flip during development).
- ACC-07 + ACC-09 baselines re-pinned (Phase 20 follow-up).

## ACC criteria touched

- ACC-04b, ACC-05b — now exercised by real-validator tests.
- ACC-07, ACC-09 — baselines re-pinned (collaborative with Phase 20).

## Cost estimate

- 25.1–25.5: ~15 min each via DeepSeek (5 × 15 = 75 min).
- 25.6: ~5 min.
- Total: ~80 min.

## Risk

Low. Adding tests is additive; no production behavior change.
