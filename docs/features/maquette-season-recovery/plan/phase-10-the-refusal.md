# Phase 10 — The refusal

**STOP C: OPEN 7** (DESIGN § 5) — the chip the refusal wears is phase 7's; under B it is the moved `queuedMark`.

**Opening measure (2026-09-29, on `b63a45438`):**

- **Commands.** `grep -n "data-pick-release" frontend/maquette/design/src/features/releases/releases-screen.tsx` →
  line **115**; `grep -cv '^\s*$' frontend/maquette/design/src/features/releases/releases-screen.tsx` → **137**;
  Silo's releases after phase 2: **5** (4 × `S03E07`, 1 pack).
- **Points ≈ 12.** R-season-recovery-d with its mutations 3; R-season-recovery-f with its mutation 3; the row's foot —
  an episode release of a season under recovery draws the chip « Couvert par la saison 3 » and « Voir la carte de la
  saison » (phase 9's pointer, reused) in place of its pick act 2; the count line when every release is covered 1;
  states `releases-season-recovering`, `releases-season-recovering-all-covered` 2; the report 1.
- **Readers.** `harness/release_candidates.py` and `harness/release_take_sentence.py` pick a release on a title —
  their subjects re-read: a subject on Silo during the recovery is re-aimed OUT LOUD to a title with no recovery.

## Red today

R-season-recovery-d on `releases-season-recovering`: `Silo.S03E07.…` rows draw « Prendre celle-ci à la place ».

## Move

1. The picker reads the derivation (`lib/`, phase 4) — never its own copy of « is this season recovered ».
2. The pack row keeps its act; another season's episode keeps its act.
3. Copy: `screens.releases.coveredBySeason`, `screens.releases.allCovered`.

## Mutation

R-d: keep the act → falls; refuse the pack → falls. R-f: draw the refusal with a feature's own variant → falls.

## Register

None.

## Oracle: states that diverge, declared by name

Every `releases`-screen state on « Silo », declared by script; the two ids above are new.

## Commit

`feat(maquette-season-recovery): the release picker says an episode is covered by its season's recovery`
