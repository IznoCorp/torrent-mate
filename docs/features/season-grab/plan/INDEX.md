# Season Grab — Implementation Plan Index

> **Feature**: season-grab (#378) — whole-season acquisition
> **Design**: [DESIGN.md](../DESIGN.md) (operator rules R1–R6 frozen 2026-08-01)
> **Version**: 0.74.1 → 0.75.0 (minor bump)

## Phases

| #   | Phase                                           | File                                                               | Status |
| --- | ----------------------------------------------- | ------------------------------------------------------------------ | ------ |
| 1   | Domain + store (season kind, absorbed/fallback) | [phase-01-domain-store.md](phase-01-domain-store.md)               | ⬜     |
| 2   | filter_to_season + season search query + rank   | [phase-02-filter-to-season.md](phase-02-filter-to-season.md)       | ⬜     |
| 3   | Auto detection R1 + absorption R5               | [phase-03-detection-auto-r1.md](phase-03-detection-auto-r1.md)     | ⬜     |
| 4   | Episode→season conversion R2 + fallback R6      | [phase-04-conversion-fallback.md](phase-04-conversion-fallback.md) | ⬜     |
| 5   | Web API (grab endpoint) + frontend              | [phase-05-web-api-frontend.md](phase-05-web-api-frontend.md)       | ⬜     |
| 6   | ACCEPTANCE.md + full gate                       | [phase-06-acceptance.md](phase-06-acceptance.md)                   | ⬜     |

## Design Coverage

Every DESIGN section (§) mapped to the phase that implements it.

| DESIGN § | Content                                        | Phase                     |
| -------- | ---------------------------------------------- | ------------------------- |
| §1       | Problem statement                              | — (context)               |
| §2 R1    | Auto season detection (aired ≥1w, ≤half owned) | P3                        |
| §2 R2    | Episode→season conversion in search pass       | P4                        |
| §2 R3    | Uniformity replace (dispatch TV merge)         | — (already shipped, #213) |
| §2 R4    | Manual per-season grab button (Suivis UI)      | P5                        |
| §2 R5    | Absorption (episodes → absorbed status)        | P1, P3                    |
| §2 R6    | Fallback (season cutoff → re-enqueue episodes) | P4                        |
| §3.1     | Domain: WantedKind "season", statuses          | P1                        |
| §3.1     | Provenance events + eager-import hub           | P1                        |
| §3.2     | Detection (R1) in acquire/detect.py            | P3                        |
| §3.3     | Episode→season conversion (R2) in _search_pass | P4                        |
| §3.4     | Season search query + filter_to_season + rank  | P2                        |
| §3.4     | Grab: unchanged shared core                    | P2 (wiring)               |
| §3.5     | Fallback (R6) in cutoff gate                   | P4                        |
| §3.6     | Web UI + API                                   | P5                        |
| §4       | Non-goals (v1)                                 | — (constraint)            |
| §5       | Acceptance seeds (ACC-*)                       | P6                        |
| §6       | Test plan                                      | P1–P6 (per phase tests)   |
| §7       | Risks                                          | — (design notes)          |

## Key Code Targets (validated against real files)

| Module       | Real Path                                                       | What Changes                                     |
| ------------ | --------------------------------------------------------------- | ------------------------------------------------ |
| Domain       | `acquire/domain.py:20-21`                                       | `WantedKind` + `WantedStatus` literals           |
| Events       | `acquire/events.py:85-91`                                       | `WantedEnqueued.kind` + new events               |
| Wanted Store | `acquire/_wanted_store.py:810-849`                              | `find()` for season kind, absorb/fallback writes |
| Migration    | `acquire/migrations/`                                           | New 013 migration (CHECK widening)               |
| Orchestrator | `acquire/orchestrator.py:201-236`                               | `build_search_query()` + `filter_to_season()`    |
| Orchestrator | `acquire/orchestrator.py:635-645`                               | `_search_chain()` season branch                  |
| Detection    | `acquire/detect.py:320-409`                                     | Post-pass season grouping (R1)                   |
| Search Pass  | `acquire/_search_pass.py:77-135`                                | Season kind in `_search_item()`                  |
| Grab Pass    | `acquire/_grab_pass.py:46-183`                                  | Season kind in `_process_item()`                 |
| Pass Gates   | `acquire/_pass_gates.py:61-115`                                 | Fallback in `_apply_cutoff_gate()` (R6)          |
| Web Routes   | `web/routes/acquisition.py:92`                                  | POST season grab endpoint                        |
| Web Models   | `web/models/acquisition.py`                                     | Season grab request/response models              |
| Frontend     | `frontend/src/components/acquisition/FollowedPanel.tsx`         | Per-season button                                |
| Frontend     | `frontend/src/components/acquisition/FileDAcquisitionPanel.tsx` | Season rows                                      |
| Frontend     | `frontend/src/components/acquisition/CompletenessAccordion.tsx` | Absorbed state legend                            |
| Ranking      | `api/tracker/_ranking.py:33-128`                                | `media_kind="season"` already wired              |
