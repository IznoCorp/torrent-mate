# Phase c·7 — No follow without a sheet

**Opening measure (2026-09-15, on `6839dd913`):**

- **Commands (tsc probe).** Baseline `design/node_modules/.bin/tsc --noEmit` from
  `frontend/maquette/design/` → exit 0, 0 diagnostics. `Follow.ids` in `design/src/contract/
  types.d.ts:1134` changed from `ids: components["schemas"]["ProviderIds"];` to `ids?: …` (the exact
  mutation the phase's proof names) → `tsc --noEmit` again → **exit 0, 0 diagnostics** — restored with
  `git checkout -- frontend/maquette/design/src/contract/types.d.ts`, `git status --porcelain` empty
  after. Every current reader of `follow.ids` already guards it (`follow.ids ?? heldIdentity(title)?.ids`
  in `follow-facts.ts:94,122`; `medium.ids != null` in `card-markup.ts:73`), so relaxing the field to
  optional changes nothing tsc can see. `git grep -n createFollow -- 'design/src/mocks/handlers/
  *.ts'` → `acquisition.ts:99-127`: the handler already carries the comment "A create naming neither
  records a follow the contract refuses (B-366); the layer does not invent an identity for it, and
  the cast says so" over `ids: (… ? {…} : source?.ids ?? null) as (typeof state.follows)[number]["ids"]`
  — an `as` cast forcing `null` past the required type, confirming the runtime gap is real and
  already flagged in place. `grep -n 'acquisition/followed"' design/src/features/acquisition/
  queries.ts` → the frontend's own `add()` call sends `{ title: follow.title, kind: follow.kind }`
  ONLY — no `provider`/`providerId` — so the handler's identity branch is reached only through the
  title-match fallback (`followedFrom`), never through a request the client actually sends. `grep -ln
  follow_has_sheet harness/*.py` → 1 file (the named gate, kept as-is per the phase). `grep -n B-366
  BUGS.md` → `open`, by audit.
- **Points ≈ 9.** ~7-9 site-lines across builders and the tile/sentence guards (`add-verbs.ts`,
  `acquisition.ts`'s handler, `follow-actions.ts`, `queries.ts`'s `add()`) ≈ 2; the runtime hold + its
  mutation (given) ≈ 3; the type mutation's proof needing re-shaping once the type-alone finding below
  is read ≈ 2-3 (provisional).
- **Found (2026-09-15).** The phase's stated proof — "The frontend gate (`tsc -b`) must fail on the
  original… the phase shows it failing with a source stripped of `ids`" — does NOT hold on this tree:
  making `Follow.ids` optional produces zero tsc diagnostics, because every reader already treats it
  defensively. The type alone cannot be the enforcement; the runtime mock refusal (already sketched by
  `acquisition.ts`'s own comment and cast) is what actually has to do the work, and it has to close a
  path the phase doesn't mention: the frontend's real `add()` call never sends `provider`/`providerId`
  at all, so the handler's only source of identity today is the title-match fallback — the refusal
  belongs on THAT path, not on a request shape nothing sends.
- **Landed (2026-09-16).** The type mutation is NOT the proof (0 diagnostics, as this measure read):
  the mock's 400 on the join path is, with the act carrying the identity when it holds one. R200,
  4 holds; the « Voir le parcours » fallback and the identity-arrival wait removed; the card's branch
  kept (an unidentified release is not a follow). B-366 `to confirm`.

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
