# Phase 25 — « Comptes » — an account's rights

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `cat frontend/maquette/design/src/features/account/live.ts` → `accountLiveRules: readonly LiveRule[] = []` — an EMPTY table, 22 lines; the stream event of demand M (« an account's rights changed ») is claimed here.
- `updateAccount` exists from phase 22; the guard from phase 4; `useRights()` from phase 3 — the affected account's bar recomposes when its next `readAccount` differs.
- `sed -n 1,40p frontend/maquette/design/src/mocks/stream.ts` (the relay the mock carries) — the event is emitted by the handler and claimed by `live.ts`; NE-DOIT-PAS-8 allows no poll.
- **Points ≈ 15.** the account's rights panel, ≈ 70 new lines (7) + two sentences (the two options; the last Operator reuses the refusal's body) (2) + the stream claim in `features/account/live.ts`, ≈ 8 lines (1) + two states — `accounts-detail`, `accounts-last-operator` (2) + R-L18-u with its mutations (3).

**DESIGN § 3.9 point 2, § 2.3.** The Operator picks a role (the three) and sets the two options, each with a sentence of what it does. A change is ANSWERED on the network, moves the roster, and reaches the affected account through the stream event — **its bar and its drawer recompose with no refetch**. **The Operator cannot demote the last Operator**: the surface says why and the operation refuses it.

## Red today

**R-L18-u — a rights change moves**: a change is ANSWERED on the network; the roster moves; the affected identity's bar recomposes on the stream event with no refetch; the last Operator cannot be demoted, said and refused.

**Red against `main`**: no change exists.

## Move

The panel, the claim, the states.

## Mutation

With the commit made first: apply the change on a timer instead of the event → R-L18-u falls; allow the last demotion → falls.

## Register

—

## Oracle: states that diverge, declared by name

`accounts-detail`, `accounts-last-operator` are new. **None** otherwise. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the Operator sets an account's role and options, and it is felt at once`
