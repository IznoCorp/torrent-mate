# Phase 05 — Verify & document

**Goal**: certify the refactor, publish the convention, wire CI.

## Sub-phase 5.1 — Coverage & runtime gates

- Run `pytest --cov=personalscraper --cov-branch tests/` on `main` ; snapshot the numbers.
- Run the same on the feature branch ; compare. Expected : ≥ on both line and branch coverage.
- Run `pytest --durations=20 tests/` ; no single test > 5 s, full suite ≤ 30 s.
- Record the before/after numbers in the phase commit body.
- Fail the phase if any gate regresses.

### Commit

`test: verify coverage and runtime budget after realism refactor`

## Sub-phase 5.2 — Documentation & CI wiring

- New file `docs/reference/testing.md` :
  - Three-tier taxonomy : pure unit, CLI-wiring unit, E2E.
  - Decision tree : "what do you mock ?" → network only (E2E) / subprocess + our-own (unit).
  - Runtime budget per tier.
  - How to run just the fast tier (`make test`) vs the full tier (`make test-e2e`).
- Update `CLAUDE.md` Reference Index row for testing.
- Add `make test-e2e` and modify `make test` to include the E2E directory (runtime budget permitting; otherwise split).
- Update the CI workflow to run both tiers, reporting timings.

### Commit

`docs(reference): publish testing-tier convention; wire e2e into CI`

## Exit criteria

- Coverage ≥ baseline (line + branch).
- Runtime ≤ 30 s locally and in CI.
- `docs/reference/testing.md` is linked from `CLAUDE.md`.
- `make test-e2e` target exists and CI invokes it.
- No orphan `@patch` calls removed by the refactor reintroduced anywhere.
