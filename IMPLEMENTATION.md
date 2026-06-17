# Implementation Progress — trailer-fallback

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Trailer download-failure → YouTube-search fallback (recover unavailable/geo-blocked TMDB trailer URLs) (minor)
**Version bump**: 0.34.1 → 0.35.0
**Branch**: feat/trailer-fallback
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/204
**Design**: docs/features/trailer-fallback/DESIGN.md
**Master plan**: docs/features/trailer-fallback/plan/INDEX.md

## Phases

| #   | Phase                              | File                                       | Status |
| --- | ---------------------------------- | ------------------------------------------ | ------ |
| 1   | Config field + fallback hook (TDD) | phase-01-config-field-and-fallback-hook.md | [x]    |
| 2   | Gate                               | phase-02-gate.md                           | [x]    |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

All phases complete — run `/implement:feature-pr` (push + PR + CI poll).
