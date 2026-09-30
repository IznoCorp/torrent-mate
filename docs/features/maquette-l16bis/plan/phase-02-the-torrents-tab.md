# Phase 2 — The « Torrents » tab around the card: the landing, the selector, the legend (S1, S2, S3)

**Opening measure** (taken on `9234341fc`; re-taken at the real opening):
`grep -n "tabMemory(" frontend/maquette/design/src/features/trackers/verbs.ts` → **18**, first tab `"trackers"`;
`grep -n "trackersTab" frontend/maquette/design/src/app/arrival.ts` → **32**, `"trackers"`;
`grep -n "function FilterLine" frontend/maquette/design/src/features/trackers/torrents-tab.tsx` → **131** (RULINGS 3's
line); the `ui` legend's tones on the train's head → six, no `danger`, no `neutral` (DESIGN § 0.4).

## What changes

1. **« Torrents » first** (S1): the first tab of the memory and of the opening state → `torrents`; the memory's key
   unchanged; a landing that names a tab is obeyed. The bar itself is `ui` `Tabs`, the train's.
2. **The tracker selector** (S2): one `filterPill` in the filter zone — « Tous les trackers » or the tracker's name,
   pressed, with its count; a tap opens the bottom panel listing « Tous les trackers » and the roster in its
   configuration order, each count, a tracker switched off said so; a choice filters through `trackers-filter` and
   pushes nothing. RULINGS 3's line (`torrentFilter`, `torrentFilterClear`) is deleted.
3. **The legend on « Torrents »** (S3; DECIDED 5): the `ui` legend inline above the list, only the codes present
   (filtered: the filtered list's); ONE tone map the rows and the legend both read; the legend ADAPTED with `danger`
   and `neutral` (a `legendSwatch` tone each, in `ui/variants/legend.ts` — written in DESIGN § 0.4).
4. **Its register row** (order 57): « The Trackers page draws seven colour codes and explains none » (DESIGN § 6),
   with escaped from / why / family repaired by R-L16bis-c.

## Acceptance — red first on the old code, then green

- **R-L16bis-a** (the landing) — red on a cold `/trackers` (« Trackers » selected); **R-L16bis-b** (the selector) —
  red on `torrents-selector` (no `torrents/selector`); **R-L16bis-c** (the legend complete) — red on
  `torrents-list` (seven tones, no entry).
- Re-aimed OUT LOUD: `trackers_page.py`'s cold landing (successor R-L16bis-a); the RULINGS 3 reads of
  `trackers_page.py` and `trackers_roster.py` (successor R-L16bis-b).
- Named states: every S1 and S2 id, `torrents-legend` and `torrents-legend-partial`; the oracle accepts every
  « Torrents » state by name.
- Walked by finger: a cold entry, a second visit after « Trackers », « Voir le tracker » naming `trackers:c411`; the
  selector's panel opened and closed with Retour.

## The midpoint — after this phase, once

`run.sh --contracts` and the full responsive sweep (Chromium + WebKit), `TM_HARNESS_JOBS=2`; their real falls
repaired before phase 3 opens.

## Commit

`feat(maquette-l16bis): the Torrents tab opens first, filters by tracker and says what its colours mean`
