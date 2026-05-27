# Phase 15 — Remove autouse `_patch_provider_registry_for_cli_tests`

Created as the follow-up to Phase 9.1 + Phase 14. With Phase 14 making `TVDBClient.__init__` pure-Python, the autouse fixture that stubs `ProviderRegistry` for CLI tests is no longer needed.

## Gate

- Phase 14 complete: `TVDBClient(settings=...)` is HTTP-free at construction.
- Phase 9.1 complete: every CLI test uses `make_typed_settings_stub()` (not `MagicMock()`).

## Goal

Remove the autouse `_patch_provider_registry_for_cli_tests` fixture from `tests/conftest.py`. Verify all CLI tests pass with the real `ProviderRegistry` booted on the typed Settings stub.

## Scope

- `tests/conftest.py` — DELETE the autouse fixture and its skip-paths block.
- Possibly other test files where event-counting assertions expected the stubbed registry to emit nothing — adjust to filter for the relevant event types only.

## Sub-phases

### 15.1 — Smoke test on one CLI test file

After Phase 14 lands, run:

```bash
python -m pytest tests/commands/test_run_e2e.py -x -q
```

with the autouse fixture STILL in place — must pass (regression check).

Now temporarily comment out the autouse (or move test_run_e2e.py to the skip_paths) and re-run. Investigate any failure. Likely outcomes:

- **Pass**: typed Settings + deferred TVDB bootstrap = real registry boots silently. Proceed to 15.2.
- **Fail with `RegistryBootValidated` event count assertion mismatch**: real registry emits the boot event; test asserts on event count. Fix the test to filter or expect the new event.
- **Fail with provider HTTP call**: some other provider also makes a construction-time HTTP call. Add a Phase 14.x sub-phase to defer it too.

Commit: `test(registry): smoke-test test_run_e2e.py without autouse (Phase 15 prep)`

### 15.2 — Remove the autouse fixture

Edit `tests/conftest.py`:

- DELETE the `@pytest.fixture(autouse=True)` decorator AND the function body of `_patch_provider_registry_for_cli_tests`.
- Replace with a one-paragraph comment explaining the historical context and that Phases 14+15 made the patching unnecessary.

```python
# NOTE: The legacy autouse `_patch_provider_registry_for_cli_tests` fixture was
# removed in feat/registry Phase 15. CLI tests now rely on:
#   - tests/fixtures/settings_stub.make_typed_settings_stub() — typed Settings
#     with dummy credentials that boot ProviderRegistry cleanly (Phase 9.1).
#   - TVDBClient deferred bootstrap (Phase 14) — no HTTP call at __init__.
# Real ProviderRegistry boots silently end-to-end on every CLI test.
```

Commit: `refactor(registry): remove autouse _patch_provider_registry_for_cli_tests (Phases 9.1+14 unblocked)`

### 15.3 — Fix event-count regressions (if any)

Real registry emits `RegistryBootValidated` at every CLI test boot. Tests that assert on bus event counts may need adjustment:

```python
# BEFORE (relied on stubbed registry emitting nothing):
assert len(captured) == N

# AFTER:
relevant = [e for e in captured if isinstance(e, ItemProgressed)]  # or the relevant type
assert len(relevant) == N
```

Find candidates: `rg --type py "assert len\(captured\) ==" tests/`.

Commit: `test(registry): filter bus captures by relevant event type (Phase 15 follow-up)`

### 15.4 — Verify

- `make test` → 5625+ passed (count may shift +/-N depending on adjusted tests).
- `make lint` → clean.
- `rg --type py "_patch_provider_registry_for_cli_tests" tests/` → empty (fixture removed).
- `rg --type py "skip_paths" tests/conftest.py` → empty (the skip_paths tuple is gone).

Commit: `chore(registry): verify autouse removal (Phase 15 gate)`

## Phase gate

- Autouse fixture removed from `tests/conftest.py`.
- All CLI tests pass with real `ProviderRegistry` booting on `make_typed_settings_stub()`.
- `make test` exit 0.

## ACC criteria touched

- ACC-07 — test count may shift if some tests are added/removed during event-count adjustments.

## Cost estimate

- 15.1: 10 min (smoke test).
- 15.2: 5 min (deletion + comment).
- 15.3: 10-20 min if any event-count tests need adjustment.
- 15.4: 5 min.
- Total: ~30-40 min.

## Risk

Low-medium. The unblocking work happens in Phase 14. This phase is essentially the cleanup. Risk: hidden tests that rely on the stubbed registry behavior — caught by `make test`.

## Depends on

- Phase 14 (TVDB bootstrap deferral).
