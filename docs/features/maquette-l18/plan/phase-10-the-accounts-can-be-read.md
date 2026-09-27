# Phase 10 — The accounts can be read

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `git grep -n -i "accounts" -- frontend/maquette/contract/openapi.json | wc -l` → **0**: the contract names no accounts route today; **demand F** (DESIGN § 6.2) is filed HERE because its first surface — the reassign chooser (phase 11) — is drawn next.
- `git grep -n "useAccount\b" -- frontend/maquette/design/src | wc -l` → **4** — the door's neighbour; `features/account/queries.ts` is 28 lines (+ phase 3's door).
- The roster is the Operator's alone (`accounts.manage`): the guard of phase 4 refuses `readAccounts` for every other identity, **including a read** — a read of who else has an account is not a right an account holds by default.
- **Points ≈ 6.** `readAccounts` declared new (2) + its handler, new (2) + `useAccounts()` in `queries.ts`, ≈ 10 new lines (1) + the guard's table gains the row; R-L18-c re-swept (1).

The smallest phase of the lot on purpose: it makes the account list a thing the maquette can ask for, so phase 11 (the chooser) and phase 24 (the roster) read one answer (§ 13). **DESIGN § 6.2 row F.** A read the Member forces answers `403`.

## Red today

**R-L18-c re-swept**: `readAccounts` forced by every identity but the Operator answers `403`.

**Red against `main`**: the operation does not exist.

## Move

The declaration, the handler (answering the six accounts of § 2.2, the invented five only under their dial), the hook, the guard row.

## Mutation

With the commit made first: let the Member read → the sweep names `readAccounts`.

## Register

—

## Oracle: states that diverge, declared by name

**None.** Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the account list is a read the Operator can make`
