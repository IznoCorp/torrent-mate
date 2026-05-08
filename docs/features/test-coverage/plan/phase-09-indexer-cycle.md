# Phase 9 — Indexer cycle → `fail_under = 85`

**Type**: cycle
**Effort**: L (~1 day) — large module, decently tested but deep domain knowledge needed for the tail.
**Entry**: Phase 8 done. `fail_under = 80`. CI green with hard `design-gaps`.
**Exit**:

- Coverage of `personalscraper/indexer/` lifts global to ≥ 85.
- Design-contract tests for `docs/reference/indexer.md` and `docs/reference/indexer-json-shapes.md` (both → codename `indexer`).
- `fail_under` bumped 80 → 85.

## Detail-at-phase-start

1. `audit_design_coverage.py | grep -E "indexer.md|indexer-json-shapes"`.
2. `coverage report --include='personalscraper/indexer/*' --show-missing`.
3. Indexer has SQLite + outbox + scanner + repos sub-modules — focus on whichever has the largest branch-gap × LOC.

## Targeted modules

- `indexer/db.py` — Schema migrations, busy_timeout, connection pooling.
- `indexer/scanner.py` — Scanner modes (full / incremental / outbox-only).
- `indexer/outbox/_disk.py`, `outbox/_publish.py` — Outbox event lifecycle.
- `indexer/repos/item_repo.py` — Item read / write / search.

## Task 9.X — Bump `fail_under` to 85

- [ ] `make test-cov` ≥ 85.
- [ ] Edit `pyproject.toml`: `fail_under = 85`.
- [ ] Commit:

```
chore(test-coverage): cycle 5 — indexer, bump fail_under to 85
```

## Task 9.Y — Phase 9 gate

- [ ] `make check` green at 85.
- [ ] `audit_design_coverage.py --strict` exits 0.
- [ ] Map `--check` clean.
- [ ] Decision review (Q3 in DESIGN): based on the slope of the last 5 cycles, confirm 90 % is the right end target or stop at 85.
- [ ] Milestone commit:

```
chore(test-coverage): phase 9 gate — indexer cycle done (fail_under=85)
```
