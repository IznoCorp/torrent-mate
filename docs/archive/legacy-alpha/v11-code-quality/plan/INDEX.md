# V11 — CODE QUALITY HARDENING — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 architectural code quality issues identified by comprehensive review — error isolation, CLI UX, dead code removal, DRY extraction.

**Architecture:** 4 independent phases modifying existing code. No new features. Each phase is self-contained with its own tests.

**Tech Stack:** Python 3.11+, typer, pydantic, tenacity, qbittorrent-api, requests, pytest

---

## Phase Table

| Phase | Name                               | Files                               | Commit prefix | Plan                       |
| ----- | ---------------------------------- | ----------------------------------- | ------------- | -------------------------- |
| 1     | Ingest per-torrent error isolation | `ingest/ingest.py`                  | v11.1.x       | [phase-01.md](phase-01.md) |
| 2     | CLI config error decorator         | `cli.py`                            | v11.2.x       | [phase-02.md](phase-02.md) |
| 3     | Remove dead select_best_image      | `scraper/tmdb_client.py`            | v11.3.x       | [phase-03.md](phase-03.md) |
| 4     | Extract shared \_is_retryable      | `scraper/http_retry.py` + 3 clients | v11.4.x       | [phase-04.md](phase-04.md) |

## Coherence Gates

Before each phase, verify:

- [ ] Previous phase tests pass (`python -m pytest tests/ -x -q`)
- [ ] No uncommitted changes from previous phase
- [ ] IMPLEMENTATION.md updated with previous phase status

After each phase, verify:

- [ ] Phase-specific tests pass
- [ ] Full test suite passes (994+ tests, 0 failures)
- [ ] No regressions in existing tests

## File Map

### Created

- `personalscraper/scraper/http_retry.py` — shared retry predicate factory (Phase 4)

### Modified

- `personalscraper/ingest/ingest.py` — restructure `run_ingest()` error handling (Phase 1)
- `personalscraper/cli.py` — add `@handle_cli_errors` decorator (Phase 2)
- `personalscraper/scraper/tmdb_client.py` — remove dead method (Phase 3), replace `_is_retryable` (Phase 4)
- `personalscraper/scraper/tvdb_client.py` — replace `_is_retryable` (Phase 4)
- `personalscraper/scraper/artwork.py` — replace `_is_retryable` (Phase 4)

### Test files modified/created

- `tests/ingest/test_ingest.py` — add per-torrent isolation tests (Phase 1)
- `tests/test_cli.py` — add config error tests (Phase 2)
- `tests/scraper/test_tmdb_client.py` — remove dead tests (Phase 3), update retryable import (Phase 4)
- `tests/scraper/test_tvdb_client.py` — update retryable import (Phase 4)
- `tests/scraper/test_http_retry.py` — new test file (Phase 4)

## Acceptance Criteria

V11 is complete when:

1. A torrent that crashes does not prevent processing of remaining torrents
2. A `.env` config error produces a user-friendly message, not a pydantic traceback
3. `TMDBClient.select_best_image` no longer exists
4. A single `make_retryable_predicate()` in `http_retry.py` replaces 3 copies
5. All tests pass (994+), zero regressions
6. Each phase has its own tests validating the fix
