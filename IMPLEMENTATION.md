# Implementation Progress — trailer

> For Claude: read this file at session start. Current feature tracker.

**Feature**: YoutubeTrailerScraper Integration (minor)
**Version bump**: 0.6.0 → 0.7.0
**Branch**: feat/trailer
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/trailer/DESIGN.md
**Master plan**: docs/features/trailer/plan/INDEX.md

## Phases

| #   | Phase                                                                    | File                             | Status |
| --- | ------------------------------------------------------------------------ | -------------------------------- | ------ |
| 1   | Extend `TMDBClient` with video endpoints                                 | phase-01-tmdbclient-videos.md    | [ ]    |
| 2   | Extract `JsonTTLCache` primitive                                         | phase-02-json-ttl-cache.md       | [ ]    |
| 3a  | Trailer discovery (`trailer_finder`, `youtube_search`, `trailers_cache`) | phase-03a-trailer-discovery.md   | [ ]    |
| 3b  | Download wrapper (`ytdlp_downloader`)                                    | phase-03b-ytdlp-downloader.md    | [ ]    |
| 3c  | Placement (`placement.py`)                                               | phase-03c-placement.md           | [ ]    |
| 4   | State tracking (`state.py`)                                              | phase-04-state-tracking.md       | [ ]    |
| 5   | Pipeline step (`trailers/step.py`)                                       | phase-05-pipeline-step.md        | [ ]    |
| 6   | Scanner + orchestrator                                                   | phase-06-scanner-orchestrator.md | [ ]    |
| 7   | Config schema via Pydantic defaults                                      | phase-07-config-defaults.md      | [ ]    |
| 8   | CLI (`personalscraper trailers …`)                                       | phase-08-cli.md                  | [ ]    |
| 9   | E2E + docs + gate                                                        | phase-09-e2e-docs-gate.md        | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to execute phases starting from Phase 1.
