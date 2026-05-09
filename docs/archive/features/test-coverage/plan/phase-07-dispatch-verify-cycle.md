# Phase 7 — Dispatch + Verify cycle → `fail_under = 85`

**Type**: cycle
**Effort**: M (~4 h) — modules already 70-80 %, so shorter than scraper.
**Entry**: Phase 6 done. `fail_under = 82`. CI green.
**Exit**:

- Coverage of `personalscraper/dispatch/` and `personalscraper/verify/` lifts global to ≥ 85.
- Worst remaining gap: `verify/fixer.py` (26 %) closed.
- Design-contract tests for sections of `docs/reference/storage.md` (codename: `dispatch`) and `docs/reference/pipeline-internals.md` (codename: `pipeline`).
- `fail_under` bumped 82 → 85.

## Detail-at-phase-start

1. `audit_design_coverage.py | grep -E "storage.md|pipeline-internals.md"` — orphan list.
2. `coverage report --include='personalscraper/dispatch/*,personalscraper/verify/*' --show-missing` — branch gaps.
3. Identify shared fixtures with Phase 5/6 to avoid duplicating mocks (real disk-fake setup, mock TMDB, etc.).

## Targeted modules

- `verify/fixer.py` — NFO fixup, dir-naming repair (worst at 26 %).
- `verify/verifier.py` — Filling the 78 → ≥ 90 tail.
- `dispatch/dispatcher.py` — Move/replace logic per Move Rules (CLAUDE.md §Move Rules).
- `dispatch/media_index.py` — Index integrity.

## Task template

Same as Phase 5/6.

## Task 7.X — Bump `fail_under` to 85

- [ ] `make test-cov` ≥ 85.
- [ ] Edit `pyproject.toml`: `fail_under = 85`.
- [ ] Commit:

```
chore(test-coverage): cycle 3 — dispatch+verify, bump fail_under to 85
```

## Task 7.Y — Phase 7 gate

- [ ] `make check` green at 85.
- [ ] Audit script clean for dispatch + pipeline sections (modulo skip_audit).
- [ ] Milestone commit:

```
chore(test-coverage): phase 7 gate — dispatch+verify cycle done (fail_under=85)
```
