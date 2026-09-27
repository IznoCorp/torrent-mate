# Phase 3 — The model

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `cat frontend/maquette/design/src/features/account/*.ts frontend/maquette/design/src/features/account/*.tsx | wc -l` → **269** lines in 6 files (`avatar.ts`, `live.ts`, `page.tsx`, `panel-account.ts`, `queries.ts`, `verbs.ts`); `git grep -l "features/account" -- frontend/maquette/design/src ':!*.d.ts'` → 3 importers (`app/navigation.ts`, `app/panel-contributions.ts`, `app/shell.tsx`).
- `git grep -n -i -E "rights|permission|isOperator|isAdmin|administrator|canDo|\.role\b" -- frontend/maquette/design/src/app frontend/maquette/design/src/features frontend/maquette/design/src/lib frontend/maquette/design/src/ui frontend/maquette/design/src/routes` → 3 lines, all comments: **no reader of a right exists**.
- `features/account/queries.ts` (28 lines) defines `accountQuery` as a query DEFINITION read by four readers (the page, the avatar, the panel producer and, from here, the model) — the door is added beside it.
- The rights of DESIGN § 1.2: 13 rows × 4 identities, a closed set.
- **Points ≈ 13.** `features/account/rights.ts`, new, ≈ 90 lines (9) + the door in `queries.ts` (`rightsOf(cache)`, `useRights()`), ≈ 10 new lines (1) + R-L18-b — the unit table over role × options × ceiling, and the role-compare hold — with mutations (3).

**DESIGN § 1.2 — the MODEL, first.** One derivation, in the feature that owns the account, read by every surface through one door. It takes what the server answered (role, two options, ceiling) and returns the closed set of rights. **No surface compares a role string**; R-L18-b holds the source for exactly that. The ceiling is a parameter from the start (phase 17 wires the surfaces to it); the `readOnly` hold R-L18-b gains at phase 17 cannot be written before the flag dies.

## Red today

**R-L18-b — one derivation, no second path**: a unit table — every combination of role × the two options × the ceiling gives the rights § 1.2 says (Operator: all; Member: no `library.write`, no `pipeline.control`, …; guest: the second option decides `acquisition.quality.own`; rights-less: `library.read` alone; ceiling on: no write right for anyone) — **and a source hold: no file outside the model compares a role string**.

**Red against `main`**: the model does not exist. The source hold is green at once (nothing compares a role today) and is proved by its mutation.

## Move

The model file and its door; the unit table (the harness's unit tier — `frontend/maquette/design/src/**/*.test.ts` are vitest files, e.g. `features/settings/format.test.ts`; `frontend/maquette/design/package.json` runs `vitest`).

## Mutation

With the commit made first: flip one cell of the table in the model → the unit falls naming the cell; add `role === "operator"` to a surface → the source hold falls naming the file.

## Register

—

## Oracle: states that diverge, declared by name

**None** — no surface reads the model yet. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the rights model — one derivation from the account's answer`
