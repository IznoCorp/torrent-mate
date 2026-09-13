# Phase c·7 — No follow without a sheet

A BEHAVIOUR change: under the operator's ruling (« le suivi sans fiche n'est pas un état
possible »), a sheetless follow becomes UNREPRESENTABLE, and the tile's guard branch goes (DESIGN
§ 5.2, § 10; B-366). It relies on `Follow.ids` being required since a·6.

## The proof FIRST

The ruling asks for a follow that cannot be BUILT without an identity, not for one more drawing
guarded against it.

- **The type refuses it.** With the commit made first, a mutation makes `Follow.ids` optional again
  in the contract and regenerates the types. The phase reads what then compiles: every mock handler
  or verb that builds a `Follow` from a source without `ids`. The frontend gate (`tsc -b`) must fail
  on the original, and the phase shows it failing with a source stripped of `ids`.
- **The mock refuses it at runtime.** A hold, labelled with the next free number, asks the follow
  operation for a title with no identity. The mock answers the contract's refusal and no follow is
  created.
  - **Red today**, because the mock accepts it.
  - **Mutation**: the handler's refusal removed. The hold falls, naming the follow created.
- **R156 (`follow_has_sheet.py`) is a GATE, not the repair**, and it stays as it is. Every followed
  title still resolves to a sheet.
- **A follow with NO EPISODE DATA stays legitimate**: it is identified, has a sheet, and is followed
  on purpose. The oracle state that carries it reads unchanged, and a hold asserts that such a follow
  is still created. « No sheet » and « no episodes » are not the same absence.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the new holds named.
- **The oracle may diverge ONLY on states whose drawing lost the sheetless branch**. The phase
  expects none, because no seed carries one.

## The move

- **Every builder requires an identity.** Each mock handler and feature verb that builds a `Follow`
  (the phase re-takes them: the follow from a search result, from a suggestion, from the add screen)
  requires `ids` from its source and cannot construct the follow without it.
- **The tile's guard branch goes.** Its branch for a follow with no sheet, and the matching
  sentence-guard in `features/acquisition/follow-actions.ts` (« AN UNIDENTIFIED RELEASE HAS NO
  SHEET »), are handling a state that no longer exists. The phase re-takes both, and keeps any
  branch that serves an unidentified RELEASE, which is not a follow.
- **No new script guard** (the operator's first measure of 2026-09-12). The refusal is the type plus
  the mock.

## Gate

Per INDEX « Gates ». In addition, B-366 closes with the type mutation's reading, the hold's red
reading and its mutation.

## Commit

`fix(maquette-l13): a follow cannot be built without a provider identity`
