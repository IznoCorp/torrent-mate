# V12 — PIPELINE HARDENING & BUG FIXES — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 22 bugs exposed by the 2026-04-13 pipeline run. Every fix includes a reproducer test — no exception.

**Architecture:** 9 phases organized by root cause patterns. Each phase is independently testable. Phase 9 audits that all 22 bugs have test coverage.

**Tech Stack:** Python 3.11+, pytest, qbittorrent-api, requests, tenacity, rsync, NTFS via macFUSE

---

## Critical Testing Requirement

Every bug fix MUST:

1. Include a test that REPRODUCES the exact bug (must FAIL before the fix)
2. Use realistic data (torrent structures with nested subdirs, filenames with `:`, NTFS constraints)
3. Prove the bug is fixed (passes after the fix)

## Phase Table

| Phase | Name                       | Bugs              | Files                     | Commit prefix | Plan                       |
| ----- | -------------------------- | ----------------- | ------------------------- | ------------- | -------------------------- |
| 1     | sanitize_filename cohérent | #3,4,5,9,10,13,16 | scraper.py, reclean.py    | v12.1.x       | [phase-01.md](phase-01.md) |
| 2     | Restructuration épisodes   | #6,7,8            | scraper.py                | v12.2.x       | [phase-02.md](phase-02.md) |
| 3     | result.media_path stale    | #17               | scraper.py                | v12.3.x       | [phase-03.md](phase-03.md) |
| 4     | qBit auth pre-check        | #1,2,12,20        | qbit_client.py            | v12.4.x       | [phase-04.md](phase-04.md) |
| 5     | Verify/Dispatch NTFS-safe  | #18,19            | checker.py, dispatcher.py | v12.5.x       | [phase-05.md](phase-05.md) |
| 6     | Crash recovery pipeline    | #15               | pipeline.py               | v12.6.x       | [phase-06.md](phase-06.md) |
| 7     | Améliorations mineures     | #21,22            | scraper.py, cleanup.py    | v12.7.x       | [phase-07.md](phase-07.md) |
| 8     | pipeline-monitor skill     | #14               | pipeline-monitor SKILL.md | v12.8.x       | [phase-08.md](phase-08.md) |
| 9     | Test audit final           | #11 (transversal) | various test files        | v12.9.x       | [phase-09.md](phase-09.md) |

## Coherence Gates

Before each phase:

- [ ] Previous phase tests pass (`python -m pytest tests/ -x -q`)
- [ ] No uncommitted changes
- [ ] IMPLEMENTATION.md updated

After each phase:

- [ ] Phase-specific tests pass
- [ ] Full test suite passes (1006+ tests, 0 failures)
- [ ] No regressions

## File Map

### Modified

- `personalscraper/scraper/scraper.py` — Phases 1, 2, 3, 7
- `personalscraper/process/reclean.py` — Phase 1
- `personalscraper/ingest/qbit_client.py` — Phase 4
- `personalscraper/verify/checker.py` — Phase 5
- `personalscraper/dispatch/dispatcher.py` — Phase 5
- `personalscraper/pipeline.py` — Phase 6
- `personalscraper/process/cleanup.py` — Phase 7
- `.claude/skills/pipeline-monitor/SKILL.md` — Phase 8

### Test files created/modified

- `tests/scraper/test_scraper.py` — Phases 1, 2, 3
- `tests/process/test_reclean.py` — Phase 1
- `tests/ingest/test_qbit_client.py` — Phase 4
- `tests/verify/test_checker.py` — Phase 5
- `tests/dispatch/test_dispatcher.py` — Phase 5
- `tests/test_pipeline.py` — Phase 6
- `tests/scraper/test_episode_manager.py` — Phase 2
- `tests/process/test_cleanup.py` — Phase 7
- `docs/IMPLEMENTATION.md` — Phase 9

## Phase Dependencies

```
Phase 1 (sanitize) ──→ Phase 5 (NTFS checks use sanitize_filename)
Phase 2 (episodes) ──→ independent
Phase 3 (media_path) → independent
Phase 4 (qBit) ──────→ independent
Phase 5 (NTFS) ──────→ depends on Phase 1
Phase 6 (recovery) ──→ independent
Phase 7 (minor) ─────→ independent
Phase 8 (skill) ─────→ independent
Phase 9 (audit) ─────→ depends on ALL 1-8
```

## Acceptance Criteria

1. No file with `:` in its name after scrape/reclean
2. Episodes in nested torrent subdirectories extracted to `Saison XX/`
3. `result.media_path` updated after tvshow folder rename
4. qBit pre-check prevents login when IP is banned (403)
5. Verify blocks items with NTFS-illegal filenames
6. Dispatch refuses NTFS-unsafe items before rsync
7. Pipeline cleans crash artifacts at startup
8. pipeline-monitor skill STOPs on auth lockout and rsync errors
9. 22 bugs → 22+ reproducer tests with traceability table
10. All tests pass, 0 regressions
