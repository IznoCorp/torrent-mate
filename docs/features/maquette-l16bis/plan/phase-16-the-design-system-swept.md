# Phase 16 — The design system, swept

**No STOP C.**

**Opening measure — re-taken at this phase's opening** (phases 6–15 move the answer; phase 5 is the conformity
train's, DECIDED 7).

- **Commands.** `grep -n "^export const" frontend/maquette/design/src/features/trackers/variants.ts` → **9** factories
  on `f3d8fed01` (`torrentTitle`, `torrentFilter`, `torrentFilterClear`, `torrentHead`, `torrentChipLine`,
  `seenControl`, `trackersTab`, `seeTorrents`, `torrentRemove`); `git grep -n "from \"./variants\"" --
  frontend/maquette/design/src/features/trackers` → who still imports them.
- **Points ≈ 7.** R-L16bis-i 3; every factory no longer used deleted, the file removed if empty 1; `seeTorrents`'s
  floor moved into `crossReference` if a second user needs it, else kept and justified in DESIGN § 1.8 1; the
  table of DESIGN § 1.8 re-read against the tree, one dated line where it is wrong 1; the report 1.
- **Readers.** None outside the feature (invariant 7).

## Red today

R-L16bis-i over `torrents-list`: a factory of `features/trackers/variants.ts` still draws a part `ui/` has.

## Move

1. Delete, never re-point: a factory with a user left is a phase that did not finish — STOP D.

## Mutation

Re-add `torrentRemove` on a row → the reuse hold falls by name.

## Register

The defect « a component redrawn » (DESIGN § 6) closed for the Trackers page by this rule.

## Oracle: states that diverge, declared by name

None expected — a deletion of unused code; one that moves is STOP A.

## Commit

`refactor(maquette-l16bis): the Trackers page draws nothing the design system already draws`
