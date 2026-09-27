# Phase 9 — The reserved place explains itself

**Amended 2026-09-27** (renumbered from the first drawing's phase 7): **OPEN 3 is RULED B — this phase is now
UNCONDITIONAL** (round 8 question 11; F29), not the conditional draw the first drawing left pending. The
explanation names the missing RIGHT and which role(s) grant it by default (ruling 17's own reading: « réservé à
l'Opérateur » reads « not granted by default to any role but Admin »), never a role or account name directly. Its
table of right-name sentences is built ONCE here and reused by Profil (phase 22) and by « Comptes »'s own reserved
form (phase 28). Re-estimated at **15** (unchanged from the first drawing's own B-reading estimate — removing the
conditional does not remove the work, it removes the branch).

> **No longer conditional.** This phase always runs; the first drawing's A-reading deletion clause does not
> apply.

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** **Conditional: this phase is drawn ONLY under reading B of OPEN 3** (DESIGN § 7.2). Under A it is deleted, the plan renumbers, and the sum falls by its points.
- `sed -n 1,37p frontend/maquette/design/src/app/not-found.tsx` → the closed-address answer under reading A (37 lines, one page component).
- `python3 -c "import json;d=json.load(open('frontend/maquette/design/src/i18n/fr.json'));print(sorted(d['screens']))"` — the sentences of a new component live under `screens.*`; the guard `check-no-french.py` forbids retyping them in code.
- The drawer's entry for a place the account lacks is drawn by phase 6 as absent; under B it is drawn MARKED reserved (a variant of `drawerEntry`, `ui/variants`).
- **Points ≈ 15.** the reserved-place component, ≈ 60 new lines (6) + four sentences (what it is, that this account does not hold it, who can, back) (4) + the drawer entry marked reserved, 4 lines (1) + one state, `place-reserved` (1) + R-L18-f with its mutations (3).
- **What to cut if the opening measure exceeds 15.** At 15. Cut: the drawer's marking (4 lines) goes to phase 6's reading-B variant.

**DESIGN § 3.3, reading B.** § 17 « Ce qu'un compte voit par défaut » — the pipeline and the configuration « restent visibles et expliqués comme réservés » — and point 2. The drawer draws the entry marked; the place, opened, says what it is and that this account does not hold it. **Cost recorded in the design**: a component, four sentences and a drawer that shows entries an account cannot use.

## Red today

**R-L18-f — a place not held explains itself**: on `place-reserved`, the drawer entry and the cold address say the place exists, that this account does not hold it, and who can open it; the reserved place carries no lever and calls nothing.

**Red against `main`**: no such place exists.

## Move

The component, its sentences, the marked entry, the state; R-L18-y's assertion is re-aimed from « the not-found page » to « the reserved place ».

## Mutation

With the commit made first: render the page itself under the reserved marking → R-L18-f falls; leave the levers in → the « calls nothing » hold falls.

## Register

—

## Oracle: states that diverge, declared by name

**None** for the Operator's states. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): a place an account does not hold says so, and who can open it`
