# Phase 5 — The roster's line

**OPEN 7 = A, unconditional.** The line has a variant, `trackers-cross-seed-engine-off` is a named scenario (not
the default, phase 2), and `engineEnabled` is drawn. M6 (rulings-coherence) corrects HOW: the engine's cause is said
FIRST and the tracker's OWN switch state is said SECOND on the same line, never one hiding the other.

**Opening measure (2026-09-27, on `1d1282567` — L16's roster does not exist on this head; figures are from L16's
plan, already re-drawn on `5e5ecd052`):**

- **Commands.** `ls frontend/maquette/design/src/features/trackers` → **no such directory**;
  `docs/features/maquette-l16/plan/phase-03-trackers-tab.md@f3d8fed01` places the collapsed entry in
  `features/trackers/trackers-tab.tsx` (one row = name, ratio, trend, volumes, the refused-identifier fact, the
  policy disclosure). `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/features/account/page.tsx` → **79**
  (the analogue for the size of a list page). `sed -n 1,30p frontend/maquette/design/src/app/tab-bar.tsx` — the bar
  knows nothing of what a badge counts (94 non-blank lines).
- **Points ≈ 11.** The line's component inside the entry ≈ 20 lines new 2 and ≈ 10 lines of the entry edited 2; the
  query's read of the `crossSeed` sub-object (≈ 6 lines edited in `queries.ts`) 1; the `fr.json` keys for the line
  and the engine-off variant 1; the states `trackers-cross-seed` and `trackers-cross-seed-engine-off`, both
  re-using phase 2's seed and scenario dial 2; R-L17-b (the count on the line equals the mark's rows, summed by
  state, across every torrent — its first hold; the rest at phase 6) 3; R-L17-a re-aimed at the entry's chip 1.
- **Found.** The line is PART OF the entry's own row, not a control (F63, corrected from the first drawing's « a
  path to the section », which ruling 19 killed before it could exist): one door onto the switch, if any, is phase
  9's.

## Red today

**R-L17-b — one derivation** (DESIGN § 5), first hold: the count of torrents the roster's line says equals the
number of pairs the mark answers for this tracker in state `active`, summed across the library, and the state it
draws equals the mock's own field. Red against `main`: no line exists.

## Move

1. The line inside L16's collapsed entry, reading the summary read's `crossSeed`. `data-part="trackers/cross-seed"`.
2. `harness/states/trackers.ts` — `trackers-cross-seed` and `trackers-cross-seed-engine-off`, under the scenario
   dial of phase 2.
3. R-L17-a re-aimed: the chip the line draws reads one of the six words.

## ~~Mutation~~

~~Commit first, then `scripts/mutate.sh`: compute the count client-side from a constant → R-L17-b falls; draw the~~
tracker's state from a hard-coded word → falls; draw the raw code → R-L17-a falls; hide the tracker's own switch
cause when the engine is off → the M6 hold falls.

## Register

—

## ~~Oracle: states that diverge, declared by name~~

L16's `trackers-list` (each entry gains a line) and `tracker-alert-active` where it draws the roster — accepted
~~with « L17 § 3.1: the entry's cross-seed line ». Any other divergence is STOP A.~~

## Gate

Per INDEX « Gates »; `--a11y` on `trackers-cross-seed` and `trackers-cross-seed-engine-off`.

## Commit

`feat(maquette-l17): each tracker's entry says where its cross-seed stands`
