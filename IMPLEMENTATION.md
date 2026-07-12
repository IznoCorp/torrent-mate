# Implementation Progress — webui-overhaul

> For Claude: read this file at session start. Current feature tracker.

**Feature**: TorrentMate Web UI — UX/UI Overhaul (3 objectives)
**Type**: feat
**Branch**: feat/webui-overhaul (off the merged post-S7 polish; #249 in main)
**PR**: #251 → main (https://github.com/IznoCorp/torrent-mate/pull/251) — **OPEN, awaiting review + squash merge**
**Merge**: squash (operator merges)
**Design**: `DESIGN_VISION.md` (brief) + `DESIGN_REPORT.md` (closing report) — both at repo root
**Deploy**: pushed to the `staging` branch on every commit (autodeploy → tm-staging.iznogoudatall.xyz), live-verified

## Status: FUNCTIONALLY COMPLETE — all 3 objectives + L9 + L10 shipped

| #   | Objective / block                                                                                          | Status |
| --- | ---------------------------------------------------------------------------------------------------------- | ------ |
| 0   | Immersion + DESIGN_VISION.md                                                                               | [x]    |
| L0  | Design-system foundation (shared components)                                                               | [x]    |
| 1   | OBJ1 — living pipeline (Flow Board + per-media timeline)                                                   | [x]    |
| 2   | OBJ2 — scraping/matching (Resolution Deck + staging library)                                               | [x]    |
| 3   | OBJ3 — acquisitions (per-series trigger + card redesign)                                                   | [x]    |
| B   | Operator bug batch (#1 mobile board, #2 resolved read-only, #3 scrape drift-unlink root cause, #4 summary) | [x]    |
| L9  | Transverse — vendor chunk split + /locks 60s cache + states                                                | [x]    |
| L10 | Final audit + DESIGN_REPORT.md                                                                             | [x]    |

## Key artefacts (for resume)

- Backend: `web/routes/staging.py` + `web/staging/` (OBJ2A read-model + poster route);
  `web/routes/pipeline.py` `pipeline_stages` (OBJ1); `web/acquisition/runner.py` +
  `web/routes/acquisition.py` trigger/enrichment (OBJ3); `acquire/migrations/005_followed_metadata.sql`.
- Frontend: `components/pipeline/FlowBoard.tsx` + `StageMediaList.tsx`; `components/staging/*`
  (library grid + timeline); `pages/AcquisitionPage.tsx` (card grid); `components/pipeline/RecentResolutions.tsx`.
- Scrape fix (#3): `scraper/movie_service.py` + `scraper/tv_service.py` (no premature NFO unlink) +
  `commands/scrape_resolve.py` (NFO-landed invariant).

## Next action

1. **Operator: review + squash-merge PR #251** into `main` (I never merge without explicit go).
   After merge: sync `main` back onto the dev checkout + confirm prod autodeploy serves the new sha.
2. **Follow-ups (operator's call, not blocking the merge):**
   - Re-scrape the 2 legacy partial folders (`Obsession (2026)`, `Ferrari … Trio (2025)`) — they hold
     artwork but no NFO from before the #3 fix; a fresh scrape recovers their NFO.
   - Optional: backfill card posters for pre-existing follows (poster URL is only cached at follow-time;
     the indexer stores a poster boolean, not a URL — existing follows show the initials fallback).

## Review cycles

_(none yet — PR #251 just opened)_
