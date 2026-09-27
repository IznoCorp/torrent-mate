# Phase 30 — « Comptes » — a role's own rights

**Amended 2026-09-27, model inverted** (renumbered from the first drawing's phase 25): ruling 20 makes this phase
about a ROLE's own rights, not an account's — the panel edits WHICH RIGHTS an ordinary role carries (§ 1.2's
list, toggled), never a per-account role-pick-plus-two-options form. **Assigning a role TO an account, with its
escalation guard, is a NEW sibling phase (31)** — round 9 Q14 asks for the escalation to be measured at its OWN
phase, at most 15 points, which this split makes literal. `updateAccount` (account-level) is phase 26's; the
role-rights operation is phase 27's. **F37**: the stream event (demand M) is now carried by a REAL emitted
carrier or `updateAccount`'s own invalidation — the live-relay guard refuses the empty-table claim the first
drawing's own § 2.3 left unproven. **F2's guards restated on rights**: the operation refuses to leave zero
accounts on the Admin role, and refuses to remove `auth.password` from its last holder. Re-estimated at **15**
(unchanged size, different content — a role's rights list replaces a role-pick-plus-options form).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

- **Commands.** `cat frontend/maquette/design/src/features/account/live.ts` → `accountLiveRules: readonly LiveRule[] = []` — an EMPTY table, 22 lines; the stream event of demand M (« an account's rights changed ») is claimed here.
- `updateAccount` exists from phase 22; the guard from phase 4; `useRights()` from phase 3 — the affected account's bar recomposes when its next `readAccount` differs.
- `sed -n 1,40p frontend/maquette/design/src/mocks/stream.ts` (the relay the mock carries) — the event is emitted by the handler and claimed by `live.ts`; NE-DOIT-PAS-8 allows no poll.
- **Points ≈ 15.** the account's rights panel, ≈ 70 new lines (7) + two sentences (the two options; the last Operator reuses the refusal's body) (2) + the stream claim in `features/account/live.ts`, ≈ 8 lines (1) + two states — `accounts-detail`, `accounts-last-operator` (2) + R-L18-u with its mutations (3).

**DESIGN § 3.9 point 2, § 2.3, § 1.2.1.** The Operator (or any `accounts.manage` holder) toggles WHICH RIGHTS an
ordinary role carries, each with a sentence of what it does. A change is ANSWERED on the network, moves every
account holding that role in the roster, and reaches each affected account through the stream event on a REAL
carrier — **its bar and its drawer recompose with no refetch**. **The last Admin-role account cannot be emptied of
Admin, and the last `auth.password` holder cannot lose it**: the surface says why and the operation refuses it.

## Red today

**R-L18-u — a rights change moves**: a change to a role's rights is ANSWERED on the network; every account
holding that role moves in the roster; each affected identity's bar recomposes on the stream event with no
refetch; the last Admin and the last `auth.password` holder cannot be emptied, said and refused.

**Red against `main`**: no change exists.

## Move

The panel, the claim, the states.

## Mutation

With the commit made first: apply the change on a timer instead of the event → R-L18-u falls; allow the last demotion → falls.

## Register

—

## Oracle: states that diverge, declared by name

`accounts-detail`, `accounts-last-admin` are new. **None** otherwise. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the Operator sets a role's own rights, and every account holding it feels it at once`
