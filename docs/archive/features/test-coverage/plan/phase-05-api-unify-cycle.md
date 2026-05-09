# Phase 5 — api-unify cycle (bootstrap markers, no threshold bump)

**Type**: cycle
**Effort**: L (~1 day)
**Entry**: Phase 4 done. Bootstrap test in place. CI green. `fail_under = 80`.
**Exit**:

- Design-contract tests covering every reasonable section of `docs/features/api-unify/DESIGN.md` (untestable sections in `skip_audit`).
- `tests/feature_map/api-unify.json` populated by `update_feature_map.py`.
- `audit_design_coverage.py` reports zero orphan `api-unify` sections outside `skip_audit`.
- **No `fail_under` bump** — branch coverage on `feat/test-coverage` already measured at 80.48 %, so api-unify's role this cycle is purely to bootstrap the marker convention and feed the design-gaps audit. The first ratchet bump happens in Phase 6 (scraper).

## Detail-at-phase-start

This cycle's exact task list is finalized at phase start by:

1. Running `python3 scripts/audit_design_coverage.py` to enumerate orphan api-unify sections.
2. Running `make test-cov` and capturing the coverage report (`coverage report --show-missing`).
3. Identifying the modules in `personalscraper/api/` with the lowest contribution to the global percentage.

The output of (1) becomes the contract-test backlog. The output of (2-3) feeds opportunistic unit-test follow-ups, but is **not** the gate for this phase since the threshold is unchanged.

## Task template (repeat per section)

For each api-unify DESIGN section in the contract-test backlog:

- [ ] Write `tests/integration/test_design_api_<section>.py::test_<behavior>` with `Design:` + `Contract:` markers.
- [ ] Verify it passes.
- [ ] `git add` (hook regenerates the map).
- [ ] Commit per logical group: `test(api-unify): contract test for <section>`.

For each undertested module in the unit-test backlog:

- [ ] Add unit tests in `tests/unit/test_<module>.py` for the missing branches identified by `coverage report --show-missing`.
- [ ] Run `make test-cov` — coverage must not regress below 80 %.
- [ ] Commit per logical group.

## Task 5.X — (no `fail_under` bump this cycle)

The threshold stays at 80. Reason: actual baseline (80.48 %) already meets the original cycle-1 target of 50, and bumping at this stage would penalize phases 6-9 which have the real test work to do. The `coverage-monotonic` job continues to enforce no decrease.

## Task 5.Y — Phase 5 gate

- [ ] `make check` green at `fail_under = 80`.
- [ ] `python3 scripts/audit_design_coverage.py` — orphan count for `api-unify` reduced to only `skip_audit` entries.
- [ ] `python3 scripts/update_feature_map.py --check` clean.
- [ ] Single milestone commit:

```
chore(test-coverage): phase 5 gate — api-unify cycle done (markers bootstrap, fail_under=80)
```
