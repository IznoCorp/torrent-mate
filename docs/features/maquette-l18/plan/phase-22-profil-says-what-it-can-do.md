# Phase 22 — Profil says what the account can do

**Amended 2026-09-27** (renumbered from the first drawing's phase 19): the reason table for a lacking right now
names WHICH ROLE(S) grant it by default (reused from phase 9's own table, § 3.3/§ 3.8), not a generic sentence;
the forbidden-writes reason (phase 20) may be PARTIAL (preprod) and Profil's line reflects that specifically. Re-estimated
at **15** (was 14, +1 for the partial-list branch).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

- **Commands.** `features/account/page.tsx` (83 lines, less phase 18's deletion) draws two `FactRows` sections; `ui/fact-rows` is the primitive.
- The list is DERIVED from the model (phase 3) — **one derivation** (§ 13): no sentence is keyed to a role, each is keyed to a right; five families (library, acquisition, pipeline, configuration, accounts) and two reasons (the ceiling, the Operator's setting).
- `python3 -c "import json;d=json.load(open('frontend/maquette/design/src/i18n/fr.json'));print(len(d['screens']))"` — the sentences live under `screens.*`; none is retyped in code (`check-no-french.py`).
- **Points ≈ 14.** the section, ≈ 30 new lines (3) + five sentences (one per family of rights) and two reasons (7) + one state, `profile-ceiling` (1) + R-L18-z with its mutations (3).
- **What to cut if the opening measure exceeds 15.** At 15-ish. Cut: the two reasons (2 sentences) go to phase 29 if the opening exceeds 15.

**DESIGN § 3.8.** § 17 point 2 for the account's own page: it says what it can do and, for a right it does not hold that would otherwise surprise, why — « l'instance est en lecture seule », « ce droit se règle par l'Opérateur ». It offers no act on other accounts.

## Red today

**R-L18-z — Profil's list is the model's**: the rights Profil lists equal the model's for each identity (`household-member`, `guest`, `izno` differ), and the ceiling appears as a reason when on.

**Red against `main`**: no list exists.

## Move

The section, its sentences, the state.

## Mutation

With the commit made first: retype one right's sentence keyed to a role → the agreement falls; drop the ceiling's reason → falls.

## Register

—

## Oracle: states that diverge, declared by name

**`profile-*`** gain the section — « L18 § 3.8 ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): Profil says what the connected account can do, from the model`
