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

## Next action

2 review cycles complete. 1910 tests passing. Merge mode is `manual` — squash merge PR #15 when ready, then run /implement:archive.
