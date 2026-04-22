# info-cmd — Implementation Plan Index

Feature: `personalscraper info` command
Branch: `feat/info-cmd`
Design: `docs/features/info-cmd/DESIGN.md`

## Phases

| #   | Phase                                   | File                                                                             | Status |
| --- | --------------------------------------- | -------------------------------------------------------------------------------- | ------ |
| 1   | Core `info` module + CLI wiring + tests | [phase-01-core-info-module-cli-tests.md](phase-01-core-info-module-cli-tests.md) | [ ]    |

## Sub-phases

| Sub-phase | Scope                                                                                                                                                    | Commit scope           |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| 1.1       | Create `personalscraper/info/` module (`run.py` with `DiskStatus`, `InfoReport`, `collect_info`, `format_info`) + unit tests in `tests/info/test_run.py` | `feat(info-cmd): ...`  |
| 1.2       | Wire `info` CLI command in `personalscraper/cli.py` + smoke test in `tests/test_cli.py`                                                                  | `feat(info-cmd): ...`  |
| 1.3       | Quality gate: ruff + mypy + full test suite                                                                                                              | `chore(info-cmd): ...` |
