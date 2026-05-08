# Phase 5 — api-unify cycle → `fail_under = 50`

**Type**: cycle
**Effort**: L (~1 day)
**Entry**: Phase 4 done. Bootstrap test in place. CI green.
**Exit**:

- Coverage of `personalscraper/api/` ≥ feature contribution to global 50 %.
- Design-contract tests for every reasonable section of `docs/features/api-unify/DESIGN.md` (untestable sections in `skip_audit`).
- `fail_under` bumped 44 (or rebaseline value) → 50.

## Detail-at-phase-start

This cycle's exact task list is finalized at phase start by:

1. Running `python3 scripts/audit_design_coverage.py` to enumerate orphan api-unify sections.
2. Running `make test-cov` and capturing the coverage report (`coverage report --show-missing`).
3. Identifying the modules in `personalscraper/api/` with the lowest contribution to the global percentage.

The output of (1) becomes the contract-test backlog. The output of (2-3) becomes the unit-test backlog.

## Task template (repeat per section)

For each api-unify DESIGN section in the contract-test backlog:

- [ ] Write `tests/integration/test_design_api_<section>.py::test_<behavior>` with `Design:` + `Contract:` markers.
- [ ] Verify it passes.
- [ ] `git add` (hook regenerates the map).
- [ ] Commit per logical group: `test(api-unify): contract test for <section>`.

For each undertested module in the unit-test backlog:

- [ ] Add unit tests in `tests/unit/test_<module>.py` for the missing branches identified by `coverage report --show-missing`.
- [ ] Run `make test-cov` and verify the global percentage rose.
- [ ] Commit per logical group.

## Task 5.X — Bump `fail_under` to 50

**Files modified**: `pyproject.toml`

- [ ] **Step 1**: Run `make test-cov` and capture the global percentage. It must be ≥ 50.
- [ ] **Step 2**: Edit `[tool.coverage.report].fail_under = 50`.
- [ ] **Step 3**: `make test-cov` passes at the new threshold.
- [ ] **Step 4**: Verify `coverage-monotonic` accepts the bump (it should; HEAD = 50 > main = 44).
- [ ] **Step 5**: Commit:

```
chore(test-coverage): cycle 1 — api-unify, bump fail_under to 50
```

## Task 5.Y — Phase 5 gate

- [ ] `make check` green at `fail_under = 50`.
- [ ] `python3 scripts/audit_design_coverage.py` — orphan count for `api-unify` reduced to only `skip_audit` entries.
- [ ] `python3 scripts/update_feature_map.py --check` clean.
- [ ] Single milestone commit:

```
chore(test-coverage): phase 5 gate — api-unify cycle done (fail_under=50)
```
