# Phase 11 — The end

**No STOP C.**

**Opening measure (2026-09-29, on `b63a45438`):**

- **Commands.** The stage verbs that move a ladder in the mock: `grep -n "route(\"" frontend/maquette/design/src/mocks/handlers/acquisition-verbs.ts`
  (requeue, rescrape, abandon — re-read); the incomplete-pack fallback's engine side:
  `grep -n "def fallback_season" personalscraper/acquire/_wanted_store.py` → **750**.
- **Points ≈ 9.** States `season-recovery-shelved-sheet`, `season-recovery-shelved-panel`,
  `season-recovery-closed-short` (the fallback's episodes in « En cours », not absorbed), `season-recovery-abandoned`,
  `season-row-ask-failed`, `season-row-ask-held` 6; holds added: R-b (no mark after shelving, `7/7`), R-c (the
  ended pointer), R-d (`S03E07` takes again) 2; the report 1.
- **Readers.** `harness/season_family.py` reads Silo's season counts — its `7/7` after shelving is a NEW read, not a
  re-aim.

## Red today

`season-recovery-shelved-sheet`: none if phases 5–10 are right — the holds are added GREEN and each is felled by its
mutation (below).

## Move

1. Nothing drawn is new: every surface returns to rest through the derivation alone.
2. The walk by FINGER: the season shelved → the row, the picker, the pointer, each read at the seven widths.

## Mutation

Keep the season card in the derivation after « rangé » → R-b's end hold falls; the picker's refusal kept after the
library → R-d's falls.

## Register

None.

## Oracle: states that diverge, declared by name

The six ids above are new; no existing state moves.

## Commit

`feat(maquette-season-recovery): a season recovery ends — shelved, closed short, abandoned`
