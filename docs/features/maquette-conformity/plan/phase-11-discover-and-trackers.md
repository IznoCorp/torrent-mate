# Phase 11 — Découvrir and Trackers

## What changes

1. **Découvrir's TMDB notice is the toned notice** (OPEN 3 = A): `surfaceError()` repainted warning by inline style
   with `role="alert"` (`features/acquisition/discover-tab.tsx:163–171`) → `warning`, no alert, no inline colour.
2. **Trackers' tab bar is `ui` `Tabs`** (D.1 #1, DECIDED 7 — Trackers resembles the existing bars, never the
   reverse): `features/trackers/page.tsx:31–46`; `trackersTab` dies (`features/trackers/variants.ts:43`).

## Acceptance — red first

- R-conformity-b extended to `trackers-page`: the three bars now share height, composition and count drawing.
- The notice's hold (`state_surfaces.py`) on `discover-degraded`: no `role="alert"`, the `warning` tone.
- Re-aimed by name: `trackers_page.py`, `discover_page.py`.
- The oracle accepts by name: `discover-degraded` (the notice), Trackers' bar if its geometry moves.

## Commit

`refactor(maquette-conformity): Découvrir's notice and Trackers' tab bar from ui`
