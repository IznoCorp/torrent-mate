# Phase 23 — « Comptes » exists — where OPEN 1 says

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `python3 -c "import json;print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/settings.json'))))"` → **6** rubrics, **served data** (`readSettings`); `wc -l frontend/maquette/design/src/features/settings/page.tsx frontend/maquette/design/src/features/settings/topic-verb.ts` → **319, 94**.
- `sed -n 20,28p frontend/maquette/design/src/lib/addresses.ts` → 7 declared pages; `ls frontend/maquette/design/src/routes | wc -l` → 14 route files; the drawer has three groups.
- **Reads OPEN 1 — both placements are drawn, and the plan carries one variant per reading.** A — a rubric composed OUTSIDE the schema (≈ 11 points): the rubric list is the server's data, so the page composes one of its own; hides behind the configuration right. B — a first-level entry (≈ 15 points): a `navigation.ts` row, a path, a thin route, a region.
- **This phase edits FRAME code** (`app/`), the only lot after L15 that does; the plan says so rather than discovering it.
- **Points ≈ 11** (reading A: 11 · reading B: 15). The base counted here: `navigation.ts` row (≈ 12 lines), `lib/addresses.ts` path (2), a thin route (≈ 15), `regions.json` (1), the page shell (≈ 25 new lines) — reading B (9) + two sentences (2) + one state, `accounts-forbidden` (1) + R-L18-s with its mutations (3).

**DESIGN § 3.9, § 7.2 OPEN 1.** The place of the surface, empty: the roster (24), the rights (25) and the creation (26) fill it. **This phase exists so the placement is decided by what the operator SAW**: reading A draws a rubric « Comptes » in Réglages (`settings/page.tsx` ≈ 15 lines composed outside the schema 3, `topic-verb.ts` 1, the rubric absent for an account without the right 1, two sentences 2, one state 1, R-L18-s 3 = 11); reading B the row above. Neither is in Profil (ruling 14, refused B).

## Red today

**R-L18-s — Comptes, both sides**: for the Operator the entry and the surface exist; for every other identity the entry is ABSENT from the DOM and the address is refused as OPEN 3 says; forced `readAccounts` / `createAccount` / `updateAccount` answer `403`.

**Red against `main`**: nothing exists.

## Move

The place, its right, the state.

## Mutation

With the commit made first: leave the entry for the Member → R-L18-s falls.

## Register

—

## Oracle: states that diverge, declared by name

**Reading A**: the settings states that draw the rubric list (`settings-*`). **Reading B**: `drawer-navigation` (a new entry). Either — « L18 § 3.9 ». Any other divergence is STOP A. The accessibility tier is re-read.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): « Comptes » has its place, closed to every account but the Operator`
