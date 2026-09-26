# Phase 14 — « Suivant » dies, and one returns to the list

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -n -E 'data-next|registerVerb\("next"|screens\.resolution\.(next|outOf|waiting)' -- frontend/maquette/design/src ':!frontend/maquette/design/src/engine'`
  → the button (`resolution-screen.tsx:182-184`, moved to Acquisition by phase 2), the verb (`next`, moved with it), the
  key `screens.resolution.next`, and the progression « n sur m en attente » (`resolution-screen.tsx` — the `rank` constant at
  102-104, the `pending.length > 1` caption at 150-158 — and the keys `screens.resolution.outOf`, `screens.resolution.waiting`;
  OPEN 7, ruled A: it dies with the button). The landing today: the
  `resolve` and `leave` verbs call `bridge.back()` after acting. Harness readers of `[data-next]`: `git grep -c 'data-next' -- 'frontend/maquette/harness/*.py'`
  → `decision.py` 2 lines and no other file; `git grep -n -i -E 'en attente|outOf' -- 'frontend/maquette/harness/*.py'` → no match:
  no rule reads the progression.
- **Found (2026-09-26) — a reader of the behaviour this phase reverses.** **R57** (`harness/decision.py:171-190`) asserts
  « a folder among several offers « Suivant » » and that a tap opens the NEXT folder, replacing its entry. It is
  re-aimed to assert the ABSENCE (DESIGN § 5.1) — a hold whose subject dies is inverted, never deleted.
- **Points ≈ 13.** About 37 lines deleted — the button (`resolution-screen.tsx` 181-188), the verb (`verbs.ts` 89-99) and the key,
  20; the progression (the `rank` constant, the caption, the two keys, and `pending` if nothing else reads it) ≈ 17 — 7; the
  return made explicit (an exit lands on « À traiter » with the tab in the address) ≈ 10 lines edited 2; R-L22-d with its
  mutations 3; R57's hold inverted 1.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run. **Two figures of the first
  drawing did not reproduce and are corrected**: `data-next` is read by `decision.py` on 2 lines and by no other file (the first
  drawing said `decision.py` 4, `actions.py` 1, `two_picks.py` 1), so the point it charged for `actions.py` and `two_picks.py` is
  not owed. **Points 11 → 13, moved by OPEN 7 (ruled A: the progression dies with « Suivant »)**: about 17 more lines deleted
  (+3), and the two files that were charged and read nothing (−1) — net +2.

Ruling 8 (revised): after a resolution one RETURNS to « À traiter »; the « Suivant » button disappears — and, by OPEN 7 (ruled A),
so does the progression « n sur m en attente » that existed to serve it: « À traiter »'s tab count carries the number.

## Red today

**R-L22-d — the return to the list**: after each exit (pick, and later « Laisser tel quel » and « Ce n'est pas un média »)
the address is `/acquisition` with « À traiter » open; `history.length` did not grow (a pop, not a push); **no « Suivant » and no
progression « n sur m en attente »** anywhere on the screen; and the same on a COLD `/resolution/<folder>` (the floor is the
rendered parent, D1b rule 3).

**Red against `main`**: « Suivant » and the progression are drawn, and a cold link's exit lands wherever `bridge.back()` finds.

## Move

Delete the button, the `next` verb and `screens.resolution.next`, and the progression (the caption, the `rank` constant,
`screens.resolution.outOf` and `screens.resolution.waiting` — **not** `screens.run.count.waiting`, a run's own count). The exits land on « À traiter » by the entry's own
address — a tab is a setting of the page and is written into its address, so the pop reopens it; where no entry exists
(a cold link) the rendered floor holds the tab the page was opened with (DESIGN § 3.4).

## Mutation

With the commit made first: restore the `next` verb → the absence hold falls; restore the progression → it falls; make an exit
push → the length hold falls.

## Register

—

## Oracle: states that diverge, declared by name

`acq-resolution-tie` (the only resolution state that offered « Suivant » and drew « n sur m en attente », both being drawn when
several wait) on `screen-resolution/body`, accepted with « L22 § 3.4: « Suivant » and its progression die ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `decision.py` re-run by name.

## Commit

`feat(maquette-l22): the candidates screen returns to « À traiter » and loses « Suivant » and its progression`

**Amended 2026-09-27 (l22a):** the cold floor's « À traiter » stopped holding by construction when the default became « Suivis » then the last tab (phase 13); `landingTab()` lays Acquisition on « À traiter » beneath `/resolution/…`, R205 = `return_to_todo.py`, R57's « Suivant » hold inverted.
