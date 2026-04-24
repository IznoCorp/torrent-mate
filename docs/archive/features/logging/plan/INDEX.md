# Plan INDEX — Logging Convention Unification (`logging`)

**Design**: `docs/features/logging/DESIGN.md`
**Version bump**: 0.4.0 → 0.5.0 (minor)
**Branch**: `feat/logging`

## Phases

| #   | Phase                        | File                           | Commits (target) | Depends on |
| --- | ---------------------------- | ------------------------------ | ---------------- | ---------- |
| 1   | Audit & enforcement tooling  | `phase-01-audit-tooling.md`    | 2                | —          |
| 2   | stdlib → structlog migration | `phase-02-stdlib-migration.md` | 4–6 (batched)    | 1          |
| 3   | print() cleanup              | `phase-03-print-cleanup.md`    | 1                | 1          |
| 4   | Enforcement + docs           | `phase-04-enforcement-docs.md` | 2                | 2, 3       |

## Exit criteria

- `scripts/check_logging.py` passes with zero offenders in `personalscraper/`.
- All existing tests pass without modification.
- `docs/reference/logging.md` describes the convention.
- CI runs `make lint-logging` and gates merges on it.
- `CLAUDE.md` points new contributors at the new reference doc.

## Explicit non-goals

- No change to log levels, destinations, rotation policy, or `logger.py` configuration.
- No move to a different logging library.
- No refactor of CLI output formatting (Rich tables stay Rich tables).
