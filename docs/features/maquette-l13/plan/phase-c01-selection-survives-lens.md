# Phase c·1 — The selection survives the lens

A BEHAVIOUR change: the operator's ruling of 2026-09-05, « La sélection doit survivre au changement
des filtres », lands with its two guard-rails (DESIGN § 10, B-312). It relies on the `lens` verb
being the library feature's since b·6.

## The proof FIRST

The rule the repair lands with is the one B-312's entry names. Its label is bound to the next free
number, re-taken against `origin/main`.

- **What it drives.** Tick media under « Tout », then switch to « Films ».
- **What it reads**:
  1. the selection bar's count, which counts every ticked MEDIUM, including those the lens hides;
  2. the delete dialog's titles, which NAME every ticked title, including the hidden ones.
- **Red today.** Both writers drop the set on a lens change: the `lens` verb (b·6) and
  `features/library/library-head.tsx`. The count falls to what is visible, and the dialog names
  fewer titles.
- **Mutation.** With the commit made first, `scripts/mutate.sh` puts back the lens write that
  re-drops the set. The rule must fall, naming the lost titles.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the new holds named.
- **The oracle may diverge ONLY on states showing a selection across a lens change**, each accepted
  with « B-312 » (D8). Any other divergence is STOP B.

## The move

- **The lens stops dropping the selection.** Both writers stop clearing it on a lens change: the
  `lens` verb in `features/library/`, and `features/library/library-head.tsx`. Clearing the search
  is re-taken against the same ruling, and the phase says whether it still clears.
- **The selection bar** (`features/library/selection-bar.tsx`) counts the selected set itself, not
  the visible rows.
- **The delete dialog** (`openDeleteDialog`, in the library feature since b·6) lists every selected
  title.
- **Invariant 7.** Nothing leaves the library feature.

## Gate

Per INDEX « Gates ». In addition, B-312 closes with the rule's red reading and its mutation.

## Commit

`fix(maquette-l13): a library selection survives a change of lens and the bar and dialog name all of it`
