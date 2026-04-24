# Phase 01 — Audit & Enforcement Tooling

**Goal**: land a CI-runnable linter that identifies every logging-convention offender without failing the build yet.

## Sub-phase 1.1 — Create `scripts/check_logging.py`

- New file `scripts/check_logging.py`.
- Python AST walker. Rules:
  - Flag any `Call(func=Name('print'))` in `personalscraper/` except in `tests/` (script scope restricts to `personalscraper/` by default).
  - Flag any `Call(func=Attribute(value=Name('logging'), attr='getLogger'))` in `personalscraper/` except `personalscraper/logger.py`.
  - Warn on any `log.<level>(f"...")` where `log` was obtained from `get_logger` — signals string-mode logging.
- Exit code : `0` always when invoked with `--report-only`; `1` on any offender otherwise.
- CLI : `python scripts/check_logging.py [--report-only] [personalscraper/...]`.

Tests under `tests/tools/test_check_logging.py` :

- Fixture tree with one `print()`, one `logging.getLogger`, one f-string log → expect three findings.
- Clean fixture → zero findings, exit 0.

## Sub-phase 1.2 — Wire into `make lint`

- Add a `lint-logging` target to the Makefile that invokes the script with `--report-only`.
- Extend the existing `lint` target to run `lint-logging` after ruff.
- Document the current offender count (baseline) in a top-of-file docstring comment inside `scripts/check_logging.py`.

### Quality gate

- New tests pass.
- `make lint` prints the offender count without failing.

### Commit

`feat(tooling): add logging-convention audit script`
