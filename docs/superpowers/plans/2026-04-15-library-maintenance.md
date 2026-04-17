# V14 — Library Maintenance — Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 6 `library-*` CLI commands for scanning, cleaning, validating, analyzing, recommending, and reporting on the existing media library across 4 NTFS storage disks.

**Architecture:** New `personalscraper/library/` package with independent modules per command. Preferences loaded from a single JSON file. Results stored as JSON in `.personalscraper/`. Read-only commands don't acquire pipeline lock; write commands do.

**Tech Stack:** Python, Typer, pydantic, dataclasses, ffprobe, pytest

**Design Spec:** `docs/superpowers/specs/2026-04-15-library-maintenance-design.md`

---

## Phase Table

| Phase | Name          | Scope                                                                           | Dependencies   | Plan File                                          |
| ----- | ------------- | ------------------------------------------------------------------------------- | -------------- | -------------------------------------------------- |
| 1     | Foundation    | Models, preferences, config, refactor `_is_nfo_complete`                        | None           | [phase1](2026-04-15-library-maintenance-phase1.md) |
| 2     | Scanner       | `scanner.py` + `library-scan` CLI + tests                                       | Phase 1        | [phase2](2026-04-15-library-maintenance-phase2.md) |
| 3     | Disk Cleaner  | `disk_cleaner.py` + `library-clean` CLI + tests                                 | Phase 1        | [phase3](2026-04-15-library-maintenance-phase3.md) |
| 4     | Validator     | `validator.py` + `library-validate` CLI + tests                                 | Phase 2        | [phase4](2026-04-15-library-maintenance-phase4.md) |
| 5     | Analyzer      | `analyzer.py` + `extract_stream_info` extension + `library-analyze` CLI + tests | Phase 1        | [phase5](2026-04-15-library-maintenance-phase5.md) |
| 6     | Recommender   | `recommender.py` + `library-recommend` CLI + tests                              | Phase 5        | [phase6](2026-04-15-library-maintenance-phase6.md) |
| 7     | Reporter      | `reporter.py` + `library-report` CLI + tests                                    | Phases 2, 5, 6 | [phase7](2026-04-15-library-maintenance-phase7.md) |
| 8     | Documentation | CLAUDE.md, MANUAL.md, ROADMAP.md, `--help` polish                               | All prior      | [phase8](2026-04-15-library-maintenance-phase8.md) |
| 9     | E2E Tests     | Integration tests across all 6 commands                                         | All prior      | [phase9](2026-04-15-library-maintenance-phase9.md) |

## Coherence Gates

Before each phase, verify:

- [ ] Previous phase tests pass: `python -m pytest tests/ -x -q`
- [ ] Interfaces match: types/signatures from this phase's plan match actual code from prior phases
- [ ] No regressions: full test suite green
- [ ] Design alignment: if implementation diverged from spec, update spec before continuing

## File Map

### New files (created by V14)

```
personalscraper/library/
├── __init__.py              # Phase 1 — package init
├── models.py                # Phase 1 — @dataclass result models
├── preferences.py           # Phase 1 — pydantic preference models
├── scanner.py               # Phase 2 — lightweight disk scanner
├── disk_cleaner.py          # Phase 3 — .actors, empty dirs, junk removal
├── validator.py             # Phase 4 — NFO/artwork/naming validation
├── analyzer.py              # Phase 5 — ffprobe deep scan
├── recommender.py           # Phase 6 — re-download recommendations
└── reporter.py              # Phase 7 — library statistics
```

```
tests/library/
├── __init__.py              # Phase 1
├── test_models.py           # Phase 1
├── test_preferences.py      # Phase 1
├── test_scanner.py          # Phase 2
├── test_disk_cleaner.py     # Phase 3
├── test_validator.py        # Phase 4
├── test_analyzer.py         # Phase 5
├── test_recommender.py      # Phase 6
├── test_reporter.py         # Phase 7
└── test_integration.py      # Phase 9
```

### Modified files

| File                                   | Phase | Change                                           |
| -------------------------------------- | ----- | ------------------------------------------------ |
| `personalscraper/config.py`            | 1     | Add `library_preferences_file` field             |
| `personalscraper/scraper/scraper.py`   | 1     | Extract `_is_nfo_complete()` to shared module    |
| `personalscraper/nfo_utils.py`         | 1     | New shared module for `is_nfo_complete()`        |
| `personalscraper/scraper/mediainfo.py` | 5     | Extend `extract_stream_info()` with 5 new fields |
| `personalscraper/cli.py`               | 2-7   | Add 6 `library-*` commands                       |
| `tests/scraper/test_scraper.py`        | 1     | Update imports after `_is_nfo_complete` move     |
| `CLAUDE.md`                            | 8     | Add V14 commands, config, version table          |
| `MANUAL.md`                            | 8     | New "Maintenance médiathèque" section            |
| `ROADMAP.md`                           | 8     | Already created, polish                          |

## Commit Convention

All V14 commits follow: `v14.{phase}.{task}: Description`

Examples:

- `v14.1.1: Add library result models (@dataclass)`
- `v14.2.3: Implement scanner disk iteration with NFO validation`
- `v14.5.1: Extend extract_stream_info with bitrate, forced, is_default`
