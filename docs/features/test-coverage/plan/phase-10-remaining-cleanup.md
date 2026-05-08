# Phase 10 — Remaining modules cleanup → `fail_under = 90`

**Type**: cycle
**Effort**: L (~1 day) — most targets already 60-80 %, fill the tail.
**Entry**: Phase 9 done. `fail_under = 85`. CI green.
**Exit**:

- Coverage of `personalscraper/sorter/`, `ingest/`, `process/`, `library/`, `conf/` lifts global to ≥ 90.
- Design-contract tests for the relevant sections of `docs/reference/architecture.md` (codename: `architecture`) and any provider docs not already covered (TMDB / TVDB / OMDB / Trakt / etc., codenames per override table).
- `fail_under` bumped 85 → 90 (the end target).
- `[tool.coverage.report].omit` list reviewed and minimized.

## Detail-at-phase-start

1. `audit_design_coverage.py --strict` — at this stage we expect zero gaps from cycles 1-5; remaining gaps are in this cycle's scope.
2. `coverage report --show-missing | sort -k4 -n | head -20` — final tail of branch gaps.

## Per-module targets

For each module group, the target is whatever brings global to 90 % — measured, not predetermined per-module.

- `sorter/` — Already 70-85 %. File-type detection edge cases.
- `ingest/` — Torrent-completion → staging copy logic.
- `process/` — Already ~80 %. Phase orchestration tail.
- `library/` — Rescraper, scanner, validator. Worst at `library/validator.py`.
- `conf/` — Config loader edge cases (NB: classifier already addressed in PR #19).

## Task 10.X — Bump `fail_under` to 90

- [ ] `make test-cov` ≥ 90.
- [ ] Edit `pyproject.toml`: `fail_under = 90`.
- [ ] Commit:

```
chore(test-coverage): cycle 6 — remaining cleanup, bump fail_under to 90 (target reached)
```

## Task 10.Y — Phase 10 gate

- [ ] `make check` green at 90.
- [ ] `audit_design_coverage.py --strict` exits 0 — no orphans, no stale refs.
- [ ] Map `--check` clean.
- [ ] `[tool.coverage.report].omit` reviewed: every entry has a `# reason:` comment justifying the exclusion.
- [ ] Milestone commit:

```
chore(test-coverage): phase 10 gate — 90% target reached
```
