# Phase 32 — « Comptes » — a new account, and the Plex link

**Amended 2026-09-27** (renumbered from the first drawing's phase 26): the initial role a new account receives
defaults to the Default role (§ 1.2.1) unless the creator (escalation-guarded, phase 31) assigns another; a
non-Admin manager creating an account may not assign Admin (round 9 Q14 = A). `auth.password` governs whether the
new account, once created, may sign in without SSO — grantable here or in phase 30, not automatic from « no Plex
match ». Re-estimated at **15** (unchanged).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

- **Commands.** `createAccount` exists from phase 22; `signInWithPlex` from phase 20; the link's state is a field of `readAccount` (phase 1).
- `grep -n "loginerr" frontend/maquette/design/src/app/entry.ts | head -3` → lines 137, 160, 330: the gate's refusal idiom (`#loginerr`); the surface reuses its wording form.
- **Not drawn** (DESIGN § 7.1): deleting or disabling an account; an approval flow for proposals; invitations by link.
- **Points ≈ 15.** the creation form, ≈ 60 new lines (6) + four sentences (title, the e-mail's rule, the link stated, the sign-in it will use) (4) + two states — `accounts-create`, `accounts-create-refused` (2) + R-L18-v with its mutations (3).

**DESIGN § 3.9 point 3.** A name, an e-mail — **mandatory** — and a role. If the e-mail is a Plex account's the two are LINKED and the roster says so; if not, and the role is not Operator, the account cannot sign in with a password and the surface says it will sign in with Plex when its e-mail matches one. Refused on the surface AND by the operation.

## Red today

**R-L18-v — a new account**: the e-mail is required (refused with its reason on the surface AND by the operation); an e-mail matching a Plex account links; a non-Operator without a Plex match cannot sign in by password and the surface says so.

**Red against `main`**: no creation exists.

## Move

The form, its sentences, the states.

## Mutation

With the commit made first: accept an empty e-mail → R-L18-v falls; link on a name instead of the e-mail → falls.

## Register

—

## Oracle: states that diverge, declared by name

`accounts-create`, `accounts-create-refused` are new. **None** otherwise. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): a new account carries its e-mail, and links to Plex by it`
