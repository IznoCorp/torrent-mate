# trailer — Implementation Plan Index

> **Note:** This plan was prepared ahead of time by `/implement:prepare-feature`. When
> `/implement:feature trailer` runs later, it will move this plan to
> `docs/features/trailer/plan/` and wire it into `IMPLEMENTATION.md`.

**Feature**: YoutubeTrailerScraper Integration
**Codename**: `trailer`
**Design**: `docs/superpowers/roadmap/trailer/specs/DESIGN.md`
**Branch (future)**: `feat/trailer`
**Version bump**: 0.4.0 → 0.5.0 (minor — applied at `/implement:create-branch` time, after `ext-staging` merges)
**Depends on**: `ext-staging` merged to `main` (staging paths must be fully configurable before this feature lands)

## Phases

| #   | Phase                                                                    | File                                                                 | Status |
| --- | ------------------------------------------------------------------------ | -------------------------------------------------------------------- | ------ |
| 1   | Extend `TMDBClient` with video endpoints                                 | [phase-01-tmdbclient-videos.md](phase-01-tmdbclient-videos.md)       | [ ]    |
| 2   | Extract `JsonTTLCache` primitive                                         | [phase-02-json-ttl-cache.md](phase-02-json-ttl-cache.md)             | [ ]    |
| 3a  | Trailer discovery (`trailer_finder`, `youtube_search`, `trailers_cache`) | [phase-03a-trailer-discovery.md](phase-03a-trailer-discovery.md)     | [ ]    |
| 3b  | Download wrapper (`ytdlp_downloader`)                                    | [phase-03b-ytdlp-downloader.md](phase-03b-ytdlp-downloader.md)       | [ ]    |
| 3c  | Placement (`placement.py`)                                               | [phase-03c-placement.md](phase-03c-placement.md)                     | [ ]    |
| 4   | State tracking (`state.py`)                                              | [phase-04-state-tracking.md](phase-04-state-tracking.md)             | [ ]    |
| 5   | Pipeline step (`trailers/step.py`)                                       | [phase-05-pipeline-step.md](phase-05-pipeline-step.md)               | [ ]    |
| 6   | Scanner + orchestrator                                                   | [phase-06-scanner-orchestrator.md](phase-06-scanner-orchestrator.md) | [ ]    |
| 7   | Config schema via Pydantic defaults                                      | [phase-07-config-defaults.md](phase-07-config-defaults.md)           | [ ]    |
| 8   | CLI (`personalscraper trailers …`)                                       | [phase-08-cli.md](phase-08-cli.md)                                   | [ ]    |
| 9   | E2E + docs + gate                                                        | [phase-09-e2e-docs-gate.md](phase-09-e2e-docs-gate.md)               | [ ]    |

## Phase Summaries

| #   | One-line goal                                                                                                             |
| --- | ------------------------------------------------------------------------------------------------------------------------- |
| 1   | Add `fetch_movie_videos()` / `fetch_tv_videos()` + `Video` dataclass to `TMDBClient`. Additive, merge-safe alone.         |
| 2   | Extract `JsonTTLCache` + shared `check_ttl()` helper. Refactor `keywords_cache` to call the helper. Format unchanged.     |
| 3a  | Implement TMDB-first / YouTube Data API v3 primary + yt-dlp `ytsearch1` fallback discovery. Caching. No download yet.     |
| 3b  | Implement `ytdlp_downloader.py`: yt-dlp Python API + cookies + bounded bot-detected retry. Fully mocked tests.            |
| 3c  | Implement `placement.py`: flat `{name}-trailer.{ext}` for movies AND TV shows + populate NFO `<trailer>` tag.             |
| 4   | Persistent JSON state file with stable composite keys, retry-after policy (UTC), status enum, auto-GC lifecycle.          |
| 5   | Wire `trailers` step between `verify` and `dispatch`. Non-blocking `StepReport` (extended after call-site audit).         |
| 6   | Scanner walks staging or library; orchestrator glues discovery → download → placement → state update.                     |
| 7   | `TrailersConfig` Pydantic model with sensible defaults (`enabled: false`). Update `.env.example` (`YOUTUBE_API_KEY`).     |
| 8   | `personalscraper trailers scan/download/verify/purge` with full filter set. Consumes `TrailersConfig` from Phase 7.       |
| 9   | E2E fixture (hermetic + opt-in network), coverage audit, `trailers.md` + updates to architecture/commands/testing/naming. |

## Phase 3 — Trailer acquisition (three sub-phases)

Phases 3a, 3b, and 3c collectively implement DESIGN §3 (Architecture — `scraper/trailer_finder.py`, `scraper/youtube_search.py`, `scraper/ytdlp_downloader.py`, `scraper/trailers_cache.py`) and DESIGN §4 (Key Decision §4: discovery + placement strategy). They are split to enforce sub-phase commit discipline and allow independent review.

## Dependencies

```
Phase 1  ──────────────────────────────────── (no prior dependency)
Phase 2  ──────────────────────────────────── (no prior dependency)
Phase 3a ──── depends on Phase 1 + Phase 2
Phase 3b ──── depends on Phase 3a
Phase 3c ──── depends on Phase 3a (placement is discovery-shape-aware)
Phase 4  ──── depends on Phase 3a + Phase 3c
Phase 5  ──── depends on Phase 3b + Phase 3c + Phase 4
Phase 6  ──── depends on Phase 4 + Phase 5
Phase 7  ──── depends on Phase 6 (config schema must land before CLI consumes it)
Phase 8  ──── depends on Phase 7 (CLI consumes TrailersConfig from Phase 7)
Phase 9  ──── depends on all prior phases
```

## Commit Convention

All commits on branch `feat/trailer`.

- Sub-phase commits: `<type>(trailer): <short description>` where `type ∈ {feat, fix, chore, refactor, test, docs}`
- Milestone commits at phase end: `chore(trailer): phase NN gate — <summary>`

No `vX.Y.Z` prefixes in commit messages — version traceability lives in `IMPLEMENTATION.md`.

## Notes for the implementer

- Phases 1 and 2 are behavior-preserving — each can be merged to main independently if the feature ever aborts early.
- Phase 7 intentionally has no `init-config` migration — Pydantic `Field(default_factory=...)` handles omission gracefully (`enabled: false` default).
- Phase 9 must first check whether a full pipeline E2E fixture already exists in `tests/e2e/` before deciding whether to create one.
- Cookie file security checks (POSIX mode 600, NTFS detection) are part of Phase 3b, not Phase 7.
- The `trailers` step icon for `PipelineReport.to_html()` should be added in Phase 5, alongside the step wiring.
- Phase 5 Sub-phase 5.1 MUST begin with a grep audit of existing `StepReport(…)` call-sites before extending the dataclass (pipeline.py, notifier.py, PipelineReport.to_html).
- Phase 7 / Phase 8 order was swapped from the original draft so the config schema lands before the CLI that consumes it.
