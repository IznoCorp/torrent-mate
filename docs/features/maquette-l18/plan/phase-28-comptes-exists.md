# Phase 28 — « Comptes » exists

**Amended 2026-09-27** (renumbered from the first drawing's phase 23): **OPEN 1 is RULED B, firm — a first-level
menu page** (round 8 question 9), address `/accounts`, grouped `configuration` beside Réglages. **No Réglages-rubric
variant survives to draw**: the first drawing's dual estimate (« A: 11 / B: 15 ») collapses to the B figure alone,
the more expensive of the two because it needs a route, a `PAGE_PATHS` entry and a navigation row (fact 10: the
rubric list is server data, so a rubric would have needed a page composing its own entry — moot now). Present and
MARKED for accounts without `accounts.manage` (F29), never absent. Re-estimated at **15** (was « B: 15 »,
unchanged).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

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
