# Phase 17 — Découvrir's header

**STOP C: DECIDED 8** (2026-09-29, PR #637 — DESIGN § 5): « n séries et m films à découvrir », beside the
view-switch buttons, both numbers from the suggestions already read — none of the three costed proposals, no engine
demand.

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -n "liveStrip()\|pill/list" frontend/maquette/design/src/features/acquisition/discover-tab.tsx`
  → lines **107** (the empty place) and **151** (the strip in the body); `grep -n '"live[A-Z]' frontend/maquette/design/src/i18n/fr.json`
  → the four literals (**850–854**); `grep -cv '^\s*$' frontend/maquette/design/src/features/acquisition/discover-tab.tsx`
  → **212**.
- **Points ≈ 9.** R-L16bis-k 3; the strip moved into the view row, its `inline` variant, the four literals
  deleted (≈ 15 lines) 2; the sentence whole on a tap 1; states `discover-header`, `discover-header-narrow`,
  `discover-header-loading`, `discover-header-unavailable` (½ each) 2; the report 1; the content (DECIDED 8): both
  counts split from the suggestions list already rendered, by media type — no field declared, no seed column, no
  demand, nothing beyond the move.
- **Readers.** `harness/page_host.py` and `harness/four_tabs.py` read Découvrir's filter zone — the region
  `acquisition/filters` kept.

## Red today

R-L16bis-k over `discover-header`: the message is a child of `discover/body`, and its figures are `fr.json` strings.

## Move

1. The message in the pill row's empty place; one line, ellipsised at the switch, its whole on a tap.
2. Every figure from a read; the TMDB-disconnected warning stays in the body.

## Mutation

Draw a figure from `fr.json` → the read hold falls by name.

## Register

The defect « four literals drawn as figures » (DESIGN § 6) closed by this rule; no demand filed (DECIDED 8 withdraws
T4 — the count needs no engine change).

## Oracle: states that diverge, declared by name

Every Découvrir state (the body lost its strip), declared by script; the new states.

## Commit

`feat(maquette-l16bis): Découvrir's header message beside the view switch, saying something read`
