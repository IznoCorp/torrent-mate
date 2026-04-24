# Phase 04 — Hotspot trimming

**Goal**: cut `@patch` count in the three hottest files by ≥ 60 % while preserving the invariants they genuinely test. E2E coverage from phases 2–3 absorbs the removed cases.

## Sub-phase 4.1 — `tests/dispatch/test_dispatcher.py`

- Identify every test whose primary assertion is an effect already covered in the E2E dispatch tests (replace, merge, new, recovery).
- Delete those tests or collapse them into narrow CLI-wiring tests.
- Replace the repeated `@patch("shutil.which", return_value="/usr/bin/rsync")` decorator with a module-level `pytest.fixture(autouse=True)` that sets `monkeypatch.setattr(shutil, "which", ...)` only when the test file declares it needs rsync.
- Keep unit tests for : pure resolver helpers (`_resolve_existing_on_filesystem`, `_has_ntfs_illegal_names`), `DispatchResult` dataclass, the `_force_rmtree` retry semantics.

Target : ≤ 15 `@patch` uses after refactor.

### Commit

`refactor(tests): trim test_dispatcher hotspot, keep resolver unit tests`

## Sub-phase 4.2 — `tests/test_cli.py`

- Introduce `tests/conftest.py::stub_pipeline_steps` autouse fixture that monkeypatches each `run_*` step to a no-op StepReport when `env_cli_integration` marker is NOT set.
- Remove per-test `@patch` blocks that were doing the same work.
- Split existing integration-leaning tests into a new `tests/test_cli_e2e.py` with the `@pytest.mark.e2e` marker — these run against a real `tmp_path` staging tree.

Target : ≤ 25 `@patch` uses in `test_cli.py` (down from ~66).

### Commit

`refactor(tests): collapse CLI step-mocks into autouse fixture`

## Sub-phase 4.3 — `tests/test_pipeline_integration.py`

- Rename the file to `tests/test_pipeline_orchestration.py` to reflect its unit-level scope.
- Keep tests that assert on :
  - Phase ordering (ingest → sort → process → enforce → verify → dispatch).
  - Early-abort behaviour when a critical step crashes.
  - Reporter aggregation (StepReports roll up into a PipelineReport).
- Delete tests whose invariant is already in the E2E `test_full_pipeline_e2e`.
- Replace per-test `@patch("personalscraper.pipeline.run_ingest")` (and siblings) with a fixture that injects a dict of fake step callables into `Pipeline(...)` (add a minimal `step_overrides=` kwarg to `Pipeline` if not already present — that's the only production-code seam).

Target : ≤ 12 `@patch` uses (down from ~42).

### Commit

`refactor(tests): reduce pipeline_integration to orchestration unit`

## Quality gate (after 4.3)

- `git grep '@patch' tests/dispatch/test_dispatcher.py tests/test_cli.py tests/test_pipeline_orchestration.py | wc -l` ≤ 52 (target).
- Full suite still green.
- Coverage delta vs `main` : `pytest --cov` shows no regression in `personalscraper/*` line OR branch coverage.
