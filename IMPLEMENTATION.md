# Implementation Progress — trailer

> For Claude: read this file at session start. Current feature tracker.

**Feature**: YoutubeTrailerScraper Integration (minor)
**Version bump**: 0.6.0 → 0.7.0
**Branch**: feat/trailer
**PR merge**: manual
**PR**: https://github.com/LounisBou/personal-scraper/pull/15
**Design**: docs/features/trailer/DESIGN.md
**Master plan**: docs/features/trailer/plan/INDEX.md

## Phases

| #   | Phase                                                                    | File                             | Status |
| --- | ------------------------------------------------------------------------ | -------------------------------- | ------ |
| 1   | Extend `TMDBClient` with video endpoints                                 | phase-01-tmdbclient-videos.md    | [x]    |
| 2   | Extract `JsonTTLCache` primitive                                         | phase-02-json-ttl-cache.md       | [x]    |
| 3a  | Trailer discovery (`trailer_finder`, `youtube_search`, `trailers_cache`) | phase-03a-trailer-discovery.md   | [x]    |
| 3b  | Download wrapper (`ytdlp_downloader`)                                    | phase-03b-ytdlp-downloader.md    | [x]    |
| 3c  | Placement (`placement.py`)                                               | phase-03c-placement.md           | [x]    |
| 4   | State tracking (`state.py`)                                              | phase-04-state-tracking.md       | [x]    |
| 5   | Pipeline step (`trailers/step.py`)                                       | phase-05-pipeline-step.md        | [x]    |
| 6   | Scanner + orchestrator                                                   | phase-06-scanner-orchestrator.md | [x]    |
| 7   | Config schema via Pydantic defaults                                      | phase-07-config-defaults.md      | [x]    |
| 8   | CLI (`personalscraper trailers …`)                                       | phase-08-cli.md                  | [x]    |
| 9   | E2E + docs + gate                                                        | phase-09-e2e-docs-gate.md        | [x]    |
| 10  | PR fixes cycle 3 (40 findings)                                           | phase-10-pr-review-cycle-3.md    | [x]    |
| 11  | PR fixes cycle 4 (22 findings)                                           | phase-11-pr-fixes-cycle-4.md     | [ ]    |

## Review cycles

### Cycle 1

- Findings received: 30 across 5 reviewers (code, tests, errors, types, comments)
- Retained: 14 actionable (0 critical, 2 major, 9 medium, 3 minor)
- Ignored: 16 (CI flake speculation, cosmetic, out of scope, validated as sound)
- Fix phase: applied inline (cohesive small fixes, hot session)
- Status: clean — all retained fixed and tests added; proceeding to merge

**Major fixes**:

- `Video.type` `.capitalize()` corrupted multi-word types ("Behind the scenes" instead of "Behind the Scenes") → introduced canonical-vocabulary mapping
- `retry_after_days` per-element `ge=0` missing → negative day collapsed back-off ladder

**Medium fixes**:

- `Video.size` doc/code mismatch — tightened validator to `> 0` (docstring already said `> 0`, code allowed `0`)
- scanner.py removed silent AttributeError fallback on library_scan_max_age_hours; relies on Pydantic-strict guarantee instead
- `_backup_corrupt` filename now preserves `.json` suffix (`with_name` instead of `with_suffix`)
- `CookieConfig.from_env()` narrowed to `(ImportError, ValidationError)` + DEBUG log instead of swallow-all
- orchestrator disk_usage `FileNotFoundError` adds `log.debug` breadcrumb
- state.py `_save` outer OSError logs at error level with `error_type` before re-raising
- `all_entries()` aggregates malformed-dropped count and emits a summary warning
- `_fallback_search` second except catches non-DownloadError yt-dlp failures and trips the breaker
- `TrailerState` field annotations now `str | datetime | None` (was `str` while runtime accepted both)

**Minor fixes**:

- `_validate_season_number` extracted into shared helper used by both TrailerState and ScanItem
- `allowed_extensions` per-element pattern `^[a-z0-9]+$` rejects `""` and `"mp4 "`

**Tests added**: Video site/type normalisation + `> 0` size validation (5 tests), retry_after_days negative element rejected, allowed_extensions empty-string + trailing-space rejected.

### Cycle 2

- Findings received: ~10 across 5 reviewers (verification pass on cycle 1 fixes)
- Retained: 2 minor (parametrise + comment rewording)
- Ignored: out-of-scope pre-existing observations (DEBUG vs WARNING level for Settings fallback, malformed retry timestamp silent skip pre-existing, unknown-type DEBUG enhancement)
- Verdict from all 5 reviewers: cycle 1 fixes are sound, no regressions, no new bugs introduced
- Status: clean — proceeding to merge

**Polish applied**:

- Test parametrise expanded `_TMDB_TYPE_CANONICAL` coverage to all 8 documented types + all 3 sites (was 1 site + 1 multi-word type) — catches a broader regression net
- Reworded `state.py:should_skip` "type system can't narrow" comment to be more explicit about the invariant
- Reworded IMPLEMENTATION.md cycle 1 record to drop process-meta phrasing

### Cycle 3

- Findings received: 40 across 4 reviewers (code, tests, errors, comments) on 2026-04-25
- Retained: 40 actionable (10 critical, 20 important, 10 suggestions)
- Ignored: a small number flagged in "Out of scope" of the Phase 10 plan
  (e.g. `_lookup_library_item` data-structure refactor, `noqa: BLE001` audit,
  `purge --legacy-paths` helper)
- Fix phase: Phase 10 (`docs/features/trailer/plan/phase-10-pr-review-cycle-3.md`),
  organised into 7 sub-phases by code area
- Status: clean — all 6 implementation sub-phases done (10.1 downloader/state-store
  correctness, 10.2 cache integrity, 10.3 orchestrator status taxonomy + flag wiring,
  10.4 error-handling hardening, 10.5 test gaps + MagicMock leak fix, 10.6 docs refresh);
  10.7 milestone gate completed
- Final test count: 1955 passing, 3 skipped, 18 deselected (+15 from baseline of 1940)
- Sub-phase commits: a6364c3, 0bb883e, 62e25b3, 9eae956, 1f2dc6d, 97c0bd0, d34e906, caf4665,
  aeea2d5, 8a99320, 3340bf1

**Critical themes** (cluster of root-cause pathologies surviving cycles 1-2):

- **Silent persistence of broken state**: TMDB/YouTube outages cached as `[]`
  / `__no_result__` for 7 days; finder import failures persisted as
  `NO_TRAILER_AVAILABLE`; yt-dlp returning SUCCESS without verifying output
  existed; `<MagicMock name='mock.trailers.lock` literal file leaked at repo
  root from a pipeline fixture
- **Flag wired but no-op**: `--continue-on-trailer-error` does nothing in
  `pipeline.py:291-299`
- **Lock contention with no surface signal**: `fcntl.flock(LOCK_EX)` without
  `LOCK_NB` deadlocks two concurrent runs silently
- **Docs lag behind code**: TV-show placement convention changed in `28d9f75`
  but `trailers.md`, `naming.md`, `CLAUDE.md`, `step.py`, `pipeline.py` still
  describe the old flat naming

### Cycle 4

- Findings received: ~50 across 4 reviewers (code, tests, errors, comments) on
  post-cycle-3 push (`918e070`)
- Retained: 22 actionable (7 critical, 8 major, 7 medium)
- Ignored: design-coherent suggestions, defensive hardening for hypothetical
  futures, polish (see Phase 11 "Out of scope")
- Fix phase created: `docs/features/trailer/plan/phase-11-pr-fixes-cycle-4.md`
  (7 sub-phases organised by code area)
- Status: fix phase dispatched → awaiting `/implement:phase`

**Critical themes**:

- **`TrailerStateLocked` only caught in `step.py`** — every other call site
  in the orchestrator and CLI leaks raw tracebacks under contention; per-item
  contention aborts the whole orchestrator
- **Cache poisoning prevention is half-done** — `TypeError` from yt-dlp parser
  drift and transport errors still slip through `_fallback_search`'s fail-soft
  contract → cached as `__no_result__` for 7d
- **Cycle-3 test work was partial** — `MagicMock(spec=…)` advertised but never
  applied; `verify --deep` error-path tests planned but only happy path
  delivered; misleading comment at `test_orchestrator.py:17`
- **New regression in `logger.py`** — broadened redaction regex over-matches
  `cookie_count`, `token_count`, `secret_count` (integer counters silently
  redacted)

## Next action

Execute Phase 11 via `/implement:phase`. After all sub-phases complete and the
milestone commit lands, push and let the auto PR-review cycle decide whether
a Cycle 5 is needed.
