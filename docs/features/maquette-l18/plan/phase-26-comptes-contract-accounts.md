# Phase 26 — « Comptes » — the contract and the mocks: accounts

**Amended 2026-09-27** (renumbered from the first drawing's phase 22): this phase now covers ONLY `createAccount`
and `updateAccount` (account-level: name, e-mail, role assignment, Plex link) plus the two last-holder guards (F2,
restated on rights — the last `accounts.manage` holder, the last `auth.password` holder, never demoted). **The
ROLE-level operations (create/rename/set a role's own rights) move to a NEW sibling phase (27)** — ruling 20 gives
Comptes a roles editor the first drawing never needed, since it assumed three fixed roles. Re-estimated at **11**
(was 11, same figure, narrower scope now the role operations have their own phase).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

- **Commands.** `grep -n "accounts" docs/reference/frontend-backend-demands.md | head -3` → no accounts route in the register; **demands G and H** (DESIGN § 6.2) are filed HERE because their first surface — the roster's detail — is drawn at phases 25 and 26. (Demand F was filed at phase 10.)
- The mock's mutable state (`mocks/state.ts`, 413 lines) must MOVE on a creation and a change (D7): a created account appears in the next `readAccounts`; a change moves the next `readAccount` of the affected identity.
- **The last Operator**: the door of last resort (DESIGN § 3.1) requires at least one Operator — the operation refuses to demote the last, and the surface says why (phase 25).
- **Points ≈ 11.** `createAccount` and `updateAccount` declared new (4) + their handlers, new (4) + the last-Operator refusal in the mock, ≈ 10 lines (1) + the guard's table gains the two rows; R-L18-c re-swept (1) + the register regenerated (1).

**DESIGN § 3.9 points 2–3.** `createAccount` carries a **mandatory e-mail** (« Un compte créé hors Plex porte un e-mail obligatoire ») and links to a Plex account whose e-mail matches; `updateAccount` changes a role and the two options and refuses to demote the last Operator. Both answered by the mock, both refused for every identity but the Operator.

## Red today

**R-L18-c re-swept**: `createAccount` and `updateAccount` forced by every identity but the Operator answer `403`; an empty e-mail is refused by the operation with its reason; demoting the last Operator is refused.

**Red against `main`**: the operations do not exist.

## Move

The declarations, the handlers, the refusals; the register regenerated.

## Mutation

With the commit made first: accept an empty e-mail → the sweep's e-mail hold falls; allow the last demotion → falls.

## Register

—

## Oracle: states that diverge, declared by name

**None.** Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the account operations — create with a mandatory e-mail, change a role, never the last Operator`
