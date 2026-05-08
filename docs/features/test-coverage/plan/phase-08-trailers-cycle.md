# Phase 8 — Trailers cycle → `fail_under = 80` + promote `design-gaps` to hard error + diff-coverage

**Type**: cycle
**Effort**: L (~1.5 day) — worst-covered feature, three explicit promotion tasks at the end.
**Entry**: Phase 7 done. `fail_under = 70`. CI green.
**Exit**:

- Coverage of `personalscraper/trailers/` lifts global to ≥ 80.
- Design-contract tests for `docs/reference/trailers.md` (codename: `trailers`) and `docs/archive/features/trailer/DESIGN.md` (codename: `trailer`).
- `fail_under` bumped 70 → 80.
- **`design-gaps` CI job promoted from `continue-on-error: true` to hard error.**
- **diff-coverage gate enabled in CI** (codecov patch %, threshold 80).
- `audit_design_coverage.py` orphan severity escalated from Warning to Error in the audit report.

This phase has the most distinct end-of-cycle promotion tasks; they are explicit, not side-notes.

## Detail-at-phase-start

Worst coverage in the codebase. Modules that are 0-30 %:

- `trailers/cli.py` (0 %) — CLI entry point. Either covered by a CliRunner test OR added to `[tool.coverage.report].omit` with reason "CLI entry — exercised by manual smoke + e2e".
- `trailers/state.py` (31 %) — State machine for download lifecycle.
- `trailers/scanner.py` (28 %) — Library / staging scan.
- `trailers/orchestrator.py` — Already partially addressed by PR #19 (MediaType migration); fill remaining branches.
- `trailers/placement.py` — Movie vs TV placement convention.

## Detail-at-phase-start

1. `audit_design_coverage.py | grep -E "trailers.md|archive/features/trailer"`.
2. `coverage report --include='personalscraper/trailers/*' --show-missing`.
3. Decide cli.py policy: covered by CliRunner test OR omit-with-reason. The former is preferred; document the choice in DESIGN §6.4.

## Task template

Contract tests + unit tests + module by module. Trailers has rich behavior (state lifecycle, placement rules) — favor integration-tier tests with a fake `yt-dlp` shim.

## Task 8.A — Bump `fail_under` to 80

- [ ] `make test-cov` ≥ 80.
- [ ] Edit `pyproject.toml`: `fail_under = 80`.
- [ ] Commit:

```
chore(test-coverage): cycle 4 — trailers, bump fail_under to 80
```

## Task 8.B — Promote `design-gaps` job to hard error

**Files modified**: `.github/workflows/ci.yml`

- [ ] Remove `continue-on-error: true` from the `design-gaps` step.
- [ ] Change the step command from `audit_design_coverage.py` to `audit_design_coverage.py --strict`.
- [ ] Verify CI fails on a synthetic orphan (introduce a temporary heading without a contract test, see CI fail, revert).
- [ ] Commit:

```
ci(test-coverage): promote design-gaps to hard error (post-fail_under=80)
```

## Task 8.C — Enable diff-coverage gate

**Files modified**: `.github/workflows/ci.yml`

Add a new CI step (after `test-cov` upload) using the `codecov/codecov-action@v4` `patch` threshold or the `pytest-cov-diff` plugin. The contract: a PR's _changed lines_ must be ≥ 80 % covered. Catches local regressions hidden by global stability.

```yaml
- name: Diff coverage gate (patch)
  uses: py-cov-action/python-coverage-comment-action@v3
  with:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    MINIMUM_GREEN: 80
```

(or the equivalent codecov configuration in `codecov.yml`).

- [ ] Add the step.
- [ ] Verify on a sample PR that adds untested code that the gate trips.
- [ ] Commit:

```
ci(test-coverage): enable diff-coverage gate (80% on changed lines)
```

## Task 8.D — Phase 8 gate

- [ ] `make check` green at 80.
- [ ] `audit_design_coverage.py --strict` exits 0 globally (only `skip_audit` entries remain).
- [ ] Map `--check` clean.
- [ ] CI on the gate PR shows: monotonic ✓, design-gaps ✓ (now hard), diff-coverage ✓.
- [ ] Milestone commit:

```
chore(test-coverage): phase 8 gate — trailers + design-gaps hard + diff-cov (fail_under=80)
```
