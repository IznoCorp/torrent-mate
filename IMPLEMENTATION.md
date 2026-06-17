# Implementation Progress — rescrape-target

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Targeted + incremental library re-scrape (minor)
**Version bump**: 0.35.1 → 0.36.0
**Branch**: feat/rescrape-target
**PR merge**: auto
**PR**: https://github.com/IznoCorp/personal-scraper/pull/206
**Design**: docs/features/rescrape-target/DESIGN.md
**Master plan**: docs/features/rescrape-target/plan/INDEX.md

## Phases

| #   | Phase                     | File                       | Status |
| --- | ------------------------- | -------------------------- | ------ |
| 1   | item-id targeting         | phase-01-item-id.md        | [x]    |
| 2   | date-refreshed population | phase-02-date-refreshed.md | [x]    |
| 3   | gate                      | phase-03-gate.md           | [x]    |

## Review cycles

### Cycle 1

4 reviewers (code, silent-failure, tests, comments). All findings verified; RT-1 reproduced + mutation-checked. No DESIGN contradiction.

- **RT-1 (major, 2 reviewers reproduced)**: `item_repo.upsert` UPDATE branch dropped `date_metadata_refreshed` → Part 2 was a no-op for existing rows (the 1909 NULLs never backfilled). Fixed: both UPDATE stmts now persist the column (`81a94dac`). Regression test (insert→re-scan→populated) mutation-verified. DESIGN note corrected.
- **RT-2/3/4 (medium)**: CLI `--item-id` error handling — dead `db_path is None` guard → `db_path.exists()`; `open_db`/`apply_migrations` raw tracebacks → clean Exit(1); silent not-found → visible error + exit (`08a89abf`). Tests F1/F2 added.
- **Minor**: docstring "both"→"either" + typo "force-rescraping" (folded).

Gate after fixes: `make check` 6952 passed / 0 failed. Pushed. Re-CI + cycle-2 re-check.

## Next action

All phases complete — run `/implement:feature-pr` (push + PR + CI + auto-merge).

> Gate: AC-1/2/4 live-verified (targeting/bypass/mutual-exclusion), AC-5 unit-tested, AC-7 `make check` green (6948 passed). AC-3 (real La Linea re-scrape) + AC-6 (no-filter incremental, needs a live scan) deferred to post-merge validation. Scan cron stays OFF until validated.
