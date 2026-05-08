# Phase 10 — Remaining modules cleanup (stay at `fail_under = 90`)

**Type**: cycle
**Effort**: M (~5 h) — tail of low-coverage modules + skip_audit hygiene.
**Entry**: Phase 9 done. `fail_under = 90`. CI green.
**Exit**:

- Coverage of `personalscraper/sorter/`, `ingest/`, `process/`, `library/`, `conf/` solid at the 90 % global target — no regression below 90 in any future cycle.
- Design-contract tests for the relevant sections of `docs/reference/architecture.md` (codename: `architecture`) and any provider docs not already covered (TMDB / TVDB / OMDB / Trakt / etc., codenames per override table).
- `[tool.coverage.report].omit` list reviewed and minimized — every entry has a `# reason:` comment.
- `skip_audit` entries reviewed across all map files — anchors that can now be tested are converted to real tests; expired entries are renewed or removed.
- **No `fail_under` bump** — Phase 9 already reached the end target. This phase consolidates and removes hidden waivers.

## Detail-at-phase-start

1. `audit_design_coverage.py --strict` — should exit 0 from Phase 9. Any remaining findings are this cycle's scope.
2. `coverage report --show-missing | sort -k4 -n | head -20` — final tail of branch gaps.
3. Walk every `tests/feature_map/*.json`'s `skip_audit` array; flag entries whose justification has weakened since they were written.

## Per-module targets

For each module group, the target is to keep global ≥ 90 % while shrinking per-module gaps where cheap.

- `sorter/` — Already 70-85 %. File-type detection edge cases.
- `ingest/` — Torrent-completion → staging copy logic.
- `process/` — Already ~80 %. Phase orchestration tail.
- `library/` — Rescraper, scanner, validator. Worst at `library/validator.py`.
- `conf/` — Config loader edge cases (NB: classifier already addressed in PR #19).

## Task 10.X — `omit` and `skip_audit` review

- [ ] Audit `[tool.coverage.report].omit`: every entry needs a `# reason:` comment.
- [ ] Walk every `tests/feature_map/*.json`'s `skip_audit` — convert any anchor that is now testable into a real contract test; renew/remove expired entries.
- [ ] `audit_design_coverage.py --strict --strict-skip` exits 0.
- [ ] Commit:

```
chore(test-coverage): cycle 6 — omit + skip_audit cleanup
```

## Task 10.Y — Phase 10 gate

- [ ] `make check` green at 90.
- [ ] `audit_design_coverage.py --strict` exits 0 — no orphans, no stale refs.
- [ ] Map `--check` clean.
- [ ] Milestone commit:

```
chore(test-coverage): phase 10 gate — cleanup done (fail_under=90, hold)
```
