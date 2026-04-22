# sort-dry-run — Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Feature:** Add `--dry-run` flag to `personalscraper sort`
**Branch:** `feat/sort-dry-run`
**Design:** `docs/features/sort-dry-run/DESIGN.md`

## Phases

| #   | Phase                                  | File                                                     | Status |
| --- | -------------------------------------- | -------------------------------------------------------- | ------ |
| 1   | CLI flag + core dry-run branch + tests | [phase-01-cli-core-tests.md](phase-01-cli-core-tests.md) | [ ]    |

## Commit convention

Each sub-phase commit uses scope `sort-dry-run`:

```
feat(sort-dry-run): description
test(sort-dry-run): description
fix(sort-dry-run): description
```

## Acceptance criteria (from DESIGN.md)

- [ ] `personalscraper sort --dry-run` runs without touching the filesystem
- [ ] Unit tests cover the `if dry_run:` branch in `Sorter.sort_item()`
- [ ] `run_sort(..., dry_run=True)` populates `report.details` with `[DRY-RUN]` lines
- [ ] `make test` green
- [ ] `make lint` green (ruff + mypy)
- [ ] No file moved/renamed in any dry-run test
