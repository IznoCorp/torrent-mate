# Phase 26 — Paused follows fold at the end of « Suivis »

**Born 2026-09-27 as « 18-bis »** (the operator's round 8, question 17 = A), **numbered 22 by the triage's F51, then 24, then 26** (B-556 and B-557 took 21 and 22; phase 23 was cut in three).

**Opening measure (estimate — RE-MEASURED at the opening):**

- Paused follows form a FOLDED section at the end of « Suivis », of the same form as « Mis de côté » at the end of
  « À traiter » (`ui/disclosure.tsx`, phase 15a's shape); it unfolds to see them and resume them; it is OUTSIDE
  « Suivis »'s count, like « Mis de côté ».
- The « En pause » filter pill DIES, with its key and its readers. **The follows rules that read the pill are re-aimed
  OUT LOUD** (docstring + commit body) — listed at the opening by `git grep` over `frontend/maquette/harness/*.py`.
- **Points ≈ 12** (the section 3, the pill's removal 2, the readers re-aimed ≈ 3, R233 3, states 1).

## Red today

**R233 — paused follows are folded, not filtered**: on the dense « Suivis », no paused follow is in the list above the
fold; the fold holds every paused follow, is closed by default, is outside the tab's count; unfolding it and resuming one
moves it into the list. No « En pause » pill anywhere. Red: the pill exists and paused follows sit in the list.

## Mutation

With the commit made first: a paused follow left in the list → falls; the fold counted in the tab → falls; the pill put
back → falls.

## Oracle

The dense « Suivis » states whose list loses its paused rows, and the fold's own state — named at the opening.

## Commit

`feat(maquette-l22): paused follows fold at the end of « Suivis »`
