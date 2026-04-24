# Phase 04 — Hotspot trimming

**Goal**: cut `@patch` count in the three hottest files from 145 total (37 + 66 + 42 measured on `d98ee04`) to ≤ 58 (≥ 60 % reduction). The new integration tier from phases 2–3 absorbs the removed invariants.

## Gate (from Phase 03)

- `tests/integration/` has ≥ 15 catalogue tests + smoke, all green.
- Baseline `@patch` counts re-measured at the start of this phase and recorded in the first commit body.

## Sub-phase 4.1 — `tests/dispatch/test_dispatcher.py` (37 → ≤ 15)

- Introduce a module-level `@pytest.fixture(autouse=True)` `_rsync_on_path(monkeypatch)` that sets `monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/rsync" if name == "rsync" else None)`. Removes the 25 repeated `@patch("shutil.which", return_value="/usr/bin/rsync")` decorators.
- Identify every test whose primary assertion is an effect already covered in `tests/integration/test_dispatch_*`:
  - replace (integration 3.2), merge (integration 3.3), new-placement (integration 3.2), crash recovery (integration 3.3).
  - Delete those tests; leave a pointer comment at the top of the file listing what moved and where.
- Keep unit tests for: pure resolver helpers (`_resolve_existing_on_filesystem`, `_has_ntfs_illegal_names`), `DispatchResult` dataclass, the `_force_rmtree` retry semantics, and any test that exercises a branch not reachable from integration.
- Drop any `@patch("personalscraper.dispatch.dispatcher._rsync")` — the integration tier does real rsync.

Target: ≤ 15 `@patch` uses remaining.

### Commit

`refactor(tests): trim test_dispatcher hotspot, keep resolver unit tests`

## Sub-phase 4.2 — `tests/test_cli.py` (66 → ≤ 25)

- Introduce an autouse fixture in `tests/conftest.py` (scoped to the CLI test file via `request.fspath.basename == "test_cli.py"`) named `_stub_pipeline_steps` that monkeypatches each `run_*` step to a no-op `StepReport`. Removes the dozens of per-test `@patch("personalscraper.<module>.run_*")` decorators.
- Keep narrow per-test patches only where the test itself asserts on the patch-call arguments (wiring tests).
- **Inventory step first, before any change**: enumerate every test function in `test_cli.py` and classify each as `wiring` (keep, narrow mock) / `pure_cli` (keep, remove broad mocks) / `real-fs-candidate` (move to `tests/integration/`). Record this classification as a markdown table in the commit body. No silent moves.
- Move `real-fs-candidate` tests into the appropriate `tests/integration/test_*.py` file from phases 2–3 (do not create a new `test_cli_e2e.py`; the integration tier is the destination). If a candidate has no integration counterpart yet, leave it in place with a `# TODO(test-realism): move to integration` comment and log it in the commit body.

Target: ≤ 25 `@patch` uses remaining.

### Commit

`refactor(tests): collapse CLI step-mocks into autouse fixture`

## Sub-phase 4.3 — `tests/test_pipeline_integration.py` (42 → ≤ 12)

- Rename the file to `tests/test_pipeline_orchestration.py` via `git mv` — the new name reflects its actual scope (orchestrator unit test). The misleading "integration" label disappears.
- Update every live reference to the old filename in the same commit. Audit at start of sub-phase via `git grep -n "test_pipeline_integration"` excluding `docs/archive/**` and `docs/features/test-realism/**` (this feature's own docs). Known live reference: `ROADMAP.md:70`. Update each hit.
- Keep tests that assert on:
  - Phase ordering (ingest → sort → process → enforce → verify → dispatch).
  - Early-abort behaviour when a critical step crashes.
  - Reporter aggregation (StepReports roll up into a PipelineReport).
- Delete tests whose invariant is already in `tests/integration/test_full_pipeline.py`.
- Replace the per-test `@patch("personalscraper.<module>.run_*")` stacks with a fixture that injects a dict of fake step callables into `Pipeline(...)`. This requires adding a `step_overrides: Mapping[str, Callable] | None = None` kwarg to `Pipeline.__init__` (the only production-code seam added by this feature, as allowed by DESIGN §2 non-goals — "minimal seam only").
- Drop the `integration_settings` and `integration_config` MagicMock fixtures from this file: use the real `tmp_path`-based fixtures from the new `tests/integration/conftest.py` (imported via `pytest_plugins` if needed, or re-exported from `tests/conftest.py`).

Target: ≤ 12 `@patch` uses remaining.

### Commit

`refactor(tests): reduce pipeline_integration to orchestration unit`

## Quality gate (after 4.3)

- `git grep -c "@patch" tests/dispatch/test_dispatcher.py tests/test_cli.py tests/test_pipeline_orchestration.py` sums to ≤ 52.
- Full default `pytest` suite still green.
- `pytest --cov=personalscraper --cov-branch tests/` line + branch coverage ≥ baseline measured against `main`.
- `tests/e2e/` diff: zero changes.
