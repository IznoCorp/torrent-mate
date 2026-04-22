# Library Rescrape & Validate Fix — Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `library-validate --fix --apply` (local fixes) and `library-rescrape` (targeted API repairs) to the V14 Library Maintenance PR.

**Architecture:** Three phases — (1) promote scanner private functions + add models + ValidationItem.**post_init**, (2) implement validate --fix with MediaFixer + empty dir + NTFS name fixes, (3) implement rescrape with targeted NFO/artwork/episode repair via reused scraper components.

**Tech Stack:** Python, Typer, pydantic, pytest, TMDB/TVDB APIs

**Design Spec:** `docs/superpowers/specs/2026-04-17-library-rescrape-design.md`

---

## Phases

| Phase | Name           | Tasks | Description                                                              |
| ----- | -------------- | ----- | ------------------------------------------------------------------------ |
| 10    | Foundation     | 3     | Promote public API, add models + constants, ValidationItem.**post_init** |
| 11    | Validate --fix | 3     | Implement fix logic in validator, wire CLI, tests                        |
| 12    | Rescrape       | 4     | Implement rescraper.py, CLI command, reporter integration, tests         |

## Coherence Gates

- **Before Phase 11:** Verify promoted public functions work, new models pass invariant tests
- **Before Phase 12:** Verify validate --fix works on real data (dry-run), all fixes applied correctly
- **After Phase 12:** Full test suite green, run all 7 library commands on real disks

## File Map

### New Files

| File                                                            | Phase | Purpose              |
| --------------------------------------------------------------- | ----- | -------------------- |
| `personalscraper/library/rescraper.py`                          | 12    | Core rescrape logic  |
| `tests/library/test_rescraper.py`                               | 12    | Rescraper unit tests |
| `docs/superpowers/plans/2026-04-17-library-rescrape-phase10.md` | —     | Phase 10 plan        |
| `docs/superpowers/plans/2026-04-17-library-rescrape-phase11.md` | —     | Phase 11 plan        |
| `docs/superpowers/plans/2026-04-17-library-rescrape-phase12.md` | —     | Phase 12 plan        |

### Modified Files

| File                                   | Phase | Changes                                                                                         |
| -------------------------------------- | ----- | ----------------------------------------------------------------------------------------------- |
| `personalscraper/library/scanner.py`   | 10    | Promote `_extract_nfo_ids` → `extract_nfo_ids`, `_parse_title_year` → `parse_title_year`        |
| `personalscraper/library/models.py`    | 10    | Add `RescrapeAction`, `LibraryRescrapeResult`, action constants, `ValidationItem.__post_init__` |
| `personalscraper/library/validator.py` | 11    | Add `fix`/`apply` params, call MediaFixer + empty dir fix + NTFS fix                            |
| `personalscraper/library/analyzer.py`  | 10    | Update imports for renamed public functions                                                     |
| `personalscraper/library/reporter.py`  | 12    | Add rescrape section (section 6)                                                                |
| `personalscraper/cli.py`               | 11+12 | Forward fix/apply to validate, add library-rescrape command                                     |
| `tests/library/test_models.py`         | 10    | ValidationItem.**post_init** + new model tests                                                  |
| `tests/library/test_scanner.py`        | 10    | Update imports for renamed functions                                                            |
| `tests/library/test_validator.py`      | 11    | Fix dry-run + apply tests                                                                       |
| `tests/library/test_reporter.py`       | 12    | Rescrape section test                                                                           |
| `tests/test_cli.py`                    | 11+12 | CLI tests                                                                                       |

### Commit Convention

- `v14.10.N` for Phase 10 tasks
- `v14.11.N` for Phase 11 tasks
- `v14.12.N` for Phase 12 tasks
