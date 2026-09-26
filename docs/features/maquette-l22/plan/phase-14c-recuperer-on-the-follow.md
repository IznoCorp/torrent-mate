# Phase 14-ter — « Récupérer maintenant » lives on the follow's sheet

Added 2026-09-26 by the steward on the operator's round 7 (DESIGN § 7.3, ruling 2 there): **« À récupérer » has left
« En cours » (phase 14-bis); « Récupérer maintenant » stays on the follow's sheet, which says « trouvé, récupéré à la
prochaine passe, à <heure> ».** Cut from 14-bis so that a removal and an addition never share a commit.

**Opening measure — written by the steward on `53a4d4c78`; the implementer RE-TAKES it at the opening:**

- **Commands.** `git grep -n -E "takeableFoot|take\b|registerVerb\(\"take\"" -- frontend/maquette/design/src` → the
  « Récupérer maintenant » act and where the follow's sheet draws its facts (`features/acquisition/panel-follow.ts`,
  `follow-facts.ts`); the next pass's time as the scheduler already words it (`screens.acquisition.nextSearch`,
  « Prochaine recherche à {{at}}. »).
- **Points ≈ 9.** The sentence « trouvé, récupéré à la prochaine passe, à <heure> » on a follow whose release was found
  and not yet grabbed (one key, its interpolation, ≈ 10 lines new, 1); « Récupérer maintenant » on that sheet if it is
  not already there (≈ 10 lines, 1); the harness readers that took from « En cours » re-aimed onto the sheet (the take
  path — `take.py`, `busy.py`, `journey_verbs.py`, `actions.py`: 1 each, 4); R-L22-w with its mutation (3).

## Red today

**R-L22-w — a found release is taken from its follow**: on the follow of a medium whose release was found and not
grabbed, the sheet reads « trouvé, récupéré à la prochaine passe, à <heure> » (the hour the scheduler states) and
offers « Récupérer maintenant »; a tap takes it (the take operation is sent) and the sentence leaves. **Red**: the
sentence does not exist.

## Move

The sentence and the act on the follow's sheet; the rules that walked « À récupérer » on « En cours » walk the sheet.

## Mutation

With the commit made first: drop the hour from the sentence → falls; the tap sending nothing → falls.

## Register

—

## Oracle: states that diverge, declared by name

The follow sheet's states of a found-not-grabbed medium (named at the opening by `grep` of the states that open that
sheet), on the sheet's body. Any other divergence is STOP A.

## Gate

The shared-lock `run.sh --contracts --oracle` with R-L22-w and the re-aimed rules NAMED, `--a11y`.
