# Phase 12 — « Suivant » dies, and one returns to the list

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -n -E 'data-next|registerVerb\("next"|screens\.resolution\.(next|outOf|waiting)' -- frontend/maquette/design/src ':!frontend/maquette/design/src/engine'`
  → the button (`resolution-screen.tsx:182-184`, moved to Acquisition by phase 2), the verb (`next`, moved with it), the
  key `screens.resolution.next`, and — untouched here — the progression `outOf` / `waiting` (OPEN 7). The landing today: the
  `resolve` and `leave` verbs call `bridge.back()` after acting. Harness readers of `[data-next]`: `decision.py` 4 sites,
  `actions.py` 1, `two_picks.py` 1 (`git grep -c 'data-next' -- 'frontend/maquette/harness/*.py'`).
- **Found (2026-09-26) — a reader of the behaviour this phase reverses.** **R57** (`harness/decision.py:171-190`) asserts
  « a folder among several offers « Suivant » » and that a tap opens the NEXT folder, replacing its entry. It is
  re-aimed to assert the ABSENCE (DESIGN § 5.1) — a hold whose subject dies is inverted, never deleted.
- **Points ≈ 11.** About 20 lines deleted (the button, the verb, the key) 4; the return made explicit (an exit lands on
  « À traiter » with the tab in the address) ≈ 10 lines edited 2; R-L22-d with its mutations 3; R57's hold inverted 1;
  `actions.py` and `two_picks.py` 1.

Ruling 8 (revised): after a resolution one RETURNS to « À traiter »; the « Suivant » button disappears.

## Red today

**R-L22-d — the return to the list**: after each exit (pick, and later « Laisser tel quel » and « Ce n'est pas un média »)
the address is `/acquisition` with « À traiter » open; `history.length` did not grow (a pop, not a push); **no « Suivant »**
anywhere on the screen; and the same on a COLD `/resolution/<folder>` (the floor is the rendered parent, D1b rule 3).

**Red against `main`**: « Suivant » is drawn, and a cold link's exit lands wherever `bridge.back()` finds.

## Move

Delete the button, the `next` verb and `screens.resolution.next`. The exits land on « À traiter » by the entry's own
address — a tab is a setting of the page and is written into its address, so the pop reopens it; where no entry exists
(a cold link) the rendered floor holds the tab the page was opened with (DESIGN § 3.4).

## Mutation

With the commit made first: restore the `next` verb → the absence hold falls; make an exit push → the length hold falls.

## Register

—

## Oracle: states that diverge, declared by name

`acq-resolution-tie` (the only resolution state that offered « Suivant », being among several) on
`screen-resolution/body`, accepted with « L22 § 3.4: « Suivant » dies ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `decision.py`, `actions.py`, `two_picks.py` re-run by name.

## Commit

`feat(maquette-l22): the candidates screen returns to « À traiter » and loses « Suivant »`
