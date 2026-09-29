# Phase 7 — The legend on Trackers

**STOP C: DECIDED 5** (2026-09-29, PR #637 — DESIGN § 5): inline, above the list — the season legend's own place,
REUSED as is. Behind a « Légende » control is refused.

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -n "statusDot(\|chip({ tone" frontend/maquette/design/src/features/trackers/*.tsx` → the seven
  codes of DESIGN § 0.1 item 5 (origin `info` / `waiting`; chips `info`, `success`, `danger` ×3, `warning`), plus the
  card's state tones once phase 9 lands — this phase lands first and the legend READS the tone map, so phase 9's
  tones join it without a second edit.
- **Points ≈ 9.** R-L16bis-c 3; one tone map per tab, the rows and the legend reading it (≈ 25 lines) 2; the words in
  `fr.json` (≈ 10) 1; three states (`torrents-legend`, `torrents-legend-partial`, `trackers-legend`) re-using seeds 3.
- **Readers.** None reads a legend on this page today.

## Red today

R-L16bis-c over `torrents-list`: seven tones drawn, zero legend entries.

## Move

1. The legend shows only the codes present on the tab read (the season rule); filtered, only the filtered list's.
2. The origin's third value (« publié par vous », L23) is an entry of the map, drawn when a row carries it.

## Mutation

Add a tone to a row outside the map → the completeness hold falls by name.

## Register

The defect « seven colour codes, none explained » closed by this rule (DESIGN § 6).

## Oracle: states that diverge, declared by name

Every state of the two tabs (the legend added), declared by script; the three new states.

## Commit

`feat(maquette-l16bis): every colour of the Trackers page has its word`
