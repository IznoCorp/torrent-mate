# Phase 5 — The absorption

**No STOP C** (OPEN 5 is phase 1's; written for A — under B this phase compares the lines « S03 » and « S03E07 » of
one provider identity instead of reading `absorbedBy`, ≈ same points).

**Opening measure (2026-09-29, on `b63a45438`):**

- **Commands.** `grep -n "episode(one) === episode(other)" frontend/maquette/design/src/features/acquisition/arrival-slots.ts`
  → line **80** (the token that keeps a season and its episode apart — moved at phase 4, re-read in its new home);
  the dense « En cours » after phase 2 draws **5** cards (3 seeded + Silo's two) — re-taken on the served answer.
- **Points ≈ 13.** R-season-recovery-a with its mutation 3; R-season-recovery-e with its mutation 3; the absorption in
  the moved derivation (a card whose `absorbedBy` names a card on its way is dropped; « En vol »'s count reads the
  same list) 2; `season-recovery-before-ask` posed (the season card lifted, the pointer cleared) 1;
  `season-recovery-absorbs-episode` 1; R224's hold re-aimed OUT LOUD (its world now holds a season card) 1; the
  finger walk at the seven widths 1; the report 1.
- **Readers.** `now-tab.tsx:40` and the tab's count (`acquisition-tabs.tsx`) read the derivation; R224
  (`now_holds_in_flight.py`) reads « one card each » on `acq-now-loaded`.

## Red today

R-season-recovery-a over `acq-now-loaded`: « Silo » · « S03E07 » drawn in « En vol » beside « Silo » · « S03 ».

## Move

1. The absorption in the derivation — one place; the tab, its count, the row (phase 6) and the pointer (phase 9)
   read it.
2. Nothing in `now-tab.tsx` changes.

## Mutation

R-a: drop the absorption → falls by name; count « En vol » before the absorption → falls on the count.
R-e: push a card per ask in `grabSeasonForFollow` → falls on the second ask.

## Register

None.

## Oracle: states that diverge, declared by name

`acq-now-loaded` (one card fewer) and every state drawing the dense « En cours », declared by script;
`season-recovery-before-ask` and `season-recovery-absorbs-episode` are new.

## Commit

`feat(maquette-season-recovery): an episode's acquisition card is absorbed while its season is recovered`
