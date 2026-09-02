# Phase 2 — The resolution screen · **conversion**

**Owns**: `features/arrivals/resolution-screen.tsx` 430 → under 400. **Constitution**: §15, §16
(the screen keeps `data-key="resolution:<folder>"` and its Back).

## What changes

1. `features/arrivals/resolution-cards.tsx` is born with `ReleaseCard`, `DecisionCard` and
   `Candidates`, their header comments and their imports (`useArrivalsReference`, `fr.json` for the
   number words, the variants they call). Exported by name; the screen imports them.
2. `resolution-screen.tsx` keeps `ResolutionScreen` alone: the route param, the reads, the
   progression, the markup.
3. `GRANDFATHERED["features/arrivals/resolution-screen.tsx"]` is removed in the SAME commit — the
   arm refuses an entry for a file back under the ceiling.
4. The moved code changes by nothing but its file: same tags, same classes, same `data-*`, same
   comments (which carry no date, no lot, no phase — and the comment that says the `Icon` helper
   is « still not shared » is gone with phase 1).

## Definition of done

- `grep -cve '^\s*$' frontend/maquette/design/src/features/arrivals/resolution-screen.tsx` → **< 400**
  (the design estimates ~170); `resolution-cards.tsx` → < 250 (no warning).
- `python3 scripts/check-frontend-boundaries.py --arm size` → 5 at or over the ceiling.
- The oracle: zero divergence (the resolution states `arr-resolution`, `arr-decision`, and the
  deep entry `screen_addresses.py` drives).
- `run.sh --contracts` green; `npm run check` green; `python3 scripts/check-no-french.py` green
  (file names English, the `fr.json` lookup keeps its comment).
- One commit: `refactor(maquette-l14): the resolution screen — its cards move beside it`.
