# Phase 12 — The tracker selector

**No STOP C.** Reverses RULINGS 3's form (DESIGN § 1.2): the pill says the filter, « Tous les trackers » lifts it.

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -n "FilterLine\|torrentFilter" frontend/maquette/design/src/features/trackers/torrents-tab.tsx`
  → the line of RULINGS 3 (**131–141**); `grep -n "export const optionList\|export const option =\|export const filterPill ="
  frontend/maquette/design/src/ui/variants/controls.ts` → the choice list and the pill exist.
- **Points ≈ 13.** R-L16bis-b 3; the filter zone and its one pill (≈ 15 lines) 2; the choices panel — « Tous les
  trackers », the roster in order, each count, the off ones said (≈ 30 lines) 3; the line of RULINGS 3 deleted 1;
  states `torrents-selector`, `torrents-selector-open` 2; `torrents-list-filtered`, `torrents-empty-filtered`
  re-drawn 1; the report 1.
- **Readers.** `harness/trackers_page.py` and `trackers_roster.py` read `torrents/filter` / `torrents/filter-clear`
  (R261, RULINGS 3) — re-aimed OUT LOUD onto the pill and « Tous les trackers », their successor R-L16bis-b.

## Red today

R-L16bis-b over `torrents-selector`: no selector — `data-part="torrents/selector"` absent.

## Move

1. A choice filters through the `trackers-filter` verb — an adjustment, `history.length` unchanged.
2. The panel lists every tracker of the roster, one switched off included and said so.

## Mutation

Drop the trackers switched off from the choices → the completeness hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

Every « Torrents » state (the filter zone), declared by script; the two new states.

## Commit

`feat(maquette-l16bis): the torrents are filtered by a tracker selector`
