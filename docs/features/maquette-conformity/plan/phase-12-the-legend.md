# Phase 12 — The legend moves to `ui/`, and is drawn over the season list (D.1 #9)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "export const legend|legendSwatch" -g '*.ts' frontend/maquette/design/src` →
  `features/media/variants.ts:346, 358`; drawn only at `features/media/panel-seasons.tsx:272`; the season list colours
  its episode dots at `features/media/season-list.tsx:178` and explains none (order 57); `grep -cv '^\s*$'
  frontend/maquette/design/src/features/media/season-list.tsx` → **390 / 400**.
- **Points ≈ 10.** The legend into its own `ui/` module (≈ 30 lines moved, 3); drawn on the media sheet's season
  list, only the codes present (≈ 8 lines, 2); R-conformity-j (3); lines moved out of `season-list.tsx` (1); the
  RESUME (1).
- **Overlap said.** L16-bis phase 6 (« the legend moves to ui ») loses its subject when this lands — reported to the
  orchestrator at this phase's gate, never edited in L16-bis's plan by this train.

## Red today

R-conformity-j on `mediasheet-series` and `followsheet-gaps`: every dot tone drawn has its legend entry — falls on
the media sheet.

## The one visible change

The media sheet's season list gains the legend (the report's item).

## Mutation

Drop one entry from the legend → falls by name.

## Oracle: states that diverge, declared by name

Every media sheet state with seasons (built by script).

## Commit

`refactor(maquette-conformity): the legend is ui's, and the season list explains its dots`
