# Phase 8 — The season's card and its journey

**STOP C: OPEN 1, 3, 6** (DESIGN § 5). Written for A, A, A. Under OPEN 1 = B the journey stays per title (≈ 3 points
less); under OPEN 3 = B the season's journey lists nothing absorbed (≈ 2 less); under OPEN 6 = B
`season-card-automatic` is not drawn (1 less).

**Opening measure (2026-09-29, on `b63a45438`):**

- **Commands.** `grep -n 'address: "journey:"' frontend/maquette/design/src/features/acquisition/panel-journey.ts` →
  line **90** (per title); `grep -n "journey: {" -A10 frontend/maquette/design/src/app/addressed-panels.ts` → the
  reopen by title, **58–67**; `grep -n "seeJourney" frontend/maquette/design/src/features/acquisition/follow-actions.ts`
  → **79** (the primary) and **129** (the secondary).
- **Points ≈ 14.** The journey addressed per acquisition — producer, reopen test, the follow panel's « Voir le
  parcours » opening the live recovery's 3; the season's journey listing its absorbed episodes, each a path to its own
  journey (OPEN 3 = A) 2; the card's line, origin and ladder — nothing to draw, the states prove it: `season-card-requested`,
  `season-card-searched-nothing`, `season-card-downloading`, `season-card-arrived`, `season-card-blocked`,
  `season-card-one-off`, `season-card-journey`, `season-card-automatic` 8; holds added to R-a (the arrival joins, one
  card) and R-b (the mark at `arrived` and `blocked`) — holds, not rules — folded into the states; the report 1.
- **Readers.** `harness/journey.py` and `harness/journey_verbs.py` open `journey:<title>` — re-aimed OUT LOUD to the
  acquisition's key.

## Red today

`season-card-arrived`: the season pack's arrival and the season card drawn as two cards (the merge reads no season
field yet) — R-a's « one card each » hold falls.

## Move

1. The merge in the derivation reads `season` / `episode`, not the line's token.
2. No new part in `features/acquisition/card-markup.ts`.

## Mutation

The merge back to the line's token → R-a's hold falls at `season-card-arrived`.

## Register

None.

## Oracle: states that diverge, declared by name

The eight `season-card-*` ids are new; `journey`-panel states re-addressed, declared by script.

## Commit

`feat(maquette-season-recovery): the season's acquisition card and its journey, every case`
