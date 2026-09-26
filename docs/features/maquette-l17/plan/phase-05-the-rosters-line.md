# Phase 5 — The roster's line

**Reads OPEN 7 (the engine's own switch).** OPEN 7 = A (said): the line has a variant, `trackers-cross-seed-engine-off` is a state and
`engineEnabled` is drawn — **+2 points (13)**. OPEN 7 = B (folded): the line reads « stoppé » under an engine that is off and the state costs
nothing; the cause is demand B's to carry (DESIGN § 7.2). The phase draws what is ruled and STOPs (C) if neither is.

**Opening measure (2026-09-27, on `46806a88d` — L16's roster does not exist on this head; figures are from L16's plan):**

- **Commands.** `ls frontend/maquette/design/src/features/trackers` → **no such directory**; `docs/features/maquette-l16/plan/phase-03-roster.md`
  places the roster in `features/trackers/page.tsx` (≈ 55 lines new in L16, one row = ratio, trend, volumes, path to the detail, data-part
  `trackers/row`); `docs/features/maquette-l16/plan/phase-10-alert-on-bar.md` places `trackersBadge` in `features/trackers/queries.ts`. On this head the
  analogue for the size of a list page is `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/features/account/page.tsx` → **79**.
  `sed -n 1,30p frontend/maquette/design/src/app/tab-bar.tsx` — the bar knows nothing of what a badge counts (94 non-blank lines).
- **Points ≈ 11.** The line's component inside the row ≈ 20 lines new 2 and ≈ 10 lines of the row edited 2; the query's read of the `crossSeed`
  sub-object (≈ 6 lines edited in `queries.ts`) 1; the `fr.json` keys for the line (≈ 8 lines) 1; the state `trackers-cross-seed` re-using
  phase 2's seed 1; R-L17-b (the count on the line equals the section's rows — its first hold; the rest at phase 6) 3; R-L17-a re-aimed at the
  line's chip 1. The unit test of phase 4, if it was cut, lands here (+3 → 14).
- **Found.** The line is a PATH to the section of the detail, not a control (DESIGN § 3.1): one door onto a setting, if any, is phase 9's.

## Red today

**R-L17-b — one derivation** (DESIGN § 5), first hold: the count of torrents the roster's line says equals the number of rows the section
lists, and the state it draws equals the mock's own field. Red against `main`: no line exists.

## Move

1. The line inside L16's row, reading the summary read's `crossSeed`. `data-part="trackers/cross-seed"`.
2. `harness/states/trackers.ts` — `trackers-cross-seed` (and `trackers-cross-seed-engine-off` under OPEN 7 = A), under the scenario of phase 2
   for the rows that need a switch on.
3. R-L17-a re-aimed: the chip the line draws reads one of the words.

## Mutation

Commit first, then `scripts/mutate.sh`: compute the count client-side from a constant → R-L17-b falls; draw the tracker's state from a hard-coded
word → falls; draw the raw code → R-L17-a falls.

## Register

—

## Oracle: states that diverge, declared by name

L16's `trackers-list` (each row gains a line) and `tracker-alert-active` where it draws the roster — accepted with « L17 § 3.1: the row's
cross-seed line ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `--a11y` on `trackers-cross-seed`.

## Commit

`feat(maquette-l17): each tracker's row says where its cross-seed stands`
